# 01 · FS Fold（.fs 折叠容器）

把一个文件夹（含子目录）打包成单个 `.fs` 文件，之后按原样还原，逐文件
sha256 校验。相同内容的文件在容器里只保留一份（内容去重），唯一文件再用
zlib 压缩。

## 工作方式

1. 遍历目录，按 sha256 去重；
2. 唯一内容池 + zlib 压缩；
3. 清单（JSON）记录每个文件的相对路径、大小、哈希；
4. 容器头：`FSF781\x00\x01` + 清单长度 + 清单 + 压缩池（详见 FORMAT.md）。

## 命令

```bash
python cli.py fold    <源文件夹> <输出.fs>    # 打包
python cli.py unfold  <输入.fs> <目标文件夹>  # 还原并校验
python cli.py verify  <输入.fs>               # 不写盘校验容器
python cli.py bench   <源文件夹>              # 与 zip 对比
python incremental_fold.py <源文件夹> <旧.fs> [新.fs]
python test_fold.py                           # 单元测试
python tools/cross_carrier_check.py           # Python↔C# 互操作自检
```

还原时会检查路径穿越并限制总大小；增量重建只处理新增/修改的文件，
复用旧容器中未变化的压缩块。

## 适用场景

- 同一软件多版本目录、备份、含大量重复资源的文件夹；
- 想要“整个目录一个文件、可精确还原”的归档需求。

## 不适用场景

- 互不相同的压缩类数据：此时普通 zip 可能更小；
- 需要直接流式读取单个文件的场景：这是一个整目录容器。

## 文件说明

- foldcore.py：核心（fold/restore/verify）
- cli.py：命令行入口
- incremental_fold.py：增量重建
- benchmark.py：zip 对照
- test_fold.py：测试
- FORMAT.md：.fs 格式说明
- tools/cross_carrier_check.py：跨实现自检

