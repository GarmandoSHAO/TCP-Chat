"""
同一台电脑能否同时运行两个 bore 隧道？
测试方法：创建两个本地 TCP 服务，分别用 bore 映射到公网，
验证两者都能独立获得外网地址且互不干扰。
"""
import socket
import threading
import time
import sys
import os

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcp_chat.tunnel import BoreTunnel


# ======================== 测试工具 ========================

def find_free_port():
    """找一个可用端口"""
    for _ in range(50):
        port = 10000 + (int(time.time() * 100) % 50000) + _
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", port))
            s.close()
            return port
        except OSError:
            continue
    return 18888


def start_echo_server(port):
    """启动一个简单的回显 TCP 服务器（用于验证隧道连通性）"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen(1)
    server.settimeout(15)

    def _handle(conn):
        try:
            data = conn.recv(1024)
            if data:
                conn.sendall(b"ECHO:" + data)
        except:
            pass
        finally:
            conn.close()

    def _serve():
        while True:
            try:
                conn, addr = server.accept()
                threading.Thread(target=_handle, args=(conn,), daemon=True).start()
            except socket.timeout:
                break
            except:
                break
        server.close()

    threading.Thread(target=_serve, daemon=True).start()
    return server


def test_tunnel(public_addr, expected_mark, timeout=10):
    """通过公网地址发送消息并验证回显"""
    if not public_addr:
        return False, "地址为空"
    host, port_str = public_addr.rsplit(":", 1)
    port = int(port_str)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.sendall(expected_mark.encode("utf-8"))
        resp = sock.recv(1024).decode("utf-8")
        sock.close()
        if resp == f"ECHO:{expected_mark}":
            return True, resp
        return False, f"响应不匹配: {resp}"
    except Exception as e:
        return False, str(e)


# ======================== 主测试 ========================

def main():
    passed = 0
    failed = 0

    def check(cond, msg):
        nonlocal passed, failed
        if cond:
            print(f"  ✅ {msg}")
            passed += 1
        else:
            print(f"  ❌ {msg}")
            failed += 1

    print("=" * 60)
    print("  bore 多隧道并发测试")
    print("=" * 60)

    # ---- 启动两个本地回显服务 ----
    port_a = find_free_port()
    time.sleep(0.01)  # 确保时间戳变化，得到不同端口
    port_b = find_free_port()
    print(f"\n[1] 启动本地回显服务:")
    print(f"    服务 A → 127.0.0.1:{port_a}")
    print(f"    服务 B → 127.0.0.1:{port_b}")
    srv_a = start_echo_server(port_a)
    srv_b = start_echo_server(port_b)
    time.sleep(0.2)

    # ---- 启动两个 bore 隧道 ----
    print(f"\n[2] 启动 bore 隧道 (超时 25s)...")
    tunnel_a = BoreTunnel(local_port=port_a)
    tunnel_b = BoreTunnel(local_port=port_b)

    results = {}
    def start_tunnel(tunnel, name):
        ok, msg = tunnel.start()
        results[name] = (ok, msg, tunnel)

    threads = [
        threading.Thread(target=start_tunnel, args=(tunnel_a, "A"), daemon=True),
        threading.Thread(target=start_tunnel, args=(tunnel_b, "B"), daemon=True),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=25)

    # ---- 验证两个隧道是否都成功 ----
    print(f"\n[3] 检查隧道状态:")
    for name in ("A", "B"):
        ok, msg, tun = results.get(name, (False, "未完成", None))
        check(ok, f"隧道{name} 启动成功: {msg}")
        if ok:
            check(tun.public_addr is not None, f"隧道{name} 有外网地址: {tun.public_addr}")

    # ---- 验证两个地址是否不同 ----
    print(f"\n[4] 检查地址唯一性:")
    addr_a = tunnel_a.public_addr
    addr_b = tunnel_b.public_addr
    if addr_a and addr_b:
        # 提取端口部分
        port_a_str = addr_a.rsplit(":", 1)[1] if ":" in addr_a else ""
        port_b_str = addr_b.rsplit(":", 1)[1] if ":" in addr_b else ""
        check(port_a_str != port_b_str, f"两个隧道端口不同: {port_a_str} vs {port_b_str}")
    else:
        print("  ⚠️  跳过地址唯一性检查（隧道未全部成功）")

    # ---- 通过公网地址实际测试连通性 ----
    print(f"\n[5] 通过公网地址测试隧道连通性:")
    for name, tun in [("A", tunnel_a), ("B", tunnel_b)]:
        if tun.public_addr:
            mark = f"HELLO_BORE_{name}"
            ok, resp = test_tunnel(tun.public_addr, mark, timeout=10)
            check(ok, f"隧道{name} 公网通信正常: {resp}")
        else:
            print(f"  ⚠️  跳过隧道{name} 连通性测试（无外网地址）")

    # ---- 交叉验证（通过隧道A访问服务B的端口应该失败） ----
    print(f"\n[6] 交叉验证（可选）:")
    if tunnel_a.public_addr and tunnel_b.public_addr:
        # 通过隧道A的地址发送服务B的标记 → 应该收到ECHO:A不是ECHO:B
        mark_a = "CROSS_CHECK_A"
        ok_a, resp_a = test_tunnel(tunnel_a.public_addr, mark_a, timeout=5)
        if ok_a:
            check(resp_a == f"ECHO:{mark_a}",
                  f"隧道A正确路由到服务A")
        # 通过隧道B的地址发送服务A的标记 → 应该收到ECHO:B不是ECHO:A
        mark_b = "CROSS_CHECK_B"
        ok_b, resp_b = test_tunnel(tunnel_b.public_addr, mark_b, timeout=5)
        if ok_b:
            check(resp_b == f"ECHO:{mark_b}",
                  f"隧道B正确路由到服务B")

    # ---- 清理 ----
    print(f"\n[7] 清理资源:")
    tunnel_a.stop()
    tunnel_b.stop()
    srv_a.close()
    srv_b.close()
    print("  已停止所有隧道和服务")

    # ---- 结果汇总 ----
    print(f"\n{'=' * 60}")
    print(f"  测试结果: {passed} 通过, {failed} 失败")
    print(f"{'=' * 60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
