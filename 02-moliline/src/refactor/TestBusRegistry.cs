using System;
using MoliLine;
class TestBusRegistry
{
    static int Main()
    {
        var r = new BusRegistry();
        if (!r.Register("a","t1","PING")) return 1;
        if (!r.Register("b","t1","")) return 1;
        if (!r.Exists("a") || r.Subscribers("t1").Count != 2) return 2;
        if (!r.Unregister("a")) return 3;
        if (r.Exists("a") || r.Subscribers("t1").Count != 1) return 4;
        if (r.Capability("b") != null) return 5;
        Console.WriteLine("BusRegistry tests pass"); return 0;
    }
}



