#!/usr/bin/env python3
"""采集器 watchdog：collector.py 退出/被远程重启后自动拉起。"""
import os
import signal
import subprocess
import sys
import time

# pythonw 无控制台，cmd 重定向对它不可靠；日志在进程内落盘。
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = open(os.path.join(HERE, "collector.log"), "a", buffering=1,
           encoding="utf-8", errors="replace")
sys.stdout = LOG
sys.stderr = LOG

# 控制台 ^C/关窗只杀 collector 子进程；watchdog 忽略 SIGINT，5 秒后自动拉起。
try:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
except (ValueError, OSError):
    pass

# 防双开：锁文件里写活进程 PID；已有活实例时本实例直接退出。
# 注意 Windows 上 os.kill(pid, 0) 语义不对（会 TerminateProcess），用 ctypes 探活。
def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == STILL_ACTIVE
    except Exception:
        return False


LOCK = os.path.join(HERE, "collector.lock")
try:
    if os.path.exists(LOCK):
        try:
            old_pid = int(open(LOCK).read().strip() or "0")
            if _pid_alive(old_pid):
                print(f"[watchdog] 已有实例 PID {old_pid} 在跑，退出", flush=True)
                sys.exit(0)
            print(f"[watchdog] 锁残留（PID {old_pid} 已死），接管", flush=True)
        except ValueError:
            pass
    with open(LOCK, "w") as f:
        f.write(str(os.getpid()))
except OSError:
    pass

while True:
    code = subprocess.call([sys.executable, os.path.join(HERE, "collector.py")],
                           cwd=HERE, stdout=LOG, stderr=LOG)
    print(f"[watchdog] collector exited ({code}); restart in 5s", flush=True)
    time.sleep(5)
