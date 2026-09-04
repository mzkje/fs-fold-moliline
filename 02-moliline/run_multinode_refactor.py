# -*- coding: utf-8 -*-
"""Multi-node verification for the refactored MoliLine (moli_line_refactor).

Scenarios covered:
  S1  3-node quorum cluster: auto leader election -> kill leader -> failover;
      kill second node -> minority stops serving (split-brain protection).
  S2  two independent single-node buses: executor bus-address rotation.
  S3  2-node cluster (quorum = 2/2): after leader death the survivor refuses
      registration by design (strict majority; documented, not a bug).

Single-node baseline is covered separately by run_matrix_refactor.py.
"""
import json
import os
import socket
import subprocess
import tempfile
import time

ROOT = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
RUNS = os.path.join(ROOT, "results")
os.makedirs(RUNS, exist_ok=True)
PROCS = []


def exe(name):
    return os.path.join(BIN, name)


def start(args, logname):
    logf = open(os.path.join(RUNS, logname), "a", encoding="utf-8")
    p = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT, cwd=ROOT)
    PROCS.append(p)
    return p


def start_bus(port, workdir, peers=()):
    args = [exe("moli_line_refactor.exe"), "--port", str(port),
            "--workdir", workdir]
    for pp in peers:
        args += ["--peer", "127.0.0.1:%d" % pp]
    return start(args, "multinode_bus_%d.log" % port)


def start_svc(name, addrs):
    args = [exe("world_svc_tcp.exe"), name, "events"] + \
           ["127.0.0.1:%d" % a for a in addrs]
    return start(args, "multinode_svc_%s.log" % name)


def ctl(port, *args, timeout=10):
    r = subprocess.run([exe("world_ctl_tcp.exe"), str(port)] + list(args),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout or r.stderr).strip()


def probe(port, tag):
    """REGISTER probe: leader(accepted) / follower(ERR) / down / err."""
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=1.0)
    except Exception:
        return "down"
    try:
        s.settimeout(0.6)
        s.sendall(("REGISTER|probe_%s_%d|probe\n" % (tag, time.time())).encode("utf-8"))
        try:
            data = s.recv(256)
        except socket.timeout:
            return "leader"
        if not data:
            return "closed"
        return "follower" if b"ERR" in data else "leader"
    except Exception:
        return "err"
    finally:
        try:
            s.close()
        except Exception:
            pass


def wait_for(pred, timeout, step=0.5, desc=""):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = pred()
        if v:
            return v
        time.sleep(step)
    return None


def ping_ok(port, target):
    try:
        out = ctl(port, "SEND", target, "PING")
    except Exception:
        return False
    return "PONG" in out


def leader_state(ports):
    return {p: probe(p, "ls") for p in ports}


def wait_leader(ports, timeout=25):
    def cond():
        st = leader_state(ports)
        leaders = [p for p, v in st.items() if v == "leader"]
        down = [p for p, v in st.items() if v == "down"]
        if len(leaders) == 1 and not down:
            return st
        return None
    return wait_for(cond, timeout, desc="leader")


def kill(p):
    try:
        p.kill()
    except Exception:
        pass
    try:
        p.wait(timeout=3)
    except Exception:
        pass
    if p in PROCS:
        PROCS.remove(p)


def run_units():
    units = ["TestBusRegistry.exe", "TestWalStore.exe", "TestLeader.exe",
             "TestOptions.exe"]
    out = {}
    for u in units:
        r = subprocess.run([exe(u)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=15)
        out[u] = {"rc": r.returncode, "out": (r.stdout or r.stderr).strip()}
    return out


def scenario_s1(buses):
    """3-node quorum cluster: election, failover, minority stop."""
    ports = sorted(buses.keys())
    res = {"scenario": "S1_3node_quorum", "ports": ports}
    for p, b in buses.items():
        buses[p] = start_bus(
            p, os.path.join(tempfile.gettempdir(), "moli_multi_%d" % p),
            [q for q in ports if q != p])
    st = wait_leader(ports, timeout=25)
    res["initial_leader"] = [p for p, v in (st or {}).items() if v == "leader"]
    expected0 = min(ports)
    res["initial_ok"] = (st is not None and res["initial_leader"] == [expected0])
    svc = start_svc("exec_multi_s1", ports)
    res["ping_before"] = wait_for(lambda: ping_ok(expected0, "exec_multi_s1"), 15)
    # follower rejection
    follower = [p for p in ports if p != expected0][0]
    res["follower_rejects"] = probe(follower, "s1_follower") == "follower"
    # kill leader
    kill(buses[expected0])
    rest = [p for p in ports if p != expected0]
    st2 = wait_leader(rest, timeout=30)
    new_leader = [p for p, v in (st2 or {}).items() if v == "leader"]
    res["new_leader_after_kill"] = new_leader
    res["failover_ping"] = None
    if new_leader:
        res["failover_ping"] = wait_for(
            lambda: ping_ok(new_leader[0], "exec_multi_s1"), 35)
    # kill second -> minority stop (no split brain)
    if new_leader:
        kill(buses[new_leader[0]])
    time.sleep(9)
    last = [p for p in rest if p != (new_leader[0] if new_leader else None)]
    last_state = probe(last[0], "s1_last") if last else "n/a"
    res["survivor_refuses_after_second_kill"] = (last_state == "follower")
    res["survivor_state"] = last_state
    return res


def scenario_s2():
    """Two independent single-node buses: executor rotates bus address."""
    pa, pb = 47701, 47702
    res = {"scenario": "S2_double_bus_rotation", "ports": [pa, pb]}
    ba = start_bus(pa, os.path.join(tempfile.gettempdir(), "moli_double_%d" % pa))
    bb = start_bus(pb, os.path.join(tempfile.gettempdir(), "moli_double_%d" % pb))
    start_svc("exec_double_s2", [pa, pb])
    res["ping_bus1"] = wait_for(lambda: ping_ok(pa, "exec_double_s2"), 15)
    kill(ba)
    res["ping_bus2_after_kill"] = wait_for(
        lambda: ping_ok(pb, "exec_double_s2"), 20)
    kill(bb)
    return res


def scenario_s3():
    """2-node cluster: strict quorum 2/2 -> survivor must refuse (by design)."""
    pa, pb = 47801, 47802
    res = {"scenario": "S3_2node_quorum_design_limit", "ports": [pa, pb]}
    ba = start_bus(pa, os.path.join(tempfile.gettempdir(), "moli_q2_%d" % pa), [pb])
    bb = start_bus(pb, os.path.join(tempfile.gettempdir(), "moli_q2_%d" % pb), [pa])
    st = wait_leader([pa, pb], timeout=25)
    leader = [p for p, v in (st or {}).items() if v == "leader"]
    res["initial_leader"] = leader
    if leader == [pa]:
        start_svc("exec_q2_s3", [pa, pb])
        res["ping_before"] = wait_for(lambda: ping_ok(pa, "exec_q2_s3"), 15)
        kill(ba)
        time.sleep(9)
        state = probe(pb, "s3_survivor")
        res["survivor_state_after_leader_kill"] = state
        res["survivor_refuses_by_design"] = (state == "follower")
    kill(bb)
    return res


def main():
    result = {"units": run_units()}
    try:
        s1_buses = {47601: None, 47602: None, 47603: None}
        result["S1"] = scenario_s1(s1_buses)
        result["S2"] = scenario_s2()
        result["S3"] = scenario_s3()
        result["ok"] = bool(
            all(u.get("rc") == 0 for u in result["units"].values())
            and result["S1"].get("initial_ok")
            and result["S1"].get("ping_before")
            and result["S1"].get("new_leader_after_kill")
            and result["S1"].get("failover_ping")
            and result["S1"].get("survivor_refuses_after_second_kill")
            and result["S2"].get("ping_bus1")
            and result["S2"].get("ping_bus2_after_kill")
            and result["S3"].get("initial_leader") == [47801]
            and result["S3"].get("survivor_refuses_by_design"))
    finally:
        for p in list(PROCS):
            kill(p)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    with open(os.path.join(RUNS, "moliline_multinode.json"), "w",
              encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())


