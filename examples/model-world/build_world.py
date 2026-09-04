# -*- coding: utf-8 -*-
"""Build a model world .fs from a GGUF file.

Usage:
  python build_world.py --name A --gguf <model.gguf> --out <dir>
                        [--state "world A initial state"]

Creates <out>/<name>_world.fs containing model.gguf, entry.py and state.txt,
and merges a worlds.json used by worldgate.py. The source tree is deleted
after folding: the world now lives as one .fs file.
"""
import argparse
import json
import pathlib
import shutil
import sys

PKG = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PKG / "01-file-space-folding"))
import foldcore  # noqa: E402


def build(name, gguf, out_dir, state):
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    src = out / ("src_" + name)
    if src.exists():
        shutil.rmtree(str(src))
    src.mkdir()
    shutil.copy2(gguf, src / "model.gguf")
    shutil.copy2(pathlib.Path(__file__).parent / "entry.py", src / "entry.py")
    (src / "state.txt").write_text(state, encoding="utf-8")
    fs = out / ("%s_world.fs" % name)
    r = foldcore.fold_tree(str(src), str(fs))
    shutil.rmtree(str(src))
    worlds_path = out / "worlds.json"
    worlds = json.loads(worlds_path.read_text(encoding="utf-8")) \
        if worlds_path.exists() else {}
    worlds[name] = {"fs": str(fs), "cache": str(out / ("cache_" + name))}
    worlds_path.write_text(json.dumps(worlds, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    return {"name": name, "fs": str(fs),
            "fs_bytes": r["fs_bytes"],
            "saved_pct": r["saved_percent"],
            "files": r["files"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--state", default="world initial state; not visited")
    a = ap.parse_args()
    print(json.dumps(build(a.name, a.gguf, a.out, a.state),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()


