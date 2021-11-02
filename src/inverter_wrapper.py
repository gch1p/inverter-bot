import json

from threading import Lock
from inverterd import (
    Format,
    Client as InverterClient,
    InverterError
)

_lock = Lock()


class InverterClientWrapper:
    def __init__(self):
        self._inverter = None
        self._host = None
        self._port = None

    def init(self, host: str, port: int):
        self._host = host
        self._port = port
        self.create()

    def create(self):
        self._inverter = InverterClient(host=self._host, port=self._port)
        self._inverter.connect()

    def exec(self, command: str, arguments: tuple = (), format=Format.JSON):
        with _lock:
            try:
                self._inverter.format(format)
                response = self._inverter.exec(command, arguments)
                if format == Format.JSON:
                    response = json.loads(response)
                return response
            except InverterError as e:
                raise e
            except Exception as e:
                # silently try to reconnect
                try:
                    self.create()
                except Exception:
                    pass
                raise e


wrapper_instance = InverterClientWrapper()
