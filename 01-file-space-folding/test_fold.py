# -*- coding: utf-8 -*-
"""Tests: python test_fold.py"""
import io, os, sys, tempfile, pathlib, random
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import foldcore
import incremental_fold

def build(files):
    d = tempfile.mkdtemp(prefix="fs_src_")
    for rel, data in files.items():
        p = os.path.join(d, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
    return d

def rmtree(p):
    import shutil; shutil.rmtree(p, ignore_errors=True)

def test_basic():
    src = build({"a.txt": b"hello world", "sub/b.txt": b"hello world", "empty.dat": b"",
                 "uni-中文.txt": ("测试内容" * 100).encode("utf-8")})
    fs = tempfile.mktemp(suffix=".fs"); out = tempfile.mkdtemp(prefix="fs_out_")
    foldcore.fold_tree(src, fs)
    r = foldcore.restore_tree(fs, out)
    assert r["lossless"], r
    for rel, data in [("a.txt", b"hello world"), ("empty.dat", b""),
                      ("uni-中文.txt", ("测试内容" * 100).encode("utf-8"))]:
        assert open(os.path.join(out, rel), "rb").read() == data
    rmtree(src); rmtree(out); os.remove(fs)
    print("basic ok")

def test_random_binary():
    rng = random.Random(1)
    src = build({"r.bin": bytes(rng.randrange(256) for _ in range(500000))})
    fs = tempfile.mktemp(suffix=".fs"); out = tempfile.mkdtemp(prefix="fs_out_")
    foldcore.fold_tree(src, fs)
    assert foldcore.restore_tree(fs, out)["lossless"]
    rmtree(src); rmtree(out); os.remove(fs)
    print("random ok")

def test_traversal_guard():
    # craft manifest with ../ escape
    src = tempfile.mkdtemp(prefix="fs_src_")
    (pathlib.Path(src) / "x.txt").write_bytes(b"abc")
    fs = tempfile.mktemp(suffix=".fs"); out = tempfile.mkdtemp(prefix="fs_out_")
    foldcore.fold_tree(src, fs)
    raw = open(fs, "rb").read()
    # patch manifest rel
    jlen = int.from_bytes(raw[8:16], "little")
    man = raw[16:16 + jlen]
    import json
    m = json.loads(man)
    m["entries"][0]["rel"] = "../evil.txt"
    man2 = json.dumps(m, ensure_ascii=False).encode("utf-8")
    open(fs, "wb").write(raw[:8] + len(man2).to_bytes(8, "little") + man2 + raw[16 + jlen:])
    r = foldcore.restore_tree(fs, out)
    assert not os.path.exists(os.path.join(out, "..", "evil.txt"))
    assert not r["lossless"]
    rmtree(src); rmtree(out); os.remove(fs)
    print("traversal ok")


def test_incremental_rebuild():
    src = build({"a.txt": b"alpha content", "sub/b.txt": b"beta content",
                 "c.bin": bytes(random.Random(2).randrange(256)
                                for _ in range(100000))})
    fs1 = tempfile.mktemp(suffix=".fs")
    foldcore.fold_tree(src, fs1)
    # no-change rebuild must be byte-identical to full fold
    fs1b = tempfile.mktemp(suffix=".fs")
    st = incremental_fold.incremental_fold(src, fs1, fs1b)
    assert st["kept"] == 3 and st["changed"] == 0 and st["added"] == 0 \
        and st["removed"] == 0, st
    assert open(fs1, "rb").read() == open(fs1b, "rb").read()
    os.remove(fs1b)
    # mutate one file + add one
    with open(os.path.join(src, "sub", "b.txt"), "wb") as f:
        f.write(b"beta content v2 (longer)")
    with open(os.path.join(src, "new.txt"), "wb") as f:
        f.write(b"hello " * 5000)
    fs2 = tempfile.mktemp(suffix=".fs")
    st2 = incremental_fold.incremental_fold(src, fs1, fs2)
    assert st2["kept"] == 2 and st2["changed"] == 1 and st2["added"] == 1 \
        and st2["removed"] == 0, st2
    assert st2["reused_pool"] >= 2, st2   # a.txt + c.bin blobs reused
    out2 = tempfile.mkdtemp(prefix="fs_out2_")
    r = foldcore.restore_tree(fs2, out2)
    assert r["lossless"], r
    assert open(os.path.join(out2, "sub", "b.txt"), "rb").read() == \
        b"beta content v2 (longer)"
    rmtree(src); rmtree(out2); os.remove(fs1); os.remove(fs2)
    print("incremental ok")


test_basic(); test_random_binary(); test_traversal_guard()
test_incremental_rebuild()
print("ALL_TESTS_PASS")


