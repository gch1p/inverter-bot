import logging

from enum import Enum, auto
from time import sleep
from threading import Thread
from typing import Union, List, Tuple, Callable, Optional
from inverter_wrapper import wrapper_instance as inverter
from inverterd import InverterError

_logger = logging.getLogger(__name__)


class BatteryPowerDirection(Enum):
    DISCHARGING = auto()
    CHARGING = auto()
    DO_NOTHING = auto()


class ChargingEvent(Enum):
    AC_CHARGING_UNAVAILABLE_BECAUSE_SOLAR = auto()
    AC_NOT_CHARGING = auto()
    AC_CHARGING_STARTED = auto()
    AC_DISCONNECTED = auto()
    AC_CURRENT_CHANGED = auto()
    AC_CHARGING_FINISHED = auto()


class ChargingState(Enum):
    NOT_CHARGING = auto()
    AC_BUT_SOLAR = auto()
    AC_WAITING = auto()
    AC_OK = auto()
    AC_DONE = auto()


class BatteryState(Enum):
    NORMAL = auto()
    LOW = auto()
    CRITICAL = auto()


def _pd_from_string(pd: str) -> BatteryPowerDirection:
    match pd:
        case 'Discharge':
            return BatteryPowerDirection.DISCHARGING
        case 'Charge':
            return BatteryPowerDirection.CHARGING
        case 'Do nothing':
            return BatteryPowerDirection.DO_NOTHING
        case _:
            raise ValueError(f'invalid power direction: {pd}')


class InverterMonitor(Thread):
    max_ac_current: Optional[int]
    min_ac_current: Optional[int]
    charging_thresholds: Optional[tuple[float, float]]
    allowed_currents: list[int]
    battery_under_voltage: Optional[float]
    charging_event_handler: Optional[Callable]
    battery_event_handler: Optional[Callable]
    error_handler: Optional[Callable]

    currents: list[int]
    active_current: Optional[int]
    interrupted: bool
    battery_state: BatteryState
    charging_state: ChargingState

    def __init__(self, ac_current_range: Union[List, Tuple] = ()):
        super().__init__()

        # settings
        self.max_ac_current = None
        self.min_ac_current = None
        self.charging_thresholds = None
        self.allowed_currents = []
        self.battery_under_voltage = None

        # event handlers
        self.charging_event_handler = None
        self.battery_event_handler = None
        self.error_handler = None

        # variables related to active program
        self.currents = []
        self.active_current = None
        self.battery_state = BatteryState.NORMAL
        self.charging_state = ChargingState.NOT_CHARGING

        # other stuff
        self.interrupted = False

        self.set_ac_current_range(ac_current_range)

    def run(self):
        self.allowed_currents = list(inverter.exec('get-allowed-ac-charging-currents')['data'])
        self.allowed_currents.sort()

        if self.max_ac_current not in self.allowed_currents or self.min_ac_current not in self.allowed_currents:
            raise RuntimeError('invalid AC currents range')

        # read config
        cfg = inverter.exec('get-rated')['data']
        self.set_battery_under_voltage(cfg['battery_under_voltage']['value'])
        self.charging_thresholds = (
            float(cfg['battery_recharge_voltage']['value']),
            float(cfg['battery_redischarge_voltage']['value']),
        )

        while not self.interrupted:
            try:
                response = inverter.exec('get-status')
                if response['result'] != 'ok':
                    _logger.error('get-status failed:', response)
                else:
                    gs = response['data']

                    ac = gs['grid_voltage']['value'] > 0 or gs['grid_freq']['value'] > 0
                    solar = gs['pv1_input_power']['value'] > 0
                    v = float(gs['battery_voltage']['value'])
                    load_watts = int(gs['ac_output_active_power']['value'])
                    pd = _pd_from_string(gs['battery_power_direction'])

                    _logger.debug(f'got status: ac={ac}, solar={solar}, v={v}, pd={pd}')

                    self.ac_charging_program(ac, solar, v, pd)

                    if not ac or pd != BatteryPowerDirection.CHARGING:
                        # if AC is disconnected or not charging, run the low voltage checking program
                        self.low_voltage_program(v, load_watts)

                    elif self.battery_state != BatteryState.NORMAL:
                        # AC is connected and charging the battery, assume its level is 'normal'
                        self.battery_state = BatteryState.NORMAL

            except InverterError as e:
                _logger.exception(e)

            sleep(2)

    def ac_charging_program(self, ac: bool, solar: bool, v: float, pd: BatteryPowerDirection):
        match self.charging_state:
            case ChargingState.NOT_CHARGING:
                if ac and solar:
                    self.charging_state = ChargingState.AC_BUT_SOLAR
                    self.charging_event_handler(ChargingEvent.AC_CHARGING_UNAVAILABLE_BECAUSE_SOLAR)
                    _logger.info('entering AC_BUT_SOLAR state')
                elif ac:
                    self.ac_charging_start(pd)

            case ChargingState.AC_BUT_SOLAR:
                if not ac:
                    self.ac_charging_stop(ChargingState.NOT_CHARGING)
                elif not solar:
                    self.ac_charging_start(pd)

            case ChargingState.AC_OK | ChargingState.AC_WAITING:
                if not ac:
                    self.ac_charging_stop(ChargingState.NOT_CHARGING)
                    return

                if solar:
                    self.charging_state = ChargingState.AC_BUT_SOLAR
                    self.charging_event_handler(ChargingEvent.AC_CHARGING_UNAVAILABLE_BECAUSE_SOLAR)
                    _logger.info('solar power connected during charging, entering AC_BUT_SOLAR state')

                state = ChargingState.AC_OK if pd == BatteryPowerDirection.CHARGING else ChargingState.AC_WAITING
                if state != self.charging_state:
                    self.charging_state = state

                    evt = ChargingEvent.AC_CHARGING_STARTED if state == ChargingState.AC_OK else ChargingEvent.AC_NOT_CHARGING
                    self.charging_event_handler(evt)

                # if currently charging, monitor battery voltage dynamics here
                if self.active_current is not None:
                    upper_bound = 56.6 if self.active_current > 10 else 54
                    if v >= upper_bound:
                        self.ac_charging_next_current()

            case ChargingState.AC_DONE:
                if not ac:
                    self.ac_charging_stop(ChargingState.NOT_CHARGING)

    def ac_charging_start(self, pd: BatteryPowerDirection):
        if pd == BatteryPowerDirection.CHARGING:
            self.charging_state = ChargingState.AC_OK
            self.charging_event_handler(ChargingEvent.AC_CHARGING_STARTED)
            _logger.info('AC line connected and charging, entering AC_OK state')
        else:
            self.charging_state = ChargingState.AC_WAITING
            self.charging_event_handler(ChargingEvent.AC_NOT_CHARGING)
            _logger.info('AC line connected but not charging yet, entering AC_WAITING state')

        # set the current even if charging has not been started yet
        # this path must be entered only once per charging cycle,
        # and self.currents array is used to guarantee that
        if not self.currents:
            index_min = self.allowed_currents.index(self.min_ac_current)
            index_max = self.allowed_currents.index(self.max_ac_current)
            self.currents = self.allowed_currents[index_min:index_max + 1]
            self.ac_charging_next_current()

    def ac_charging_stop(self, reason: ChargingState):
        self.charging_state = reason

        match reason:
            case ChargingState.AC_DONE:
                event = ChargingEvent.AC_CHARGING_FINISHED

            case ChargingState.NOT_CHARGING:
                event = ChargingEvent.AC_DISCONNECTED

            case _:
                raise ValueError(f'ac_charging_stop: unexpected reason {reason}')

        _logger.info(f'charging is finished, entering {reason} state')
        self.charging_event_handler(event)

        if self.currents:
            self.currents = []
            self.active_current = None

    def ac_charging_next_current(self):
        try:
            current = self.currents.pop()
            _logger.debug(f'ready to change charging current to {current}A')
            self.active_current = current
        except IndexError:
            _logger.debug('was going to change charging current, but no currents left; finishing charging program')
            self.ac_charging_stop(ChargingState.AC_DONE)
            return

        try:
            response = inverter.exec('set-max-ac-charging-current', (0, current))
            if response['result'] != 'ok':
                _logger.error(f'failed to change AC charging current to {current} A')
                raise InverterError('set-max-ac-charging-current: inverterd reported error')
            else:
                self.charging_event_handler(ChargingEvent.AC_CURRENT_CHANGED, current=current)
                _logger.info(f'changed AC charging current to {current} A')
        except InverterError as e:
            self.error_handler(f'failed to set charging current to {current} A (caught InverterError)')
            _logger.exception(e)

    def low_voltage_program(self, v: float, load_watts: int):
        if v < 45:
            state = BatteryState.CRITICAL
        elif v < 47:
            state = BatteryState.LOW
        else:
            state = BatteryState.NORMAL

        if state != self.battery_state:
            self.battery_state = state
            self.battery_event_handler(state, v, load_watts)

    def set_charging_event_handler(self, handler: Callable):
        self.charging_event_handler = handler

    def set_battery_event_handler(self, handler: Callable):
        self.battery_event_handler = handler

    def set_error_handler(self, handler: Callable):
        self.error_handler = handler

    def set_ac_current_range(self, ac_current_range: Union[List, Tuple] = ()) -> None:
        self.max_ac_current = ac_current_range[0]
        self.min_ac_current = ac_current_range[1]
        _logger.debug(f'setting AC current range to {ac_current_range[0]} A .. {ac_current_range[1]} A')

    def set_battery_under_voltage(self, v: float):
        self.battery_under_voltage = v
        _logger.debug(f'setting battery under voltage: {v}')

    def set_battery_ac_charging_thresholds(self, cv: float, dv: float):
        self.charging_thresholds = (cv, dv)

    def stop(self):
        self.interrupted = True
