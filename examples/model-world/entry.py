# -*- coding: utf-8 -*-
"""World entry: boots a model as a live MoliLine node.

Environment:
  MOLI_LINE_PORT  bus port
  MOLI_NAME      registered name (e.g. modelA)
  MOLI_MODEL     path to model.gguf inside this world

At boot it reads the world's state.txt (a simple world-memory file).
Commands (payload of a bus SEND/CMD):
  PING                -> PONG state=<world state>
  ASK <text>          -> model generation
  ACT|ENTER|NAME      -> ask worldgate to unfold+enter NAME's world (no boot)
  ACT|WRITE|N|F|TEXT  -> dynamic write into N's world file F
  ACT|READ|N|F        -> read N's world file F
  ACT|HOME            -> return to caller-world context
"""
import base64
import os
import socket
import time

from llama_cpp import Llama

port = int(os.environ["MOLI_LINE_PORT"])
name = os.environ["MOLI_NAME"]
model = os.environ["MOLI_MODEL"]
state_p = os.path.join(os.path.dirname(model), "state.txt")
try:
    with open(state_p, encoding="utf-8") as f:
        STATE = f.read().strip()
except Exception:
    STATE = ""

llm = Llama(model_path=model, n_ctx=512, n_gpu_layers=0, verbose=False)


def ask(prompt):
    out = llm(prompt, max_tokens=60, temperature=0.6)
    return out["choices"][0]["text"]


def bus_send(target, payload, timeout=90):
    req = os.urandom(6).hex()
    b64 = base64.b64encode(payload.encode()).decode()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=10) as s:
            s.sendall(("SEND|%s|%s|%s\n" % (req, target, b64)).encode())
            s.settimeout(timeout)
            buf = b""
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    return "ERR:closed"
                buf += chunk
                if b"\n" in buf:
                    line = buf.split(b"\n", 1)[0].decode("utf-8", "replace")
                    if line.startswith("REPLY|" + req):
                        return base64.b64decode(line.split("|", 2)[2]).decode()
    except Exception as e:
        return "ERR:" + repr(e)


def handle(cmd):
    if cmd == "PING":
        return "PONG state=" + STATE
    if cmd.startswith("ASK "):
        return ask(cmd[4:])
    if cmd.startswith("ACT|"):
        p = cmd.split("|")
        if p[1] == "ENTER" and len(p) >= 3:
            return bus_send("worldgate", "ENTER|" + p[2])
        if p[1] == "HOME":
            return bus_send("worldgate", "HOME")
        if p[1] == "READ" and len(p) >= 4:
            return bus_send("worldgate", "READ|" + p[2] + "|" + p[3])
        if p[1] == "WRITE" and len(p) >= 5:
            return bus_send("worldgate", "WRITE|" + p[2] + "|" + p[3] +
                            "|" + p[4])
        if p[1] == "SAVE" and len(p) >= 3:
            return bus_send("worldgate", "SAVE|" + p[2])
        return "ERR:bad ACT"
    return "ERR:unknown"


while True:
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=10)
        s.sendall(("REGISTER|%s|models\n" % name).encode())
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
                    except Exception as e:
                        out = "ERR:" + repr(e)
                    s.sendall(("RESP|%s|%s\n" % (
                        req, base64.b64encode(out.encode()).decode())
                    ).encode())
    except Exception:
        time.sleep(1)


