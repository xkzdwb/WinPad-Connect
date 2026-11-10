package com.padlink.pad.core;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 四指轻点检测器（用于替换 Moonlight fork 里的「三指呼出键盘」）。
 *
 * <p>设计目标：与原生触控共存。只有同时满足以下条件才算命中：
 * <ul>
 *   <li>四根手指在 {@code downWindowMs} 内先后按下；</li>
 *   <li>全程移动不超过 {@code slopPx}；</li>
 *   <li>从第四指按下到最后一指抬起不超过 {@code tapMs}。</li>
 * </ul>
 *
 * <p>协议与 moonlight-android 的 {@code Game.java} 手势常量一致，便于替换
 * {@code THREE_FINGER_TAP_THRESHOLD} 那段逻辑。该类不引用任何 Android 类型，
 * 可以直接用 javac 编译并测试。</p>
 */
public final class FourFingerTapDetector {

    public static final int FINGERS = 4;

    private final long downWindowMs;
    private final long tapMs;
    private final float slopPx;

    private final Map<Integer, Float[]> starts = new LinkedHashMap<>();
    private long firstDownAt = -1;
    private long fourthDownAt = -1;
    private float maxTravel;
    private boolean cancelled;

    public FourFingerTapDetector() {
        this(250, 300, 24);
    }

    public FourFingerTapDetector(long downWindowMs, long tapMs, float slopPx) {
        this.downWindowMs = downWindowMs;
        this.tapMs = tapMs;
        this.slopPx = slopPx;
    }

    public void reset() {
        starts.clear();
        firstDownAt = -1;
        fourthDownAt = -1;
        maxTravel = 0;
        cancelled = false;
    }

    /** 手指按下；返回 false（事件本身不需要消费）。 */
    public boolean down(int pointerId, float x, float y, long eventTimeMs) {
        if (starts.isEmpty()) {
            reset();
            firstDownAt = eventTimeMs;
        }
        starts.put(pointerId, new Float[]{x, y});
        if (starts.size() == FINGERS) {
            fourthDownAt = eventTimeMs;
            if (eventTimeMs - firstDownAt > downWindowMs) {
                cancelled = true;
            }
        }
        return false;
    }

    /** 手指移动；累计位移超过阈值即取消本次手势。 */
    public boolean move(int pointerId, float x, float y) {
        Float[] start = starts.get(pointerId);
        if (start != null) {
            trackTravel(start[0], start[1], x, y);
        }
        return false;
    }

    /**
     * 手指抬起。
     *
     * @return true 表示这一抬指完成了四指轻点，调用方应消费事件并触发「呼出键盘」。
     */
    public boolean up(int pointerId, long eventTimeMs) {
        if (!starts.containsKey(pointerId)) {
            return false;
        }
        starts.remove(pointerId);
        boolean completed = false;
        if (starts.isEmpty()) {
            if (fourthDownAt >= 0 && !cancelled && maxTravel <= slopPx) {
                long duration = eventTimeMs - fourthDownAt;
                completed = duration >= 0 && duration <= tapMs;
            }
            reset();
        }
        return completed;
    }

    /** 指针取消（例如被系统拦截），直接作废本次手势。 */
    public void cancel() {
        reset();
    }

    public boolean tracking() {
        return !starts.isEmpty();
    }

    public int fingerCount() {
        return starts.size();
    }

    public float maxTravel() {
        return maxTravel;
    }

    private void trackTravel(float sx, float sy, float x, float y) {
        float dx = x - sx;
        float dy = y - sy;
        float travel = (float) Math.sqrt(dx * dx + dy * dy);
        maxTravel = Math.max(maxTravel, travel);
        if (maxTravel > slopPx) {
            cancelled = true;
        }
    }
}
