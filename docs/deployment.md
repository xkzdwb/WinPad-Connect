# 部署手册：Windows 主机 + OPPO Pad 4 Pro

目标：坐在平板前，用原生触控直接操作 Windows 桌面；局域网优先，异地叠 Tailscale。

按 P0 → P4 的顺序做，每步都有验收点。不要跳步：编码器没锁好就上跨网络，会把两类问题混在一起。

## 1. Windows 主机

### 1.1 系统与硬件前提

| 项 | 要求 |
|---|---|
| 系统 | Windows 10 22H2 / Windows 11（build ≥ 19045 / 22000） |
| GPU | NVIDIA（NVENC）/ Intel（QSV）/ AMD（AMF）任一硬件编码器 |
| 网络 | 与平板同一 Wi-Fi 6 路由器，主机建议网线或 5GHz/6GHz |
| 权限 | 写 Program Files 下的 Sunshine 配置需要管理员 |

### 1.2 安装 Foundation Sunshine

1. 从 `AlkaidLab/foundation-sunshine` 的 Releases 下载安装包（自带 ZakoVDD 虚拟显示器）。
2. 安装后先不要改配置，打开 Win-Pad Connect → “Sunshine 配置”，确认“基线探测”能识别安装目录与配置文件。
3. 若安装目录在 `Program Files`，Win-Pad Connect 写配置前会提示权限不足：右键 `run.bat` → 以管理员身份运行。
4. 首次打开 `https://localhost:47990`，创建管理员账号（用户名/密码仅本机使用）。

为什么选它：ZakoVDD 会在串流开始时自动创建虚拟显示器、结束时销毁，熄屏/无头场景不需要物理显示器常亮。原版 Sunshine 也能用，但要自己装虚拟显示驱动并手动切换。

### 1.3 锁定低延迟编码参数

在 Win-Pad Connect 的“Sunshine 配置”页选择目标编码器，点“应用低延迟配置”。它只改这些键，其余配置与注释原样保留，并在同目录生成 `sunshine.conf.<时间戳>.bak`：

| 编码器 | 写入的键 |
|---|---|
| NVENC | `encoder=nvenc`、`nvenc_preset=p4`、`nvenc_tune=ll`、`nvenc_rc=cbr`、`nvenc_realtime_hags=enabled` |
| QSV | `encoder=qsv`、`qsv_preset=fast`、`qsv_slow=disabled` |
| AMF | `encoder=amdvce`、`amd_quality=speed`、`amd_rc=cbr`、`amd_preanalysis=disabled`、`amd_vbaq=disabled` |

改完重启 Sunshine（页面上有按钮），用 Moonlight 的性能叠加层确认编码延迟：

- NVENC 10–15 ms
- QSV 12–18 ms
- AMF 15–20 ms

局域网内就明显超标时，先查编码器是否真的生效、Wi-Fi 是否跑在 2.4GHz，不要进入下一步。

### 1.4 虚拟显示器

1. 设备管理器 → 显示适配器，确认 `ZakoVDD`（或 Foundation Sunshine 自带虚拟显示驱动）已启用。
2. Win-Pad Connect 的“显示与网络”页应显示 VDD 类型；若显示 `spacedesk` 等第三方驱动，说明当前不是 ZakoVDD，熄屏串流要手动切换显示模式。
3. 验收：关闭物理显示器 → 发起一次串流 → 画面正常 → 结束串流 → 设备管理器里虚拟显示器被移除（或恢复原状）。

如果切换设备后 VDD 黑屏，确认 Foundation Sunshine 版本包含 v2026.411 之后的显示器生命周期修复。

### 1.5 防火墙与端口

Win-Pad Connect 需要两个入站规则（首次启动服务时 Windows 会弹窗，勾选“专用网络”）：

| 端口 | 协议 | 用途 |
|---|---|---|
| 47800 | TCP | HTTP：ping / profile / 测速 |
| 47801 | UDP | 广播发现 |

Sunshine 自身还需要 TCP 47984–47990、UDP 47998–48010 等（安装时通常已自动加规则）。若平板能发现但连不上，先在主机浏览器访问 `http://127.0.0.1:47800/padlink/ping` 自测，再从平板浏览器访问 `http://<主机IP>:47800/padlink/ping`。

### 1.6 启动接入服务

1. Win-Pad Connect → “接入服务” → “启动接入服务”。
2. 记下配对码（6 位，可关闭校验；只用于一次握手，不参与视频加密）。
3. 页面会列出本机局域网地址与 Tailscale 地址，异地连接时用后者。

## 2. OPPO Pad 4 Pro

### 2.1 安装

- 方式一：Android Studio 打开 `padlink/pad-android`，Run 到平板；
- 方式二：`./gradlew :app:assembleDebug` 后 `adb install -r app-debug.apk`。

要求 Android 10+（minSdk 26），平板与主机在同一 Wi-Fi。

### 2.2 配网与发现

1. 打开 Win-Pad Connect Pad → “搜索主机”，选中列表里的电脑。
2. 需要配对码时输入 Host 页面上的 6 位数字。
3. 若列表为空：确认同一网段、Host 服务已启动、路由器未开启 AP 隔离；仍不行就在“手动 IP”里填 `主机IP:47800`。

### 2.3 体检与档位

“主机体检”卡会显示就绪度分数、编码器与未通过项。红色项回电脑处理，黄色项可先跑。

档位建议：

| 档位 | 分辨率 | 起点码率 | 适用 |
|---|---|---|---|
| 流畅 1080p | 1920×1080 | 20 Mbps | 首次跑通、Wi-Fi 一般 |
| 均衡 2.5K | 2560×1600 | 40 Mbps | 日常办公 |
| 原生 3.4K | 3392×2400 | 70 Mbps | Wi-Fi 6 近距离、看文字 |

先 1080p60 跑通，再逐档上调；每档用“测 8MB 吞吐”确认实测值高于档位码率 25% 以上。

### 2.4 连接 Moonlight

1. 安装 fork 版 Moonlight（见 [moonlight-android-integration.md](moonlight-android-integration.md)）。
2. 在 Moonlight 里新增主机，填 Win-Pad Connect Pad 复制的 `IP:端口`。
3. 输入 Moonlight 自己的 PIN（与 Win-Pad Connect 配对码无关），在 Sunshine Web 后台确认。
4. 关闭“触控屏作为触摸板”，四指轻点呼出键盘。

## 3. 异地：Tailscale 叠加

不改 Moonlight/Sunshine 的任何 NAT 逻辑，只在系统层加一层虚拟局域网：

1. 主机与平板各自安装 Tailscale，登录同一账号；
2. 主机 `tailscale status` 里平板应为 `direct`（直连），不是 `relay`；中继会带来额外延迟与周期性卡顿；
3. Win-Pad Connect 的“显示与网络”页会显示直连/中继节点数；
4. 平板端把主机地址改为 `100.x.y.z:47800`（Win-Pad Connect 发现包在 Tailscale 下通常收不到广播，手动填 IP 更稳）。

预期：同局域网直连 ≤10 ms；不同 ISP 直连 20–30 ms；走 DERP 中继属于降级状态，不作为目标。

## 4. 常见问题

| 现象 | 先查 |
|---|---|
| 平板搜不到主机 | 同一网段？UDP 47801 入站规则？AP 隔离？ |
| 能发现、连不上 | 防火墙 TCP 47800；Host 服务是否在监听（页面上的自测 HTTP） |
| 401 | 配对码错/已更换；Host 页面点“换一个”后需重新输入 |
| 画面糊、延迟高 | 编码器是否生效；码率是否超过实测吞吐；Wi-Fi 频段 |
| 触控像触控板 | “触控屏作为触摸板”没关；原生触控注释未恢复 |
| 四指仍呼出键盘 | 手势判定还是三指；或四指判定参数过松 |
| 熄屏后黑屏 | VDD 未启用；或用了非 ZakoVDD 驱动 |

## 5. 回退

- 配置：Win-Pad Connect “Sunshine 配置” → “还原最近备份”，选择写入前的 `.bak`。
- 服务：直接“停止接入服务”，不影响 Sunshine 与 Moonlight。
- 客户端：卸载 Win-Pad Connect Pad 即可，Moonlight 仍可独立使用。
