using System;
using System.IO;
using MoliLine;
class TestWalStore
{
    static int Main()
    {
        string dir = Path.Combine(Path.GetTempPath(), "moli_wal_test_" + Guid.NewGuid().ToString("N"));
        var w = new WalStore(dir);
        w.AppendW("r1","x","b64"); w.AppendW("r2","y","b642"); w.AppendD("r1");
        var pending = w.Replay();
        if (pending.Count != 1 || !pending.ContainsKey("r2")) return 1;
        if (pending["r2"][0] != "y" || pending["r2"][1] != "b642") return 2;
        Directory.Delete(dir, true);
        Console.WriteLine("WalStore tests pass"); return 0;
    }
}



