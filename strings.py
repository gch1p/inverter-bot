__strings = {
    'status': 'Status',
    'generation': 'Generation',

    # flags
    'flag_buzzer': 'Buzzer',
    'flag_overload_bypass': 'Overload bypass',
    'flag_escape_to_default_screen_after_1min_timeout': 'Reset to default LCD page after 1min timeout',
    'flag_overload_restart': 'Restart on overload',
    'flag_over_temp_restart': 'Restart on overtemp',
    'flag_backlight_on': 'LCD backlight',
    'flag_alarm_on_on_primary_source_interrupt': 'Beep on primary source interrupt',
    'flag_fault_code_record': 'Fault code recording',
}


def lang(key):
    global __strings
    return __strings[key] if key in __strings else f'{{{key}}}'
