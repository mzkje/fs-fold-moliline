# -*- coding: utf-8 -*-
"""CLI: python cli.py fold SRC [OUT.fs] | unfold FS [OUT] | bench SRC"""
import argparse, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import foldcore

def main():
    ap = argparse.ArgumentParser(description="File-space folding (.fs) tool")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("fold"); p1.add_argument("src"); p1.add_argument("out", nargs="?")
    p2 = sub.add_parser("unfold"); p2.add_argument("fs"); p2.add_argument("out", nargs="?")
    p3 = sub.add_parser("bench"); p3.add_argument("src")
    p4 = sub.add_parser("verify"); p4.add_argument("fs")
    a = ap.parse_args()
    if a.cmd == "fold":
        out = a.out or (pathlib.Path(a.src).name + ".fs")
        print(foldcore.fold_tree(a.src, out))
    elif a.cmd == "unfold":
        out = a.out or (pathlib.Path(a.fs).stem + "_restore")
        print(foldcore.restore_tree(a.fs, out))
    elif a.cmd == "bench":
        import benchmark
        print(benchmark.run(a.src))
    elif a.cmd == "verify":
        print(foldcore.verify_fs(a.fs))

if __name__ == "__main__":
    main()
