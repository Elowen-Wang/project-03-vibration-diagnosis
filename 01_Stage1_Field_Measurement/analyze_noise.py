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
    has_val = lambda r: r.get("avg_db") and r.get("min_db") and r.get("max_db")
    # N01–N15 是官网要求的标准 15 格；H01–H16 是历史/补测记录。
    # 被归入标准格的 H 记录（grid_slot 非空）其数值已复制到对应 N 行，
    # 若两边都算一次会重复计数，所以证据组只取**未归位**的 H 记录。
    standard = [r for r in rows if str(r.get("record_id", "")).startswith("N") and has_val(r)]
    evidence = [r for r in rows if str(r.get("record_id", "")).startswith("H")
                and has_val(r) and not r.get("grid_slot")]
    filled = standard + evidence          # 每行 = 一次独立实测，不重复
    print(f"独立实测 {len(filled)} 组（标准 15 格已填 {len(standard)} 格 + 佐证 {len(evidence)} 组）")
    if len(standard) < 15:
        missing = [r["record_id"] for r in rows
                   if str(r.get("record_id", "")).startswith("N") and not has_val(r)]
        print(f"  标准表还缺 {15 - len(standard)} 格：{' '.join(missing) if missing else '—'}"
              f"（真实缺口，不补造；补测后重跑本脚本）")
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

    # 噪声地图：始终以官网要求的「5 点位 × 3 时段」完整矩阵呈现。
    # 无论采到几组，未采集的格子都保留占位（雷达图按 0 绘制、热力图画斜线标注），
    # 这样老师看到的是完整矩阵结构 + 真实完成度，而不是缺格后只剩几条线。
    grid = {}
    for r in standard:
        grid[(r.get("period"), r.get("location"))] = core.fnum(r["avg_db"])
    series = [{"name": p, "color": core.PALETTE[i],
               "values": [grid.get((p, s), 0) for s in SPOTS]}
              for i, p in enumerate(PERIODS)]
    title = ("校园五点位 × 三时段噪声地图（dB，标准 15 组已完成 "
             f"{len(standard)}/15，未采集格按 0 占位）" if len(standard) < 15
             else "校园五点位 × 三时段噪声地图（标准 15 组全采集，dB）")
    # 径向标尺从 30 dB 起（环境背景噪声下限），让 38–62 dB 的实际差异拉开
    # limits 传入各时段阈值 → 画成虚线参考多边形，越线即超标
    core.save_svg(RESULTS / "06_noise_radar.svg", 760, 430,
                  core.radar_chart(SPOTS, series, title=title, width=760, height=430,
                                   vmin=30, vmax=70,
                                   limits=[LIMITS.get(p, 55.0) for p in PERIODS],
                                   limit_labels=[f"{p} 阈值 {LIMITS.get(p, 55.0):.0f} dB"
                                                 for p in PERIODS],
                                   footnote="虚线＝该时段阈值，越线即超标"))

    # 配套矩阵热力图：缺失格明确标注「未采集」，超标格红框，一眼看清完成度
    # 行 = 时段（3 行），列 = 点位（5 列），与官网「5 点位 × 3 时段」一致
    cells = [[grid.get((p, s)) for s in SPOTS] for p in PERIODS]
    core.save_svg(RESULTS / "06_noise_matrix.svg", 680, 340,
                  core.matrix_grid(PERIODS, SPOTS, cells,
                                   limits=[LIMITS.get(p, 55.0) for p in PERIODS],
                                   title="标准 15 组声学数据表 · 点位 × 时段矩阵",
                                   note=f"已完成 {len(standard)}/15 格；虚线格为未采集，红框为超出时段阈值"))
    print(f"雷达图 -> results/06_noise_radar.svg（5 点位 × 3 时段完整矩阵，"
          f"{len(standard)}/15 格已采集）")
    print(f"矩阵热力图 -> results/06_noise_matrix.svg（{len(standard)}/15 格已采集）")

    # 光效逻辑状态机仿真
    fsm, t, timeline = LightAlertFSM(), 0, []
    for r in filled:
        avg, peak = core.fnum(r["avg_db"]), core.fnum(r["max_db"])
        for _ in range(6):
            timeline.append(fsm.step(avg, peak, r.get("period", "午"), t))
            t += 1
    trans = [e for e in fsm.events if "->" in e[1]]
    peaks = [e for e in fsm.events if e[1] == "PEAK_FLASH"]

    # 状态时间线图：横轴帧序，纵轴状态等级，直观看状态机如何随声级切换
    STATE_ORDER = ["QUIET", "NORMAL", "WARN", "ALERT"]
    STATE_COLOR = {"QUIET": "#2f9e44", "NORMAL": "#1971c2",
                   "WARN": "#f08c00", "ALERT": "#e5484d"}
    series = []
    for st in STATE_ORDER:
        pts = [(i, STATE_ORDER.index(st)) for i, s in enumerate(timeline) if s == st]
        if pts:
            series.append({"name": st, "color": STATE_COLOR[st], "points": pts})
    core.save_svg(RESULTS / "06_alert_timeline.svg", 680, 260,
                  core.line_chart(series, title="超标提醒光效状态机 · 仿真状态时间线",
                                  xlabel="仿真帧（1 s/帧）", ylabel="状态等级",
                                  width=680, height=260))

    # 状态机转移图：把「什么条件 → 什么光效」画成可读的框图
    fsm_states = [
        {"name": "QUIET", "light": "绿色常亮（低亮度）", "color": "#2f9e44",
         "cond": "连续 5 帧 < 阈值−12 dB"},
        {"name": "NORMAL", "light": "蓝色常亮", "color": "#1971c2",
         "cond": "连续 5 帧回落滞回带"},
        {"name": "WARN", "light": "黄色慢闪 1 Hz", "color": "#f08c00",
         "cond": "连续 3 帧 ≥ 阈值"},
        {"name": "ALERT", "light": "红色快闪 2 Hz + 蜂鸣", "color": "#e5484d",
         "cond": "连续 3 帧 ≥ 阈值+6 dB"},
    ]
    fsm_edges = [
        {"from": "QUIET", "to": "NORMAL", "label": "回落滞回带", "style": "up"},
        {"from": "NORMAL", "to": "WARN", "label": "连续 3 帧超阈", "style": "up"},
        {"from": "WARN", "to": "ALERT", "label": "连续 3 帧超阈 +6", "style": "up"},
        {"from": "ALERT", "to": "WARN", "label": "连续 5 帧回落", "style": "down"},
        {"from": "WARN", "to": "NORMAL", "label": "连续 5 帧回落", "style": "down"},
        {"from": "NORMAL", "to": "QUIET", "label": "连续 5 帧 < −12", "style": "down"},
        {"from": "WARN", "to": "WARN", "label": f"峰值 ≥ 阈值+{fsm.PEAK_DELTA:.0f} dB",
         "style": "peak"},
    ]
    core.save_svg(RESULTS / "06_alert_fsm.svg", 680, 400,
                  core.fsm_diagram(fsm_states, fsm_edges,
                                   title="声学超标自动提醒光效逻辑 · 状态机",
                                   footnote="实现见 analyze_noise.py 的 LightAlertFSM（可运行代码）"))

    md = [
        "# 课题 06 · 声学超标自动提醒光效逻辑", "",
        "> 由 `analyze_noise.py` 生成，可并入本目录 README.md。", "",
        "![光效状态机](../results/06_alert_fsm.svg)", "",
        "## 设计目标", "",
        "校园噪声超标提醒最容易犯的错是「一超就红、一降就绿」——在阈值附近来回跳变，",
        "看的人反而注意不到真正的超标。本套逻辑解决三件事：",
        "",
        "1. **不抖**：用「连续 N 帧确认 + 滞回带」把临界波动滤掉；",
        "2. **看得懂**：光效分 4 级，颜色对应严重程度，一眼能判断该不该管；",
        "3. **不漏报**：瞬时峰值（哪怕等效声级还没到阈值）也触发短闪，噪声偶发尖峰不丢。", "",
        "## 阈值分级", "",
        "| 时段 | 阈值 | 说明 |", "|---|---|---|",
        "| 早 07:00–09:00 | 55 dB | 教学区管理阈值，参考 GB 3096 1 类区昼间 |",
        "| 午 11:00–14:00 | 55 dB | 同上 |",
        "| 晚 20:00–22:00 | 50 dB | 校园自习时段自定收紧 |", "",
        "> 阈值来源写明：GB 3096-2008《声环境质量标准》1 类区昼间 55 dB 为标准限值；",
        "> " + "晚间 50 dB 是针对校园晚自习场景的自定收紧值，**不是国标限值**，报告里如实区分。", "",
        "## 状态机", "",
        "| 状态 | 光效 | 进入条件 |", "|---|---|---|",
        "| QUIET | 绿色常亮（低亮度） | 连续 5 帧低于 阈值−12 dB |",
        "| NORMAL | 蓝色常亮 | 连续 5 帧回落到 阈值−3 dB 滞回带内 |",
        "| WARN | 黄色慢闪 1 Hz | 连续 3 帧 平均声级 ≥ 阈值 |",
        "| ALERT | 红色快闪 2 Hz + 蜂鸣 | 连续 3 帧 ≥ 阈值+6 dB |", "",
        f"- 升级确认 {fsm.UP_FRAMES} 帧、降级确认 {fsm.DOWN_FRAMES} 帧、滞回带 {fsm.HYSTERESIS} dB，防止临界抖动",
        f"- 瞬时峰值 ≥ 阈值+{fsm.PEAK_DELTA} dB 触发单次短闪，不改变主状态",
        "- 采样周期 1 s，取滑动 60 s 等效声级；装置可用 ESP32-S3 + WS2812 灯环实现",
        "- 状态机实现见 `analyze_noise.py` 的 `LightAlertFSM` 类，**是可运行代码而非伪代码**", "",
        "### 三个关键参数为什么这么定", "",
        "| 参数 | 取值 | 理由 |", "|---|---|---|",
        "| 升级确认帧数 | 3 帧（3 s） | 单帧可能撞上关门声、拖椅声；连续 3 帧超阈才算真超标 |",
        "| 降级确认帧数 | 5 帧（5 s） | 比升级慢，是**故意的**——超标后不应立刻降级，给人留出处理时间 |",
        "| 滞回带 | 3.0 dB | 升级线 `阈值`、降级线 `阈值−3 dB` 之间留出空档，两个方向不共用同一条线 |",
        "| 瞬时峰值 | +10 dB | 差 10 dB 的尖峰（关门、刹车）在 A 计权下相当于响度差 10 倍，不能忽略 |", "",
        "![状态时间线](../results/06_alert_timeline.svg)", "",
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
        f"- 基于当前 {len(filled)} 组真实数据扩展为 {len(timeline)} 帧，状态切换 {len(trans)} 次，峰值短闪 {len(peaks)} 次",
        f"- 结束状态：`{fsm.state}`（{fsm.LIGHT[fsm.state]}）",
        "- 状态时间线图见 `results/06_alert_timeline.svg`", "",
        "## 数据边界（面试预判）", "",
        "- 手机 App 非专业声级计、未做 A 计权校准：全程用同一台 OPPO Reno 15、同一持握高度与朝向，",
        "  在报告中说明系统误差；有条件时用标准声级计做一次对照。",
        "- `H04` 最小 7 dB、`H15` 最小 18 dB 为 App 启动瞬间麦克风未稳定的爬升假值，",
        "  原始记录保留不删不改，平均值仍可参考，最小值不纳入统计。",
        "- 雨天 / 校园活动会抬高食堂与运动场读数，已在 CSV 的 `weather` / `note` 列预留归因字段。",
        "- 状态机当前**未接真实硬件**：仿真用实测数据驱动，光效输出为状态字符串；",
        "  接 WS2812 灯环时把 `LIGHT[state]` 映射成 RGB 与闪烁频率即可，状态机逻辑无需改动。",
    ]
    (RESULTS / "06_alert_logic.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"超标组数：{sum(1 for d in out if d['is_exceed'] == '是')} / {len(out)}")
    print("已输出 06_summary.csv / 06_noise_bars.svg / 06_noise_radar.svg / "
          "06_noise_matrix.svg / 06_alert_timeline.svg / 06_alert_logic.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
