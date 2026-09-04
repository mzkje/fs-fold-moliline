# -*- coding: utf-8 -*-
"""Cross-carrier integration check for .fs.

Builds a synthetic duplicate-heavy tree, folds it with the Python
reference implementation, then verifies the same .fs with the C#/.NET
carrier (fs_tool check) and with the Python verify/restore paths.
This proves the container is carrier-independent: same bytes, two runtimes.

Usage:
  python tools/cross_carrier_check.py [--fs-tool PATH]
"""
import argparse
import json
import os
import pathlib
import random
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import foldcore


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fs-tool", default="")
    a = ap.parse_args()
    fs_tool = a.fs_tool or str(
        pathlib.Path(__file__).resolve().parents[2] /
        "02-molibus" / "bin" / "fs_tool.exe")
    if not os.path.exists(fs_tool):
        raise SystemExit("fs_tool not found: %s" % fs_tool)
    rng = random.Random(7)
    tmp = tempfile.mkdtemp(prefix="fs_cross_")
    src = os.path.join(tmp, "src")
    os.makedirs(src)
    blobs = {}
    for i in range(8):
        if i % 3 == 0:
            data = bytes(rng.randrange(256) for _ in range(200000))
        else:
            data = ("line %d " % i * 150000).encode()
        blobs["f%d" % i] = data
    for i in range(24):
        rel = "dir%d/f%02d.bin" % (i % 3, i)
        p = os.path.join(src, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(blobs["f%d" % (i % 8)] + b"tail%d" % i)
    fs = os.path.join(tmp, "demo.fs")
    out = os.path.join(tmp, "restore")
    res = dict(foldcore.fold_tree(src, fs))
    res["verify_py"] = foldcore.verify_fs(fs)
    res["restore_lossless"] = foldcore.restore_tree(fs, out)["lossless"]
    r = subprocess.run([fs_tool, "check", fs], capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=180)
    res["fs_tool_rc"] = r.returncode
    res["fs_tool_out"] = (r.stdout or r.stderr).strip()
    res["ok"] = bool(res["verify_py"]["lossless"]
                     and res["restore_lossless"] and r.returncode == 0)
    shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
