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
# import time
# import os

#读取当前时间，接下来所有备份文件均会使用此时间（不包含脚本运行延后的时间）
TIME_NOW = datetime.now()
TIME_NOW = TIME_NOW.strftime("%Y-%m-%d_%H-%M-%S")
print(TIME_NOW)

USERNAME = "admin"
SECONDARY_PASSWORD = "" #无需enable就留空（确实不需要）
DEVICE = "ruijie_os" #选择交换机系统
BACKUP_CMD = [ #交换机备份命令
    f"copy flash:/config.text flash:/config_{TIME_NOW}.text.bak",
    "dir"
]

IP_LIST = [f"10.1.254.{i}" for i in range(1, 91)]
# IP_LIST = ["10.1.254.254"]
#这里可以修改IP列表，SS端口默认为22

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

        #执行预设备份命令
        for cmd in BACKUP_CMD:
            output = conn.send_command_timing(cmd)
            if "Y/N" in output or "[Y/N]" in output or "confirm" in output.lower():
                output += conn.send_command_timing("y")
            print(output)

        print(f"[成功] {ip} -> 备份完成，文件: config_{TIME_NOW}.text.bak")


    except Exception as e:
        print(f"[失败] {ip} -> {e}")

    finally:
        if conn is not None:
            try:
                conn.disconnect()
            except Exception:
                pass