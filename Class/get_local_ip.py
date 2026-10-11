import socket
import sys
import psutil

class LocalIPSelector:
    def __init__(self):
        self.interface: dict[str, list[str]] = {}
        self.selected_ip: str | None = None

    def choose(self):
        self.interface = self._list_interfaces()
        if self.selected_ip is None:
            raise RuntimeError("没有可用的IPv4地址。")

        name = self._prompt_interface()
        self.selected_ip = self._prompt_ip(name)
        return self.selected_ip

    @staticmethod
    def _list_interfaces() -> dict:

