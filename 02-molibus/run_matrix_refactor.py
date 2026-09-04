# -*- coding: utf-8 -*-
"""Run baseline matrix against refactored bus (moli_bus_refactor)."""
import json, os, subprocess, time
ROOT = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(ROOT, "bin")
PORT = "47128"
procs=[]
def start(exe,args):
    p=subprocess.Popen([os.path.join(BIN,exe)]+args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    procs.append(p); return p
def ctl(*args):
    r=subprocess.run([os.path.join(BIN,"world_ctl_tcp.exe"),PORT]+list(args),
                     capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=30)
    return (r.stdout or r.stderr).strip()
try:
    start("moli_bus_refactor.exe",["--port",PORT,"--workdir",os.path.join(os.environ.get("TEMP","."),"moli_rf_"+PORT)])
    time.sleep(0.8)
    svc=start("world_svc_tcp.exe",["executor","events","127.0.0.1:"+PORT]); time.sleep(1.0)
    res={"ping":ctl("SEND","executor","PING"), "echo":ctl("SEND","executor","ECHO refactor ok"),
         "status":ctl("SEND","executor","STATUS"), "stats":ctl("SEND","executor","STATS")}
    svc.kill(); procs.remove(svc); time.sleep(0.5)
    res["deadletter"]=ctl("SEND","executor","PING")
    svc2=start("world_svc_tcp.exe",["executor","events","127.0.0.1:"+PORT]); time.sleep(1.0)
    res["recover_ping"]=ctl("SEND","executor","PING")
    res["ok"]="PONG" in res["ping"] and "PONG" in res["recover_ping"]
    print(json.dumps(res,ensure_ascii=False,indent=1))
finally:
    for p in procs:
        try: p.kill()
        except Exception: pass
