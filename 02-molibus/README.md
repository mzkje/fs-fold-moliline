# 02 · MoliBus (message bus)

Lightweight TCP message bus between programs, zero third-party dependencies.
Builds with the C# compiler included in Windows .NET Framework.

## Features

- request/response, publish/event, command execution
- WAL: commands are written to disk before routing; restart replays
- exactly-once: executor dedupes by request id (persisted)
- dead letters, retry-once, automatic reconnect, bus-address rotation
- multi-node leader election (lowest port among a live quorum)

## Quick start

```bash
powershell -File build.ps1
python examples/hello.py
python run_matrix_refactor.py        # single-node baseline
python run_multinode_refactor.py     # multi-node matrix (results in results/)
```

Manual:

```text
bin\moli_bus_refactor.exe --port 47001 --workdir <dir>
bin\world_svc_tcp.exe     executor events 127.0.0.1:47001
bin\world_ctl_tcp.exe     47001 SEND executor PING
```

Multi-node (3 nodes): pass the other nodes as `--peer`.

## Parameters

- bus: `--port`, `--workdir`, `--peer ip:port ...`
- service: `<name> <topic> [busAddr ...]`; dedupe table dir overridable with
  env `MOLI_DONE_DIR`

## Wire protocol

See docs/WIRE.md.

## Honest limits

- No authentication or encryption; loopback / intranet only.
- 2-node clusters have no failover (quorum 2/2 is split-brain protection).
- Throughput curves from older experiments are not re-bundled; run the
  included matrices for current numbers.
