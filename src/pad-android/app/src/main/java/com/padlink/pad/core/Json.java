package com.padlink.pad.core;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 极简 JSON 解析器。Win-Pad Connect 协议只使用对象、数组、字符串、数字、布尔和 null，
 * 因此不引入第三方依赖，保证 core 包可以在没有 Android SDK 的机器上用 javac 直接编译测试。
 */
public final class Json {

    private final String text;
    private int pos;

    private Json(String text) {
        this.text = text;
    }

    public static Object parse(String text) {
        Json parser = new Json(text);
        parser.skipSpace();
        Object value = parser.readValue();
        parser.skipSpace();
        if (parser.pos != text.length()) {
            throw new IllegalArgumentException("多余字符，位置 " + parser.pos);
        }
        return value;
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> parseObject(String text) {
        Object value = parse(text);
        if (!(value instanceof Map)) {
            throw new IllegalArgumentException("期望 JSON 对象");
        }
        return (Map<String, Object>) value;
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> object(Object value) {
        return value instanceof Map ? (Map<String, Object>) value : new LinkedHashMap<>();
    }

    @SuppressWarnings("unchecked")
    public static List<Object> array(Object value) {
        return value instanceof List ? (List<Object>) value : new ArrayList<>();
    }

    public static String string(Map<String, Object> map, String key, String fallback) {
        Object value = map.get(key);
        return value == null ? fallback : String.valueOf(value);
    }

    public static int integer(Map<String, Object> map, String key, int fallback) {
        Object value = map.get(key);
        if (value instanceof Number) {
            return ((Number) value).intValue();
        }
        if (value instanceof String) {
            try {
                return Integer.parseInt((String) value);
            } catch (NumberFormatException ignored) {
                return fallback;
            }
        }
        return fallback;
    }

    public static double number(Map<String, Object> map, String key, double fallback) {
        Object value = map.get(key);
        if (value instanceof Number) {
            return ((Number) value).doubleValue();
        }
        if (value instanceof String) {
            try {
                return Double.parseDouble((String) value);
            } catch (NumberFormatException ignored) {
                return fallback;
            }
        }
        return fallback;
    }

    public static boolean bool(Map<String, Object> map, String key, boolean fallback) {
        Object value = map.get(key);
        if (value instanceof Boolean) {
            return (Boolean) value;
        }
        if (value instanceof String) {
            return Boolean.parseBoolean((String) value);
        }
        return fallback;
    }

    // ---- 解析实现 -------------------------------------------------------

    private Object readValue() {
        if (pos >= text.length()) {
            throw new IllegalArgumentException("意外的结尾");
        }
        char c = text.charAt(pos);
        switch (c) {
            case '{':
                return readObject();
            case '[':
                return readArray();
            case '"':
                return readString();
            case 't':
                expect("true");
                return Boolean.TRUE;
            case 'f':
                expect("false");
                return Boolean.FALSE;
            case 'n':
                expect("null");
                return null;
            default:
                return readNumber();
        }
    }

    private Map<String, Object> readObject() {
        Map<String, Object> result = new LinkedHashMap<>();
        pos++; // {
        skipSpace();
        if (peek() == '}') {
            pos++;
            return result;
        }
        while (true) {
            skipSpace();
            String key = readString();
            skipSpace();
            if (peek() != ':') {
                throw new IllegalArgumentException("缺少冒号，位置 " + pos);
            }
            pos++;
            skipSpace();
            result.put(key, readValue());
            skipSpace();
            char c = peek();
            if (c == ',') {
                pos++;
            } else if (c == '}') {
                pos++;
                return result;
            } else {
                throw new IllegalArgumentException("对象未闭合，位置 " + pos);
            }
        }
    }

    private List<Object> readArray() {
        List<Object> result = new ArrayList<>();
        pos++; // [
        skipSpace();
        if (peek() == ']') {
            pos++;
            return result;
        }
        while (true) {
            skipSpace();
            result.add(readValue());
            skipSpace();
            char c = peek();
            if (c == ',') {
                pos++;
            } else if (c == ']') {
                pos++;
                return result;
            } else {
                throw new IllegalArgumentException("数组未闭合，位置 " + pos);
            }
        }
    }

    private String readString() {
        if (peek() != '"') {
            throw new IllegalArgumentException("期望字符串，位置 " + pos);
        }
        pos++;
        StringBuilder builder = new StringBuilder();
        while (pos < text.length()) {
            char c = text.charAt(pos++);
            if (c == '"') {
                return builder.toString();
            }
            if (c != '\\') {
                builder.append(c);
                continue;
            }
            if (pos >= text.length()) {
                break;
            }
            char escaped = text.charAt(pos++);
            switch (escaped) {
                case '"':
                case '\\':
                case '/':
                    builder.append(escaped);
                    break;
                case 'b':
                    builder.append('\b');
                    break;
                case 'f':
                    builder.append('\f');
                    break;
                case 'n':
                    builder.append('\n');
                    break;
                case 'r':
                    builder.append('\r');
                    break;
                case 't':
                    builder.append('\t');
                    break;
                case 'u':
                    if (pos + 4 > text.length()) {
                        throw new IllegalArgumentException("\\u 转义不完整");
                    }
                    String hex = text.substring(pos, pos + 4);
                    pos += 4;
                    builder.append((char) Integer.parseInt(hex, 16));
                    break;
                default:
                    throw new IllegalArgumentException("未知转义 \\" + escaped);
            }
        }
        throw new IllegalArgumentException("字符串未闭合");
    }

    private Object readNumber() {
        int start = pos;
        while (pos < text.length()) {
            char c = text.charAt(pos);
            if (c == '-' || c == '+' || c == '.' || c == 'e' || c == 'E' || (c >= '0' && c <= '9')) {
                pos++;
            } else {
                break;
            }
        }
        String raw = text.substring(start, pos);
        if (raw.isEmpty()) {
            throw new IllegalArgumentException("无法识别的值，位置 " + start);
        }
        if (raw.contains(".") || raw.contains("e") || raw.contains("E")) {
            return Double.parseDouble(raw);
        }
        long value = Long.parseLong(raw);
        if (value >= Integer.MIN_VALUE && value <= Integer.MAX_VALUE) {
            return (int) value;
        }
        return value;
    }

    private void expect(String literal) {
        if (!text.startsWith(literal, pos)) {
            throw new IllegalArgumentException("期望 " + literal + "，位置 " + pos);
        }
        pos += literal.length();
    }

    private char peek() {
        return pos < text.length() ? text.charAt(pos) : '\0';
    }

    private void skipSpace() {
        while (pos < text.length() && Character.isWhitespace(text.charAt(pos))) {
            pos++;
        }
    }
}
