# 02 · MoliLine（程序间消息总线）

让同一台电脑上的程序互发消息：请求/应答、事件广播、命令执行。带日志、
去重、死信、重连、多节点选主等可靠行为。无第三方依赖，用 Windows 自带
C# 编译器构建。

## 组成

- `moli_line_refactor.exe`：总线（转发、日志、心跳、选主）
- `world_svc_tcp.exe`：服务方（注册并执行命令）
- `world_ctl_tcp.exe`：控制方（发命令、收回复）

## 消息类型

| 消息 | 说明 |
|---|---|
| REGISTER | 服务方注册名字与主题 |
| SEND/REPLY | 请求应答 |
| PUBLISH/EVT | 事件广播（按主题订阅） |
| CMD/RESP | 总线投递命令、服务方回报结果 |

## 可靠性行为

- WAL：命令先写盘再路由，重启补发未完成请求；
- exactly-once：同一请求只执行一次（服务方持久化去重）；
- 死信：目标不在线进入死信记录；
- 自动重连与总线地址轮换；
- 多节点：心跳握手，最小端口为主；断主后重选。

## 规模选择

- 1 节点：开箱即用；
- 2 节点：两个同时在线才服务（防脑裂设计），一个下线即停服；
- 3 节点及以上：断主后约 6 秒内交接并恢复服务。

## 构建与运行

```bash
powershell -File build.ps1
python examples/hello.py
python run_matrix_refactor.py
python run_multinode_refactor.py
```

手动：

```text
bin\moli_line_refactor.exe --port 47001 --workdir <dir>
bin\world_svc_tcp.exe     executor events 127.0.0.1:47001
bin\world_ctl_tcp.exe     47001 SEND executor PING
```

多节点：每个实例把其他实例地址作为 `--peer` 传入。

## 参数

- 总线：`--port`、`--workdir`、`--peer ip:port ...`
- 服务方：`<名字> <主题> [总线地址...]`；去重表目录可用环境变量
  `MOLI_DONE_DIR` 指定

## 协议

行协议（UTF-8，`|` 分隔，payload base64），详见 docs/WIRE.md。

## 限制

- 无登录与加密：仅本机/内网；
- 两节点无故障转移（多数派 2/2 是防脑裂设计）；
- 本仓库给出的数字为本机 Windows 测试结果。

