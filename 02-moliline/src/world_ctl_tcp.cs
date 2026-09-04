// commander over TCP MoliLine. usage: world_ctl_tcp SEND <target>
// <cmd...> | interactive | PUBLISH <topic> <data...>
using System;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;

class WorldCtlTcp
{
    static string Do(TcpClient c, StreamReader sr, StreamWriter w,
        string req, string op, string target, string payload)
    {
        w.WriteLine(op + "|" + req + "|" + target + "|" +
            Convert.ToBase64String(Encoding.UTF8.GetBytes(payload)));
        string line;
        while ((line = sr.ReadLine()) != null)
        {
            var p = line.Split('|');
            if (p.Length >= 3 && p[0] == "REPLY" && p[1] == req)
                return Encoding.UTF8.GetString(
                    Convert.FromBase64String(p[2]));
        }
        return "ERR:closed";
    }

    static int Main(string[] args)
    {
        int port = 47001;
        var rest = args;
        if (args.Length >= 1 && args[0].Length == 5 &&
            args[0].All(char.IsDigit))
        {
            port = int.Parse(args[0]);
            rest = new string[args.Length - 1];
            Array.Copy(args, 1, rest, 0, rest.Length);
        }
        if (rest.Length < 1)
        {
            Console.WriteLine("usage: world_ctl_tcp [port] SEND <target> "
                + "<cmd...> | PUBLISH <topic> <data> | interactive");
            return 1;
        }
        args = rest;
        using (var c = new TcpClient())
        {
            c.Connect(IPAddress.Loopback, port);
            using (var net = c.GetStream())
            using (var sr = new StreamReader(net, Encoding.UTF8, false,
                4096, true))
            using (var w = new StreamWriter(net, Encoding.UTF8, 4096, true)
            { AutoFlush = true })
            {
                if (args[0] == "SEND" && args.Length >= 3)
                {
                    string payload = string.Join(" ", args, 2,
                        args.Length - 2);
                    string req = Guid.NewGuid().ToString("N").Substring(0, 16);
                    Console.WriteLine("-> " + args[1] + " [" +
                        Do(c, sr, w, req, "SEND", args[1], payload) + "]");
                    return 0;
                }
                if (args[0] == "PUBLISH" && args.Length >= 3)
                {
                    string payload = string.Join(" ", args, 2,
                        args.Length - 2);
                    w.WriteLine("PUBLISH|x|" + args[1] + "|" +
                        Convert.ToBase64String(
                            Encoding.UTF8.GetBytes(payload)));
                    Console.WriteLine("published");
                    return 0;
                }
                if (args[0] == "FIND" && args.Length >= 2)
                {
                    string req = Guid.NewGuid().ToString("N")
                        .Substring(0, 16);
                    string resp = Do(c, sr, w, req, "FIND", args[1], "");
                    Console.WriteLine("cap " + args[1] + " worlds: " +
                        resp);
                    return 0;
                }
                if (args[0] == "interactive")
                {
                    Console.WriteLine("ctl tcp interactive ready");
                    string line;
                    while ((line = Console.ReadLine()) != null)
                    {
                        if (line.Trim() == "quit") break;
                        var parts = line.Split(' ');
                        if (parts.Length >= 3 && parts[0] == "SEND")
                        {
                            string payload = string.Join(" ", parts, 2,
                                parts.Length - 2);
                            string req = Guid.NewGuid().ToString("N")
                                .Substring(0, 16);
                            Console.WriteLine("-> " + parts[1] + " [" +
                                Do(c, sr, w, req, "SEND", parts[1],
                                    payload) + "]");
                        }
                    }
                }
            }
        }
        return 0;
    }
}



