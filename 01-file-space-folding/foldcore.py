# -*- coding: utf-8 -*-
"""foldcore.py - lossless full-tree folder folding container (.fs)."""
import hashlib, json, os, pathlib, zlib

MAGIC = b"FSF781\x00\x01"
LEVEL = 6

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _digest(p):
    """Streaming sha256 hexdigest of a file (no full read)."""
    return sha256_file(p)


def _zlib_stream(p):
    """zlib-compress a file streaming; equals zlib.compress(raw, LEVEL)."""
    co = zlib.compressobj(LEVEL)
    out = bytearray()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            out += co.compress(chunk)
    out += co.flush()
    return bytes(out)


def _walk(src):
    out = []
    for root, dirs, files in os.walk(src):
        dirs.sort()
        for name in sorted(files):
            p = os.path.join(root, name)
            out.append((os.path.relpath(p, src).replace("\\", "/"), p))
    return out

def fold_tree(src, out_fs):
    src = pathlib.Path(src)
    files = _walk(src)
    entries, pool = [], {}
    orig = 0
    for rel, p in files:
        size = os.path.getsize(p)
        orig += size
        h = _digest(p)
        if h not in pool:              # first occurrence only: compress once
            pool[h] = _zlib_stream(p)
        entries.append({"rel": rel, "size": size, "hash": h})
    pool_hashes = sorted(pool.keys())
    manifest = {"tech": "fs-folder-fold v1 (content-hash dedupe + zlib)",
                "n_files": len(entries), "entries": entries,
                "pool_hashes": pool_hashes,
                "pool_sizes": [len(pool[h]) for h in pool_hashes]}
    j = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
    with open(out_fs, "wb") as f:
        f.write(MAGIC)
        f.write(len(j).to_bytes(8, "little"))
        f.write(j)
        for h in pool_hashes:
            f.write(pool[h])
    size = os.path.getsize(out_fs)
    return {"files": len(entries), "original_bytes": orig, "fs_bytes": size,
            "unique_files": len(pool),
            "saved_percent": round(100 * (1 - size / orig), 2) if orig else 0}

def restore_tree(fs_path, out_dir, max_total=None):
    with open(fs_path, "rb") as f:
        assert f.read(8) == MAGIC, "not a .fs file"
        jlen = int.from_bytes(f.read(8), "little")
        m = json.loads(f.read(jlen))
        blobs = {}
        for h, sz in zip(m["pool_hashes"], m["pool_sizes"]):
            blobs[h] = f.read(sz)
    out_root = pathlib.Path(out_dir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    total = 0
    bad = []
    for e in m["entries"]:
        raw = zlib.decompress(blobs[e["hash"]])
        total += len(raw)
        if max_total is not None and total > max_total:
            raise ValueError("restore exceeds max_total=%d bytes" % max_total)
        out = (out_root / e["rel"]).resolve()
        if not str(out).startswith(str(out_root) + os.sep) and out != out_root:
            bad.append(e["rel"] + " (traversal)")
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(raw)
        if len(raw) != e["size"] or sha256_file(out) != e["hash"]:
            bad.append(e["rel"])
    return {"restored": len(m["entries"]), "lossless": not bad, "bad": bad[:5]}

def verify_fs(fs_path):
    """In-memory lossless check: decompress pool, compare size+sha256 (no disk write)."""
    with open(fs_path, "rb") as f:
        assert f.read(8) == MAGIC, "not a .fs file"
        jlen = int.from_bytes(f.read(8), "little")
        m = json.loads(f.read(jlen))
        blobs = {}
        for h, sz in zip(m["pool_hashes"], m["pool_sizes"]):
            blobs[h] = f.read(sz)
    bad = []
    for e in m["entries"]:
        raw = zlib.decompress(blobs[e["hash"]])
        if len(raw) != e["size"] or hashlib.sha256(raw).hexdigest() != e["hash"]:
            bad.append(e["rel"])
    return {"files": len(m["entries"]), "lossless": not bad, "bad": bad[:5]}
