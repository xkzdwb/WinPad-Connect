# Win-Pad Connect（Windows 主机端）

在 Moonlight/Sunshine 基线上做“体检 + 参数锁定 + 接入服务”的桌面工具。它**不实现串流**，也不碰 Moonlight 的传输协议；画面与输入仍然由 Sunshine + Moonlight 完成。

![总览](shots/overview.png)

## 能做什么

| 页面 | 能力 |
|---|---|
| 总览 | 一屏看就绪度分数、推荐编码器、VDD 类型、网络路径、9 项体检与平板接入按钮 |
| 接入服务 | 启停 HTTP/UDP 服务、改端口、开关 6 位配对码、复制地址、自测 `/padlink/ping`、看接入日志 |
| Sunshine 配置 | 探测 Foundation Sunshine / 原版 Sunshine；按 GPU 选 NVENC/QSV/AMF；一键写入低延迟参数（增量改键、自动备份、可还原）；启停 Sunshine、打开 Web 后台、看日志 |
| 显示与网络 | 活动显示器列表、VDD 判定与熄屏清单、Tailscale 直连/中继状态、网关延迟诊断 |
| 体检报告 | 9 项检查的评分与建议、纯文本预览、保存 TXT/JSON、复制全文 |
| 关于 | 版本、协议、数据目录、许可与致谢、命令行与自检 |

## 运行

要求：Windows 10 22H2+，Python 3.10+，**只依赖标准库**（tkinter 随 Python 安装）。

```bat
cd padlink\host-windows
run.bat
rem 或者
python -m padlink
```

首次启动会在 `%APPDATA%\Win-Pad Connect\` 下建立 `settings.json`、`backups\`、`reports\`；若 `%APPDATA%` 不可写，会退到 `%LOCALAPPDATA%`、程序目录 `.padlink-data`（也可用环境变量 `PADLINK_DATA_DIR` 指定）。

命令行：

```bat
python -m padlink --smoke-test          # 不打开窗口，打印体检与 profile 摘要
python -m padlink --port 47900 --no-pairing
python -m padlink --page sunshine --exit-after 5   # 指定页 + 5 秒后退出（截图用）
python -m padlink --version
```

## 截图

| | |
|---|---|
| ![接入服务](shots/service.png) | ![Sunshine 配置](shots/sunshine.png) |
| ![显示与网络](shots/network.png) | ![体检报告](shots/report.png) |

## 设计要点

- **只改官方配置**：`sunshine.apply_profile()` 逐键替换，保留注释与其他键；写前备份到同目录 `sunshine.conf.<stamp>.bak`，失败即中止，不留半写文件。
- **探测不依赖子进程**：GPU 走注册表、显示器走 `EnumDisplayDevices/EnumDisplaySettings`、网关走 `GetIpForwardTable`、地址走 socket。没有管理员权限或 WMI 被禁用时仍能工作。
- **VDD 分级**：ZakoVDD 记“通过”，spacedesk 等记“可改进”，没装记“未完成”，不会把“不是最优”误报成“不可用”。
- **服务只读**：HTTP 只下发 profile、ping、测速与健康状态；所有写操作留在桌面界面。
- **配对码是握手级校验**：6 位数字、可关闭、可更换；不参与视频链路加密。

## 目录

```
host-windows/
├── padlink/
│   ├── platform_windows.py   # 注册表/显示器/网络/进程探针
│   ├── sunshine.py           # 探测、低延迟 profile、备份/还原、启停
│   ├── tailscale.py          # status --json 解析，直连/中继判定
│   ├── snapshot.py           # 主机快照与档位
│   ├── checks.py             # 9 项体检与评分
│   ├── profile.py            # 协议 v1 JSON
│   ├── handoff.py            # HTTP + UDP 发现服务
│   ├── settings.py / paths.py
│   └── ui/                   # theme / widgets / app / pages
├── tests/test_core.py        # 19 项离线测试
├── tools/shot.py             # PrintWindow 截图（验收用）
├── shots/                    # 六页截图
└── run.bat
```

## 测试

```bat
cd padlink\host-windows
python -m unittest discover -s tests -v
```

19 项全部离线，不写真实 `%APPDATA%`（测试把 `PADLINK_DATA_DIR` 指向 `tests/.tmp`），不需要 Sunshine 或网络。

## 已知限制

- 未安装 Sunshine 时，Sunshine 页大部分按钮不可用，这是预期行为；先按 [部署手册](../docs/deployment.md) 安装基线。
- 无管理员权限时不能写 `Program Files` 下的配置，会给出明确提示而不是静默失败。
- GPU 只按厂商关键字映射编码器（nvidia/intel/amd），多显卡机器按“推荐编码器”选对应 GPU，不做性能基准。

## 许可

Win-Pad Connect 自身 MIT。它探测/配置的 Foundation Sunshine、Sunshine、moonlight-android 均为 GPL-3.0；若分发包含这些修改版的组合包，需按 GPL-3.0 开源相应修改。

## 作者

- 作者：lzx_xkzdwb
- GitHub：<https://github.com/xkzdwb>
- 项目仓库：<https://github.com/xkzdwb/WinPad-Connect>
