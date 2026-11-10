# Win-Pad Connect Pad（Android / OPPO Pad 4 Pro）

配套 [Win-Pad Connect Host](../host-windows/README.md) 的平板端：**发现主机 → 读取体检 → 测链路 → 把参数交给 Moonlight**。

它不实现串流，也不修改 Moonlight 协议；真正的画面与输入由 Sunshine + Moonlight 客户端完成。这样做的原因是：低延迟是这条基线的核心资产，重写传输层会把优势一起丢掉。

## 功能

| 模块 | 说明 |
|---|---|
| 发现主机 | UDP 47801 广播 `PADLINK?1`，主机应答 JSON；收不到广播时可手动填 IP |
| 配对 | 主机开启 6 位配对码时，HTTP 401 会弹出输入框，成功后本地保存 |
| 体检摘要 | 显示主机名、编码器、就绪度分数、未通过检查项与建议 |
| 分辨率档位 | 1080p / 2.5K / 原生 3.4K 三档，来自主机 profile，可保存首选档 |
| 链路自测 | 10 次 HTTP RTT（平均/最低/最高/抖动/丢包）+ 8MB 下载吞吐 |
| 码率建议 | 依据实测吞吐与 RTT 选档并给出 Mbps（留 25% 余量，丢包/高延迟再下调） |
| 启动 | 打开 Moonlight（`com.limelight`），并复制 `IP:端口 / 配对码` 到剪贴板 |
| 四指手势 | `core/FourFingerTapDetector`：四指轻点判定，供 Moonlight fork 替换三指手势 |

## 工程结构

```
pad-android/
├── settings.gradle / build.gradle / gradle.properties
├── app/
│   ├── build.gradle                       # AGP 8.5.2, compileSdk 34, minSdk 26, 纯 Java
│   ├── proguard-rules.pro
│   └── src/
│       ├── main/
│       │   ├── AndroidManifest.xml        # INTERNET + 广播相关权限，允许明文 HTTP
│       │   ├── java/com/padlink/pad/
│       │   │   ├── MainActivity.java      # 单 Activity，程序化布局，深色主题
│       │   │   ├── core/                  # 纯 Java，可 javac 直接测试
│       │   │   │   ├── Json.java
│       │   │   │   ├── HostProfile.java   # 协议 v1 模型
│       │   │   │   ├── RttStats.java
│       │   │   │   ├── Throughput.java    # 吞吐换算 + 码率建议
│       │   │   │   └── FourFingerTapDetector.java
│       │   │   └── net/
│       │   │       ├── Discovery.java     # UDP 广播发现
│       │   │       └── HostClient.java    # /ping /profile.json /download
│       │   └── res/values/                # strings / colors / themes
│       └── test/java/com/padlink/pad/core/CoreTests.java
├── run-core-tests.bat / run-core-tests.sh # 32 项核心逻辑测试，无需 Android SDK
└── README.md
```

## 编译 APK

需要 JDK 17+、Android SDK（compileSdk 34）与 Gradle 8.7+（或 Android Studio Ladybug 及以上）。

```bash
# 方式一：Android Studio 打开 pad-android 目录，直接 Run
# 方式二：命令行
cd padlink/pad-android
gradle wrapper          # 首次可在有网络的机器上生成 wrapper
./gradlew :app:assembleDebug
# 产物：app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

说明：

- 未附带 `gradle-wrapper.jar`（二进制，当前环境无法下载）；有 Android Studio 时不需要它，命令行首次用系统 Gradle 生成即可。
- 不依赖 AndroidX / Kotlin / 第三方库，AGP 8.5.2 与 JDK 17 是全部要求。
- 明文 HTTP 仅用于局域网内读取 profile 与测速，不承载视频流；已设 `usesCleartextTraffic="true"`。

## 纯 Java 核心自测

无需 Android SDK，只要 JDK：

```bat
run-core-tests.bat
```

覆盖：JSON 解析与转义、profile 字段映射（含 Tailscale/档位）、RTT 均值/抖动/丢包、吞吐换算、码率建议选档与降档、四指轻点的命中/三指忽略/拖动取消/超时取消。

## 使用流程

1. Windows 上启动 **Win-Pad Connect Host**，点“启动接入服务”，记住配对码。
2. Pad 与电脑连同一 Wi-Fi（异地则两端先登录 Tailscale）。
3. 打开 Win-Pad Connect Pad → “搜索主机” → 点选主机 → 输入配对码。
4. 看“主机体检”：红/黄项按提示回电脑处理；先保证 1080p60 跑通。
5. “测 10 次 RTT”“测 8MB 吞吐”，按建议档位起步。
6. 点“打开 Moonlight”，在 Moonlight 里新增主机并填上方 IP。

## 与 moonlight-android fork 的关系

Win-Pad Connect Pad 是**配套端**，不替换 Moonlight。真正的触控改造在 fork 内完成：

- 取消 `Game.java` 中原生触控相关注释；
- 把三指呼出键盘改为四指轻点（可直接照搬 `FourFingerTapDetector` 的判定参数：250ms 按下窗口、300ms 轻点、24px 容差）；
- 设置里关闭“触控屏作为触摸板使用”。

详细步骤与验收点见 [docs/moonlight-android-integration.md](../docs/moonlight-android-integration.md)。

## 作者

- 作者：lzx_xkzdwb
- GitHub：<https://github.com/xkzdwb>
- 项目仓库：<https://github.com/xkzdwb/WinPad-Connect>
