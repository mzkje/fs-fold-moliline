using System;
using System.Collections.Generic;
namespace MoliBus
{
    public sealed class LeaderElection
    {
        private readonly object _lock = new object();
        private readonly int _myPort;
        private readonly int _nodeN;
        private readonly HashSet<int> _alive = new HashSet<int>();
        public LeaderElection(int myPort, int nodeN) { _myPort = myPort; _nodeN = nodeN; }
        public void AddPeer(int port) { lock (_lock) _alive.Add(port); }
        public void RemovePeer(int port) { lock (_lock) _alive.Remove(port); }
        public bool IsLeader()
        {
            lock (_lock)
            {
                var alive = new List<int>(); alive.Add(_myPort);
                foreach (var a in _alive) alive.Add(a);
                alive.Sort();
                int majority = _nodeN / 2 + 1;
                return alive.Count >= majority && (_nodeN == 1 || alive[0] == _myPort);
            }
        }
        public int AliveCount() { lock (_lock) { return _alive.Count + 1; } }
    }
}


