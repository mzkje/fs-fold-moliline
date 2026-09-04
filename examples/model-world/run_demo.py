# -*- coding: utf-8 -*-
"""End-to-end model-world demo over MoliLine (Windows).

Scenario:
  1) build worlds A and B from one GGUF (demo copies the weights twice;
     production can point both worlds at one shared .fs pool),
  2) ON A (embedded llama.cpp, no Ollama),
  3) A ENTERs B's world (B not booted) and WRITEs a visit note,
  4) SAVE|B folds B's working world back into its .fs (save-back),
  5) A returns HOME; its own state is untouched,
  6) B cache is dropped; ON|B unfolds the SAVED .fs and boots B,
  7) PING B shows A's note -> the note is now part of the world file.

Usage:
  python run_demo.py --gguf <model.gguf> --out <dir>
                     [--engine-python <python-with-llama-cpp>]
"""
import argparse
import base64
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time
import uuid

PKG = pathlib.Path(__file__).resolve().parents[2]
BIN = PKG / "02-moliline" / "bin"
PROCS = []


def start(prog, args, env=None):
    p = subprocess.Popen([prog] + args, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, env=env)
    PROCS.append(p)
    return p


def raw_req(port, target, payload, timeout=180):
    req = uuid.uuid4().hex[:12]
    b64 = base64.b64encode(payload.encode()).decode()
    with socket.create_connection(("127.0.0.1", port), timeout=10) as s:
        s.sendall(("SEND|%s|%s|%s\n" % (req, target, b64)).encode())
        s.settimeout(timeout)
        buf = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                return None
            buf += chunk
            if b"\n" in buf:
                line = buf.split(b"\n", 1)[0].decode("utf-8", "replace")
                if line.startswith("REPLY|" + req):
                    return base64.b64decode(line.split("|", 2)[2]).decode()


def ask(port, target, payload, tries=15):
    for _ in range(tries):
        r = raw_req(port, target, payload)
        if r and not r.startswith("ERR:target_unreachable"):
            return r
        time.sleep(0.5)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--engine-python", default=sys.executable)
    ap.add_argument("--port", type=int, default=48017)
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    note = "visit note: model A entered this world via MoliLine"
    res = {"note": note}
    try:
        sys.path.insert(0, str(pathlib.Path(__file__).parent))
        import build_world
        res["build_A"] = build_world.build("A", a.gguf, str(out),
                                           "world A initial state; not visited")
        res["build_B"] = build_world.build("B", a.gguf, str(out),
                                           "world B initial state; not visited")
        bus = start(str(BIN / "moli_line_refactor.exe"),
                    ["--port", str(a.port),
                     "--workdir", str(out / "buswd")])
        env = dict(os.environ)
        env["WORLDGATE_LOG"] = str(out / "worldgate.log")
        gate = start(sys.executable,
                     [str(pathlib.Path(__file__).parent / "worldgate.py"),
                      str(a.port), str(out / "worlds.json"), a.engine_python],
                     env=env)
        time.sleep(1.5)
        res["on_A"] = ask(a.port, "worldgate", "ON|A")
        res["enter_B"] = ask(a.port, "modelA", "ACT|ENTER|B")
        res["stat_B_before"] = ask(a.port, "worldgate", "STAT|B")
        res["write_B"] = ask(a.port, "modelA",
                             "ACT|WRITE|B|state.txt|" + note)
        res["stat_B_after"] = ask(a.port, "worldgate", "STAT|B")
        res["save_B"] = ask(a.port, "modelA", "ACT|SAVE|B")
        res["home"] = ask(a.port, "modelA", "ACT|HOME")
        res["own_state_A"] = ask(a.port, "modelA", "ACT|READ|A|state.txt")
        # drop B cache, then boot B from the SAVED .fs
        shutil.rmtree(str(out / "cache_B"), ignore_errors=True)
        res["on_B_from_saved_fs"] = ask(a.port, "worldgate", "ON|B")
        res["ping_B"] = ask(a.port, "modelB", "PING")
        res["off_A"] = ask(a.port, "worldgate", "OFF|A")
        res["off_B"] = ask(a.port, "worldgate", "OFF|B")
        res["ok"] = bool(
            res.get("on_A") and "ready" in res.get("on_A", "")
            and res.get("enter_B") and "ENTERED" in res.get("enter_B", "")
            and res.get("write_B") and "WROTE" in res.get("write_B", "")
            and res.get("save_B") and "SAVED" in res.get("save_B", "")
            and res.get("home") and "HOME" in res.get("home", "")
            and "initial state" in res.get("own_state_A", "")
            and res.get("on_B_from_saved_fs")
            and "ready" in res.get("on_B_from_saved_fs", "")
            and res.get("ping_B") and note in res.get("ping_B", ""))
    finally:
        for p in PROCS:
            try:
                p.kill()
            except Exception:
                pass
    (out / "demo_results.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())


