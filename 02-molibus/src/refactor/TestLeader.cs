using System;
using MoliBus;
class TestLeader
{
    static int Main()
    {
        var l3 = new LeaderElection(47001, 3);
        if (l3.IsLeader()) return 1;            // 1/3 minority -> no leader
        l3.AddPeer(47002);
        if (!l3.IsLeader()) return 2;           // 2/3 majority & smallest -> leader
        l3.AddPeer(47003);
        if (!l3.IsLeader()) return 3;
        l3.RemovePeer(47002); l3.RemovePeer(47003);
        if (l3.IsLeader()) return 4;            // minority -> protection
        var l1 = new LeaderElection(1, 1);
        if (!l1.IsLeader()) return 5;           // single node leader
        Console.WriteLine("LeaderElection tests pass"); return 0;
    }
}


