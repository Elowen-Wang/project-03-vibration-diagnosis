# 课题 06 · 声学超标自动提醒光效逻辑

> 由 `analyze_noise.py` 生成，可并入本目录 README.md。

## 阈值分级

| 时段 | 阈值 | 说明 |
|---|---|---|
| 早 07:00–09:00 | 55 dB | 教学区管理阈值，参考 GB 3096 1 类区昼间 |
| 午 11:00–14:00 | 55 dB | 同上 |
| 晚 20:00–22:00 | 50 dB | 校园自习时段自定收紧 |

## 状态机

| 状态 | 光效 | 进入条件 |
|---|---|---|
| QUIET | 绿色常亮（低亮度） | 连续 5 帧低于 阈值−12 dB |
| NORMAL | 蓝色常亮 | 连续 5 帧回落到 阈值−3 dB 滞回带内 |
| WARN | 黄色慢闪 1 Hz | 连续 3 帧 平均声级 ≥ 阈值 |
| ALERT | 红色快闪 2 Hz + 蜂鸣 | 连续 3 帧 ≥ 阈值+6 dB |

- 升级确认 3 帧、降级确认 5 帧、滞回带 3.0 dB，防止临界抖动
- 瞬时峰值 ≥ 阈值+10.0 dB 触发单次短闪，不改变主状态
- 采样周期 1 s，取滑动 60 s 等效声级；装置可用 ESP32-S3 + WS2812 灯环实现
- 状态机实现见 `analyze_noise.py` 的 `LightAlertFSM` 类，**是可运行代码而非伪代码**

```python
if peak >= limit + 10: emit(PEAK_FLASH)
if leq >= limit:
    up += 1; down = 0
    if up >= 3: state = ALERT if leq >= limit + 6 else WARN
else:
    down = down + 1 if leq < limit - 3 else 0; up = 0
    if down >= 5: state = QUIET if leq < limit - 12 else NORMAL
```

## 仿真结果

- 基于当前 23 组真实数据扩展为 138 帧，状态切换 17 次，峰值短闪 84 次
- 结束状态：`WARN`（黄色慢闪 1 Hz）
- 状态时间线图见 `results/06_alert_timeline.svg`

## 数据边界（面试预判）

- 手机 App 非专业声级计、未做 A 计权校准：全程用同一台 OPPO Reno 15、同一持握高度与朝向，
  在报告中说明系统误差；有条件时用标准声级计做一次对照。
- `H04` 最小 7 dB、`H15` 最小 18 dB 为 App 启动瞬间麦克风未稳定的爬升假值，
  原始记录保留不删不改，平均值仍可参考，最小值不纳入统计。
- 雨天 / 校园活动会抬高食堂与运动场读数，已在 CSV 的 `weather` / `note` 列预留归因字段。
