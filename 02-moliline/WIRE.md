# MoliLine Wire Protocol (TCP line protocol)

> UTF-8, newline `\n`, fields separated by `|`; payloads are base64 so the
> separator never collides. Line length guard 1 MiB; payload guard 256 KiB
> (see `MoliWire.cs`).

## Message types

| Direction | Line | Meaning |
|---|---|---|
| svc → bus | `REGISTER\|name\|topic` | register a world/executor (leader only; follower replies `ERR\|not-leader`) |
| ctl → bus | `SEND\|req\|target\|b64` | request/response command to a registered world |
| bus → svc | `CMD\|req\|bus\|b64` | deliver a command; executor answers with RESP |
| svc → bus | `RESP\|req\|b64` | command result (executor dedupes by req → exactly-once) |
| bus → ctl | `REPLY\|req\|b64` | final response to the ctl |
| ctl → bus | `PUBLISH\|req\|topic\|b64` | event publish; bus fans out to topic subscribers |
| bus → svc | `EVT\|req\|topic\|b64` | event delivery |
| node → node | `HELLO\|port` | heartbeat handshake (peer liveness) |
| svc → bus | (any `ERR` reply) | e.g. `ERR\|not-leader` — client should rotate bus addresses |

## Reliability semantics

1. **WAL first**: on `SEND`, the bus appends `W|req|target|b64` to disk before
   routing; on `RESP`/unreachable it appends `D|req` (done). On restart the bus
   replays pending W-entries into deferred delivery.
2. **Dead letter**: if a target is unreachable the request is answered
   `ERR:target_unreachable` and logged under the bus workdir `dead/`.
3. **Exactly-once**: the executor persists `req -> resp`; re-delivery returns
   the cached response, so the same req never executes twice.
4. **Retry**: an executor can answer `ERR:RETRY_ME`; the bus retransmits once.
5. **Liveness / quorum**: heartbeat misses ≥3 rounds remove the peer; with
   `N` nodes a leader needs `N/2+1` alive members and is the lowest port among
   them. `N=1` always serves; `N=2` refuses service after one node dies
   (design limit); `N≥3` fails over.

## Bus state

- Registry: name → topic / capability / connection (thread-safe).
- WAL store: append-only `W`/`D` lines under `--workdir/wal/wal.log`.
- Dead letters: `--workdir/dead/dead.log`.

## Notes

- No authentication or encryption in this version. Bind to loopback only.
- The optional `FSSIGSIG` footer is a container signature used by `.fs`
  carrier tooling, unrelated to this wire protocol.

