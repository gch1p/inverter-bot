# inverter-bot

This is a Telegram bot for querying information from an InfiniSolar V family of hybrid solar inverters.

It supports querying general status, such as battery voltage or power usage, printing amounts of energy generated in
the last days, dumping status or rated information and more.

It requires Python 3.6+ or so.

## Requirements

- **`inverterd`** from [inverter-tools](https://github.com/gch1p/inverter-tools)
- **[`inverterd`](https://pypi.org/project/inverterd/)** python library
- Python 3.6+ or so

## Configuration

The bot accepts following parameters:

* ``--token`` — your telegram bot token (required)
* ``--users-whitelist`` — space-separated list of IDs of users who are allowed
  to use the bot (required)
* ``--inverterd-host`` (default is `127.0.0.1`)
* ``--inverterd-port`` (default is `8305`)

## Launching with systemd

This is tested on Debian 10. Something might differ on other systems.

Create environment configuration file `/etc/default/inverter-bot`:
```
TOKEN="YOUR_TOKEN"
USERS="ID ID ID ..."
OPTS="" # here you can pass other options such as --inverterd-host
```

Create systemd service file `/etc/systemd/system/inverter-bot.service` with the following content (changing stuff like paths):

```systemd
[Unit]
Description=inverter bot
After=network.target

[Service]
EnvironmentFile=/etc/default/inverter-bot
User=user
Group=user
Restart=on-failure
ExecStart=python3 /home/user/inverter-bot/inverter-bot --token $TOKEN --users-whitelist $USERS $PARAMS
WorkingDirectory=/home/user/inverter-bot

[Install]
WantedBy=multi-user.target
```

Then enable and start the service:
```
systemctl enable inverter-bot
systemctl start inverter-bot
```

## License

MIT