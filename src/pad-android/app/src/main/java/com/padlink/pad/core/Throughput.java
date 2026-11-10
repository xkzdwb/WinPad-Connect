package com.padlink.pad.core;

import java.util.List;
import java.util.Locale;

/**
 * 吞吐测量与码率建议。
 *
 * <p>测量本身由 Android 端的 {@code HostClient.download} 完成，这里只做纯计算：
 * 给定下载字节数与耗时，换算成 Mbps，再结合 RTT / 丢包给出「档位 + 码率」建议。</p>
 */
public final class Throughput {

    private Throughput() {
    }

    /** 字节数与纳秒耗时 → Mbps。 */
    public static double mbps(long bytes, long nanos) {
        if (bytes <= 0 || nanos <= 0) {
            return 0;
        }
        return bytes * 8.0 / (nanos / 1_000_000_000.0) / 1_000_000.0;
    }

    /** 根据实测吞吐与 RTT 选档位。返回建议的档位与码率。 */
    public static Recommendation recommend(List<HostProfile.Tier> tiers, double measuredMbps,
                                           RttStats rtt) {
        if (tiers == null || tiers.isEmpty()) {
            throw new IllegalArgumentException("至少需要一个档位");
        }
        double loss = rtt == null ? 0 : rtt.lossPercent();
        double avg = rtt == null ? 0 : rtt.average();

        // 留 25% 余量；丢包或高延迟时进一步下调。
        double budget = measuredMbps * 0.75;
        if (loss >= 2) {
            budget *= 0.8;
        }
        if (avg >= 40) {
            budget *= 0.85;
        }

        HostProfile.Tier best = tiers.get(0);
        for (HostProfile.Tier tier : tiers) {
            if (tier.bitrateKbps / 1000.0 <= budget) {
                best = tier;
            }
        }

        int kbps = best.bitrateKbps;
        String note;
        if (best.bitrateKbps / 1000.0 > budget) {
            kbps = Math.max(5000, (int) Math.round(measuredMbps * 1000 * 0.7));
            note = "实测带宽不足最低档，码率下调到 " + (kbps / 1000) + "Mbps";
        } else if (measuredMbps < 25) {
            note = "带宽偏紧，保持 1080p 并关闭高动态场景";
        } else if (loss >= 2) {
            note = "有丢包，适当降码率可减少卡顿";
        } else if (avg >= 30) {
            note = "延迟偏高，优先排查中继与 Wi-Fi 干扰";
        } else {
            note = "带宽余量充足，可按建议档位起步";
        }
        return new Recommendation(tiers.indexOf(best), best, kbps, note);
    }

    public static final class Recommendation {
        public final int index;
        public final HostProfile.Tier tier;
        public final int bitrateKbps;
        public final String note;

        public Recommendation(int index, HostProfile.Tier tier, int bitrateKbps, String note) {
            this.index = index;
            this.tier = tier;
            this.bitrateKbps = bitrateKbps;
            this.note = note;
        }

        public String describe() {
            return String.format(
                    Locale.US,
                    "%s · %d×%d · %d Mbps — %s",
                    tier.label, tier.width, tier.height, bitrateKbps / 1000, note
            );
        }
    }
}
