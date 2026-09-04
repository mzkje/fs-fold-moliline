# -*- coding: utf-8 -*-
"""benchmark.py - .fs vs zip(deflate) on a folder."""
import io, os, pathlib, zipfile
import foldcore

def _dir_size(src):
    return sum(os.path.getsize(os.path.join(r, f))
               for r, _, fs in os.walk(src) for f in fs)

def run(src):
    src = pathlib.Path(src)
    out_fs = str(pathlib.Path(src).parent / (src.name + "_bench.fs"))
    rep = foldcore.fold_tree(src, out_fs)
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for r, _, fs in os.walk(src):
            for f in fs:
                p = os.path.join(r, f)
                z.write(p, os.path.relpath(p, src))
    zsize = zip_buf.tell()
    orig = rep["original_bytes"]
    return {"original_bytes": orig,
            "fs_bytes": rep["fs_bytes"],
            "zip_bytes": zsize,
            "fs_saved_percent": rep["saved_percent"],
            "zip_saved_percent": round(100 * (1 - zsize / orig), 2),
            "fs_vs_zip_smaller_percent": round(100 * (1 - rep["fs_bytes"] / zsize), 2)}

