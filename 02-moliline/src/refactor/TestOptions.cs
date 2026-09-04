using System;
using MoliLine;
class TestOptions
{
    static int Main()
    {
        var o = MoliOptions.Parse(new[]{"--port","47123","--workdir","D:\\tmp\\moli"});
        if (o.Port != 47123) return 1;
        if (o.WorkDir != "D:\\tmp\\moli") return 2;
        Console.WriteLine("MoliOptions tests pass"); return 0;
    }
}



