# 验收记录与测试矩阵

本仓库在本机（Windows 11 24H2，无 Sunshine、无 Tailscale、无 Android SDK）能验证什么、不能验证什么，都写在下面。**不把“代码写了”当成“功能验过”**。

## 1. 可自动验证（已通过）

### 1.1 主机端离线测试

```bat
cd padlink\host-windows
python -m unittest discover -s tests -v
```

实际结果：`Ran 19 tests ... OK`。覆盖：

| 组 | 用例 |
|---|---|
| Sunshine 配置 | 增量写入保留注释、备份生成、还原、未知编码器拒绝、不可写中止 |
| 体检 | 权重合计、评分分级、9 项检查顺序与状态 |
| profile | 协议 v1 字段、三档位、service 标识 |
| HTTP | `/padlink/ping`、`/padlink/profile.json`（含 401/404）、`/padlink/download` 字节数、`/padlink/health` |
| 设置 | 端口归一化、配对码 6 位、开关持久化 |
| 平台探针 | GPU/显示器/IPv4/网关在无子进程条件下的兜底 |

### 1.2 主机端冒烟（不打开窗口）

```bat
cd padlink\host-windows
python -m padlink --smoke-test
```

实际结果：输出主机名、Windows 版本、CPU、内存、GPU、推荐编码器、VDD 类型、局域网地址、Tailscale 状态、就绪度分数、9 项检查逐条状态、profile JSON 字符数与档位数。

### 1.3 平板端纯 Java 核心

```bat
cd padlink\pad-android
run-core-tests.bat
```

实际结果：`32 项通过，0 失败`。覆盖 JSON 解析与转义、profile 映射、RTT 均值/抖动/丢包、吞吐换算、码率建议选档/降档、四指手势命中/三指忽略/拖动取消/超时取消。

### 1.4 协议联调（本机回环）

Host 启动服务后：

```bat
curl http://127.0.0.1:47800/padlink/ping
curl "http://127.0.0.1:47800/padlink/profile.json?code=<配对码>"
curl -o NUL "http://127.0.0.1:47800/padlink/download?mb=8"
```

期望：ping 返回 `service=padlink`；profile 返回完整 JSON（未带 code 时 401）；download 返回 8 MiB。

## 2. 需要真机/真环境（本机未验，给出验收方法）

| 编号 | 项 | 本机状态 | 验收方法 |
|---|---|---|---|
| P0 | Foundation Sunshine + 1080p60 局域网串流 | 未安装 Sunshine，无法验证 | 装 Foundation Sunshine，Win-Pad Connect 写入 NVENC 参数，Moonlight 叠加层看编码延迟 10–15 ms |
| P1 | 原生触控 + 四指手势 | 只有参考实现与测试，未改 fork | 按 [moonlight-android-integration.md](moonlight-android-integration.md) 改 `Game.java`，跑 8 条验收清单 |
| P2 | ZakoVDD 熄屏串流 | 本机是 spacedesk，无 ZakoVDD | 设备管理器确认 VDD，关物理显示器后串流 |
| P3 | Tailscale 异地直连 | 未安装 Tailscale | 两端登录同账号，`tailscale status` 显示 `direct`，Pad 填 100.x 地址 |
| P4 | 三档分辨率切换 | 主机 profile 与平板 RadioGroup 已实现 | 三档各跑一次，记录带宽与主观跟手度 |

## 3. 提纲 → 交付物对照

| 提纲条目 | 落地位置 | 说明 |
|---|---|---|
| 选基线，不改协议 | `docs/deployment.md` §1.2、`padlink/host-windows/padlink/sunshine.py` | 检测 Foundation Sunshine，只写官方配置键 |
| 编码参数锁定 | `padlink/host-windows/padlink/sunshine.py` `LOW_LATENCY_PROFILES` | NVENC p4/ll/cbr 等，带备份与还原 |
| 原生触控启用 | `docs/moonlight-android-integration.md` + `FourFingerTapDetector.java` | 定位方法、改动形状、参数、验收、回退 |
| 三指改四指 | 同上 | 250/300/24 参数 |
| ZakoVDD | `padlink/host-windows/padlink/snapshot.py`、`checks.py` | 检测 VDD 类型；非 ZakoVDD 给“可改进”而非“失败” |
| 三档分辨率 | `profile.py` `PAD_TIERS`、`MainActivity` 档位卡 | 1080p/2.5K/原生 |
| Tailscale 叠加 | `padlink/host-windows/padlink/tailscale.py` | 只读状态，判直连/中继 |
| 触控 fork 选择 | `docs/moonlight-android-integration.md` §0 | Axixi2233 优先，a2012s 备选 |

## 4. 已知边界

- 主机端**不实现串流**，不替代 Sunshine；平板端不替代 Moonlight。两者是“体检 + 参数下发 + 手势参考”。
- 主机端在无子进程权限的沙箱里会退化为“注册表 + socket + ctypes”探针；真实用户环境会额外走 `nvidia-smi`、`ipconfig`、`ping`，结果更准。
- 平板 APK 未在本机构建（无 Android SDK/NDK/AGP 缓存）；工程按 AGP 8.5.2 + compileSdk 34 + JDK 17 编写，纯 Java 无第三方依赖。
- 配对码是握手级校验，不是加密；不要把 47800 暴露到公网。

## 5. 一键回归

```bat
cd padlink\host-windows && python -m unittest discover -s tests
cd ..\pad-android && run-core-tests.bat
cd ..\host-windows && python -m padlink --smoke-test
```

三条都应为 0 退出码；UI 可用 `python -m padlink --exit-after 5` 启动后人工检查，截图见 `host-windows/shots/`。
