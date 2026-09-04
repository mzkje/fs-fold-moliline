using System;
using System.IO;
namespace MoliLine
{
    public sealed class MoliOptions
    {
        public int Port = 47001;
        public string WorkDir = Path.Combine(Path.GetTempPath(), "moli_v1");
        public int MaxLineBytes = 1 << 20;
        public int MaxPayloadBytes = 256 << 10;
        public int LeaderIntervalMs = 2000;
        public int ReconnectMs = 1000;

        public static MoliOptions Parse(string[] args)
        {
            var o = new MoliOptions();
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "--port" && i + 1 < args.Length) int.TryParse(args[++i], out o.Port);
                else if (args[i] == "--workdir" && i + 1 < args.Length) o.WorkDir = args[++i];
            }
            return o;
        }
    }
}




