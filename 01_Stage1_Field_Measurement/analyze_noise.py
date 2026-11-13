"""课题 06 · 校园昼夜声学噪声地图测绘（零第三方依赖）

用法（仓库根目录执行）：
    python 01_Stage1_Field_Measurement\\analyze_noise.py

读取 noise_log.csv，输出雷达图、柱状图、汇总表与超标光效逻辑。
只有部分数据时也能跑，会提示还缺几组；填满 15 组后图表自动完整。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
import signal_core as core  # noqa: E402

RESULTS = HERE / "results"
RESULTS.mkdir(exist_ok=True)
CSV = HERE / "noise_log.csv"

SPOTS = ["图书馆", "食堂", "主干道", "运动场", "实训室走廊"]
PERIODS = ["早", "午", "晚"]
LIMITS = {"早": 55.0, "午": 55.0, "晚": 50.0}


class LightAlertFSM:
    """声学超标自动提醒光效状态机：滞回防抖 + 持续确认 + 瞬时峰值事件。"""

    LIGHT = {"QUIET": "绿色常亮（低亮度）", "NORMAL": "蓝色常亮",
             "WARN": "黄色慢闪 1 Hz", "ALERT": "红色快闪 2 Hz + 蜂鸣"}
    UP_FRAMES, DOWN_FRAMES = 3, 5
    HYSTERESIS, PEAK_DELTA = 3.0, 10.0

    def __init__(self, limits=LIMITS):
        self.limits, self.state, self._up, self._down, self.events = limits, "NORMAL", 0, 0, []

    def step(self, leq, peak, period, t=0):
        limit = self.limits.get(period, 55.0)
        if peak >= limit + self.PEAK_DELTA:
            self.events.append((t, "PEAK_FLASH", f"瞬时峰值 {peak:.1f} dB 超阈值 +{self.PEAK_DELTA:.0f} dB"))
        over = leq >= limit
        if over:
            self._up, self._down = self._up + 1, 0
        else:
            self._down = self._down + 1 if leq < limit - self.HYSTERESIS else 0
            self._up = 0
        old = self.state
        if over and self._up >= self.UP_FRAMES:
            self.state = "ALERT" if leq >= limit + 6 else "WARN"
            self._up = 0
        elif not over and self._down >= self.DOWN_FRAMES:
            self.state = "QUIET" if leq < limit - 12 else "NORMAL"
            self._down = 0
        if self.state != old:
            self.events.append((t, f"{old}->{self.state}", f"Leq {leq:.1f} dB / 阈值 {limit:.0f} dB"))
        return self.state


def main():
    if not CSV.exists():
        print(f"找不到 {CSV}")
        return 1
    rows = core.read_csv(CSV)
    filled = [r for r in rows if r.get("avg_db") and r.get("min_db") and r.get("max_db")]
    standard = [r for r in filled if str(r.get("record_id", "")).startswith("N")]
    print(f"已录入数值：{len(filled)} 组（其中标准 15 组表已完成 {len(standard)}/15）")
    if len(standard) < 15:
        print(f"  还缺 {15 - len(standard)} 组，按 DAILY_PLAN.md 的 Day1/Day2 补测后重跑本脚本")
    if not filled:
        print("暂无数值，先补测。")
        return 0

    # 汇总表
    out = []
    for r in filled:
        d = dict(r)
        avg = core.fnum(r["avg_db"])
        period = r.get("period", "")
        limit = LIMITS.get(period, 55.0)
        d["limit_db"], d["exceed_db"] = limit, round(avg - limit, 1)
        d["is_exceed"] = "是" if avg >= limit else "否"
        d["is_abnormal"] = "是" if core.fnum(r["min_db"]) < 15 else "否"
        out.append(d)
    core.write_csv(RESULTS / "06_summary.csv", out)
    print(f"汇总表 -> {(RESULTS / '06_summary.csv').relative_to(ROOT)}")

    # 柱状图：所有已填记录的平均分贝
    labels = [f"{r['record_id']} {r.get('location', '')}" for r in filled]
    vals = [core.fnum(r["avg_db"]) for r in filled]
    core.save_svg(RESULTS / "06_noise_bars.svg", 680, 300,
                  core.bar_chart(labels, vals, title="各记录平均声级 dB(A)", ylabel="dB"))

    # 雷达图：标准 15 组填满才画，否则画已有分组的点位均值
    grid = {}
    for r in standard:
        grid[(r.get("period"), r.get("location"))] = core.fnum(r["avg_db"])
    if len(standard) >= 15:
        series = [{"name": p, "color": core.PALETTE[i],
                   "values": [grid.get((p, s), 0) for s in SPOTS]}
                  for i, p in enumerate(PERIODS)]
        title = "校园五点位 × 三时段噪声地图（15 组，dB）"
    else:
        spot_vals = {}
        for r in filled:
            spot_vals.setdefault(r.get("location", "未标注"), []).append(core.fnum(r["avg_db"]))
        cats = list(spot_vals.keys())[:6] or SPOTS
        series = [{"name": "当前已采均值", "color": core.PALETTE[0],
                   "values": [core.mean(spot_vals.get(c, [0])) for c in cats]}]
        SPOTS_LOCAL = cats
        series[0]["values"] = [core.mean(spot_vals.get(c, [0])) for c in SPOTS_LOCAL]
        core.save_svg(RESULTS / "06_noise_radar.svg", 680, 340,
                      core.radar_chart(SPOTS_LOCAL, series, title="当前已采点位均值 dB（待补 15 组标准表）", vmax=85))
        print("雷达图（进度版）-> results/06_noise_radar.svg")
    if len(standard) >= 15:
        core.save_svg(RESULTS / "06_noise_radar.svg", 680, 340,
                      core.radar_chart(SPOTS, series, title=title, vmax=85))

    # 光效逻辑状态机仿真
    fsm, t, timeline = LightAlertFSM(), 0, []
    for r in filled:
        avg, peak = core.fnum(r["avg_db"]), core.fnum(r["max_db"])
        for _ in range(6):
            timeline.append(fsm.step(avg, peak, r.get("period", "午"), t))
            t += 1
    trans = [e for e in fsm.events if "->" in e[1]]
    peaks = [e for e in fsm.events if e[1] == "PEAK_FLASH"]
    md = [
        "# 课题 06 · 声学超标自动提醒光效逻辑", "",
        "> 由 `analyze_noise.py` 生成，可并入本目录 README.md。", "",
        "## 阈值分级", "",
        "| 时段 | 阈值 | 说明 |", "|---|---|---|",
        "| 早 07:00–09:00 | 55 dB | 教学区管理阈值，参考 GB 3096 1 类区昼间 |",
        "| 午 11:00–14:00 | 55 dB | 同上 |",
        "| 晚 20:00–22:00 | 50 dB | 校园自习时段自定收紧 |", "",
        "## 状态机", "",
        "| 状态 | 光效 | 进入条件 |", "|---|---|---|",
        "| QUIET | 绿色常亮（低亮度） | 连续 5 帧低于 阈值−12 dB |",
        "| NORMAL | 蓝色常亮 | 连续 5 帧回落到 阈值−3 dB 滞回带内 |",
        "| WARN | 黄色慢闪 1 Hz | 连续 3 帧 平均声级 ≥ 阈值 |",
        "| ALERT | 红色快闪 2 Hz + 蜂鸣 | 连续 3 帧 ≥ 阈值+6 dB |", "",
        f"- 升级确认 {fsm.UP_FRAMES} 帧、降级确认 {fsm.DOWN_FRAMES} 帧、滞回带 {fsm.HYSTERESIS} dB，防止临界抖动",
        f"- 瞬时峰值 ≥ 阈值+{fsm.PEAK_DELTA} dB 触发单次短闪，不改变主状态",
        "- 采样周期 1 s，取滑动 60 s 等效声级；装置可用 ESP32-S3 + WS2812 灯环实现", "",
        "```python",
        "if peak >= limit + 10: emit(PEAK_FLASH)",
        "if leq >= limit:",
        "    up += 1; down = 0",
        "    if up >= 3: state = ALERT if leq >= limit + 6 else WARN",
        "else:",
        "    down = down + 1 if leq < limit - 3 else 0; up = 0",
        "    if down >= 5: state = QUIET if leq < limit - 12 else NORMAL",
        "```", "",
        "## 仿真结果", "",
        f"- 基于当前 {len(filled)} 组数据扩展为 {len(timeline)} 帧，状态切换 {len(trans)} 次，峰值短闪 {len(peaks)} 次",
        f"- 结束状态：`{fsm.state}`（{fsm.LIGHT[fsm.state]}）", "",
        "## 数据边界（面试预判）", "",
        "- 手机 App 非专业声级计、未做 A 计权校准：全程用同一台 OPPO Reno 15、同一持握高度与朝向，",
        "  在报告中说明系统误差；有条件时用标准声级计做一次对照。",
        "- `H04` 最小 7 dB 为 App 启动瞬间麦克风未稳定的爬升假值，",
        "  保留原始记录并在 `R01` 重测，不删除、不静默改数。",
        "- 雨天 / 校园活动会抬高食堂与运动场读数，已在 CSV 的 `weather` / `note` 列预留归因字段。",
    ]
    (RESULTS / "06_alert_logic.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"超标组数：{sum(1 for d in out if d['is_exceed'] == '是')} / {len(out)}")
    print("已输出 06_summary.csv / 06_noise_bars.svg / 06_noise_radar.svg / 06_alert_logic.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
