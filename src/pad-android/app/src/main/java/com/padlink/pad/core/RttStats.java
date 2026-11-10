package com.padlink.pad.core;

import java.util.ArrayList;
import java.util.List;

/**
 * 往返时延统计：平均、最小、最大、抖动（相邻样本差的平均绝对值）与丢包率。
 * 只依赖 Java 标准库，便于在无 Android SDK 的环境里做单元测试。
 */
public final class RttStats {

    private final List<Double> samples = new ArrayList<>();
    private int sent;

    public void reset() {
        samples.clear();
        sent = 0;
    }

    public void recordSuccess(double rttMs) {
        sent++;
        samples.add(rttMs);
    }

    public void recordLoss() {
        sent++;
    }

    public int sent() {
        return sent;
    }

    public int received() {
        return samples.size();
    }

    public double lossPercent() {
        if (sent == 0) {
            return 0;
        }
        return 100.0 * (sent - samples.size()) / sent;
    }

    public double min() {
        if (samples.isEmpty()) {
            return 0;
        }
        double value = Double.MAX_VALUE;
        for (double sample : samples) {
            value = Math.min(value, sample);
        }
        return value;
    }

    public double max() {
        double value = 0;
        for (double sample : samples) {
            value = Math.max(value, sample);
        }
        return value;
    }

    public double average() {
        if (samples.isEmpty()) {
            return 0;
        }
        double sum = 0;
        for (double sample : samples) {
            sum += sample;
        }
        return sum / samples.size();
    }

    /** 抖动：相邻 RTT 样本差的平均绝对值，单位毫秒。 */
    public double jitter() {
        if (samples.size() < 2) {
            return 0;
        }
        double sum = 0;
        for (int i = 1; i < samples.size(); i++) {
            sum += Math.abs(samples.get(i) - samples.get(i - 1));
        }
        return sum / (samples.size() - 1);
    }

    public String verdict() {
        if (samples.isEmpty()) {
            return "未测试";
        }
        double avg = average();
        double loss = lossPercent();
        if (loss >= 5) {
            return "丢包严重，先修网络";
        }
        if (avg <= 10 && jitter() <= 5) {
            return "优秀，接近局域网";
        }
        if (avg <= 20 && jitter() <= 10) {
            return "良好，可办公";
        }
        if (avg <= 40) {
            return "一般，适合轻量操作";
        }
        return "偏高，检查是否走中继";
    }

    public String summary() {
        if (samples.isEmpty()) {
            return "尚无样本";
        }
        return String.format(
                java.util.Locale.US,
                "平均 %.1f ms · 最低 %.1f · 最高 %.1f · 抖动 %.1f · 丢包 %.0f%%",
                average(), min(), max(), jitter(), lossPercent()
        );
    }
}
