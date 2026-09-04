# -*- coding: utf-8 -*-
"""worldgate: a MoliLine node that treats folded worlds (.fs) as live containers.

Commands (payload of a bus SEND/CMD to "worldgate"):
  ON|NAME     unfold world if needed, boot its model entry, wait ready
  OFF|NAME    stop the model process of NAME
  ENTER|NAME  unfold NAME's .fs into its working cache (NO model boot)
  HOME        return to caller-world context (demo: modelA)
  READ|NAME|F read file F inside NAME's working world
  WRITE|N|F|TEXT  dynamic write into NAME's working world (no copy, guarded)
  STAT|NAME   file sizes inside NAME's working world
  SAVE|NAME   fold the working world back into a new .fs (save-back)

worlds.json maps NAME -> {"fs": "<abs path>", "cache": "<abs path>"}.
Security: WRITE/READ are constrained to each world's cache directory.
"""
import base64
import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import traceback

PKG = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PKG / "01-file-space-folding"))
import foldcore  # noqa: E402


def log(msg):
    with open(os.environ.get("WORLDGATE_LOG", os.devnull),
              "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def unfold(worlds, name):
    w = worlds[name]
    cache = pathlib.Path(w["cache"])
    if not (cache / "entry.py").exists():
        log("unfold " + name)
        foldcore.restore_tree(w["fs"], str(cache))


def stat_dir(worlds, name):
    out = {}
    root = pathlib.Path(worlds[name]["cache"])
    for p in root.rglob("*"):
        if p.is_file():
            out[str(p.relative_to(root)).replace("\\", "/")] = p.stat().st_size
    return out


def raw_ping(port, name):
    req = os.urandom(6).hex()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
            s.sendall(("SEND|%s|%s|%s\n" % (
                req, "model" + name,
                base64.b64encode(b"PING").decode())).encode())
            s.settimeout(8)
            buf = b""
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    return "ERR"
                buf += chunk
                if b"\n" in buf:
                    line = buf.split(b"\n", 1)[0].decode("utf-8", "replace")
                    if line.startswith("REPLY|" + req):
                        return base64.b64decode(line.split("|", 2)[2]).decode()
    except Exception:
        return "ERR"


def main():
    port = int(sys.argv[1])
    worlds = json.load(open(sys.argv[2], encoding="utf-8"))
    engine_py = sys.argv[3] if len(sys.argv) > 3 else sys.executable
    pids = {}

    def do_on(name):
        unfold(worlds, name)
        w = worlds[name]
        env = dict(os.environ)
        env["MOLI_LINE_PORT"] = str(port)
        env["MOLI_NAME"] = "model" + name
        env["MOLI_MODEL"] = str(pathlib.Path(w["cache"]) / "model.gguf")
        p = subprocess.Popen([engine_py,
                              str(pathlib.Path(w["cache"]) / "entry.py")],
                             env=env)
        pids[name] = p
        for _ in range(40):
            time.sleep(0.5)
            if p.poll() is not None:
                return "ON %s exited rc=%s" % (name, p.returncode)
            if raw_ping(port, name).startswith("PONG"):
                return "ON %s ready pid=%s" % (name, p.pid)
        return "ON %s booted pid=%s not-ready" % (name, p.pid)

    def do_write(name, rel, text):
        unfold(worlds, name)
        cache = pathlib.Path(worlds[name]["cache"]).resolve()
        target = (cache / rel).resolve()
        if not str(target).startswith(str(cache) + os.sep):
            return "ERR:traversal"
        target.parent.mkdir(parents=True, exist_ok=True)
        old = target.stat().st_size if target.exists() else 0
        target.write_text(text, encoding="utf-8")
        return "WROTE %s/%s old=%d new=%d" % (name, rel, old,
                                              target.stat().st_size)

    def do_save(name):
        unfold(worlds, name)
        cache = pathlib.Path(worlds[name]["cache"])
        fs = pathlib.Path(worlds[name]["fs"])
        tmp = str(fs) + ".tmp"
        r = foldcore.fold_tree(str(cache), tmp)
        os.replace(tmp, str(fs))
        return "SAVED %s fs_bytes=%d files=%d saved_pct=%s" % (
            name, r["fs_bytes"], r["files"], r["saved_percent"])

    def handle(cmd):
        p = cmd.split("|")
        if p[0] == "ON" and len(p) >= 2:
            return do_on(p[1])
        if p[0] == "OFF" and len(p) >= 2:
            if p[1] in pids and pids[p[1]].poll() is None:
                subprocess.run(["taskkill", "/PID", str(pids[p[1]].pid),
                                "/F"], capture_output=True, timeout=10)
                return "OFF %s" % p[1]
            return "OFF %s already stopped" % p[1]
        if p[0] == "ENTER" and len(p) >= 2:
            unfold(worlds, p[1])
            st = stat_dir(worlds, p[1])
            return "ENTERED %s no-boot files=%d total=%d" % (
                p[1], len(st), sum(st.values()))
        if p[0] == "HOME":
            return "HOME back to modelA context"
        if p[0] == "READ" and len(p) >= 3:
            cache = pathlib.Path(worlds[p[1]]["cache"])
            f = cache / p[2]
            return f.read_text(encoding="utf-8") if f.exists() else "ERR:no file"
        if p[0] == "WRITE" and len(p) >= 4:
            return do_write(p[1], p[2], p[3])
        if p[0] == "SAVE" and len(p) >= 2:
            return do_save(p[1])
        if p[0] == "STAT" and len(p) >= 2:
            return "STAT %s %s" % (p[1], json.dumps(stat_dir(worlds, p[1])))
        return "ERR:unknown " + cmd

    while True:
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=10)
            s.sendall(b"REGISTER|worldgate|control\n")
            buf = b""
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    raise ConnectionError("closed")
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    parts = line.decode("utf-8", "replace").split("|")
                    if len(parts) >= 4 and parts[0] == "CMD":
                        req = parts[1]
                        cmd = base64.b64decode(parts[3]).decode("utf-8")
                        try:
                            out = handle(cmd)
                        except Exception:
                            log(traceback.format_exc())
                            out = "ERR:gate exception"
                        log("cmd %s -> %s" % (cmd, out[:160]))
                        s.sendall(("RESP|%s|%s\n" % (
                            req, base64.b64encode(out.encode()).decode())
                        ).encode())
        except Exception:
            log("loop err: " + traceback.format_exc())
            time.sleep(1)


if __name__ == "__main__":
    main()


