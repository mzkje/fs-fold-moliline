using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
namespace MoliBus
{
    public sealed class WalStore
    {
        private readonly object _lock = new object();
        private readonly string _path;
        public WalStore(string dir, string name = "wal.log")
        {
            Directory.CreateDirectory(dir); _path = Path.Combine(dir, name);
        }
        public void AppendW(string req, string target, string b64)
        {
            lock (_lock) File.AppendAllText(_path, "W|" + req + "|" + target + "|" + b64 + "\n", new UTF8Encoding(false));
        }
        public void AppendD(string req)
        {
            lock (_lock) File.AppendAllText(_path, "D|" + req + "\n", new UTF8Encoding(false));
        }
        public Dictionary<string,string[]> Replay()
        {
            lock (_lock)
            {
                var pending = new Dictionary<string,string[]>(); var done = new HashSet<string>();
                if (!File.Exists(_path)) return pending;
                foreach (var raw in File.ReadAllLines(_path))
                {
                    var p = raw.Split('|');
                    if (p.Length >= 4 && p[0] == "W") pending[p[1]] = new[]{p[2],p[3]};
                    else if (p.Length >= 2 && p[0] == "D") done.Add(p[1]);
                }
                foreach (var d in done) pending.Remove(d);
                return pending;
            }
        }
    }
}


