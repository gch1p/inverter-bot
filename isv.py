import subprocess
import configstore
import json


def __run(argv: list, fmt='json-w-units'):
    argv.insert(0, configstore.get_isv_bin())
    if configstore.use_sudo():
        argv.insert(0, 'sudo')
    argv.append('--format')
    argv.append(fmt)

    result = subprocess.run(argv, capture_output=True)
    if result.returncode != 0:
        raise ChildProcessError("isv returned %d: %s" % (result.returncode, result.stderr))

    return json.loads(result.stdout) if 'json' in fmt else result.stdout.decode('utf-8')


def general_status(as_table=False):
    kwargs = {}
    if as_table:
        kwargs['fmt'] = 'table'
    return __run(['--get-general-status'], **kwargs)


def day_generated(y: int, m: int, d: int):
    return __run(['--get-day-generated', str(y), str(m), str(d)])


def rated_information(as_table=False):
    kwargs = {}
    if as_table:
        kwargs['fmt'] = 'table'
    return __run(['--get-rated-information'], **kwargs)


def faults(as_table=False):
    kwargs = {}
    if as_table:
        kwargs['fmt'] = 'table'
    return __run(['--get-faults-warnings'], **kwargs)
