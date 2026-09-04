# FS Fold (.fs) & MoliBus

Two small Windows tools, no extra libraries needed.

## FS Fold (`01-file-space-folding/`)

Packs a whole folder into one `.fs` file, and restores it later exactly
(sha256 checked). If the folder contains the same file many times, it is
stored once. A no-Python C# tool (`carriers/fs_tool`) can check or run folded
folders.

Commands:

```bash
python cli.py fold    <source-folder> <out.fs>
python cli.py unfold  <out.fs> <target-folder>
python cli.py verify  <out.fs>
python incremental_fold.py <source-folder> <old.fs> [new.fs]
```

Note: this is a deduplication container, not a general compressor. On data
with little duplication, ordinary zip may be smaller.

## MoliBus (`02-molibus/`)

Lets programs on the same computer exchange messages: one program asks,
another answers; events can be broadcast. It keeps a journal, avoids running
the same request twice, retries/reconnects, and can coordinate several bus
instances (one acts as leader).

```bash
powershell -File build.ps1
python examples/hello.py
python run_matrix_refactor.py
```

## Notes

- MoliBus has no login or encryption; use it on your own computer only.
- Fold only folders you are allowed to copy or share.
- License: MIT License (see LICENSE).
