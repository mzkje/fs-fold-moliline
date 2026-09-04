// MoliWire.cs - line protocol primitives (v1.0 port start)
using System;
using System.Text;

namespace MoliLine
{
    public static class MoliWire
    {
        public const int MaxLineBytes = 1 << 20;   // 1 MiB guard
        public const int MaxPayloadBytes = 256 << 10; // 256 KiB default

        public static string Build(params string[] parts)
        {
            return string.Join("|", parts);
        }

        // Parse with length guard; throws on oversize/null.
        public static string[] Parse(string line)
        {
            if (line == null)
                throw new ArgumentNullException("line");
            if (Encoding.UTF8.GetByteCount(line) > MaxLineBytes)
                throw new InvalidOperationException("line too long");
            return line.Split('|');
        }

        public static string EncodeB64(string s)
        {
            return Convert.ToBase64String(Encoding.UTF8.GetBytes(s));
        }

        public static string DecodeB64(string b64)
        {
            var raw = Convert.FromBase64String(b64);
            if (raw.Length > MaxPayloadBytes)
                throw new InvalidOperationException("payload too large");
            return Encoding.UTF8.GetString(raw);
        }
    }
}


