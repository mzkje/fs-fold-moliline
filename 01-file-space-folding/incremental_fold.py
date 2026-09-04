# -*- coding: utf-8 -*-
"""Incremental fold for .fs containers.

Reuses unchanged pool blobs from an existing .fs and only hashes/compresses
added or changed files.  A no-change rebuild reproduces the full fold output
byte-for-byte (same manifest schema and zlib level as foldcore.fold_tree).

Usage:
  python incremental_fold.py SRC EXISTING.fs [OUT.fs] [--dry-run]
"""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sys
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import foldcore


def _walk(src):
    out = []
    for root, dirs, files in os.walk(src):
        dirs.sort()
        for name in sorted(files):
            p = os.path.join(root, name)
            out.append((os.path.relpath(p, src).replace("\\", "/"), p))
    return out


def _digest(p):
    return foldcore.sha256_file(p)


def _zlib_stream(p):
    co = zlib.compressobj(foldcore.LEVEL)
    out = bytearray()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            out += co.compress(chunk)
    out += co.flush()
    return bytes(out)


def read_fs(fs_path):
    with open(fs_path, "rb") as f:
        assert f.read(8) == foldcore.MAGIC, "not a .fs file"
        jlen = int.from_bytes(f.read(8), "little")
        m = json.loads(f.read(jlen))
        m["_pool_offset"] = 16 + jlen
    return m


def incremental_fold(src, fs_path, out_path=None, dry_run=False):
    src = str(src)
    m = read_fs(fs_path)
    old_by_rel = {e["rel"]: e for e in m["entries"]}
    old_hashes = {e["hash"] for e in m["entries"]}
    files = _walk(src)
    new_entries = []
    by_rel = {}
    for rel, p in files:
        size = os.path.getsize(p)
        h = _digest(p)
        new_entries.append({"rel": rel, "size": size, "hash": h})
        by_rel[rel] = (h, p)
    kept = changed = added = 0
    new_hashes = set()
    for e in new_entries:
        new_hashes.add(e["hash"])
        old = old_by_rel.get(e["rel"])
        if old and old["hash"] == e["hash"]:
            kept += 1
        elif old:
            changed += 1
        else:
            added += 1
    removed = len(old_by_rel) - kept - changed
    new_hashes = sorted(new_hashes)
    reused = sum(1 for h in new_hashes if h in old_hashes)
    stats = {"kept": kept, "changed": changed, "added": added,
             "removed": removed, "unique": len(new_hashes),
             "reused_pool": reused}
    if dry_run:
        return stats
    out_path = pathlib.Path(out_path or fs_path)
    # load old pool once
    with open(fs_path, "rb") as f:
        f.seek(m["_pool_offset"])
        old_pool = {}
        for h, sz in zip(m["pool_hashes"], m["pool_sizes"]):
            old_pool[h] = f.read(sz)
    new_pool = {}
    for h in new_hashes:
        blob = old_pool.get(h)
        if blob is None:
            p = next(p for (rel, p) in files if by_rel[rel][0] == h)
            blob = _zlib_stream(p)
        new_pool[h] = blob
    orig = sum(e["size"] for e in new_entries)
    manifest = {"tech": "fs-folder-fold v1 (content-hash dedupe + zlib)",
                "n_files": len(new_entries), "entries": new_entries,
                "pool_hashes": new_hashes,
                "pool_sizes": [len(new_pool[h]) for h in new_hashes]}
    j = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
    tmp = str(out_path) + ".tmp"
    with open(tmp, "wb") as f:
        f.write(foldcore.MAGIC)
        f.write(len(j).to_bytes(8, "little"))
        f.write(j)
        for h in new_hashes:
            f.write(new_pool[h])
    shutil.move(tmp, str(out_path))
    fs_size = os.path.getsize(out_path)
    stats["fs_bytes"] = fs_size
    stats["original_bytes"] = orig
    stats["saved_percent"] = round(100 * (1 - fs_size / orig), 2) if orig else 0
    stats["out"] = str(out_path)
    return stats


def main():
    ap = argparse.ArgumentParser(description="Incremental .fs rebuild")
    ap.add_argument("src")
    ap.add_argument("fs")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    print(incremental_fold(a.src, a.fs, a.out, a.dry_run))


if __name__ == "__main__":
    main()


