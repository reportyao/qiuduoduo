#!/usr/bin/env python3
"""采集器 watchdog：collector.py 退出/被远程重启后自动拉起。"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
while True:
    code = subprocess.call([sys.executable, os.path.join(HERE, "collector.py")],
                           cwd=HERE)
    print(f"[watchdog] collector exited ({code}); restart in 5s", flush=True)
    time.sleep(5)
