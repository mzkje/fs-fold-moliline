# -*- coding: utf-8 -*-
"""Agent-in-world demo: the model itself operates a folded program world.

The model (llama.cpp, no API) gets an allowlisted toolset bound to an
unfolded .fs world and a goal:
  1) browse the world, 2) bump config version to 2.0.0, 3) run the program,
  4) read notes.txt, then DONE.

Usage:
  python agent_demo.py --gguf <model.gguf> [--out <dir>]
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

PKG = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PKG / "01-file-space-folding"))
import foldcore  # noqa: E402
from llama_cpp import Llama  # noqa: E402

SYSTEM = (
    "You are a file-world operator. You may only use these tools, one "
    "command per line:\n"
    "LIST\n"
    "READ <file>\n"
    "WRITE <file>|<new full content>\n"
    "RUN_APP\n"
    "DONE <final summary>\n"
    "Read files before changing them. Finish with DONE only after version is "
    "2.0.0 and the app ran successfully.")

GOAL = ("Goal: inside this world, (1) list and read the files, "
        "(2) change config.json so version is exactly \"2.0.0\", "
        "(3) run the app with RUN_APP, (4) read notes.txt and mention what "
        "the notes say in your DONE summary. Output one command per line, "
        "nothing else.")


def build_world(root):
    src = root / "src"
    src.mkdir()
    (src / "config.json").write_text(
        json.dumps({"app": "hello_world", "version": "1.0.0",
                    "enabled": True}), encoding="utf-8")
    (src / "data.txt").write_text("hello world data 42", encoding="utf-8")
    (src / "notes.txt").write_text(
        "knowledge: the sky is blue; the world remembers what models write.",
        encoding="utf-8")
    (src / "run.py").write_text(
        "import json, pathlib\n"
        "c = json.loads(pathlib.Path('config.json').read_text(encoding='utf-8'))\n"
        "d = pathlib.Path('data.txt').read_text(encoding='utf-8').strip()\n"
        "print('app %s version %s data=%s' % (c['app'], c['version'], d))\n",
        encoding="utf-8")
    fs = root / "program_world.fs"
    foldcore.fold_tree(str(src), str(fs))
    shutil.rmtree(str(src))
    cache = root / "cache"
    foldcore.restore_tree(str(fs), str(cache))
    return cache


class Tools:
    def __init__(self, root):
        self.root = root
        self.app_runs = []

    def _p(self, rel):
        t = (self.root / rel).resolve()
        if not str(t).startswith(str(self.root.resolve()) + os.sep):
            raise ValueError("traversal")
        return t

    def list(self):
        return "\n".join(
            "%s (%d B)" % (str(p.relative_to(self.root)).replace("\\", "/"),
                           p.stat().st_size)
            for p in sorted(self.root.rglob("*")) if p.is_file())

    def read(self, rel):
        t = self._p(rel)
        if not t.exists():
            return "ERR:no file " + rel
        data = t.read_text(encoding="utf-8")
        return data if len(data) <= 1500 else data[:1500] + "\n...[truncated]"

    def write(self, rel, content):
        t = self._p(rel)
        if len(content) > 4000:
            return "ERR:content too long"
        t.parent.mkdir(parents=True, exist_ok=True)
        old = t.read_text(encoding="utf-8") if t.exists() else ""
        t.write_text(content, encoding="utf-8")
        return "WROTE %s (old %d B -> new %d B)" % (rel, len(old),
                                                    len(content))

    def run_app(self):
        r = subprocess.run([sys.executable, "run.py"], cwd=str(self.root),
                           capture_output=True, text=True, timeout=30)
        self.app_runs.append((r.returncode, r.stdout))
        return "rc=%d stdout=%s" % (r.returncode, r.stdout.strip())


def parse(cmd):
    cmd = cmd.strip()
    if cmd.upper().startswith("LIST"):
        return ("LIST", "")
    m = re.match(r"(?i)^READ\s+(.+)$", cmd)
    if m:
        return ("READ", m.group(1).strip())
    m = re.match(r"(?i)^WRITE\s+([^|]+)\|(.*)$", cmd, re.S)
    if m:
        return ("WRITE", m.group(1).strip(), m.group(2))
    if cmd.upper().startswith("RUN_APP"):
        return ("RUN_APP", "")
    m = re.match(r"(?i)^DONE\s*(.*)$", cmd, re.S)
    if m:
        return ("DONE", m.group(1).strip())
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = pathlib.Path(a.out) if a.out else \
        pathlib.Path(tempfile.mkdtemp(prefix="agentworld_"))
    out.mkdir(parents=True, exist_ok=True)
    cache = build_world(out)
    tools = Tools(cache)
    llm = Llama(model_path=a.gguf, n_ctx=2048, n_gpu_layers=0, verbose=False)
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": GOAL}]
    transcript = []
    done = None
    t0 = time.time()
    for _ in range(14):
        r = llm.create_chat_completion(messages=messages, max_tokens=140,
                                       temperature=0.3)
        text = r["choices"][0]["message"]["content"].strip()
        line = text.splitlines()[0] if text else ""
        parsed = parse(line)
        transcript.append({"step": len(transcript), "model": text[:200]})
        if parsed is None:
            obs = "ERR:unrecognized (%r). Use LIST / READ / WRITE / RUN_APP / DONE." % line[:80]
        else:
            try:
                kind = parsed[0]
                if kind == "LIST":
                    obs = tools.list()
                elif kind == "READ":
                    obs = tools.read(parsed[1])
                elif kind == "WRITE":
                    obs = tools.write(parsed[1], parsed[2])
                elif kind == "RUN_APP":
                    obs = tools.run_app()
                else:
                    done = parsed[1]
                    obs = "OK task finished"
            except Exception as e:
                obs = "ERR:" + str(e)
        transcript[-1]["obs"] = obs
        messages += [{"role": "assistant", "content": line},
                     {"role": "user",
                      "content": "Observation: " + obs +
                      "\nContinue with one command (or DONE summary)."}]
        if done is not None:
            break
    config = json.loads((cache / "config.json").read_text(encoding="utf-8"))
    res = {
        "steps": len(transcript),
        "final_version": config["version"],
        "app_runs": tools.app_runs,
        "done_summary": done,
        "ok": config["version"] == "2.0.0" and len(tools.app_runs) > 0
              and bool(done),
        "wall_s": round(time.time() - t0, 1),
        "transcript": transcript}
    (out / "agent_results.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "transcript"},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

