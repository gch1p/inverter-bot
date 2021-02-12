__strings = {
    'status': 'Status',
    'generation': 'Generation',
    'gs': 'GS',
    'ri': 'RI',
    'errors': 'Errors'
}


def lang(key):
    global __strings
    return __strings[key] if key in __strings else f'{{{key}}}'
