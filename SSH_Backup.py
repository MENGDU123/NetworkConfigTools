"""
此脚本用于对开启了SSH的服务器进行远程备份。
脚本计划开发TFTP服务器功能，可以命令远端网络设备将备份的配置文件上传至本地（此功能要求本地与交换机处于同一网络域）。
备份命令可以修改作为其它内容，理论不止可以用于备份。
"""
from netmiko import ConnectHandler, NetmikoAuthenticationException
from datetime import datetime
#后续打算开发本地tftp服务端，这样备份时可以让交换机自动上传备份。
# import tftpy
# import threading
# import random
# import socket
import time
import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__),"Class"))
# noinspection PyUnresolvedReferences
from tftp_server import TFTPServer
# 抱歉我没买 Pycharm Pro，社区版有些不那么智能。
# from Class.tftp_server import TFTPServer

#读取当前时间，接下来所有备份文件均会使用此时间（不包含脚本运行延后的时间）
TIME_NOW = datetime.now()
TIME_NOW = TIME_NOW.strftime("%Y-%m-%d_%H-%M-%S")
print(TIME_NOW)

USERNAME = "admin"
SECONDARY_PASSWORD = "" #无需enable就留空（确实不需要）
DEVICE = "ruijie_os" #选择交换机系统

#已弃用
# BACKUP_CMD = [ #交换机备份命令
#     f"copy flash:/config.text flash:/config_{TIME_NOW}.text.bak",
#     "dir"
# ]

TFTP_BIND_HOST = "0.0.0.0"
TFTP_SERVER_IP = "172.16.20.183" #后续会开发自动获取IP
TFTP_ROOT = "./TftpFiles"
os.makedirs(TFTP_ROOT, exist_ok=True)

IP_LIST = [f"10.1.254.{i}" for i in range(1, 91)]
# IP_LIST = ["10.1.254.254"]
#这里可以修改IP列表，SS端口默认为22

srv = TFTPServer(root_dir=TFTP_ROOT, host=TFTP_SERVER_IP)
port = srv.start()
print(f"TFTP 服务器已启动，端口{port}")

try:
    for ip in IP_LIST:
        password_list = [
            "ruijie",
            "123456"
        ] #密码列表，假设网络域中每台设备密码不一样，那么脚本将会从密码列表中选取一个尝试。
          #以上密码仅供测试，请勿在生产环境设置弱密码！
          #后续有打算开发数据库导入的计划。

        conn = None
        try:
            for idx, password in enumerate(password_list):
                try:
                    conn = ConnectHandler(
                        device_type=DEVICE,
                        host=ip,
                        username=USERNAME,
                        password=password,
                        secret=SECONDARY_PASSWORD,
                    )
                    print()
                    print(f"{ip}    -> 密码 {idx + 1} 认证成功")
                    break
                except NetmikoAuthenticationException:
                    if idx < len(password_list) - 1:
                        print(f"{ip}    -> 密码 {idx + 1} 认证失败，尝试下一个")
                        continue
            if conn is None:
                print(f"[失败] {ip} -> 没有匹配密码。")
                continue

            if SECONDARY_PASSWORD:
                conn.enable()

            remote_name = f"{ip}_{TIME_NOW}.bak"  # 本地最终想用的名字
            tmp_name = "config.text"  # 交换机上传时的固定名字
            tftp_url = f"tftp://{TFTP_SERVER_IP}/{tmp_name}"

            tmp_path = os.path.join(TFTP_ROOT, tmp_name)
            final_path = os.path.join(TFTP_ROOT, remote_name)

            # 清除上次文件残留
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

            cmd_list = [
                f"copy flash:/config.text {tftp_url}",
                "dir"
            ]

            for cmd in cmd_list:
                output = conn.send_command_timing(cmd, read_timeout=60)
                if "Y/N" in output or "[Y/N]" in output or "confirm" in output.lower():
                    output += conn.send_command_timing("y", read_timeout=60)
                print(output)

            # 等 config.text 落地
            for _ in range(60):
                if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                    break
                time.sleep(0.5)

            # 落地后立刻改名
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                try:
                    os.replace(tmp_path, final_path)  # 本地改名
                    print(f"[成功] {ip} -> 已保存 {final_path}")
                except OSError as e:
                    print(f"[警告] {ip} -> 文件已到但改名失败: {e}")
            else:
                print(f"[警告] {ip} -> 命令执行了，但本地没等到文件")

        except Exception as e:
            print(f"[失败] {ip} -> {e}")

        finally:
            if conn is not None:
                try:
                    conn.disconnect()
                except Exception:
                    pass
finally:
    srv.stop()