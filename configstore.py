import os, re
from configparser import ConfigParser

CONFIG_DIR = os.environ['HOME'] + '/.config/inverter-bot'
CONFIG_FILE = 'config.ini'

__config__ = None


def _get_config_path() -> str:
    return "%s/%s" % (CONFIG_DIR, CONFIG_FILE)


def get_config():
    global __config__
    if __config__ is not None:
        return __config__['root']

    if not os.path.exists(CONFIG_DIR):
        raise IOError("%s directory not found" % CONFIG_DIR)

    if not os.path.isdir(CONFIG_DIR):
        raise IOError("%s is not a directory" % CONFIG_DIR)

    config_path = _get_config_path()
    if not os.path.isfile(config_path):
        raise IOError("%s file not found" % config_path)

    __config__ = ConfigParser()
    with open(config_path) as config_content:
        __config__.read_string("[root]\n" + config_content.read())

    return __config__['root']


def get_token() -> str:
    return get_config()['token']


def get_admins() -> tuple:
    config = get_config()
    return tuple([int(s) for s in re.findall(r'\b\d+\b', config['admins'], flags=re.MULTILINE)])


def get_isv_bin() -> str:
    return get_config()['isv_bin']


def use_sudo() -> bool:
    config = get_config()
    return 'use_sudo' in config and config['use_sudo'] == '1'