# inverter-bot

This is a Telegram bot for querying information from an InfiniSolar V family of hybrid solar inverters, in particular
inverters supported by **isv** utility, which is an older version of **infinisolarctl** from **infinisolar-tools**
package.

It supports querying general status, such as battery voltage or power usage, printing amounts of energy generated in
the last days, dumping status or rated information and more.

It requires Python 3.6+ or so.

## Configuration

Configuration is stored in `config.ini` file in `~/.config/inverter-bot`.

Config example:
```
token=YOUR_TOKEN
admins=
        123456     ; admin id
        000123   ; another admin id
isv_bin=/path/to/isv
use_sudo=0
```

Only users in `admins` are allowed to use the bot.

## License

BSD-2c
