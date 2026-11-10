package com.padlink.pad.core;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * 主机 profile（协议 v1）的只读模型。字段与 host-windows/padlink/profile.py 一一对应。
 */
public final class HostProfile {

    public static final String SERVICE = "padlink";

    public final String app;
    public final int protocol;
    public final Host host;
    public final Sunshine sunshine;
    public final Display display;
    public final Network network;
    public final Client client;
    public final Readiness readiness;
    public final ServiceInfo serviceInfo;

    private HostProfile(String app, int protocol, Host host, Sunshine sunshine, Display display,
                        Network network, Client client, Readiness readiness, ServiceInfo serviceInfo) {
        this.app = app;
        this.protocol = protocol;
        this.host = host;
        this.sunshine = sunshine;
        this.display = display;
        this.network = network;
        this.client = client;
        this.readiness = readiness;
        this.serviceInfo = serviceInfo;
    }

    public static HostProfile parse(String json) {
        return fromJson(Json.parseObject(json));
    }

    public static HostProfile fromJson(Map<String, Object> root) {
        String service = Json.string(root, "service", "");
        if (!SERVICE.equals(service)) {
            throw new IllegalArgumentException("不是 Win-Pad Connect profile：" + service);
        }
        Map<String, Object> hostJson = Json.object(root.get("host"));
        Map<String, Object> sunJson = Json.object(root.get("sunshine"));
        Map<String, Object> displayJson = Json.object(root.get("display"));
        Map<String, Object> netJson = Json.object(root.get("network"));
        Map<String, Object> clientJson = Json.object(root.get("client"));
        Map<String, Object> readinessJson = Json.object(root.get("readiness"));
        Map<String, Object> infoJson = Json.object(root.get("service_info"));

        Host host = new Host(
                Json.string(hostJson, "name", "未知主机"),
                Json.string(hostJson, "os", ""),
                Json.string(hostJson, "cpu", ""),
                Json.number(hostJson, "ram_gb", 0),
                Json.string(hostJson, "gpu", ""),
                Json.string(hostJson, "encoder", "software"),
                Json.string(hostJson, "encoder_label", ""),
                Json.bool(hostJson, "admin", false)
        );

        Sunshine sunshine = new Sunshine(
                Json.bool(sunJson, "installed", false),
                Json.bool(sunJson, "running", false),
                Json.string(sunJson, "version", ""),
                Json.string(sunJson, "web", ""),
                Json.bool(sunJson, "locked", false)
        );

        Map<String, Object> tailJson = Json.object(netJson.get("tailscale"));
        List<String> lan = new ArrayList<>();
        for (Object item : Json.array(netJson.get("lan"))) {
            if (item != null) {
                lan.add(String.valueOf(item));
            }
        }
        Network network = new Network(
                Collections.unmodifiableList(lan),
                Json.string(netJson, "primary", lan.isEmpty() ? "" : lan.get(0)),
                new Tailscale(
                        Json.bool(tailJson, "installed", false),
                        Json.string(tailJson, "state", "未安装"),
                        Json.string(tailJson, "ipv4", ""),
                        Json.integer(tailJson, "direct", 0),
                        Json.integer(tailJson, "relay", 0)
                ),
                Json.integer(netJson, "service_port", 47800)
        );

        Display display = new Display(
                Json.bool(displayJson, "detected", false),
                Json.string(displayJson, "kind", ""),
                Json.string(displayJson, "name", ""),
                Json.string(displayJson, "resolution", ""),
                Json.string(displayJson, "refresh", ""),
                Json.bool(displayJson, "supports_pad", false)
        );

        List<Tier> tiers = new ArrayList<>();
        for (Object item : Json.array(clientJson.get("tiers"))) {
            Map<String, Object> tierJson = Json.object(item);
            tiers.add(new Tier(
                    Json.string(tierJson, "label", "自定义"),
                    Json.integer(tierJson, "width", 1920),
                    Json.integer(tierJson, "height", 1080),
                    Json.integer(tierJson, "fps", 60),
                    Json.integer(tierJson, "bitrate_kbps", 20000)
            ));
        }
        if (tiers.isEmpty()) {
            tiers.add(new Tier("流畅 1080p", 1920, 1080, 60, 20000));
        }
        Client client = new Client(
                Collections.unmodifiableList(tiers),
                Json.integer(clientJson, "fps", 60),
                Json.string(clientJson, "codec", "H.264"),
                Json.string(clientJson, "note", "")
        );

        List<Check> checks = new ArrayList<>();
        for (Object item : Json.array(readinessJson.get("checks"))) {
            Map<String, Object> checkJson = Json.object(item);
            checks.add(new Check(
                    Json.string(checkJson, "key", ""),
                    Json.string(checkJson, "title", ""),
                    Json.string(checkJson, "status", "unknown"),
                    Json.string(checkJson, "detail", "")
            ));
        }
        Readiness readiness = new Readiness(
                Json.integer(readinessJson, "score", 0),
                Collections.unmodifiableList(checks)
        );

        ServiceInfo serviceInfo = new ServiceInfo(
                Json.bool(infoJson, "running", false),
                Json.integer(infoJson, "port", 47800),
                Json.bool(infoJson, "code_required", true)
        );

        return new HostProfile(
                Json.string(root, "app", ""),
                Json.integer(root, "protocol", 1),
                host, sunshine, display, network, client, readiness, serviceInfo
        );
    }

    /** 用于 UI 的短标签，例如 "NVIDIA NVENC · 1080p60"。 */
    public String headline() {
        return host.encoderLabel.isEmpty() ? host.encoder : host.encoderLabel;
    }

    public static final class Host {
        public final String name;
        public final String os;
        public final String cpu;
        public final double ramGb;
        public final String gpu;
        public final String encoder;
        public final String encoderLabel;
        public final boolean admin;

        Host(String name, String os, String cpu, double ramGb, String gpu,
             String encoder, String encoderLabel, boolean admin) {
            this.name = name;
            this.os = os;
            this.cpu = cpu;
            this.ramGb = ramGb;
            this.gpu = gpu;
            this.encoder = encoder;
            this.encoderLabel = encoderLabel;
            this.admin = admin;
        }
    }

    public static final class Sunshine {
        public final boolean installed;
        public final boolean running;
        public final String version;
        public final String web;
        public final boolean locked;

        Sunshine(boolean installed, boolean running, String version, String web, boolean locked) {
            this.installed = installed;
            this.running = running;
            this.version = version;
            this.web = web;
            this.locked = locked;
        }
    }

    public static final class Display {
        public final boolean detected;
        public final String kind;
        public final String name;
        public final String resolution;
        public final String refresh;
        public final boolean supportsPad;

        Display(boolean detected, String kind, String name, String resolution, String refresh,
                boolean supportsPad) {
            this.detected = detected;
            this.kind = kind;
            this.name = name;
            this.resolution = resolution;
            this.refresh = refresh;
            this.supportsPad = supportsPad;
        }
    }

    public static final class Network {
        public final List<String> lan;
        public final String primary;
        public final Tailscale tailscale;
        public final int servicePort;

        Network(List<String> lan, String primary, Tailscale tailscale, int servicePort) {
            this.lan = lan;
            this.primary = primary;
            this.tailscale = tailscale;
            this.servicePort = servicePort;
        }

        /** 平板应使用的连接地址：优先 Tailscale（异地），否则局域网。 */
        public String connectHost(boolean preferTailscale) {
            if (preferTailscale && !tailscale.ipv4.isEmpty()) {
                return tailscale.ipv4;
            }
            return primary;
        }
    }

    public static final class Tailscale {
        public final boolean installed;
        public final String state;
        public final String ipv4;
        public final int direct;
        public final int relay;

        Tailscale(boolean installed, String state, String ipv4, int direct, int relay) {
            this.installed = installed;
            this.state = state;
            this.ipv4 = ipv4;
            this.direct = direct;
            this.relay = relay;
        }
    }

    public static final class Client {
        public final List<Tier> tiers;
        public final int fps;
        public final String codec;
        public final String note;

        Client(List<Tier> tiers, int fps, String codec, String note) {
            this.tiers = tiers;
            this.fps = fps;
            this.codec = codec;
            this.note = note;
        }
    }

    public static final class Tier {
        public final String label;
        public final int width;
        public final int height;
        public final int fps;
        public final int bitrateKbps;

        public Tier(String label, int width, int height, int fps, int bitrateKbps) {
            this.label = label;
            this.width = width;
            this.height = height;
            this.fps = fps;
            this.bitrateKbps = bitrateKbps;
        }

        public String detail() {
            return width + "×" + height + " · " + fps + "fps · " + (bitrateKbps / 1000) + "Mbps";
        }
    }

    public static final class Readiness {
        public final int score;
        public final List<Check> checks;

        Readiness(int score, List<Check> checks) {
            this.score = score;
            this.checks = checks;
        }
    }

    public static final class Check {
        public final String key;
        public final String title;
        public final String status;
        public final String detail;

        Check(String key, String title, String status, String detail) {
            this.key = key;
            this.title = title;
            this.status = status;
            this.detail = detail;
        }
    }

    public static final class ServiceInfo {
        public final boolean running;
        public final int port;
        public final boolean codeRequired;

        ServiceInfo(boolean running, int port, boolean codeRequired) {
            this.running = running;
            this.port = port;
            this.codeRequired = codeRequired;
        }
    }
}
