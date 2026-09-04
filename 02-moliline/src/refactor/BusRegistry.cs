// BusRegistry.cs - thread-safe world/topic registry (C#5 compatible)
using System;
using System.Collections.Generic;
using System.Linq;
namespace MoliLine
{
    public sealed class BusRegistry
    {
        private readonly object _lock = new object();
        private readonly Dictionary<string,string> _topic = new Dictionary<string,string>();
        private readonly Dictionary<string,string> _cap = new Dictionary<string,string>();
        private readonly Dictionary<string,List<string>> _subs = new Dictionary<string,List<string>>();

        public bool Register(string name, string topic, string cap)
        {
            lock (_lock)
            {
                if (string.IsNullOrEmpty(name)) return false;
                _topic[name] = topic == null ? "" : topic;
                if (!string.IsNullOrEmpty(cap)) _cap[name] = cap;
                if (!string.IsNullOrEmpty(topic))
                {
                    List<string> list;
                    if (!_subs.TryGetValue(topic, out list))
                    {
                        list = new List<string>();
                        _subs[topic] = list;
                    }
                    if (!list.Contains(name)) list.Add(name);
                }
                return true;
            }
        }

        public bool Unregister(string name)
        {
            lock (_lock)
            {
                if (!_topic.Remove(name)) return false;
                _cap.Remove(name);
                foreach (var list in _subs.Values) list.Remove(name);
                return true;
            }
        }

        public bool Exists(string name)
        {
            lock (_lock) { return _topic.ContainsKey(name); }
        }

        public string Topic(string name)
        {
            lock (_lock)
            {
                string t;
                return _topic.TryGetValue(name, out t) ? t : null;
            }
        }

        public string Capability(string name)
        {
            lock (_lock)
            {
                string c;
                return _cap.TryGetValue(name, out c) ? c : null;
            }
        }

        public List<string> Worlds()
        {
            lock (_lock) { return _topic.Keys.ToList(); }
        }

        public List<string> Subscribers(string topic)
        {
            lock (_lock)
            {
                List<string> l;
                if (_subs.TryGetValue(topic, out l)) return new List<string>(l);
                return new List<string>();
            }
        }
    }
}



