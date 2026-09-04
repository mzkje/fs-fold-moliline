# 01 · FS Fold (.fs container)

Fold a folder tree into one lossless `.fs` file. Content-hash deduplication
stores identical files once; zlib compresses the pool. Restore is verified
per file with sha256.

## Why this exists

Deduplication containers are useful for trees with repeated content: two
versions of an app, backup folders, duplicated resources. On such trees `.fs`
is smaller than zip; on compression-only workloads zip can be smaller.

## Commands

```bash
python cli.py fold    <source-dir> <out.fs>
python cli.py unfold  <out.fs> <target-dir>
python cli.py verify  <out.fs>          # lossless sha256 check
python cli.py bench   <source-dir>      # compare with zip
python incremental_fold.py <source-dir> <old.fs> [new.fs]
python test_fold.py                     # unit tests
python tools/cross_carrier_check.py     # Python fold -> C# carrier verify
```

## Format

`FSF781\x00\x01` + manifest length + UTF-8 JSON manifest + zlib pool.
Details in FORMAT.md.

## Limits

- Whole-tree container, no streaming random access.
- zlib backend only; no filesystem-transparent layer.
- Python reference implementation is cross-platform; the C# carrier is
  Windows/.NET (compiles with the built-in .NET Framework compiler).
