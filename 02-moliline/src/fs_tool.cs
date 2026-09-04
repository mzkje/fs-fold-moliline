// fs_tool: no-Python carrier for .fs containers.
// check: decompress pool via .NET DeflateStream, verify SHA256 of every
//        unique file against the manifest (structure runs on any carrier).
// run:   unfold runnable subset (root + version tree) into %TEMP% cache
//        and start the entry executable (default YoudaoDict.exe).
// Build: csc /nologo /out:fs_tool.exe /r:System.Web.Extensions.dll fs_tool.cs
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;

class FsTool
{
    static readonly byte[] MAGIC = new byte[] {
        (byte)'F', (byte)'S', (byte)'F', (byte)'7',
        (byte)'8', (byte)'1', 0, 1 };
    static readonly byte[] EMBED = new byte[] {
        (byte)'F', (byte)'S', (byte)'E', (byte)'M',
        (byte)'B', (byte)'E', (byte)'D', (byte)'1' };

    // detect an .fs appended to this executable itself
    static byte[] SelfFs()
    {
        string loc = System.Reflection.Assembly.GetExecutingAssembly().Location;
        byte[] all = File.ReadAllBytes(loc);
        int n = all.Length;
        if (n < 24 + 8) return null;
        int tail = n - 24;
        for (int i = 0; i < 8; i++)
            if (all[tail + i] != EMBED[i]) return null;
        long fsLen = BitConverter.ToInt64(all, tail + 8);
        long fsOff = BitConverter.ToInt64(all, tail + 16);
        if (fsOff < 0 || fsOff + fsLen > n - 24) return null;
        var fs = new byte[fsLen];
        Array.Copy(all, fsOff, fs, 0, fsLen);
        return fs;
    }

    static Dictionary<string, object> ReadManifest(byte[] data, out int poolOff)
    {
        for (int i = 0; i < 8; i++)
            if (data[i] != MAGIC[i])
                throw new Exception("bad magic");
        long jlen = BitConverter.ToInt64(data, 8);
        string json = Encoding.UTF8.GetString(data, 16, (int)jlen);
        poolOff = 16 + (int)jlen;
        var ser = new JavaScriptSerializer();
        ser.MaxJsonLength = int.MaxValue;
        return ser.Deserialize<Dictionary<string, object>>(json);
    }

    static byte[] ZlibDecompress(byte[] blob)
    {
        // zlib = 2-byte header + raw deflate + 4-byte adler; DeflateStream
        // stops at the deflate end marker, tail adler is ignored.
        using (var src = new MemoryStream(blob, 2, blob.Length - 2))
        using (var ds = new DeflateStream(src, CompressionMode.Decompress))
        using (var dst = new MemoryStream())
        {
            ds.CopyTo(dst);
            return dst.ToArray();
        }
    }

    static string Sha256Hex(byte[] b)
    {
        using (var sha = SHA256.Create())
        {
            var h = sha.ComputeHash(b);
            var sb = new StringBuilder(64);
            for (int i = 0; i < h.Length; i++) sb.Append(h[i].ToString("x2"));
            return sb.ToString();
        }
    }

    static byte[] ReadAll(string path)
    {
        using (var f = File.OpenRead(path))
        {
            var b = new byte[f.Length];
            f.Read(b, 0, b.Length);
            return b;
        }
    }

    static int Check(string fsPath)
    {
        var data = ReadAll(fsPath);
        bool sigOk = false;
        bool sigPresent = false;
        if (data.Length >= 40 &&
            data[data.Length - 40] == (byte)'F' &&
            data[data.Length - 39] == (byte)'S' &&
            data[data.Length - 38] == (byte)'S' &&
            data[data.Length - 37] == (byte)'I' &&
            data[data.Length - 36] == (byte)'G' &&
            data[data.Length - 35] == (byte)'S' &&
            data[data.Length - 34] == (byte)'I' &&
            data[data.Length - 33] == (byte)'G')
        {
            sigPresent = true;
            var body = new byte[data.Length - 40];
            Array.Copy(data, body, body.Length);
            var expect = new byte[32];
            Array.Copy(data, data.Length - 32, expect, 0, 32);
            byte[] got;
            using (var sha = SHA256.Create())
                got = sha.ComputeHash(body);
            sigOk = Convert.ToBase64String(got) ==
                Convert.ToBase64String(expect);
        }
        Console.WriteLine("container signature: " +
            (sigPresent ? (sigOk ? "OK" : "FAIL") : "absent"));
        int poolOff;
        var m = ReadManifest(data, out poolOff);
        var hashes = (ArrayList)m["pool_hashes"];
        var sizes = (ArrayList)m["pool_sizes"];
        int off = poolOff;
        int ok = 0;
        long rawTotal = 0;
        for (int i = 0; i < hashes.Count; i++)
        {
            int sz = Convert.ToInt32(sizes[i]);
            var blob = new byte[sz];
            Array.Copy(data, off, blob, 0, sz);
            off += sz;
            var raw = ZlibDecompress(blob);
            rawTotal += raw.Length;
            if (Sha256Hex(raw) == (string)hashes[i]) ok++;
            else Console.WriteLine("HASH MISMATCH: " + (string)hashes[i]);
        }
        Console.WriteLine("check: " + ok + "/" + hashes.Count +
            " unique files hash-verified, raw " + rawTotal +
            " bytes, carrier = .NET (no Python)");
        return (ok == hashes.Count && (!sigPresent || sigOk)) ? 0 : 1;
    }

    static int Run(string fsPath, string version, string entry, string arg)
    {
        var data = ReadAll(fsPath);
        int poolOff;
        var m = ReadManifest(data, out poolOff);
        var hashes = (ArrayList)m["pool_hashes"];
        var sizes = (ArrayList)m["pool_sizes"];
        var entries = (ArrayList)m["entries"];
        string cache = Path.Combine(Path.GetTempPath(),
            "fs_carrier_run_" + data.Length + "_" +
            Path.GetFileNameWithoutExtension(fsPath));
        Directory.CreateDirectory(cache);
        // pool offsets by hash
        var pool = new Dictionary<string, int[]>();
        int off = poolOff;
        for (int i = 0; i < hashes.Count; i++)
        {
            int sz = Convert.ToInt32(sizes[i]);
            pool[(string)hashes[i]] = new int[] { off, sz };
            off += sz;
        }
        var blobCache = new Dictionary<string, byte[]>();
        int count = 0;
        foreach (object o in entries)
        {
            var e = (Dictionary<string, object>)o;
            string rel = (string)e["rel"];
            if (rel.IndexOf('/') >= 0 && !rel.StartsWith(version + "/"))
                continue;
            string h = (string)e["hash"];
            byte[] raw;
            if (!blobCache.TryGetValue(h, out raw))
            {
                int po = pool[h][0];
                int sz = pool[h][1];
                var blob = new byte[sz];
                Array.Copy(data, po, blob, 0, sz);
                raw = ZlibDecompress(blob);
                blobCache[h] = raw;
            }
            string dest = Path.Combine(cache, rel.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(dest));
            File.WriteAllBytes(dest, raw);
            count++;
        }
        string exe = Path.Combine(cache, entry);
        Console.WriteLine("run: unfolded " + count + " files to " + cache);
        var psi = new System.Diagnostics.ProcessStartInfo(exe);
        psi.WorkingDirectory = cache;
        if (arg.Length > 0) psi.Arguments = arg;
        System.Diagnostics.Process.Start(psi);
        Console.WriteLine("run: launched " + exe);
        return 0;
    }

    static int Main(string[] args)
    {
        try
        {
            byte[] self = SelfFs();
            if (args.Length >= 2 && args[0] == "check")
                return Check(args[1]);
            if (args.Length >= 2 && args[0] == "run")
                return Run(args[1],
                    args.Length >= 3 ? args[2] : "11.3.16.0",
                    args.Length >= 4 ? args[3] : "YoudaoDict.exe",
                    args.Length >= 5 ? args[4] : "");
            if (self != null)
            {
                Console.WriteLine("embedded fs found: " + self.Length + " bytes");
                if (args.Length >= 1 && args[0] == "check")
                {
                    string tmp = Path.Combine(Path.GetTempPath(),
                        "fs_embedded_check_" + self.Length + ".fs");
                    File.WriteAllBytes(tmp, self);
                    int rc = Check(tmp);
                    try { File.Delete(tmp); } catch { }
                    return rc;
                }
                return RunEmbedded(self);
            }
            Console.WriteLine("usage: fs_tool check <file.fs> | "
                + "run <file.fs> [version] [entry] [arg]");
            return 1;
        }
        catch (Exception ex)
        {
            Console.WriteLine("ERROR: " + ex.Message);
            return 2;
        }
    }

    static int RunEmbedded(byte[] fs)
    {
        // reuse Run by writing fs to a temp path
        string tmp = Path.Combine(Path.GetTempPath(),
            "fs_embedded_" + fs.Length + ".fs");
        File.WriteAllBytes(tmp, fs);
        int rc = Run(tmp, "11.3.16.0", "YoudaoDict.exe", "");
        try { File.Delete(tmp); } catch { }
        return rc;
    }
}



