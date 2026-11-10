package com.padlink.pad.net;

import android.util.Log;

import com.padlink.pad.core.Json;

import java.io.IOException;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.NetworkInterface;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * UDP 广播发现。协议：平板向 47801 端口发送 {@code PADLINK?1}，
 * 主机回一个 JSON（service/name/port/ips）。
 */
public final class Discovery {

    private static final String TAG = "Win-Pad ConnectDiscovery";
    public static final int DISCOVERY_PORT = 47801;
    private static final String PROBE = "PADLINK?1";

    private Discovery() {
    }

    public interface Listener {
        void onFound(FoundHost host);

        void onFinished(int total, String error);
    }

    public static final class FoundHost {
        public final String name;
        public final String ip;
        public final int port;
        public final boolean codeRequired;
        public final List<String> ips;

        FoundHost(String name, String ip, int port, boolean codeRequired, List<String> ips) {
            this.name = name;
            this.ip = ip;
            this.port = port;
            this.codeRequired = codeRequired;
            this.ips = ips;
        }

        public String label() {
            return name + "  ·  " + ip + ":" + port;
        }
    }

    /** 阻塞调用，请放在后台线程执行。 */
    public static void scan(int timeoutMs, Listener listener) {
        Map<String, FoundHost> found = new LinkedHashMap<>();
        String error = null;
        DatagramSocket socket = null;
        try {
            socket = new DatagramSocket(null);
            socket.setReuseAddress(true);
            socket.setBroadcast(true);
            socket.bind(new InetSocketAddress(DISCOVERY_PORT));
            socket.setSoTimeout(250);

            byte[] probe = PROBE.getBytes(StandardCharsets.UTF_8);
            for (InetAddress target : broadcastTargets()) {
                try {
                    socket.send(new DatagramPacket(probe, probe.length, target, DISCOVERY_PORT));
                } catch (IOException exc) {
                    Log.w(TAG, "发送广播失败 " + target, exc);
                }
            }

            long deadline = System.currentTimeMillis() + timeoutMs;
            byte[] buffer = new byte[4096];
            while (System.currentTimeMillis() < deadline) {
                DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
                try {
                    socket.receive(packet);
                } catch (SocketTimeoutException timeout) {
                    continue;
                }
                String body = new String(packet.getData(), 0, packet.getLength(), StandardCharsets.UTF_8);
                FoundHost host = parse(body, packet.getAddress().getHostAddress());
                if (host != null && !found.containsKey(host.ip)) {
                    found.put(host.ip, host);
                    listener.onFound(host);
                }
            }
        } catch (IOException exc) {
            error = "广播发现失败：" + exc.getMessage();
            Log.w(TAG, "discovery failed", exc);
        } finally {
            if (socket != null) {
                socket.close();
            }
        }
        listener.onFinished(found.size(), error);
    }

    static FoundHost parse(String body, String sourceIp) {
        try {
            Map<String, Object> json = Json.parseObject(body);
            if (!"padlink".equals(Json.string(json, "service", ""))) {
                return null;
            }
            List<String> ips = new ArrayList<>();
            for (Object item : Json.array(json.get("ips"))) {
                if (item != null) {
                    ips.add(String.valueOf(item));
                }
            }
            return new FoundHost(
                    Json.string(json, "name", "Win-Pad Connect"),
                    sourceIp,
                    Json.integer(json, "port", 47800),
                    Json.bool(json, "code_required", true),
                    Collections.unmodifiableList(ips)
            );
        } catch (RuntimeException exc) {
            Log.w(TAG, "忽略无法解析的应答", exc);
            return null;
        }
    }

    private static List<InetAddress> broadcastTargets() {
        List<InetAddress> targets = new ArrayList<>();
        try {
            targets.add(InetAddress.getByName("255.255.255.255"));
        } catch (IOException ignored) {
            // 继续尝试网卡定向广播。
        }
        try {
            for (NetworkInterface nic : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                if (!nic.isUp() || nic.isLoopback()) {
                    continue;
                }
                for (java.net.InterfaceAddress address : nic.getInterfaceAddresses()) {
                    InetAddress broadcast = address.getBroadcast();
                    if (broadcast != null && !targets.contains(broadcast)) {
                        targets.add(broadcast);
                    }
                }
            }
        } catch (IOException exc) {
            Log.w(TAG, "枚举网卡失败", exc);
        }
        return targets;
    }
}
