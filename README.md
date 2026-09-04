# FS Fold (.fs) & MoliLine

> English: two local tools for Windows, no third-party libraries needed.
> 1) FS Fold packs a folder into one `.fs` file and restores it exactly;
> 2) MoliLine lets programs on the same computer exchange messages.

## 一、FS Fold：把一个文件夹打包成一个 .fs 文件

### 做什么

把一个文件夹（包括子目录）整体打包成一个 `.fs` 文件，之后可以把它还原成原来的文件夹，逐文件用 sha256 校验，保证内容一模一样。

打包不是普通压缩，而是先做“内容去重”再做压缩：

1. 遍历目录里的每个文件，计算 sha256；
2. 内容相同的文件（比如同一份文件被复制了很多份）在文件池里只保留一份；
3. 文件池里的每个唯一文件再用 zlib 压缩；
4. 生成一份清单，记录每个文件的路径、大小、哈希。

所以它特别适合“重复内容很多”的文件夹，例如：同一软件的多个版本目录、备份文件夹、包含大量重复 dll/资源的程序目录。这类场景下 `.fs` 能比 zip 小很多。

### 命令

```bash
python cli.py fold    <源文件夹> <输出.fs>      # 打包
python cli.py unfold  <输入.fs> <目标文件夹>    # 还原（逐文件 sha256 校验）
python cli.py verify  <输入.fs>                 # 不写盘，直接校验容器是否完好
python cli.py bench   <源文件夹>                # 和 zip 对比大小
python incremental_fold.py <源文件夹> <旧.fs> [新.fs]  # 增量重建
python test_fold.py                            # 单元测试
python tools/cross_carrier_check.py            # Python 打包 → C# 校验的互操作自检
```

### 几个细节

- 还原时会检查路径是否越界（防 `../` 穿越），并有总量上限防止解压炸弹；
- `incremental_fold.py` 会复用旧容器里没变的文件，只重新处理新增/修改的文件；
- 自带一个免 Python 的 C# 工具 `fs_tool.exe`（见 `carriers/fs_tool`），可以 `check`（校验）或 `run`（把折叠的文件夹展开到临时目录并启动其中的程序），也支持把 `.fs` 追加进 exe 做成“一个文件=一个程序”的演示。

### 适用与不适用

- 适用：重复文件多、想要“一个文件保存整个目录、可精确还原”的场景；
- 不适用：互相都不相同的压缩类数据（此时普通 zip 可能更小）——它是一个去重容器，不是一个通用压缩器。

## 二、MoliLine：程序之间的消息总线

### 做什么

让同一台电脑上的多个程序互相通信：一个程序发请求，另一个程序收到后执行并回复；也可以一个程序发事件，多个程序同时订阅。

它由三部分组成：

- `moli_line_refactor`：总线，负责转发消息、记录日志、处理断线；
- `world_svc_tcp`：服务方，注册到总线上，接收命令并执行（自带 PING/ECHO/STATUS/STATS 等可测命令）；
- `world_ctl_tcp`：控制方，向总线发命令、收回复。

### 消息类型

| 方向 | 作用 |
|---|---|
| REGISTER | 服务方注册自己的名字 |
| SEND / REPLY | 一问一答：控制方发请求，服务方执行后返回结果 |
| PUBLISH / EVT | 广播事件：控制方发布，订阅了同一主题的服务方都会收到 |
| CMD / RESP | 总线把命令投递给服务方，服务方执行后回报 |

### 可靠性相关的内置行为

- 日志（WAL）：命令先写盘再转发，程序重启后可以补发没完成的部分；
- 不重复执行：同一个请求只执行一次（服务方保存“已处理”记录）；
- 死信：目标不在线时，请求会进入死信记录而不是凭空消失；
- 重连：服务方断线后会自动换地址重连；
- 多节点：多个总线实例可以互相心跳，其中最小的端口当主节点；主节点挂了，其余节点重新选主。

### 多节点规模怎么选

- 1 个节点：开箱即用，始终可服务；
- 2 个节点：需要两个同时在线才能服务（这是防脑裂的设计）；一个挂了另一个会停止服务；
- 3 个或更多：主节点挂掉后，约几秒内其余节点选出新主并继续服务。

### 命令

```bash
powershell -File build.ps1                 # 编译（用 Windows 自带 C# 编译器）
python examples/hello.py                   # 一键 demo：控制方 → 总线 → 服务方
python run_matrix_refactor.py              # 单节点测试矩阵
python run_multinode_refactor.py           # 多节点测试矩阵（结果存到 results/）
```

手动运行：

```text
bin\moli_line_refactor.exe --port 47001 --workdir <工作目录>
bin\world_svc_tcp.exe     executor events 127.0.0.1:47001
bin\world_ctl_tcp.exe     47001 SEND executor PING
```

多节点：给每个实例传另外几个实例的地址作为 `--peer`。

### 说明与限制

- 本机 Windows 测试中：单节点请求应答为毫秒级；三节点自动选主、断主后约 6 秒切换并恢复；
- 没有登录和加密，只适合本机/内网实验；
- 总线可以让程序 A 控制程序 B，请在受控环境使用；
- 详细协议见 `02-moliline/docs/WIRE.md`。

## 三、目录结构

```text
01-file-space-folding/   .fs 折叠容器
02-moliline/             MoliLine 消息总线
carriers/fs_tool/        免 Python 的 .fs C# 工具
examples/model-world/    可选示例：把模型折成世界文件，经 MoliLine 开关/进入/保存
```

## 四、构建与测试

Windows + Python 3.8+ 即可；C# 用 Windows 自带 .NET Framework 编译器，无需下载。

```bash
cd 01-file-space-folding && python test_fold.py
cd ../02-moliline && powershell -File build.ps1 && python run_matrix_refactor.py
```

## License

MIT License（见 LICENSE）。

