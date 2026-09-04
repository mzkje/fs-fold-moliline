# fs_tool — .fs carrier without Python

Small C#/.NET carrier that reads `.fs` containers produced by FS Fold and
verifies or runs them. Builds with the C# compiler included in Windows .NET
Framework.

```powershell
powershell -File build.ps1
```

```text
fs_tool.exe check <file.fs>                  # sha256 verify pool
fs_tool.exe run <file.fs> [version] [entry] [args]
```

`run` unfolds the selected version subtree to a temp cache and launches the
entry executable (fold-and-run demo). Defaults in code point at a demo app
used during development; pass explicit `version entry` for other folded apps.

Single-file mode: append `.fs` plus the `FSEMBED1 + fs_len + fs_offset`
footer to the exe to create a self-contained "one file = one app" demo.
Only fold files you have the right to redistribute.


