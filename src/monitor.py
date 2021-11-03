import logging

from enum import Enum, auto
from time import sleep
from threading import Thread
from typing import Union, List, Tuple, Callable, Optional
from inverter_wrapper import wrapper_instance as inverter
from inverterd import InverterError


_logger = logging.getLogger(__name__)


class ChargingEvent(Enum):
    AC_CHARGING_UNAVAILABLE_BECAUSE_SOLAR = auto()
    AC_CHARGING_STARTED = auto()
    AC_DISCONNECTED = auto()
    AC_CURRENT_CHANGED = auto()
    AC_CHARGING_FINISHED = auto()


class ChargingState(Enum):
    NOT_CHARGING = auto()
    AC_BUT_SOLAR = auto()
    AC_OK = auto()
    AC_DONE = auto()


class BatteryState(Enum):
    NORMAL = auto()
    LOW = auto()
    CRITICAL = auto()


class InverterMonitor(Thread):
    def __init__(self, ac_current_range: Union[List, Tuple] = ()):
        super().__init__()

        self.max_ac_current = None
        self.min_ac_current = None
        self.allowed_currents = []
        self.battery_under_voltage = None
        self.charging_event_handler = None
        self.battery_event_handler = None

        self.currents = []
        self.active_current = None
        self.interrupted = False
        self.battery_state = BatteryState.NORMAL
        self.charging_state = ChargingState.NOT_CHARGING

        self.set_ac_current_range(ac_current_range)

    def set_ac_current_range(self, ac_current_range: Union[List, Tuple] = ()) -> None:
        self.max_ac_current = ac_current_range[0]
        self.min_ac_current = ac_current_range[1]
        _logger.debug(f'setting AC current range to {ac_current_range[0]}..{ac_current_range[1]}')

    def set_battery_under_voltage(self, v: float):
        self.battery_under_voltage = v
        _logger.debug(f'setting battery under voltage: {v}')

    def run(self):
        self.allowed_currents = list(inverter.exec('get-allowed-ac-charging-currents')['data'])
        self.allowed_currents.sort()

        if self.max_ac_current not in self.allowed_currents or self.min_ac_current not in self.allowed_currents:
            raise RuntimeError('invalid AC currents range')

        cfg = inverter.exec('get-rated')['data']
        self.set_battery_under_voltage(cfg['battery_under_voltage']['value'])

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

                    _logger.debug(f'got status: ac={ac}, solar={solar}, v={v}')

                    self.ac_charging_program(ac, solar, v)

                    if not ac:
                        self.low_voltage_program(v, load_watts)
                    elif self.battery_state != BatteryState.NORMAL:
                        self.battery_state = BatteryState.NORMAL

            except InverterError as e:
                _logger.exception(e)

            sleep(2)

    def ac_charging_program(self, ac: bool, solar: bool, v: float):
        if self.charging_state == ChargingState.NOT_CHARGING:
            if ac and solar:
                self.charging_state = ChargingState.AC_BUT_SOLAR
                self.charging_event_handler(ChargingEvent.AC_CHARGING_UNAVAILABLE_BECAUSE_SOLAR)
                _logger.info('entering charging AC_BUT_SOLAR state')

            elif ac:
                self.ac_charging_start()

        elif self.charging_state == ChargingState.AC_BUT_SOLAR:
            if not ac:
                self.charging_state = ChargingState.NOT_CHARGING
                self.charging_event_handler(ChargingEvent.AC_DISCONNECTED)
                _logger.info('AC disconnected, entering NOT_CHARGING state')

            elif not solar:
                self.ac_charging_start()

        elif self.charging_state == ChargingState.AC_OK:
            if not ac:
                self.charging_state = ChargingState.NOT_CHARGING
                self.charging_event_handler(ChargingEvent.AC_DISCONNECTED)
                _logger.info('AC disconnected, entering NOT_CHARGING state')
                return

            if solar:
                self.charging_state = ChargingState.AC_BUT_SOLAR
                self.charging_event_handler(ChargingEvent.AC_CHARGING_UNAVAILABLE_BECAUSE_SOLAR)
                _logger.info('solar power connected, entering AC_BUT_SOLAR state')

            # if currently charging, monitor battery voltage dynamics here
            if self.active_current is not None:
                upper_bound = 56.6 if self.active_current > 10 else 54
                if v >= upper_bound:
                    self.ac_charging_next_current()

            # TODO
            # handle battery charging direction changes to do-nothing or discharging,
            # as well as drops to 0A current

        elif self.charging_state == ChargingState.AC_DONE:
            if not ac:
                self.charging_state = ChargingState.NOT_CHARGING
                self.charging_event_handler(ChargingEvent.AC_DISCONNECTED)
                _logger.info('AC disconnected, charging is done, entering NOT_CHARGING state')

    def ac_charging_start(self):
        self.charging_state = ChargingState.AC_OK
        self.charging_event_handler(ChargingEvent.AC_CHARGING_STARTED)
        _logger.info('AC line connected, entering AC_OK state')

        index_min = self.allowed_currents.index(self.min_ac_current)
        index_max = self.allowed_currents.index(self.max_ac_current)

        self.currents = self.allowed_currents[index_min:index_max + 1]

        self.ac_charging_next_current()

    def ac_charging_stop(self):
        self.charging_state = ChargingState.AC_DONE
        self.charging_event_handler(ChargingEvent.AC_CHARGING_FINISHED)
        _logger.info('charging is finished, entering AC_DONE state')

    def ac_charging_next_current(self):
        try:
            current = self.currents.pop()
            _logger.debug(f'ready to change charging current to {current}A')
            self.active_current = current
        except IndexError:
            _logger.debug('was going to change charging current, but no currents left; finishing charging program')
            self.ac_charging_stop()
            return

        try:
            response = inverter.exec('set-max-ac-charging-current', (0, current))
            if response['result'] != 'ok':
                _logger.error(f'failed to change AC charging current to {current}A')
                raise InverterError('set-max-ac-charging-current: inverterd reported error')
            else:
                self.charging_event_handler(ChargingEvent.AC_CURRENT_CHANGED, current=current)
                _logger.info(f'changed AC charging current to {current}A')
        except InverterError as e:
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

    def stop(self):
        self.interrupted = True
