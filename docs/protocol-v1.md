# Win-Pad Connect 协议 v1

Win-Pad Connect 的协议只解决一件事：**把 Windows 主机端的体检结论与接入参数，可靠地交给平板端**。它不传输画面、不代理输入，也不参与 Moonlight 的配对与加密。

- 传输：局域网 / Tailscale 上的明文 HTTP + UDP 广播
- 端口：HTTP `47800`（可在 Host 设置里改），UDP 发现 `47801`
- 编码：UTF-8 JSON
- 版本：`protocol = 1`；新增字段保持向后兼容，不改已有字段名

## 1. 发现（UDP 47801）

平板向广播地址的 `47801` 端口发送 ASCII 字符串：

```
PADLINK?1
```

主机在 `47801` 上监听，收到后向来源地址回一份 JSON（单包，≤ 1 KB）：

```json
{
  "service": "padlink",
  "protocol": 1,
  "app": "Win-Pad Connect 1.0.0",
  "name": "XKlcq-MDesktop",
  "port": 47800,
  "code_required": true,
  "ips": ["10.89.166.118", "100.64.0.3"]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `service` | string | 固定 `padlink`，用于过滤无关广播 |
| `protocol` | int | 协议版本 |
| `name` | string | 主机名，平板列表里显示 |
| `port` | int | HTTP 端口 |
| `code_required` | bool | 是否需要配对码 |
| `ips` | string[] | 主机自报的地址（平板应以应答包的源地址为准） |

平板应同时向 `255.255.255.255` 和各网卡的定向广播地址发送，监听 2 秒左右；Windows 防火墙需允许 UDP 47801 入站。

## 2. HTTP 端点

所有响应均为 `application/json; charset=utf-8`，除非特别说明。

### `GET /padlink/ping`

```json
{"service":"padlink","protocol":1,"time":1762684800,"name":"XKlcq-MDesktop",
 "port":47800,"code_required":true,"app":"Win-Pad Connect 1.0.0"}
```

平板用它测 RTT：一次请求-响应记为一次样本。

### `GET /padlink/profile.json?code=123456`

主机体检与接入参数。开启配对校验时，`code` 必须匹配，否则返回 `401`。

```json
{
  "service": "padlink",
  "protocol": 1,
  "app": "Win-Pad Connect 1.0.0",
  "generated_at": 1762684800,
  "host": {
    "name": "XKlcq-MDesktop",
    "os": "Windows 11 Home China 26H2",
    "cpu": "13th Gen Intel(R) Core(TM) i7-13700HX",
    "ram_gb": 15.7,
    "gpu": "Intel(R) UHD Graphics",
    "encoder": "nvenc",
    "encoder_label": "NVIDIA NVENC",
    "admin": false
  },
  "sunshine": {
    "installed": true,
    "running": true,
    "version": "2026.411",
    "web": "https://localhost:47990",
    "locked": true
  },
  "display": {
    "detected": true,
    "kind": "ZakoVDD",
    "name": "Zako Virtual Display",
    "resolution": "3392x2400",
    "refresh": "60 Hz",
    "supports_pad": true
  },
  "network": {
    "lan": ["10.89.166.118"],
    "primary": "10.89.166.118",
    "tailscale": {"installed": true, "state": "直连", "ipv4": "100.64.0.3",
                   "direct": 2, "relay": 0},
    "service_port": 47800
  },
  "client": {
    "tiers": [
      {"label": "流畅 1080p", "width": 1920, "height": 1080, "fps": 60, "bitrate_kbps": 20000},
      {"label": "均衡 2.5K", "width": 2560, "height": 1600, "fps": 60, "bitrate_kbps": 40000},
      {"label": "原生 3.4K", "width": 3392, "height": 2400, "fps": 60, "bitrate_kbps": 70000}
    ],
    "fps": 60,
    "codec": "HEVC",
    "note": "码率为 60fps 的起点值，实际以平板端体检测得的吞吐为准。"
  },
  "readiness": {
    "score": 86,
    "checks": [
      {"key": "sunshine", "title": "Sunshine 基线", "status": "ok", "detail": "..."}
    ]
  },
  "service_info": {"running": true, "port": 47800, "code_required": true},
  "code_required": true
}
```

约定：

- `readiness.checks[].status` ∈ `ok | warn | fail | unknown`，与 Host 的 9 项检查一一对应。
- `client.tiers[].bitrate_kbps` 是**起点值**，不是上限；平板按实测吞吐用 25% 余量选档。
- `network.tailscale.state` 是展示文案（`未安装 / 未运行 / 直连 / 中继 / 部分中继`），程序判断请用 `installed` 与 `direct`/`relay` 计数。

### `GET /padlink/download?mb=8`

返回 `mb` MiB 的随机字节流（上限 64），用于测下行吞吐。响应头带 `Content-Type: application/octet-stream` 与 `Content-Length`。

### `GET /padlink/health`

```json
{"service":"padlink","protocol":1,"time":1762684800,"name":"XKlcq-MDesktop",
 "port":47800,"code_required":true,"app":"Win-Pad Connect 1.0.0",
 "uptime_s":312,"requests":27}
```

### `GET /`

浏览器可读的说明页（纯文本 HTML），列出上述端点与当前配对状态。

## 3. 错误与安全

| 状态 | 含义 |
|---|---|
| `401` | 配对码缺失或不匹配；响应体 `{"error":"pairing code required"}` |
| `404` | 未知路径 |
| `429` | 预留（当前未启用限流） |

- 配对码为 6 位数字，只用于同一局域网的一次性握手，**不参与视频链路加密**，也不替代 Moonlight 自己的 PIN。
- 服务只读主机状态、写格式化报告；所有写操作（改配置、启停 Sunshine）只在 Host 桌面界面里发生。
- 明文 HTTP 的适用前提是可信局域网或已加密的 Tailscale 隧道；不要直接暴露到公网。
