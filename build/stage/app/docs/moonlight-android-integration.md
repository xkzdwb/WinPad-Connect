# 在 moonlight-android fork 上启用原生触控（四指手势）

这份文档对应提纲里**投入产出比最高的一个代码级改动**：Moonlight Android 已经实现了原生触控，但与“三指呼出键盘”冲突，被注释掉了。我们要做的是取消注释、把键盘手势从三指改成四指，然后验证手感。

> 前提：本仓库没有附带 moonlight-android 的源码，也不伪造 patch。下面给出的是可照着操作的定位方法、改动形状与验收标准；具体行号以你选定的 fork 版本为准。

## 0. 选基线

| 候选 | 特点 | 建议 |
|---|---|---|
| `Axixi2233/moonlight-android` | 多种鼠标模式、触控板模式、虚拟触控板灵敏度 | 首选：手势语义完整，改动面最小 |
| `a2012s/moonlight-android_axixi` | 在上一者基础上的整合分支 | 若前者更新停滞可用 |

官方 `moonlight-stream/moonlight-android` 不建议用来硬补触控：从零补齐的代码量远大于在 fork 上改手势冲突。

## 1. 定位原生触控代码

在 fork 根目录执行：

```bash
grep -rn "THREE_FINGER_TAP_THRESHOLD" app/src/main/java
grep -rn "三指\|three.finger\|threeFinger" app/src/main/java
grep -rn "touch.*disabled\|isTouchEnabled\|nativeTouch" app/src/main/java
```

预期命中 `Game.java`（路径通常是 `app/src/main/java/com/limelight/game/Game.java`），里面有一段被注释的原生触控分发逻辑（把 `MotionEvent` 直接映射为鼠标位置/按键，而不是走触控板相对位移）。同时会看到三指轻点呼出键盘的判定，阈值常量名为 `THREE_FINGER_TAP_THRESHOLD`。

把命中的注释块与相关设置项列出来，确认三件事：

1. 原生触控路径确实存在，只是被 `//` 或 `/* */` 包住；
2. 阻塞点只有“与三指手势冲突”，不是缺少输入注入通道；
3. 设置项 `touchscreen as touchpad`（触控屏作为触摸板）能关掉——关掉后才走原生触控。

## 2. 改动一：取消原生触控注释

只恢复**输入分发**相关代码，不要顺手恢复无关的实验代码。恢复后应满足：

- 单指按下 → `ACTION_DOWN` 映射为绝对坐标的鼠标左键按下；
- 单指移动 → 绝对坐标移动（不是相对位移）；
- 单指抬起 → 左键抬起；
- 双指 → 滚动（保留 fork 原有实现，不要改语义）。

如果恢复后出现“点击落在屏幕外”或“坐标偏移”，先检查是否漏了 `renderView` 的缩放换算（Moonlight 的 `StreamView` 会把视频坐标系映射到 View 坐标系），不要改协议层。

## 3. 改动二：三指 → 四指

在 `Game.java` 的手势判定处：

1. 把 `THREE_FINGER_TAP_THRESHOLD` 改名为 `FOUR_FINGER_TAP_THRESHOLD`（或新增常量并删除旧引用）；
2. 判定条件从 `pointerCount == 3` 改为 `pointerCount == 4`；
3. 增加“按下窗口 / 轻点时长 / 位移容差”三个判断，避免四指拖动时误触。

参数可直接照搬本仓库 `pad-android/app/src/main/java/com/padlink/pad/core/FourFingerTapDetector.java`：

| 参数 | 值 | 作用 |
|---|---|---|
| `spreadMs` | 250 | 四指必须在这个窗口内全部按下 |
| `tapMs` | 300 | 第四指按下到最后一指抬起的最长时长 |
| `slopPx` | 24 | 任一手指的累计位移上限（超过即判为拖动） |

该类的 `down/move/up` 返回 `true` 即表示“四指轻点成立”，可以直接把调用点接到原来三指呼出键盘的分支。

如果不想改 `Game.java` 的手写判定，也可以把 `FourFingerTapDetector` 原样拷进 fork，在 `dispatchTouchEvent` 里先喂事件，命中后再执行原来的键盘切换逻辑。

## 4. 改动三：设置项

在 fork 的设置页确认：

- “触控屏作为触摸板使用”（touchscreen as touchpad）默认关闭，或至少在开启原生触控时强制关闭；
- 保留触控板模式作为回退项，不要删除——原生触控在部分应用（需要相对移动的游戏）里不如触控板。

Win-Pad Connect Pad 的四指提示文案与此一致：四指轻点 = 呼出/收起键盘。

## 5. 编译与安装

```bash
cd moonlight-android
./gradlew :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

要求：JDK 17、Android SDK 34、NDK 版本与 fork 的 `build.gradle` 一致（Moonlight 含 native 解码库，缺 NDK 会失败）。

## 6. 验收清单

| # | 操作 | 期望 |
|---|---|---|
| 1 | 关闭“触控屏作为触摸板”，单击桌面图标 | 直接选中/打开，落点与手指一致 |
| 2 | 单指拖动窗口 | 窗口跟手移动，无“漂移” |
| 3 | 双指上下滑 | 页面滚动，方向正确 |
| 4 | 四指轻点 | 呼出/收起软键盘，不触发鼠标点击 |
| 5 | 四指按住拖动 | 不呼出键盘（被 slop 判定取消） |
| 6 | 三指轻点 | 不再呼出键盘（冲突已解除） |
| 7 | 长按 → 右键 | 与 fork 原行为一致 |
| 8 | 串流 10 分钟 | 无触摸事件堆积、无 ANR |

第 1、2 条是“质变”的判据：如果仍然像触控板（相对移动），说明原生触控没有真正启用，回到第 2 步检查设置项与注释块。

## 7. 回退

保留 fork 的触控板模式即可：设置里重新打开“触控屏作为触摸板”，四指手势不影响原有三指以外的操作。代码层面回退只需还原 `Game.java` 的三指判定与注释块，不涉及协议与解码。

## 8. 与 Win-Pad Connect 的分工

- Win-Pad Connect Pad 负责发现、体检、测速、给出档位与码率，并负责把四指手势的**参考实现**交付给你；
- 真正的触控改造发生在这个 fork 里；
- 两者通过 Moonlight 的既有配对流程连接，Win-Pad Connect 不介入视频链路，也不修改 Sunshine 的配对逻辑。
