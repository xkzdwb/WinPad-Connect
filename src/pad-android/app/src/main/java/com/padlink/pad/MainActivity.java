package com.padlink.pad;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import com.padlink.pad.core.HostProfile;
import com.padlink.pad.core.RttStats;
import com.padlink.pad.core.Throughput;
import com.padlink.pad.net.Discovery;
import com.padlink.pad.net.HostClient;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Win-Pad Connect Pad：在 OPPO Pad 4 Pro 上发现主机、读取体检结论、测链路，
 * 然后把连接参数交给 Moonlight（moonlight-android 触控 fork）。
 */
public class MainActivity extends Activity {

    private static final int BG = Color.parseColor("#0B1220");
    private static final int CARD = Color.parseColor("#131E33");
    private static final int CARD_ALT = Color.parseColor("#17243C");
    private static final int TEXT = Color.parseColor("#E6EDF7");
    private static final int MUTED = Color.parseColor("#8DA2C0");
    private static final int FAINT = Color.parseColor("#5D7290");
    private static final int ACCENT = Color.parseColor("#3DDC97");
    private static final int BLUE = Color.parseColor("#5AA9FF");
    private static final int AMBER = Color.parseColor("#F5B83D");
    private static final int RED = Color.parseColor("#FF6B6B");
    private static final int BORDER = Color.parseColor("#22324F");

    private static final String PREFS = "padlink";
    private static final String MOONLIGHT_PACKAGE = "com.limelight";

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final ExecutorService io = Executors.newCachedThreadPool();
    private final RttStats rtt = new RttStats();
    private final List<Discovery.FoundHost> discovered = new ArrayList<>();

    private SharedPreferences prefs;
    private HostProfile profile;
    private String hostIp = "";
    private int hostPort = HostClient.DEFAULT_PORT;
    private String pairingCode = "";
    private int selectedTier = 0;
    private double measuredMbps = 0;
    private Throughput.Recommendation recommendation;

    private TextView discoveryStatus;
    private TextView hostSummary;
    private TextView profileTitle;
    private TextView profileMeta;
    private TextView scoreText;
    private TextView rttText;
    private TextView throughputText;
    private TextView advisorText;
    private LinearLayout hostList;
    private LinearLayout checksBox;
    private RadioGroup tierGroup;
    private EditText manualIp;
    private Button scanButton;
    private Button testRttButton;
    private Button testThroughputButton;
    private ProgressBar busyBar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(BG);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        hostIp = prefs.getString("host", "");
        hostPort = prefs.getInt("port", HostClient.DEFAULT_PORT);
        pairingCode = prefs.getString("code", "");
        selectedTier = prefs.getInt("tier", 0);

        setContentView(buildUi());
        if (!hostIp.isEmpty()) {
            discoveryStatus.setText("上次连接：" + hostIp + ":" + hostPort);
            connect(hostIp, hostPort, pairingCode, false);
        }
    }

    @Override
    protected void onDestroy() {
        io.shutdownNow();
        super.onDestroy();
    }

    // ------------------------------------------------------------------ UI

    private View buildUi() {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(BG);
        scroll.setFillViewport(true);

        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(18);
        page.setPadding(pad, dp(22), pad, dp(28));
        scroll.addView(page, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView title = text("Win-Pad Connect Pad", 26, TEXT, Typeface.BOLD);
        page.addView(title);
        TextView subtitle = text("OPPO Pad 4 Pro · 主机体检、链路自测与 Moonlight 接入", 13, MUTED, Typeface.NORMAL);
        subtitle.setPadding(0, dp(4), 0, dp(18));
        page.addView(subtitle);

        page.addView(buildDiscoveryCard());
        page.addView(buildProfileCard());
        page.addView(buildNetworkCard());
        page.addView(buildLaunchCard());

        TextView footer = text("Win-Pad Connect 只负责“连得上、看得懂、测得准”；画面与输入由 Moonlight + Sunshine 完成。\n"
                + "四指轻点呼出键盘的逻辑随包提供（core/FourFingerTapDetector），接入说明见文档。", 11, FAINT, Typeface.NORMAL);
        footer.setPadding(0, dp(14), 0, 0);
        page.addView(footer);
        return scroll;
    }

    private View buildDiscoveryCard() {
        LinearLayout card = card("发现主机");
        discoveryStatus = text("未连接。点“搜索主机”或手动填地址。", 13, MUTED, Typeface.NORMAL);
        card.addView(discoveryStatus);

        LinearLayout buttons = row();
        scanButton = button("搜索主机", ACCENT, this::startDiscovery);
        buttons.addView(scanButton);
        buttons.addView(button("重新连接", BLUE, () -> connect(hostIp, hostPort, pairingCode, true)));
        card.addView(buttons);

        manualIp = new EditText(this);
        manualIp.setHint("手动输入主机 IP，例如 10.89.166.118");
        manualIp.setTextColor(TEXT);
        manualIp.setHintTextColor(FAINT);
        manualIp.setInputType(InputType.TYPE_CLASS_TEXT);
        manualIp.setTextSize(13);
        manualIp.setSingleLine(true);
        manualIp.setBackground(roundRect(CARD_ALT, BORDER, dp(10)));
        manualIp.setPadding(dp(12), dp(8), dp(12), dp(8));
        LinearLayout.LayoutParams ipParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        ipParams.topMargin = dp(10);
        card.addView(manualIp, ipParams);

        LinearLayout manualRow = row();
        manualRow.addView(button("连接此地址", BLUE, () -> {
            String ip = manualIp.getText().toString().trim();
            if (ip.isEmpty()) {
                toast("先填主机 IP");
                return;
            }
            connect(ip, hostPort, pairingCode, false);
        }));

        busyBar = new ProgressBar(this, null, android.R.attr.progressBarStyleSmall);
        busyBar.setVisibility(View.GONE);
        LinearLayout.LayoutParams busyParams = new LinearLayout.LayoutParams(dp(22), dp(22));
        busyParams.leftMargin = dp(10);
        manualRow.addView(busyBar, busyParams);
        card.addView(manualRow);

        hostList = new LinearLayout(this);
        hostList.setOrientation(LinearLayout.VERTICAL);
        card.addView(hostList);
        return card;
    }

    private View buildProfileCard() {
        LinearLayout card = card("主机体检");
        hostSummary = text("连接后显示主机名、编码器、就绪度与待处理项。", 13, MUTED, Typeface.NORMAL);
        card.addView(hostSummary);

        LinearLayout scoreRow = row();
        scoreText = text("--", 30, ACCENT, Typeface.BOLD);
        scoreRow.addView(scoreText);
        profileTitle = text("", 16, TEXT, Typeface.BOLD);
        profileTitle.setPadding(dp(14), dp(12), 0, 0);
        scoreRow.addView(profileTitle);
        card.addView(scoreRow);

        profileMeta = text("", 12, MUTED, Typeface.NORMAL);
        profileMeta.setPadding(0, dp(2), 0, dp(8));
        card.addView(profileMeta);

        checksBox = new LinearLayout(this);
        checksBox.setOrientation(LinearLayout.VERTICAL);
        card.addView(checksBox);

        TextView tierLabel = text("分辨率档位", 13, TEXT, Typeface.BOLD);
        tierLabel.setPadding(0, dp(12), 0, dp(4));
        card.addView(tierLabel);
        tierGroup = new RadioGroup(this);
        tierGroup.setOrientation(RadioGroup.VERTICAL);
        card.addView(tierGroup);

        card.addView(button("保存档位", BLUE, () -> {
            int checked = tierGroup.getCheckedRadioButtonId();
            if (checked >= 0) {
                selectedTier = checked - 1;
                prefs.edit().putInt("tier", selectedTier).apply();
                toast("已保存为启动时的首选档位");
            }
        }));
        return card;
    }

    private View buildNetworkCard() {
        LinearLayout card = card("链路自测");
        rttText = text("RTT：未测", 13, MUTED, Typeface.NORMAL);
        card.addView(rttText);
        throughputText = text("吞吐：未测（建议连 Wi-Fi 6 后跑一次）", 13, MUTED, Typeface.NORMAL);
        throughputText.setPadding(0, dp(4), 0, dp(8));
        card.addView(throughputText);

        LinearLayout buttons = row();
        testRttButton = button("测 10 次 RTT", BLUE, this::runRttTest);
        buttons.addView(testRttButton);
        testThroughputButton = button("测 8MB 吞吐", BLUE, this::runThroughputTest);
        buttons.addView(testThroughputButton);
        card.addView(buttons);

        advisorText = text("测完吞吐后给出码率建议。", 12, FAINT, Typeface.NORMAL);
        advisorText.setPadding(0, dp(10), 0, 0);
        card.addView(advisorText);
        return card;
    }

    private View buildLaunchCard() {
        LinearLayout card = card("开始串流");
        TextView hint = text("1. 确认主机 Sunshine 已启动；\n"
                + "2. 在 Moonlight 中新增主机，填上面的 IP；\n"
                + "3. 首选 1080p60，跑顺后再升到 2.5K / 原生。", 13, MUTED, Typeface.NORMAL);
        card.addView(hint);

        LinearLayout buttons = row();
        buttons.addView(button("打开 Moonlight", ACCENT, this::launchMoonlight));
        buttons.addView(button("复制连接信息", BLUE, this::copyConnection));
        card.addView(buttons);

        TextView gesture = text("手势提示：启用原生触控后，四指轻点呼出键盘；三指手势留给系统与 Moonlight。",
                12, FAINT, Typeface.NORMAL);
        gesture.setPadding(0, dp(10), 0, 0);
        card.addView(gesture);
        return card;
    }

    // -------------------------------------------------------------- 发现/连接

    private void startDiscovery() {
        if (scanButton.isEnabled() == false) {
            return;
        }
        scanButton.setEnabled(false);
        busyBar.setVisibility(View.VISIBLE);
        discoveryStatus.setText("正在广播搜索，保持平板与电脑在同一 Wi-Fi…");
        hostList.removeAllViews();
        discovered.clear();
        io.submit(() -> Discovery.scan(2200, new Discovery.Listener() {
            @Override
            public void onFound(Discovery.FoundHost host) {
                mainHandler.post(() -> addHostRow(host));
            }

            @Override
            public void onFinished(int total, String error) {
                mainHandler.post(() -> {
                    scanButton.setEnabled(true);
                    busyBar.setVisibility(View.GONE);
                    if (error != null) {
                        discoveryStatus.setText(error + "，可改用手动地址。");
                    } else if (total == 0) {
                        discoveryStatus.setText("没有搜到主机。确认 Win-Pad Connect 已启动，或手动填 IP。");
                    } else {
                        discoveryStatus.setText("发现 " + total + " 台主机，点选即可读取体检。");
                    }
                });
            }
        }));
    }

    private void addHostRow(Discovery.FoundHost host) {
        discovered.add(host);
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(0, dp(8), 0, 0);

        TextView label = text(host.label(), 13, TEXT, Typeface.NORMAL);
        label.setLayoutParams(new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        row.addView(label);
        row.addView(button("连接", ACCENT, () -> connect(host.ip, host.port, pairingCode, false)));
        hostList.addView(row);
    }

    private void connect(String ip, int port, String code, boolean force) {
        if (ip == null || ip.isEmpty()) {
            toast("先选择或填写主机地址");
            return;
        }
        if (!force && ip.equals(hostIp) && profile != null) {
            discoveryStatus.setText("已连接 " + ip + ":" + port);
            return;
        }
        discoveryStatus.setText("正在连接 " + ip + ":" + port + " …");
        busyBar.setVisibility(View.VISIBLE);
        io.submit(() -> {
            try {
                HostClient client = new HostClient(ip, port);
                HostProfile loaded = client.profile(code);
                mainHandler.post(() -> {
                    busyBar.setVisibility(View.GONE);
                    hostIp = ip;
                    hostPort = port;
                    pairingCode = code == null ? "" : code;
                    prefs.edit().putString("host", ip).putInt("port", port)
                            .putString("code", pairingCode).apply();
                    applyProfile(loaded);
                    discoveryStatus.setText("已连接 " + loaded.host.name + " · " + ip + ":" + port);
                });
            } catch (HostClient.UnauthorizedException unauthorized) {
                mainHandler.post(() -> {
                    busyBar.setVisibility(View.GONE);
                    promptPairingCode(ip, port);
                });
            } catch (IOException exc) {
                mainHandler.post(() -> {
                    busyBar.setVisibility(View.GONE);
                    discoveryStatus.setText("连接失败：" + exc.getMessage() + "。确认服务已启动、地址正确。");
                });
            }
        });
    }

    private void promptPairingCode(String ip, int port) {
        EditText input = new EditText(this);
        input.setInputType(InputType.TYPE_CLASS_NUMBER);
        input.setHint("6 位配对码");
        input.setTextColor(TEXT);
        input.setHintTextColor(FAINT);
        new AlertDialog.Builder(this)
                .setTitle("需要配对码")
                .setMessage("主机开启了配对校验，请输入 Win-Pad Connect 界面上显示的 6 位数字。")
                .setView(input)
                .setPositiveButton("连接", (dialog, which) -> {
                    String code = input.getText().toString().trim();
                    connect(ip, port, code, true);
                })
                .setNegativeButton("取消", null)
                .show();
    }

    private void applyProfile(HostProfile loaded) {
        profile = loaded;
        scoreText.setText(String.valueOf(loaded.readiness.score));
        scoreText.setTextColor(loaded.readiness.score >= 85 ? ACCENT
                : loaded.readiness.score >= 60 ? AMBER : RED);
        profileTitle.setText(loaded.host.name);
        hostSummary.setText(loaded.sunshine.installed
                ? (loaded.sunshine.running ? "Sunshine 运行中" : "Sunshine 已安装但未运行")
                : "未检测到 Sunshine，先在电脑上装好基线");
        profileMeta.setText(loaded.host.encoderLabel + " · " + loaded.host.os + "\n"
                + "局域网 " + loaded.network.primary
                + (loaded.network.tailscale.installed
                ? " · Tailscale " + loaded.network.tailscale.state + " " + loaded.network.tailscale.ipv4
                : " · 未装 Tailscale"));

        checksBox.removeAllViews();
        for (HostProfile.Check check : loaded.readiness.checks) {
            if ("ok".equals(check.status)) {
                continue;
            }
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setPadding(0, dp(5), 0, dp(5));
            TextView dot = text("●", 10, statusColor(check.status), Typeface.NORMAL);
            dot.setPadding(0, dp(4), dp(8), 0);
            row.addView(dot);
            LinearLayout body = new LinearLayout(this);
            body.setOrientation(LinearLayout.VERTICAL);
            body.addView(text(check.title, 13, TEXT, Typeface.BOLD));
            body.addView(text(check.detail, 11, MUTED, Typeface.NORMAL));
            row.addView(body);
            checksBox.addView(row);
        }
        if (checksBox.getChildCount() == 0) {
            checksBox.addView(text("全部检查通过，可以开始串流。", 13, ACCENT, Typeface.NORMAL));
        }

        tierGroup.removeAllViews();
        int index = 0;
        int checkId = -1;
        for (HostProfile.Tier tier : loaded.client.tiers) {
            RadioButton radio = new RadioButton(this);
            radio.setId(index + 1);
            radio.setText(tier.label + "  ·  " + tier.detail());
            radio.setTextColor(TEXT);
            radio.setTextSize(13);
            radio.setButtonTintList(android.content.res.ColorStateList.valueOf(ACCENT));
            tierGroup.addView(radio);
            if (index == selectedTier) {
                checkId = index + 1;
            }
            index++;
        }
        if (checkId >= 0) {
            tierGroup.check(checkId);
        }
        advisorText.setText(loaded.client.note.isEmpty()
                ? "测完吞吐后给出码率建议。" : loaded.client.note);
    }

    // ------------------------------------------------------------------ 测试

    private void runRttTest() {
        if (hostIp.isEmpty()) {
            toast("先连接主机");
            return;
        }
        testRttButton.setEnabled(false);
        rttText.setText("测试中…");
        io.submit(() -> {
            rtt.reset();
            HostClient client = new HostClient(hostIp, hostPort, 2000, 3000);
            for (int i = 0; i < 10; i++) {
                try {
                    rtt.recordSuccess(client.ping());
                } catch (IOException exc) {
                    rtt.recordLoss();
                }
                try {
                    Thread.sleep(120);
                } catch (InterruptedException exc) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
            mainHandler.post(() -> {
                testRttButton.setEnabled(true);
                rttText.setText("RTT：" + rtt.summary() + "\n" + rtt.verdict());
                rttText.setTextColor(rttColor());
                updateAdvisor();
            });
        });
    }

    private int rttColor() {
        if (rtt.received() == 0) {
            return RED;
        }
        double avg = rtt.average();
        return avg <= 20 ? ACCENT : avg <= 40 ? AMBER : RED;
    }

    private void runThroughputTest() {
        if (hostIp.isEmpty()) {
            toast("先连接主机");
            return;
        }
        testThroughputButton.setEnabled(false);
        throughputText.setText("下载 8MB 测试数据…");
        io.submit(() -> {
            HostClient client = new HostClient(hostIp, hostPort, 3000, 15000);
            long start = System.nanoTime();
            try {
                long bytes = client.download(8, (received, total) ->
                        mainHandler.post(() -> throughputText.setText(
                                "下载中 " + (received * 100 / Math.max(1, total)) + "%")));
                double seconds = (System.nanoTime() - start) / 1_000_000_000.0;
                measuredMbps = Throughput.mbps(bytes, System.nanoTime() - start);
                mainHandler.post(() -> {
                    testThroughputButton.setEnabled(true);
                    throughputText.setText(String.format(Locale.US,
                            "吞吐：%.1f Mbps（%.1f MB / %.2f s）· %s",
                            measuredMbps, bytes / 1024.0 / 1024.0, seconds, throughputVerdict()));
                    throughputText.setTextColor(measuredMbps >= 30 ? ACCENT : measuredMbps >= 12 ? AMBER : RED);
                    if (profile != null) {
                        recommendation = Throughput.recommend(profile.client.tiers, measuredMbps, rtt);
                        if (recommendation.index >= 0) {
                            selectedTier = recommendation.index;
                            tierGroup.check(selectedTier);
                        }
                    }
                    updateAdvisor();
                });
            } catch (IOException exc) {
                mainHandler.post(() -> {
                    testThroughputButton.setEnabled(true);
                    throughputText.setText("吞吐测试失败：" + exc.getMessage());
                    throughputText.setTextColor(RED);
                });
            }
        });
    }

    private String throughputVerdict() {
        if (measuredMbps >= 60) {
            return "可跑原生 3.4K";
        }
        if (measuredMbps >= 32) {
            return "可跑 2.5K";
        }
        if (measuredMbps >= 16) {
            return "适合 1080p60";
        }
        return "带宽偏低，降码率或换 5GHz/6GHz";
    }

    private void updateAdvisor() {
        if (recommendation != null) {
            advisorText.setText("建议：" + recommendation.describe());
        } else if (profile != null && rtt.received() > 0) {
            advisorText.setText("延迟结论：" + rtt.verdict() + "。再跑一次吞吐即可给出码率建议。");
        }
    }

    // ------------------------------------------------------------------ 启动

    private void launchMoonlight() {
        if (hostIp.isEmpty()) {
            toast("先连接一台主机");
            return;
        }
        Intent launch = getPackageManager().getLaunchIntentForPackage(MOONLIGHT_PACKAGE);
        if (launch == null) {
            new AlertDialog.Builder(this)
                    .setTitle("未安装 Moonlight")
                    .setMessage("请先安装 moonlight-android 触控 fork（或其修改版），再回来点此按钮。\n\n"
                            + "连接参数：主机 " + hostIp + ":" + hostPort
                            + (pairingCode.isEmpty() ? "" : "，配对码 " + pairingCode))
                    .setPositiveButton("去应用商店", (dialog, which) -> {
                        try {
                            startActivity(new Intent(Intent.ACTION_VIEW,
                                    Uri.parse("market://details?id=" + MOONLIGHT_PACKAGE)));
                        } catch (Exception exc) {
                            toast("没有可用的应用商店");
                        }
                    })
                    .setNegativeButton("知道了", null)
                    .show();
            return;
        }
        copyConnection();
        toast("已打开 Moonlight，连接参数已复制");
        startActivity(launch);
    }

    private void copyConnection() {
        String text = "主机 " + (hostIp.isEmpty() ? "未连接" : hostIp + ":" + hostPort)
                + (pairingCode.isEmpty() ? "" : "\n配对码 " + pairingCode);
        ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (clipboard != null) {
            clipboard.setPrimaryClip(ClipData.newPlainText("Win-Pad Connect", text));
            toast("已复制连接信息");
        }
    }

    // ------------------------------------------------------------------ 小工具

    private LinearLayout card(String title) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(16), dp(16), dp(16));
        card.setBackground(roundRect(CARD, BORDER, dp(14)));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = dp(14);
        card.setLayoutParams(params);

        TextView heading = text(title, 15, TEXT, Typeface.BOLD);
        heading.setPadding(0, 0, 0, dp(10));
        card.addView(heading);
        return card;
    }

    private LinearLayout row() {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(0, dp(10), 0, 0);
        return row;
    }

    private TextView text(String value, int size, int color, int style) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setTypeface(Typeface.create("sans-serif", style));
        view.setLineSpacing(dp(3), 1f);
        return view;
    }

    private Button button(String label, int color, Runnable action) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setTextSize(13);
        button.setTextColor(color);
        button.setBackground(roundRect(withAlpha(color, 0.12f), color, dp(10)));
        button.setPadding(dp(14), dp(8), dp(14), dp(8));
        button.setOnClickListener(view -> action.run());
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.rightMargin = dp(8);
        button.setLayoutParams(params);
        return button;
    }

    private GradientDrawable roundRect(int fill, int stroke, int radius) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fill);
        drawable.setCornerRadius(radius);
        drawable.setStroke(dp(1), stroke);
        return drawable;
    }

    private int withAlpha(int color, float alpha) {
        return Color.argb((int) (255 * alpha), Color.red(color), Color.green(color), Color.blue(color));
    }

    private int statusColor(String status) {
        switch (status) {
            case "ok":
                return ACCENT;
            case "warn":
                return AMBER;
            case "fail":
                return RED;
            default:
                return FAINT;
        }
    }

    private void toast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }

    private int dp(int value) {
        return Math.round(getResources().getDisplayMetrics().density * value);
    }
}
