package com.padlink.pad.net;

import com.padlink.pad.core.HostProfile;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

/**
 * Win-Pad Connect 主机 HTTP 客户端。只使用 HttpURLConnection，避免引入第三方库。
 */
public final class HostClient {

    public static final int DEFAULT_PORT = 47800;

    private final String host;
    private final int port;
    private final int connectTimeoutMs;
    private final int readTimeoutMs;

    public HostClient(String host, int port) {
        this(host, port, 3000, 8000);
    }

    public HostClient(String host, int port, int connectTimeoutMs, int readTimeoutMs) {
        this.host = host;
        this.port = port;
        this.connectTimeoutMs = connectTimeoutMs;
        this.readTimeoutMs = readTimeoutMs;
    }

    public static final class UnauthorizedException extends IOException {
        public UnauthorizedException(String message) {
            super(message);
        }
    }

    /** 单次 ping，返回毫秒。 */
    public double ping() throws IOException {
        long start = System.nanoTime();
        String body = get("/padlink/ping");
        double elapsed = (System.nanoTime() - start) / 1_000_000.0;
        if (!body.contains("\"padlink\"")) {
            throw new IOException("应答不是 Win-Pad Connect 主机");
        }
        return elapsed;
    }

    public HostProfile profile(String code) throws IOException {
        String path = "/padlink/profile.json";
        if (code != null && !code.isEmpty()) {
            path += "?code=" + URLEncoder.encode(code, "UTF-8");
        }
        String body = get(path);
        try {
            return HostProfile.parse(body);
        } catch (RuntimeException exc) {
            throw new IOException("profile 解析失败：" + exc.getMessage(), exc);
        }
    }

    public String health() throws IOException {
        return get("/padlink/health");
    }

    public interface Progress {
        void onProgress(long bytes, long total);
    }

    /**
     * 下载指定 MB 的测试数据，返回实际字节数。用于测量下行吞吐。
     */
    public long download(int megabytes, Progress progress) throws IOException {
        URL url = new URL("http://" + host + ":" + port + "/padlink/download?mb=" + megabytes);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setConnectTimeout(connectTimeoutMs);
        conn.setReadTimeout(15000);
        conn.setRequestProperty("User-Agent", "Win-Pad Connect-Pad/1.0");
        try {
            int status = conn.getResponseCode();
            if (status == 401) {
                throw new UnauthorizedException("需要配对码");
            }
            if (status != 200) {
                throw new IOException("HTTP " + status);
            }
            long total = megabytes * 1024L * 1024L;
            long received = 0;
            byte[] buffer = new byte[64 * 1024];
            try (InputStream input = new BufferedInputStream(conn.getInputStream())) {
                int read;
                while ((read = input.read(buffer)) >= 0) {
                    received += read;
                    if (progress != null && received % (256 * 1024) < read) {
                        progress.onProgress(received, total);
                    }
                }
            }
            return received;
        } finally {
            conn.disconnect();
        }
    }

    private String get(String path) throws IOException {
        URL url = new URL("http://" + host + ":" + port + path);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setConnectTimeout(connectTimeoutMs);
        conn.setReadTimeout(readTimeoutMs);
        conn.setRequestProperty("User-Agent", "Win-Pad Connect-Pad/1.0");
        try {
            int status = conn.getResponseCode();
            if (status == 401) {
                throw new UnauthorizedException("需要配对码");
            }
            if (status != 200) {
                throw new IOException("HTTP " + status);
            }
            return readAll(conn.getInputStream());
        } finally {
            conn.disconnect();
        }
    }

    private static String readAll(InputStream input) throws IOException {
        try (InputStream stream = input; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = stream.read(buffer)) >= 0) {
                output.write(buffer, 0, read);
            }
            return new String(output.toByteArray(), StandardCharsets.UTF_8);
        }
    }
}
