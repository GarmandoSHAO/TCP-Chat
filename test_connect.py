"""
TCP-Chat 连接诊断工具
测试服务端是否可达，以及广播发现是否正常
"""
import socket
import time
import sys

HOST = "127.0.0.1"
PORT = 8888
DISCOVERY_PORT = 9999

print("=" * 55)
print("🔍 TCP-Chat 连接诊断工具")
print("=" * 55)

# === 测试 1: TCP 直连 ===
print("\n[1/4] 测试 TCP 直连到 127.0.0.1:8888 ...")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    s.connect((HOST, PORT))
    print("  ✅ TCP 连接成功！服务端正在运行")
    # 检查是否收到了欢迎消息
    s.settimeout(2)
    try:
        data = s.recv(1024)
        print(f"  ✅ 收到服务端消息: {data.decode('utf-8')[:60]}...")
    except socket.timeout:
        print("  ⚠️  连接成功但未收到数据")
    s.close()
except ConnectionRefusedError:
    print("  ❌ 连接被拒绝 — 服务端未运行？")
    print("     请先启动 server.py")
except socket.timeout:
    print("  ❌ 连接超时 — 防火墙可能拦截了端口")
except Exception as e:
    print(f"  ❌ 错误: {e}")

# === 测试 2: 检查服务端 UDP 广播 ===
print("\n[2/4] 监听服务端 UDP 广播 (端口 9999, 5秒超时) ...")
try:
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_sock.bind(("0.0.0.0", DISCOVERY_PORT))
    udp_sock.settimeout(5)

    try:
        data, addr = udp_sock.recvfrom(1024)
        msg = data.decode("utf-8")
        print(f"  ✅ 收到UDP广播！来源: {addr}")
        print(f"     内容: {msg}")

        if msg.startswith("CHAT_ROOM|"):
            parts = msg.split("|")
            if len(parts) == 4:
                _, room_name, ip, port = parts
                print(f"     房间: {room_name}, IP: {ip}, 端口: {port}")
    except socket.timeout:
        print("  ❌ 未收到UDP广播")
        print("     ⚠️  Windows 可能不将 UDP 广播回环到本机")
        print("     → 这是单机测试时遇到的主要问题")
    finally:
        udp_sock.close()
except OSError as e:
    print(f"  ❌ 绑定端口失败: {e}")
    print("     → 可能端口被占用，或者另一个客户端已在监听")

# === 测试 3: 测试 connect 到局域网 IP ===
print("\n[3/4] 尝试连接本机局域网 IP ...")
try:
    # 获取本机局域网 IP
    temp_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    temp_s.connect(("8.8.8.8", 80))
    local_ip = temp_s.getsockname()[0]
    temp_s.close()
    print(f"   本机局域网 IP: {local_ip}")

    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.settimeout(3)
    s2.connect((local_ip, PORT))
    print(f"  ✅ 通过 {local_ip}:{PORT} 连接成功！")
    s2.close()
except Exception as e:
    print(f"  ❌ 连接 {local_ip}:{PORT} 失败: {e}")

# === 测试 4: 检查防火墙规则 ===
print("\n[4/4] 检查 Windows 防火墙状态 ...")
try:
    import subprocess
    result = subprocess.run(
        "netsh advfirewall firewall show rule name=all dir=in | findstr /I \"8888 9999 python\"",
        shell=True, capture_output=True, text=True, timeout=5
    )
    if result.stdout.strip():
        print(f"   找到相关防火墙规则:")
        for line in result.stdout.strip().split("\n"):
            print(f"   {line.strip()}")
    else:
        print("   ℹ️  未找到特定于 8888/9999 的入站规则")

    fp = subprocess.run(
        "netsh advfirewall show allprofiles state",
        shell=True, capture_output=True, text=True, timeout=5
    )
    for line in fp.stdout.strip().split("\n"):
        if "State" in line:
            print(f"   {line.strip()}")
except:
    print("   ⚠️  无法检查防火墙状态")

print("\n" + "=" * 55)
print("📋 诊断完成")
print("=" * 55)
