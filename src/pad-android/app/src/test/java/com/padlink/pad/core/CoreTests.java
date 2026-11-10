package com.padlink.pad.core;

import java.util.Arrays;
import java.util.List;

/**
 * 纯 Java 核心测试。无需 JUnit / Android SDK：
 * <pre>javac -d out $(find app/src/main/java/com/padlink/pad/core -name '*.java') app/src/test/java/com/padlink/pad/core/CoreTests.java</pre>
 */
public final class CoreTests {

    private static int passed;
    private static int failed;

    public static void main(String[] args) {
        testJson();
        testProfile();
        testRtt();
        testThroughput();
        testAdvisor();
        testFourFingerTap();

        System.out.println();
        System.out.println("通过 " + passed + " 项，失败 " + failed + " 项");
        if (failed > 0) {
            System.exit(1);
        }
    }

    private static void testJson() {
        String body = "{\"service\":\"padlink\",\"protocol\":1,\"ok\":true,"
                + "\"ips\":[\"10.0.0.2\",\"100.64.0.3\"],\"escaped\":\"a\\\"b\\n\"}";
        java.util.Map<String, Object> json = Json.parseObject(body);
        check("json service", "padlink".equals(Json.string(json, "service", "")));
        check("json int", Json.integer(json, "protocol", 0) == 1);
        check("json bool", Json.bool(json, "ok", false));
        check("json array", Json.array(json.get("ips")).size() == 2);
        check("json escape", "a\"b\n".equals(Json.string(json, "escaped", "")));
    }

    private static void testProfile() {
        String body = "{\"service\":\"padlink\",\"protocol\":1,\"app\":\"Win-Pad Connect Host 1.0.0\","
                + "\"host\":{\"name\":\"XKlcq-MDesktop\",\"os\":\"Windows 11\",\"cpu\":\"i7-13700HX\","
                + "\"ram_gb\":15.7,\"gpu\":\"RTX 5060\",\"encoder\":\"nvenc\","
                + "\"encoder_label\":\"NVIDIA NVENC\",\"admin\":false},"
                + "\"sunshine\":{\"installed\":true,\"running\":true,\"version\":\"2026.1\",\"web\":\"https://localhost:47990\",\"locked\":true},"
                + "\"display\":{\"detected\":true,\"kind\":\"ZakoVDD\",\"resolution\":\"3392x2400\",\"supports_pad\":true},"
                + "\"network\":{\"lan\":[\"10.89.166.118\"],\"primary\":\"10.89.166.118\","
                + "\"tailscale\":{\"installed\":true,\"state\":\"直连\",\"ipv4\":\"100.64.0.3\",\"direct\":2,\"relay\":0},"
                + "\"service_port\":47800},"
                + "\"client\":{\"tiers\":["
                + "{\"label\":\"流畅 1080p\",\"width\":1920,\"height\":1080,\"fps\":60,\"bitrate_kbps\":20000},"
                + "{\"label\":\"原生 3.4K\",\"width\":3392,\"height\":2400,\"fps\":60,\"bitrate_kbps\":70000}],"
                + "\"fps\":60,\"codec\":\"HEVC\",\"note\":\"以实测吞吐为准\"},"
                + "\"readiness\":{\"score\":86,\"checks\":[{\"key\":\"sunshine\",\"title\":\"Sunshine 基线\",\"status\":\"ok\",\"detail\":\"已安装\"}]},"
                + "\"service_info\":{\"running\":true,\"port\":47800,\"code_required\":true}}";

        HostProfile profile = HostProfile.parse(body);
        check("profile host", "XKlcq-MDesktop".equals(profile.host.name));
        check("profile encoder", "nvenc".equals(profile.host.encoder));
        check("profile score", profile.readiness.score == 86);
        check("profile tiers", profile.client.tiers.size() == 2);
        check("profile tier detail", profile.client.tiers.get(1).detail().contains("3392×2400"));
        check("profile tailscale", profile.network.tailscale.ipv4.equals("100.64.0.3"));
        check("profile connect host", profile.network.connectHost(true).equals("100.64.0.3"));
        check("profile connect lan", profile.network.connectHost(false).equals("10.89.166.118"));
        check("profile checks", profile.readiness.checks.get(0).status.equals("ok"));
    }

    private static void testRtt() {
        RttStats stats = new RttStats();
        stats.recordSuccess(10);
        stats.recordSuccess(14);
        stats.recordSuccess(12);
        stats.recordLoss();
        check("rtt avg", Math.abs(stats.average() - 12.0) < 0.001);
        check("rtt min", stats.min() == 10.0);
        check("rtt max", stats.max() == 14.0);
        check("rtt jitter", Math.abs(stats.jitter() - 3.0) < 0.001);
        check("rtt loss", Math.abs(stats.lossPercent() - 25.0) < 0.001);
        check("rtt verdict", stats.verdict().contains("丢包"));
    }

    private static void testThroughput() {
        double mbps = Throughput.mbps(10L * 1024 * 1024, 1_000_000_000L);
        check("throughput 10MB/s", Math.abs(mbps - 83.886) < 0.01);
        check("throughput zero", Throughput.mbps(0, 10) == 0);
    }

    private static void testAdvisor() {
        List<HostProfile.Tier> tiers = Arrays.asList(
                new HostProfile.Tier("流畅 1080p", 1920, 1080, 60, 20000),
                new HostProfile.Tier("均衡 2.5K", 2560, 1600, 60, 40000),
                new HostProfile.Tier("原生 3.4K", 3392, 2400, 60, 70000)
        );
        RttStats good = new RttStats();
        good.recordSuccess(12);
        good.recordSuccess(13);

        Throughput.Recommendation fits = Throughput.recommend(tiers, 45, good);
        check("advisor picks 1080p", fits.index == 0);

        Throughput.Recommendation wide = Throughput.recommend(tiers, 70, good);
        check("advisor picks 2.5K", wide.index == 1);

        Throughput.Recommendation huge = Throughput.recommend(tiers, 110, good);
        check("advisor picks native", huge.index == 2);

        Throughput.Recommendation tiny = Throughput.recommend(tiers, 8, good);
        check("advisor downscales", tiny.bitrateKbps < 20000);
        check("advisor note", !tiny.note.isEmpty());
    }

    private static void testFourFingerTap() {
        FourFingerTapDetector detector = new FourFingerTapDetector();
        for (int id = 0; id < 4; id++) {
            detector.down(id, 100 + id * 10, 200 + id * 10, 1000 + id * 40);
        }
        boolean firstUp = detector.up(0, 1150);
        detector.up(1, 1160);
        detector.up(2, 1170);
        boolean lastUp = detector.up(3, 1180);
        check("four finger up not yet", !firstUp);
        check("four finger tap", lastUp);

        FourFingerTapDetector three = new FourFingerTapDetector();
        for (int id = 0; id < 3; id++) {
            three.down(id, 100, 200, 1000 + id * 30);
        }
        three.up(0, 1100);
        three.up(1, 1110);
        boolean threeUp = three.up(2, 1120);
        check("three fingers ignored", !threeUp);

        FourFingerTapDetector drag = new FourFingerTapDetector();
        for (int id = 0; id < 4; id++) {
            drag.down(id, 100, 200, 1000 + id * 20);
        }
        drag.move(0, 100, 260);
        drag.up(0, 1100);
        drag.up(1, 1100);
        drag.up(2, 1100);
        boolean dragUp = drag.up(3, 1100);
        check("four finger drag rejected", !dragUp);

        FourFingerTapDetector slow = new FourFingerTapDetector();
        for (int id = 0; id < 4; id++) {
            slow.down(id, 100, 200, 1000 + id * 300);
        }
        slow.up(0, 2300);
        slow.up(1, 2300);
        slow.up(2, 2300);
        check("slow spread rejected", !slow.up(3, 2300));
    }

    private static void check(String name, boolean ok) {
        if (ok) {
            passed++;
            System.out.println("  PASS  " + name);
        } else {
            failed++;
            System.out.println("  FAIL  " + name);
        }
    }
}
