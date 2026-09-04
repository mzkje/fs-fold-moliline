// MoliLineRefactor.cs - v1.0 bus using MoliWire/BusRegistry/WalStore/LeaderElection/MoliOptions
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using MoliLine;

class MoliLineRefactor
{
    static readonly object Lock = new object();
    static readonly Dictionary<string, StreamWriter> Writers = new Dictionary<string, StreamWriter>();
    static readonly Dictionary<string, StreamWriter> Pending = new Dictionary<string, StreamWriter>();
    static readonly Dictionary<string, string> Orig = new Dictionary<string, string>();
    static readonly Dictionary<string, List<string[]>> Deferred = new Dictionary<string, List<string[]>>();
    static BusRegistry Registry = new BusRegistry();
    static WalStore Wal;
    static LeaderElection Leader;
    static MoliOptions Opt;
    static string Dead;
    static readonly List<string> Peers = new List<string>();
    static int NodeN = 1;

    static void Log(string s) { Console.WriteLine("[bus-refactor] " + s); }

    static void HeartbeatLoop(string addr)
    {
        int peerPort = 0;
        var ep = addr.Split(':');
        int.TryParse(ep[1], out peerPort);
        int misses = 0;
        while (true)
        {
            bool ok = false;
            try
            {
                using (var c = new TcpClient())
                {
                    c.Connect(IPAddress.Parse(ep[0]), peerPort);
                    using (var net = c.GetStream())
                    using (var w = new StreamWriter(net, new UTF8Encoding(false), 4096, true)
                    { AutoFlush = true, NewLine = "\n" })
                    using (var sr = new StreamReader(net, Encoding.UTF8, false, 4096, true))
                    {
                        w.WriteLine("HELLO|" + Opt.Port);
                        string line = sr.ReadLine();
                        if (line != null)
                        {
                            var pp = line.Split('|');
                            if (pp.Length >= 2)
                            {
                                int gotPort;
                                if (int.TryParse(pp[1], out gotPort))
                                {
                                    Leader.AddPeer(gotPort);
                                    ok = true;
                                }
                            }
                        }
                    }
                }
            }
            catch { }
            if (ok) misses = 0;
            else if (++misses >= 3) Leader.RemovePeer(peerPort);
            Thread.Sleep(Opt.LeaderIntervalMs);
        }
    }

    static void Send(StreamWriter w, string line)
    {
        lock (Lock) { w.WriteLine(line); w.Flush(); }
    }

    static void ReplyUnreachable(string req, StreamWriter ctl, string target)
    {
        Wal.AppendD(req);
        Directory.CreateDirectory(Dead);
        File.AppendAllText(Path.Combine(Dead, "dead.log"),
            DateTime.Now + " SEND " + req + " target " + target + " unreachable\n",
            new UTF8Encoding(false));
        Send(ctl, "REPLY|" + req + "|" + MoliWire.EncodeB64("ERR:target_unreachable"));
    }

    static void Handle(string[] p, StreamWriter me, string myName)
    {
        if (p.Length < 1) return;
        if (p[0] == "REGISTER" && p.Length >= 3)
        {
            if (!Leader.IsLeader())
            {
                Send(me, "ERR|not-leader");
                return;
            }
            string name = p[1], topic = p[2];
            string cap = p.Length > 3 ? p[3] : "";
            lock (Lock)
            {
                Registry.Register(name, topic, cap);
                Writers[name] = me;
                List<string[]> def;
                if (Deferred.TryGetValue(name, out def))
                {
                    foreach (var kv in def)
                        Send(me, "CMD|" + kv[0] + "|bus|" + kv[1]);
                    Deferred.Remove(name);
                }
            }
            Log("registered " + name);
            return;
        }
        if (p[0] == "SEND" && p.Length >= 4)
        {
            string req = p[1], target = p[2], b64 = p[3];
            StreamWriter tw;
            lock (Lock)
            {
                Pending[req] = me;
                Orig[req] = b64;
                Writers.TryGetValue(target, out tw);
            }
            Wal.AppendW(req, target, b64);
            if (tw == null) { ReplyUnreachable(req, me, target); return; }
            Send(tw, "CMD|" + req + "|bus|" + b64);
            return;
        }
        if (p[0] == "RESP" && p.Length >= 3)
        {
            string req = p[1];
            Wal.AppendD(req);
            StreamWriter ctl;
            lock (Lock)
            {
                Pending.TryGetValue(req, out ctl);
                Pending.Remove(req);
                Orig.Remove(req);
            }
            if (ctl != null) Send(ctl, "REPLY|" + req + "|" + p[2]);
            return;
        }
        if (p[0] == "PUBLISH" && p.Length >= 4)
        {
            string topic = p[2], b64 = p[3];
            lock (Lock)
            {
                foreach (var name in Registry.Subscribers(topic))
                {
                    StreamWriter w;
                    if (Writers.TryGetValue(name, out w))
                        Send(w, "EVT|" + p[1] + "|" + topic + "|" + b64);
                }
            }
        }
    }

    static void Serve(TcpClient c)
    {
        string myName = "";
        try
        {
            using (c)
            using (var net = c.GetStream())
            using (var sr = new StreamReader(net, Encoding.UTF8, false, 4096, true))
            using (var w = new StreamWriter(net, new UTF8Encoding(false), 4096, true)
            { AutoFlush = true, NewLine = "\n" })
            {
                string line;
                line = sr.ReadLine();
                if (line != null)
                {
                    var hp = MoliWire.Parse(line);
                    if (hp.Length >= 1 && hp[0] == "HELLO")
                    {
                        int hpPort;
                        if (hp.Length >= 2 && int.TryParse(hp[1], out hpPort))
                        {
                            Send(w, "HELLO|" + Opt.Port);
                        }
                        // keep peer liveness handled on client side; close
                        return;
                    }
                }
                while (line != null)
                {
                    try
                    {
                        var p = MoliWire.Parse(line);
                        if (p.Length >= 1 && p[0] == "REGISTER" && p.Length >= 2) myName = p[1];
                        Handle(p, w, myName);
                    }
                    catch (Exception ex) { Log("err " + ex.Message); }
                    line = sr.ReadLine();
                }
            }
        }
        catch (Exception ex) { Log("serve-fatal " + ex.Message); }
        lock (Lock)
        {
            if (myName.Length > 0)
            {
                Writers.Remove(myName);
                Registry.Unregister(myName);
            }
        }
    }

    static int Main(string[] args)
    {
        Opt = MoliOptions.Parse(args);
        Directory.CreateDirectory(Opt.WorkDir);
        Wal = new WalStore(Path.Combine(Opt.WorkDir, "wal"));
        for (int i = 0; i < args.Length; i++)
            if (args[i] == "--peer" && i + 1 < args.Length) Peers.Add(args[++i]);
        NodeN = 1 + Peers.Count;
        Leader = new LeaderElection(Opt.Port, NodeN);
        Dead = Path.Combine(Opt.WorkDir, "dead");
        foreach (var kv in Wal.Replay())
        {
            string target = kv.Value[0];
            List<string[]> list;
            if (!Deferred.TryGetValue(target, out list)) { list = new List<string[]>(); Deferred[target] = list; }
            list.Add(new[] { kv.Key, kv.Value[1] });
        }
        foreach (var peer in Peers)
        {
            var ht = new Thread(() => HeartbeatLoop(peer));
            ht.IsBackground = true;
            ht.Start();
        }
        var listener = new TcpListener(IPAddress.Loopback, Opt.Port);
        listener.Start();
        Log("MoliLine refactor on " + Opt.Port);
        while (true)
        {
            var c = listener.AcceptTcpClient();
            var t = new Thread(() => Serve(c));
            t.IsBackground = true;
            t.Start();
        }
    }
}




