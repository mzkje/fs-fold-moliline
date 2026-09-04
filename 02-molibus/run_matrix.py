# -*- coding: utf-8 -*-
"""MoliBus v1.0 baseline matrix runner (Python subprocess)."""
import json, os, subprocess, time
ROOT = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(ROOT, "bin")
PORT = "47126"
procs = []
def start(exe, args):
    p = subprocess.Popen([os.path.join(BIN, exe)] + args,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    procs.append(p)
    return p
try:
    start("moli_bus_tcp.exe", [PORT])
    time.sleep(0.8)
    svc = start("world_svc_tcp.exe", ["executor", "events", "127.0.0.1:" + PORT])
    time.sleep(1.0)
    res = {}
    def ctl(*args):
        r = subprocess.run([os.path.join(BIN, "world_ctl_tcp.exe"), PORT] + list(args),
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        return (r.stdout or r.stderr).strip()
    res["ping"] = ctl("SEND","executor","PING")
    res["echo"] = ctl("SEND","executor","ECHO hello molibus")
    res["status"] = ctl("SEND","executor","STATUS")
    res["stats"] = ctl("SEND","executor","STATS")
    # crash-restore
    svc.kill(); procs.remove(svc); time.sleep(0.5)
    res["deadletter"] = ctl("SEND","executor","PING")
    svc2 = start("world_svc_tcp.exe", ["executor", "events", "127.0.0.1:" + PORT])
    time.sleep(1.2)
    res["recover_ping"] = ctl("SEND","executor","PING")
    res["ok"] = res["ping"].find("PONG") >= 0 and res["recover_ping"].find("PONG") >= 0
    print(json.dumps(res, ensure_ascii=False, indent=1))
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    open(os.path.join(ROOT, "results", "molibus_matrix.json"), "w",
         encoding="utf-8").write(
        json.dumps(res, ensure_ascii=False, indent=1))
finally:
    for p in procs:
        try: p.kill()
        except Exception: pass
