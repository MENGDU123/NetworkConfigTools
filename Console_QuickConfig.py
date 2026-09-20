"""
此脚本基于锐捷交换机，后续有机会将其进行类化，以提供更好的兼容性。
使用此脚本可以快速对Console连接的设备进行批量配置，可以有效提升现场配置速度。
此脚本命令部分可以进行修改，不过只建议用于RuijieOS或CiscoIOS。
"""
import serial.tools.list_ports
import time
from datetime import datetime
now = datetime.now()
now = now.strftime("%Y-%m-%d_%H-%M-%S")
print(now)

while True:
    NEW_PASSWORD = input("[*]Enter new password: ")
    ENSURE_PASSWORD = input("[*]Enter ensure password: ")
    if ENSURE_PASSWORD != NEW_PASSWORD:
        print("[!]Passwords do not match!")
        continue
    break

def get_com_port(): #此函数用于寻找com口。
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("[!] No serial ports found!")
        exit()

    print("\n[+] Available serial ports:")
    for idx, port in enumerate(ports,start=1):
        print(f"{idx}. {port.device} - {port.description}")

    while True:
        choice = input("[+]Select serial port: ")
        try:
            idx = int(choice)
        except ValueError:
            print("[!] Invalid choice.")
            continue
        if 1 <= idx <= len(ports):
            selected_port = ports[idx-1].device
            print("[+]Selected port: ", selected_port)
            return selected_port
        else:
            print(f"[!] Invalid choice.(1 ~ {len(ports)})")
            continue

def send_command(ser, command, timeout=90, sleep_time=0.5):
    ser.write((command + "\n").encode('gbk', errors='ignore'))
    if command == "end":
        ser.write(b"\r\n")
    output = ""
    start_time = time.time()

    while time.time() - start_time < timeout:
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting).decode('gbk', errors='ignore')
            output += data
            if "Choose the size" in output:
                ser.write(b"2048\n")
                output = ""
                time.sleep(sleep_time)
                continue
            # 处理 "Do you really want to replace them?" 提示
            if "replace them" in output:
                ser.write(b"yes\n")  # 确认替换已有密钥[reference:19]
                output = ""
                time.sleep(sleep_time)
                continue
            # 处理分页提示（发送空格翻页）
            if "--More--" in output:
                ser.write(b" ")          # 锐捷通常用空格翻页
                output = output.replace("--More--", "")
                # 翻页后立即继续读取，不检查结束符
                time.sleep(sleep_time)
                continue
            # 检测命令提示符（表示命令执行完毕）
            lines = output.splitlines()
            if lines:
                last_line = lines[-1].strip()
                if last_line.endswith("#") or last_line.endswith(">"):
                    break  # 正常结束，跳出循环
        time.sleep(sleep_time)
    else:
        # 循环因超时结束（未执行 break）
        print(f"[!] Command timed out after {timeout}s: {command}")
    return output

def enable_login(ser):
    """进入特权模式，自动输入密码"""
    print("[+] Sending 'enable'")
    ser.write(b"enable\n")
    time.sleep(2)

    response = ser.read(ser.inWaiting()).decode('gbk', errors='ignore')
    print("[+] Response:", response.strip() if response else "(empty)")

    # 检查是否需要密码
    if "Password" in response or "password" in response:
        password = str(input("[*]Password:"))  # 如果有密码，请输入密码！
        print(f"[+] Sending password: {password}")
        ser.write((password + "\n").encode('gbk', errors='ignore'))
        time.sleep(2)
        # 读取登录后的响应
        login_resp = ser.read(ser.inWaiting()).decode('gbk', errors='ignore')
        if login_resp:
            print("[+] Login response:", login_resp.strip())
        # 检查是否成功进入特权模式（提示符包含 #）
        if '#' in login_resp or '#' in response:
            print("[+] Successfully entered privileged mode")
            return True
        else:
            for _ in range(3):
                ser.write(b"\n")
            print("[!] Failed to enter privileged mode")
            return False
    elif '#' in response:
        print("[+] Already in privileged mode")
        return True
    else:
        print("[!] Unknown response, assuming not privileged")
        return False

BAUD_RATE = 9600
TIMEOUT = 5

# 在这里输入配置命令。
commands = [
    f"copy flash:config.text flash:config_{now}.bak", #备份配置文件,
    "dir",
    "configure terminal",           # 进入全局配置模式
    "show ip interface brief",
    "no enable service telnet-server", # 1. 关闭Telnet服务
    "line vty 0 4",                 # 2. 进入VTY线路配置模式
    "no password",                  # 3. 删除VTY登录密码
    "exit",                         # 4. 退出VTY配置模式
    "no enable password",           # 5. 删除enable明文密码
    "no enable secret",             # 6. 删除enable密文密码
    "ip ssh version 2",             # 7. 指定SSH版本。
    "enable service ssh-server",    # 8. 使能SSH服务。
    f"username admin privilege 15 password {NEW_PASSWORD}",
    f"enable secret {NEW_PASSWORD}",
    "line vty 0 4",
    "transport input ssh",
    "login local",
    "exit",
    "crypto key generate rsa",
    "end",                          # 退出全局配置模式
    "write memory"                  # 保存配置
]

if __name__ == "__main__":
    COM_PORT = get_com_port()
    if COM_PORT is None:
        exit()

    try:
        print("[+]Connecting to serial port ", COM_PORT)
        ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=TIMEOUT)
        if ser.is_open:
            print("[+]Connected to ", COM_PORT)
            ser.reset_input_buffer()  # 清空缓冲区
            # 尝试唤醒设备
            for attempt in range(5):
                print(f"[+]Attempt {attempt + 1}/5 to wake up device...")
                ser.write(b"\n\r")
                time.sleep(3)  # 等待设备响应
                response = ser.read(ser.in_waiting).decode('gbk', errors='ignore')
                if response:  # 如果收到任何字符，认为唤醒成功
                    print("[+]Device responded, wake up successful.")
                    break
                else:
                    print("[!]No response, retrying...")
            else:
                # 如果循环未break，说明10次都无响应
                print("[!]Failed to wake up device after 5 attempts. Exiting.")
                ser.close()
                exit(-1)
        else:
            print("[!]Failed to connect to ", COM_PORT)
            exit()

        time.sleep(5)
        ser.reset_input_buffer() #清空缓冲区

        #尝试登录
        if not enable_login(ser):
            print("[!] Cannot get privileged mode, aborting.")
            ser.close()
            exit()
        #执行命令
        for cmd in commands:
            print("[+]Sending ", cmd)
            response = send_command(ser,cmd)
            if response:
                print("[+]Response: ", response)
        #结束通讯
        ser.close()
        print("[-]Disconnecting from ", COM_PORT)
        exit()

    except serial.SerialException as e:
        print(f"[!]Serial Error:{e}")
        exit()

    except Exception as e:
        print(f"[!]Unknow Error:{e}")