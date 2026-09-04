# FS Fold (.fs) & MoliBus

Two small, zero-extra-dependency local tools for Windows:

1. **FS Fold** (`01-file-space-folding/`) — fold a folder tree into a single lossless `.fs` container (content-hash deduplication + zlib, incremental rebuild, no-Python C# carrier).
2. **MoliBus** (`02-molibus/`) — a lightweight TCP message bus between programs: requests/responses, events, WAL, exactly-once dedupe, dead letters, automatic reconnect and multi-node leader election.

Status: research-grade, reproducible. MIT licensed (author: mzkje).

## Layout

```text
01-file-space-folding/   .fs container: fold / unfold / verify / incremental
02-molibus/              message bus: bus / service / control + tests
carriers/fs_tool/        C#/.NET carrier that reads .fs without Python
examples/model-world/    optional demo: GGUF folded into a world, booted through MoliBus (needs llama-cpp-python)
```

## Quick start (Windows)

```bash
cd 01-file-space-folding
python cli.py fold   <source-dir> <out.fs>
python cli.py unfold <out.fs> <target-dir>
python cli.py verify <out.fs>
python test_fold.py

cd ../02-molibus
powershell -File build.ps1            # C# compiler inside .NET Framework
python run_matrix_refactor.py         # single-node baseline
python run_multinode_refactor.py      # multi-node matrix
python examples/hello.py
```

## Measured results (author's Windows machine; third-party reproduction welcome)

### FS Fold

| Case | Result | Note |
|---|---|---|
| 65 files, 60 identical (19.8 MB) | .fs 10,095 B (~83% smaller than zip) | content-dedupe is the strength |
| 40 different compressible texts | zip smaller than .fs | honestly documented limit |
| Real app folder (author test) | 732 MB -> 196 MB, lossless sha256 | author-measured, not bundled |

`.fs` is a deduplication container, not a "better deflate": on compression-only workloads zip can win.

### MoliBus

- Single node: PING in milliseconds; crash -> dead letter -> restart recovery; exactly-once dedupe.
- 3-node cluster: auto leader election; leader killed -> failover ~6 s; executor migrates and PING recovers; second node killed -> service stops (split-brain protection).
- 2-node cluster: strict quorum (2/2); survivor refuses service after one node dies — documented design limit.

## Safety notes

- MoliBus has **no authentication or encryption**; bind to loopback only.
- The bus can make program A control program B. Controlled/auditable use only; add sandboxing before production use.
- Fold only directories you have the right to process or redistribute. Real app `.fs` artifacts from author tests are intentionally not included.

## Requirements

- Windows (bus binaries build with the C# compiler included in .NET Framework; no downloads).
- Python 3.8+ (standard library only) for the reference implementations.
- Optional: `llama-cpp-python` for `examples/model-world`.

## License

MIT — see [LICENSE](LICENSE).
