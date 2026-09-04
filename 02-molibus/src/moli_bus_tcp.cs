// MoliBus over TCP: central hub with per-client lines.
// Protocol lines (UTF-8): REGISTER|name|topic / SEND|req|target|b64 /
// PUBLISH|req|topic|b64 / CMD|req|from|b64 (bus->service) /
// RESP|req|b64 (service->bus) / REPLY|req|b64 (bus->ctl) /
// EVT|req|topic|b64 (bus->subscriber). Reliable layer: RESP carries
// ERR:RETRY_ME -> bus retransmits once; unreachable target -> deadletter.
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

class MoliBusTcp
{
    static readonly object Lock = new object();
    static Dictionary<string, StreamWriter> Worlds =
        new Dictionary<string, StreamWriter>();
    static Dictionary<string, string> NameCaps =
        new Dictionary<string, string>();
    static Dictionary<string, List<StreamWriter>> Subs =
        new Dictionary<string, List<StreamWriter>>();
    static Dictionary<string, StreamWriter> Pending =
        new Dictionary<string, StreamWriter>();
    static Dictionary<string, string> Orig =
        new Dictionary<string, string>();
    static string Dead = Path.Combine(Path.GetTempPath(),
        "moli_bus_dead");
    static string WalDir = Path.Combine(Path.GetTempPath(), "moli_bus_wal");
    static string WalPath = Path.Combine(WalDir, "wal.log");
    static Dictionary<string, List<string[]>> PendingWal =
        new Dictionary<string, List<string[]>>();  // target -> [[req,b64]]
    static List<StreamWriter> ReplicaOuts = new List<StreamWriter>();
    static string PeerAddr = "";
    static string WalPrefix = "WAL|";
    static List<string> Peers = new List<string>();
    static int MyPort = 47001;
    static int NodeN = 1;
    static volatile bool IsLeader = true;
    static HashSet<int> AlivePeers = new HashSet<int>();

    static void Log(string s) { Console.WriteLine("[tcp-bus] " + s); }

    static void AppendLocal(string line)
    {
        try
        {
            Directory.CreateDirectory(WalDir);
            File.AppendAllText(WalPath, line + "\n",
                new UTF8Encoding(false));
        }
        catch (Exception ex)
        {
            Log("wal err " + ex.Message);
        }
    }

    static void Wal(string line)
    {
        AppendLocal(line);
        lock (Lock)
        {
            foreach (var w in ReplicaOuts)
            {
                try
                {
                    w.WriteLine(WalPrefix + line);
                    w.Flush();
                }
                catch { }
            }
        }
    }

    static void PeerLoopOne(string addr)
    {
        while (true)
        {
            try
            {
                using (var c = new TcpClient())
                {
                    var ep = addr.Split(':');
                    c.Connect(IPAddress.Parse(ep[0]),
                        int.Parse(ep[1]));
                    using (var net = c.GetStream())
                    using (var w = new StreamWriter(net,
                        new UTF8Encoding(false), 4096, true)
                    { AutoFlush = true, NewLine = "\n" })
                    {
                        w.WriteLine("WALREPL|" + MyPort);
                        lock (Lock) ReplicaOuts.Add(w);
                        Log("wal peer connected " + addr);
                        using (var sr = new StreamReader(net, Encoding.UTF8,
                            false, 4096, true))
                            while (sr.ReadLine() != null) { }
                    }
                }
            }
            catch (Exception ex)
            {
                Log("wal peer err " + addr + " " + ex.Message);
            }
            System.Threading.Thread.Sleep(2000);
        }
    }

    static void LeaderLoop()
    {
        while (true)
        {
            bool lead;
            lock (Lock)
            {
                var alive = new List<int>();
                alive.Add(MyPort);
                foreach (var a in AlivePeers) alive.Add(a);
                alive.Sort();
                int majority = NodeN / 2 + 1;
                lead = alive.Count >= majority &&
                    (NodeN == 1 || alive[0] == MyPort);
            }
            if (lead != IsLeader)
                Log((lead ? "LEADER" : "FOLLOWER") +
                    " (alive=" + (AlivePeers.Count + 1) + ")");
            IsLeader = lead;
            System.Threading.Thread.Sleep(2000);
        }
    }

    static void ReplayWal()
    {
        if (!File.Exists(WalPath)) return;
        var pending = new Dictionary<string, string[]>();
        var done = new HashSet<string>();
        foreach (var raw in File.ReadAllLines(WalPath))
        {
            var p = raw.Split('|');
            if (p.Length >= 3 && p[0] == "W")
                pending[p[1]] = new[] { p[2], p[3] };
            else if (p.Length >= 2 && p[0] == "D")
                done.Add(p[1]);
        }
        int replayed = 0;
        lock (Lock)
        {
            foreach (var kv in pending)
            {
                if (done.Contains(kv.Key)) continue;
                string target = kv.Value[0];
                StreamWriter tw = null;
                Worlds.TryGetValue(target, out tw);
                if (tw != null)
                {
                    Send(tw, "CMD|" + kv.Key + "|wal-replay|" + kv.Value[1]);
                    replayed++;
                }
                else
                {
                    if (!PendingWal.ContainsKey(target))
                        PendingWal[target] = new List<string[]>();
                    PendingWal[target].Add(new[] { kv.Key, kv.Value[1] });
                }
            }
        }
        Log("wal replay: " + replayed + " delivered, " +
            (pending.Count - replayed) + " deferred");
    }

    static void Send(StreamWriter w, string line)
    {
        lock (Lock) { w.WriteLine(line); w.Flush(); }
    }

    static void Handle(string[] p, StreamWriter me, string myName)
    {
        string kind = p[0];
        if (kind == "REGISTER" && p.Length >= 3)
        {
            if (!IsLeader)
            {
                Log("reject register (not leader)");
                Send(me, "ERR|not-leader");
                return;
            }
            lock (Lock)
            {
                Worlds[p[1]] = me;
                if (p.Length >= 4 && p[3].Length > 0)
                    NameCaps[p[1]] = p[3];
                // deliver deferred WAL commands for this target
                if (PendingWal.ContainsKey(p[1]))
                {
                    foreach (var kv in PendingWal[p[1]])
                    {
                        Send(me, "CMD|" + kv[0] + "|wal-replay|" + kv[1]);
                        Log("wal deferred delivered " + kv[0]);
                    }
                    PendingWal.Remove(p[1]);
                }
                string topic = p.Length >= 3 ? p[2] : "";
                if (topic.Length > 0)
                {
                    if (!Subs.ContainsKey(topic))
                        Subs[topic] = new List<StreamWriter>();
                    Subs[topic].Add(me);
                }
            }
            Log("registered " + p[1] + " topic=" +
                (p.Length >= 3 ? p[2] : ""));
            return;
        }
        if (kind == "SEND" && p.Length >= 4)
        {
            string req = p[1], target = p[2], b64 = p[3];
            Log("SEND to " + target + " req " + req);
            StreamWriter tw;
            lock (Lock)
            {
                Pending[req] = me;
                Orig[req] = b64;
                Worlds.TryGetValue(target, out tw);
            }
            Wal("W|" + req + "|" + target + "|" + b64);
            if (tw == null)
            {
                Wal("D|" + req);
                Directory.CreateDirectory(Dead);
                File.AppendAllText(Path.Combine(Dead, "dead.log"),
                    DateTime.Now + " SEND " + req + " target " + target +
                    " unreachable\n", Encoding.UTF8);
                Send(me, "REPLY|" + req + "|" +
                    Convert.ToBase64String(Encoding.UTF8.GetBytes(
                        "ERR:target_unreachable")));
                return;
            }
            Send(tw, "CMD|" + req + "|" + myName + "|" + b64);
            return;
        }
        if (kind == "FIND" && p.Length >= 3)
        {
            string cap = p[2];
            var hit = new System.Text.StringBuilder();
            foreach (var kv in NameCaps)
                if (("," + kv.Value + ",").Contains("," + cap + ","))
                    hit.Append(kv.Key + ",");
            Send(me, "REPLY|" + p[1] + "|" +
                Convert.ToBase64String(Encoding.UTF8.GetBytes(
                    hit.Length > 0 ? hit.ToString().TrimEnd(',')
                    : "NONE")));
            Log("find cap " + cap + " -> " + hit);
            return;
        }
        if (kind == "PUBLISH" && p.Length >= 4)
        {
            List<StreamWriter> list;
            lock (Lock) Subs.TryGetValue(p[2], out list);
            if (list != null)
                foreach (var w in list)
                    Send(w, "EVT|" + p[1] + "|" + p[2] + "|" + p[3]);
            return;
        }
        if (kind == "RESP" && p.Length >= 3)
        {
            string resp = Encoding.UTF8.GetString(
                Convert.FromBase64String(p[2]));
            StreamWriter ctl;
            lock (Lock)
            {
                Pending.TryGetValue(p[1], out ctl);
                Pending.Remove(p[1]);
            }
            if (ctl == null)
            {
                Wal("D|" + p[1]);
                lock (Lock) { Orig.Remove(p[1]); }
                return;
            }
            if (resp.StartsWith("ERR:RETRY_ME"))
            {
                // retransmit once to the same target
                lock (Lock)
                {
                    Pending[p[1]] = ctl;
                    StreamWriter tw2 = null;
                    Worlds.TryGetValue(myName, out tw2);
                    string origB64 = "";
                    Orig.TryGetValue(p[1], out origB64);
                    if (tw2 != null)
                        Send(tw2, "CMD|" + p[1] + "|bus|" +
                            (origB64.Length > 0 ? origB64 : p[2]));
                    else
                        Send(ctl, "REPLY|" + p[1] + "|" + p[2]);
                    Orig.Remove(p[1]);
                }
                Log("retry " + p[1]);
                return;
            }
            lock (Lock) { Orig.Remove(p[1]); }
            Wal("D|" + p[1]);
            Send(ctl, "REPLY|" + p[1] + "|" + p[2]);
            return;
        }
    }

    static void Serve(TcpClient c)
    {
        string myName = "";
        try
        {
            using (c)
            using (var net = c.GetStream())
            using (var sr = new StreamReader(net, Encoding.UTF8, false,
                4096, true))
            using (var w = new StreamWriter(net, new UTF8Encoding(false),
                4096, true)
            { AutoFlush = true, NewLine = "\n" })
            {
                string line;
                line = sr.ReadLine();
                if (line != null && line.StartsWith("WALREPL"))
                {
                    int peerPort = 0;
                    var wp = line.Split('|');
                    if (wp.Length > 1) int.TryParse(wp[1], out peerPort);
                    if (peerPort > 0)
                        lock (Lock) AlivePeers.Add(peerPort);
                    Log("wal receiver from port " + peerPort);
                    try
                    {
                        while ((line = sr.ReadLine()) != null)
                        {
                            if (line.StartsWith(WalPrefix))
                                AppendLocal(line.Substring(WalPrefix.Length));
                        }
                    }
                    finally
                    {
                        if (peerPort > 0)
                            lock (Lock) AlivePeers.Remove(peerPort);
                    }
                    return;
                }
                while (line != null)
                {
                    var p = line.Split('|');
                    if (p.Length >= 1 && p[0] == "REGISTER" && p.Length >= 2)
                        myName = p[1];
                    try { Handle(p, w, myName); }
                    catch (Exception ex) { Log("err " + ex); }
                    line = sr.ReadLine();
                }
            }
        }
        catch (Exception ex)
        {
            Log("serve-fatal " + ex);
        }
        lock (Lock)
        {
            if (myName.Length > 0) Worlds.Remove(myName);
        }
    }

    static int Main()
    {
        int port = 47001;
        var margs = Environment.GetCommandLineArgs();
        if (margs.Length > 1)
            int.TryParse(margs[1], out port);
        MyPort = port;
        for (int i = 2; i < margs.Length; i++)
            Peers.Add(margs[i]);
        NodeN = 1 + Peers.Count;
        ReplayWal();
        foreach (var peer in Peers)
        {
            var t = new Thread(() => PeerLoopOne(peer));
            t.IsBackground = true;
            t.Start();
        }
        var lt = new Thread(LeaderLoop);
        lt.IsBackground = true;
        lt.Start();
        var listener = new TcpListener(IPAddress.Loopback, port);
        listener.Start();
        Log("MoliBus TCP bus " + port + " nodes=" + NodeN +
            (IsLeader ? " LEADER" : " follower"));
        while (true)
        {
            var c = listener.AcceptTcpClient();
            var t = new Thread(() => Serve(c));
            t.IsBackground = true;
            t.Start();
        }
    }
}

