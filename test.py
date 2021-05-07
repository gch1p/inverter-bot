import json, re
from pprint import pprint


s = '{"result":"ok","data":{"grid_voltage":{"unit":"V","value":0.0},"grid_freq":{"unit":"Hz","value":0.0},"ac_output_voltage":{"unit":"V","value":230.0},"ac_output_freq":{"unit":"Hz","value":50.0},"ac_output_apparent_power":{"unit":"VA","value":115},"ac_output_active_power":{"unit":"Wh","value":18},"output_load_percent":{"unit":"%","value":2},"battery_voltage":{"unit":"V","value":50.0},"battery_voltage_scc":{"unit":"V","value":0.0},"battery_voltage_scc2":{"unit":"V","value":0.0},"battery_discharging_current":{"unit":"A","value":0},"battery_charging_current":{"unit":"A","value":0},"battery_capacity":{"unit":"%","value":78},"inverter_heat_sink_temp":{"unit":"°C","value":19},"mppt1_charger_temp":{"unit":"°C","value":0},"mppt2_charger_temp":{"unit":"°C","value":0},"pv1_input_power":{"unit":"Wh","value":1000},"pv2_input_power":{"unit":"Wh","value":0},"pv1_input_voltage":{"unit":"V","value":0.0},"pv2_input_voltage":{"unit":"V","value":0.0},"settings_values_changed":"Custom","mppt1_charger_status":"Abnormal","mppt2_charger_status":"Abnormal","load_connected":"Connected","battery_power_direction":"Discharge","dc_ac_power_direction":"DC/AC","line_power_direction":"Do nothing","local_parallel_id":0}}'

if __name__ == '__main__':
    gs = json.loads(s)['data']
    # pprint(gs)

    # render response
    power_direction = gs['battery_power_direction'].lower()
    power_direction = re.sub(r'ge$', 'ging', power_direction)

    charging_rate = ''
    if power_direction == 'charging':
        charging_rate = ' @ %s %s' % (gs['battery_charging_current']['value'], gs['battery_charging_current']['unit'])
    elif power_direction == 'discharging':
        charging_rate = ' @ %s %s' % (gs['battery_discharging_current']['value'], gs['battery_discharging_current']['unit'])

    html = '<b>Battery:</b> %s %s' % (gs['battery_voltage']['value'], gs['battery_voltage']['unit'])
    html += ' (%s%s, ' % (gs['battery_capacity']['value'], gs['battery_capacity']['unit'])
    html += '%s%s)' % (power_direction, charging_rate)

    html += '\n<b>Load:</b> %s %s' % (gs['ac_output_active_power']['value'], gs['ac_output_active_power']['unit'])
    html += ' (%s%%)' % (gs['output_load_percent']['value'])

    if gs['pv1_input_power']['value'] > 0:
        html += '\n<b>Input power:</b> %s%s' % (gs['pv1_input_power']['value'], gs['pv1_input_power']['unit'])

    if gs['grid_voltage']['value'] > 0 or gs['grid_freq']['value'] > 0:
        html += '\n<b>Generator:</b> %s %s' % (gs['grid_voltage']['unit'], gs['grid_voltage']['value'])
        html += ', %s %s' % (gs['grid_freq']['value'], gs['grid_freq']['unit'])

    print(html)