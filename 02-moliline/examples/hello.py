# -*- coding: utf-8 -*-
"""example: start refactor bus + world, then PING via ctl (run anywhere)."""
import os, subprocess, time, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
PORT = "47127"
procs=[]
def start(exe, args):
    p=subprocess.Popen([os.path.join(BIN,exe)]+args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    procs.append(p); return p
try:
    start("moli_line_refactor.exe",["--port", PORT,
          "--workdir", os.path.join(os.environ.get("TEMP", "."),
                                    "moli_hello_" + PORT)]); time.sleep(0.8)
    start("world_svc_tcp.exe",["executor","events","127.0.0.1:"+PORT]); time.sleep(1)
    r=subprocess.run([os.path.join(BIN,"world_ctl_tcp.exe"),PORT,"SEND","executor","PING"],
                     capture_output=True,text=True,encoding="utf-8",errors="replace")
    print(r.stdout or r.stderr)
finally:
    for p in procs:
        try: p.kill()
        except Exception: pass


