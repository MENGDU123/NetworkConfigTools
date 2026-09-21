import random
import socket
import threading
import tftpy

class TFTPServer:
    def __init__(self,root_dir: str = "./TftpFiles", host: str = "0.0.0.0",
                  port_range: tuple = (69,69)):
        self.root_dir = root_dir
        self.host = host
        #单下划线不会触发名称改写，子类调用请注意
        self.port_range = port_range
        self.port = None
        self._server = None
        self._thread = None


    def _pick_free_port(self) -> int :
        """此方法用于在 port_range 内随机挑一个空闲 UDP 端口"""
        lo,hi = self.port_range
        ports = list(range(lo,hi+1))
        random.shuffle(ports)

        for port in ports:
            #测试端口是否被占用
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.bind((self.host, port))
                return port
            except OSError:
                continue
            finally:
                sock.close()

        raise OSError(f"在 {lo}--{hi} 范围内找不到可用端口。")

    def start(self) -> int :
        """启动服务器，返回实际使用的端口号"""
        self.port = self._pick_free_port()

        self._server = tftpy.TftpServer(self.root_dir)
        self._thread = threading.Thread(
            target=self._server.listen,
            kwargs={"listenip": self.host, "listenport": self.port},
            daemon=True
        )
        self._thread.start()
        return self.port

    def stop(self) -> None:
        if self._server:
            self._server.stop(now = True)
            self._server = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()

