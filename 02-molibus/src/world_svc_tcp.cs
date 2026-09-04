// executor world over TCP MoliBus. usage: world_svc_tcp <name> [topic]
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;

class WorldSvcTcp
{
    static int FailCount = 0;
    static string Name = "executor";
    static string DoneDir = Path.Combine(Path.GetTempPath(), "moli_exec_done");
    static Dictionary<string, string> Done =
        new Dictionary<string, string>();
    static Queue<string> DoneOrder = new Queue<string>();
    static int Processed = 0;
    const int DONE_MAX = 10000;
    static string DonePath = "";
    static string[] BusAddrs = { "127.0.0.1:47001" };
    static int BusIdx = 0;

    static void LoadDone()
    {
        if (DonePath.Length == 0 || !File.Exists(DonePath)) return;
        foreach (var raw in File.ReadAllLines(DonePath))
        {
            var p = raw.Split('|');
            if (p.Length == 2)
                Done[p[0]] = Encoding.UTF8.GetString(
                    Convert.FromBase64String(p[1]));
        }
        Console.WriteLine(Name + " loaded done-table entries=" +
            Done.Count);
    }

    static void PersistDone(string req, string resp)
    {
        try
        {
            Directory.CreateDirectory(DoneDir);
            File.AppendAllText(Path.Combine(DoneDir, Name + ".log"),
                req + "|" + Convert.ToBase64String(
                    Encoding.UTF8.GetBytes(resp)) + "\n",
                new UTF8Encoding(false));
        }
        catch (Exception ex)
        {
            Console.WriteLine(Name + " persist err " + ex.Message);
        }
    }

    static string Execute(string cmd)
    {
        if (cmd.StartsWith("PING")) return "PONG";
        if (cmd.StartsWith("ECHO")) return "ECHO:" +
            cmd.Substring(4).TrimStart();
        if (cmd.StartsWith("STATUS"))
            return "STATUS:" + Name + "|" +
                System.Reflection.Assembly.GetExecutingAssembly().Location;
        if (cmd.StartsWith("STATS"))
            return "STATS:processed=" + Processed + ":done=" + Done.Count;
        if (cmd.StartsWith("SLEEP"))
        {
            int ms = 300;
            int.TryParse(cmd.Substring(5).Trim(), out ms);
            System.Threading.Thread.Sleep(ms);
            return "SLEPT:" + Name + ":" + ms;
        }
        if (cmd.StartsWith("FAIL_ONCE"))
        {
            FailCount++;
            if (FailCount == 1) return "ERR:RETRY_ME(simulated)";
            return "PONG-after-retry";
        }
        if (cmd.StartsWith("WRITE"))
        {
            string rest = cmd.Substring(5).TrimStart();
            int sp = rest.IndexOf(' ');
            if (sp <= 0) return "ERR:bad WRITE";
            string dir = Path.Combine(Path.GetTempPath(), "moli_bus_dead");
            Directory.CreateDirectory(dir);
            File.WriteAllText(Path.Combine(dir, "svc_" +
                rest.Substring(0, sp)), rest.Substring(sp + 1), Encoding.UTF8);
            return "WROTE:" + rest.Substring(0, sp);
        }
        return "ERR:unknown " + cmd;
    }

    static string ExecuteOnce(string req, string cmd)
    {
        lock (Done)
        {
            string cached;
            if (Done.TryGetValue(req, out cached))
                return cached;      // idempotent replay: return cached result
            string resp = Execute(cmd);
            Processed++;
            Done[req] = resp;
            DoneOrder.Enqueue(req);
            while (DoneOrder.Count > DONE_MAX)
                Done.Remove(DoneOrder.Dequeue());
            PersistDone(req, resp);
            return resp;
        }
    }

    static int Main(string[] args)
    {
        Name = args.Length > 0 ? args[0] : "executor";
        string topic = args.Length > 1 ? args[1] : "";
        if (args.Length > 2)
        {
            var list = new List<string>();
            for (int i = 2; i < args.Length; i++)
                list.Add(args[i]);
            if (list.Count > 0) BusAddrs = list.ToArray();
        }
        string envDir = Environment.GetEnvironmentVariable("MOLI_DONE_DIR");
        if (!string.IsNullOrEmpty(envDir)) DoneDir = envDir;
        DonePath = Path.Combine(DoneDir, Name + ".log");
        LoadDone();
        while (true)
        {
            try
            {
                using (var c = new TcpClient())
                {
                    var ep = BusAddrs[BusIdx].Split(':');
                    c.Connect(IPAddress.Parse(ep[0]),
                        int.Parse(ep[1]));
                    using (var net = c.GetStream())
                    using (var sr = new StreamReader(net, Encoding.UTF8,
                        false, 4096, true))
                    using (var w = new StreamWriter(net,
                        new UTF8Encoding(false), 4096, true)
                    { AutoFlush = true, NewLine = "\n" })
                    {
                        w.WriteLine("REGISTER|" + Name + "|" + topic);
                        Console.WriteLine(Name +
                            " connected to MoliBus TCP bus");
                        string line;
                        while ((line = sr.ReadLine()) != null)
                        {
                            var p = line.Split('|');
                            if (p.Length >= 1 && p[0].StartsWith("ERR"))
                            {
                                Console.WriteLine(Name + " rejected: " +
                                    line);
                                break;
                            }
                            if (p.Length >= 4 && p[0] == "CMD")
                            {
                                string cmd = Encoding.UTF8.GetString(
                                    Convert.FromBase64String(p[3]));
                                string resp = ExecuteOnce(p[1], cmd);
                                w.WriteLine("RESP|" + p[1] + "|" +
                                    Convert.ToBase64String(Encoding.UTF8
                                        .GetBytes(resp)));
                                Console.WriteLine(Name + " " + p[1] +
                                    " -> " + resp);
                            }
                            else if (p.Length >= 4 && p[0] == "EVT")
                            {
                                Console.WriteLine(Name + " event " + p[2] +
                                    " " + Encoding.UTF8.GetString(
                                        Convert.FromBase64String(p[3])));
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine(Name + " reconnect err: " + ex.Message);
            }
            BusIdx = (BusIdx + 1) % BusAddrs.Length;
            Console.WriteLine(Name + " bus lost, trying " +
                BusAddrs[BusIdx] + " in 1s");
            System.Threading.Thread.Sleep(1000);
        }
    }
}


