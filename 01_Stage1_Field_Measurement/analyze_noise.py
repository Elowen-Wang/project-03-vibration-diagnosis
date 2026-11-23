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
    """声学超标提醒光效状态机：四档光效 + 峰值事件，阈值由场所基线决定。

    档位（颜色即严重程度，与 06_alert_profiles.md 的五套场所方案同一套定义）：
      NORMAL 绿灯常亮 → WATCH 黄灯常亮 → WARN 橙灯慢闪 1 Hz → ALERT 红灯快闪 2 Hz
    峰值：瞬时 max ≥ 基线+12 dB 时红灯闪一次并记录，不改变主状态。
    """

    LIGHT = {"NORMAL": "绿灯常亮", "WATCH": "黄灯常亮",
             "WARN": "橙灯慢闪 1 Hz", "ALERT": "红灯快闪 2 Hz + 蜂鸣"}
    COLOR = {"NORMAL": "#2f9e44", "WATCH": "#f2c00e",
             "WARN": "#f76707", "ALERT": "#e5484d"}
    ORDER = ["NORMAL", "WATCH", "WARN", "ALERT"]
    UP_FRAMES, DOWN_FRAMES = 3, 5     # 升级 3 帧、降级 5 帧确认
    HYSTERESIS, PEAK_DELTA = 3.0, 12.0

    def __init__(self, base=55.0):
        self.base = float(base)
        self.state = "NORMAL"
        self._up = self._down = 0
        self.events = []

    def band(self, leq):
        """瞬时档位：≤B 绿；(B,B+3] 黄；(B+3,B+8] 橙；>B+8 红。"""
        if leq <= self.base:
            return "NORMAL"
        if leq <= self.base + 3:
            return "WATCH"
        if leq <= self.base + 8:
            return "WARN"
        return "ALERT"

    def step(self, leq, peak, t=0, check_peak=True):
        # 峰值是一段测量的属性，同一段连续多帧读同一个 max，只在首帧判定一次，
        # 否则一段测量会被记成 6 次短闪，事件数虚高。
        if check_peak and peak >= self.base + self.PEAK_DELTA:
            self.events.append((t, "PEAK_FLASH",
                                f"瞬时峰值 {peak:.0f} dB ≥ 基线+{self.PEAK_DELTA:.0f} dB"))
        target = self.band(leq)
        cur, tgt = self.ORDER.index(self.state), self.ORDER.index(target)
        old = self.state
        if tgt > cur:
            self._up, self._down = self._up + 1, 0
            if self._up >= self.UP_FRAMES:
                self.state, self._up = target, 0
        elif tgt < cur:
            # 滞回：回落需低于目标档上限 3 dB，临界波动不会把灯色来回切换
            upper = [self.base, self.base + 3, self.base + 8, float("inf")][tgt]
            if leq <= upper - self.HYSTERESIS:
                self._down, self._up = self._down + 1, 0
                if self._down >= self.DOWN_FRAMES:
                    self.state, self._down = target, 0
            else:
                self._down = 0
        else:
            self._up = self._down = 0
        if self.state != old:
            self.events.append((t, f"{old}->{self.state}",
                                f"Leq {leq:.0f} dB / 基线 {self.base:.0f} dB"))
        return self.state


TIER_STATE = [("NORMAL", "绿灯常亮", "#2f9e44"),
              ("WATCH", "黄灯常亮", "#f2c00e"),
              ("WARN", "橙灯慢闪 1 Hz", "#f76707"),
              ("ALERT", "红灯快闪 2 Hz + 蜂鸣", "#e5484d")]


def tier_of(leq, base):
    """按场所基线分档：≤B 正常；(B, B+3] 接近；(B+3, B+8] 轻度；>B+8 严重。"""
    for i, cut in enumerate((base, base + 3, base + 8)):
        if leq <= cut:
            return i
    return 3


def profile_chart(profiles, title):
    """五场所阈值阶梯图：每个场所一行，色带即四档判定区间，圆点为实测读数落点。"""
    W = 760
    H = 132 + 62 * len(profiles)
    LEFT, RIGHT, TOP = 122, 30, 84
    x0, x1 = LEFT, W - RIGHT
    LO, HI = 30.0, 75.0
    px = lambda v: x0 + (max(LO, min(HI, v)) - LO) / (HI - LO) * (x1 - x0)
    b = [f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         f'<text x="{W/2}" y="32" text-anchor="middle" font-size="16" '
         f'font-weight="600" fill="#1a1a1a">{core._esc(title)}</text>']
    # 顶部刻度轴
    ax = TOP - 14
    for v in range(30, 76, 5):
        b.append(f'<line x1="{px(v):.1f}" y1="{ax}" x2="{px(v):.1f}" y2="{H-30}" '
                 f'stroke="#e9ecef" stroke-width="1"/>')
        b.append(f'<text x="{px(v):.1f}" y="{ax-5}" text-anchor="middle" font-size="10" '
                 f'fill="#868e96">{v}</text>')
    b.append(f'<text x="{x0-6}" y="{ax-19}" text-anchor="end" font-size="9.5" fill="#868e96">单位 dB(A)</text>')
    for i, p in enumerate(profiles):
        y = TOP + i * 62
        base = p["base"]
        cuts = (LO, base, base + 3, base + 8, HI)
        # 四段色带
        for k in range(4):
            a1, a2 = cuts[k], cuts[k + 1]
            if a2 <= a1:
                continue
            b.append(f'<rect x="{px(a1):.1f}" y="{y}" width="{px(a2)-px(a1):.1f}" height="22" '
                     f'fill="{TIER_STATE[k][2]}" fill-opacity="0.85" rx="2"/>')
        # 档位边界数字
        for cut in (base, base + 3, base + 8):
            b.append(f'<line x1="{px(cut):.1f}" y1="{y-4}" x2="{px(cut):.1f}" y2="{y+26}" '
                     f'stroke="#343a40" stroke-width="1.2"/>')
            b.append(f'<text x="{px(cut):.1f}" y="{y+40}" text-anchor="middle" font-size="10" '
                     f'font-weight="600" fill="#343a40">{cut}</text>')
        b.append(f'<text x="{LEFT-10}" y="{y+16}" text-anchor="end" font-size="12.5" '
                 f'font-weight="600" fill="#1a1a1a">{core._esc(p["spot"])}</text>')
        b.append(f'<text x="{LEFT-10}" y="{y+30}" text-anchor="end" font-size="10" '
                 f'fill="#868e96">基线 {base} dB</text>')
        # 三时段实测落点
        marks = []
        for j, (per, v) in enumerate(zip(PERIODS, p["vals"])):
            if not v:
                continue
            ty = y + 11 + (j - 1) * 6
            b.append(f'<circle cx="{px(v):.1f}" cy="{ty:.1f}" r="3.2" fill="#ffffff" '
                     f'stroke="#1a1a1a" stroke-width="1.2"/>')
            marks.append(f"{per} {v:.0f}→{TIER_STATE[tier_of(v, base)][1][:2]}")
        b.append(f'<text x="{LEFT}" y="{y+56}" font-size="10" fill="#495057">'
                 f'{" · ".join(marks)}</text>')
    b.append(f'<text x="{W/2}" y="{H-8}" text-anchor="middle" font-size="10.5" fill="#868e96">'
             f'色带：绿＝正常 · 黄＝接近阈值 · 橙＝轻度超标 · 红＝严重超标；'
             f'竖线为档位边界（基线 / +3 / +8 dB），圆点为该场所早午晚实测读数</text>')
    return core.svg_doc(W, H, "".join(b))


SPOT_NOTE = {
    "图书馆": "安静阅读区，声环境要求最高。基线 41 dB（早 40 / 午 42 / 晚 40）。"
              "不采用国标 55 dB 作警戒线——图书馆的环境恶化通常从 45 dB 量级就已开始，"
              "等到 55 dB 早已影响阅读，因此以本底为基线、超 3 dB 即黄灯提示。",
    "食堂": "高声级人声区，本身本底即 60 dB（早 59 / 午 58 / 晚 62）。"
            "用 55 dB 绝对阈值会让该点位终年红灯、提醒失效。"
            "方案关注「相对用餐常态的叠加」：超 63 dB 提示喧哗，超 68 dB 才判严重。",
    "主干道": "交通与人流混合声，本底 60 dB（早 61 / 午 59 / 晚 59）。"
              "早高峰读数 61 dB 落在黄灯区属预期内波动，判据侧重**持续**超标而非瞬时，"
              "配合 3 帧升级确认避免车流单次通过误触发。",
    "运动场": "开阔活动区，本底 50 dB（早 54 / 午 48 / 晚 47），三时段差异最大（7 dB）。"
              "早间晨练使读数抬升，按统一模板会落橙灯——这是真实事件，不是误报；"
              "该点位以「夜间休息时段」为管控重点，晚 47 dB 长期处于绿灯区。",
    "实训室走廊": "教学过渡区，本底 47 dB（早 43 / 午 59 / 晚 38），日内波动达 21 dB。"
                  "午间下课时段人流集中，实测 59 dB 会触发红灯——这是本方案对该点位的主要局限，"
                  "优化方向见第六节。",
}


def main():
    if not CSV.exists():
        print(f"找不到 {CSV}")
        return 1
    rows = core.read_csv(CSV)
    has_val = lambda r: r.get("avg_db") and r.get("min_db") and r.get("max_db")
    # N01–N15 是官网要求的标准 15 格；H01–H20 是历史/补测记录。
    # 被归入标准格的 H 记录（grid_slot 非空）其数值已复制到对应 N 行，
    # 若两边都算一次会重复计数，所以证据组只取**未归位**的 H 记录。
    # 另需剔除 min < 15 dB 的排障样本（App 启动爬升假值），它们不是有效声级实测。
    standard = [r for r in rows if str(r.get("record_id", "")).startswith("N") and has_val(r)]
    evidence = [r for r in rows if str(r.get("record_id", "")).startswith("H")
                and has_val(r) and not r.get("grid_slot")
                and core.fnum(r["min_db"]) >= 15]
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
    core.save_svg(RESULTS / "06_noise_radar.svg", 760, 470,
                  core.radar_chart(SPOTS, series, title=title, width=760, height=470,
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

    # ---- 五场所基线与峰值（光效仿真与方案文档共用同一份数据） ----
    grid_avg, grid_peak = {}, {}
    for r in standard:
        grid_avg[(r.get("location"), r.get("period"))] = core.fnum(r["avg_db"])
        grid_peak[(r.get("location"), r.get("period"))] = core.fnum(r["max_db"])
    profiles = []
    for s in SPOTS:
        avgs = [grid_avg.get((s, p)) for p in PERIODS]
        pks = [grid_peak.get((s, p), 0) for p in PERIODS]
        got = [v for v in avgs if v]
        if not got:
            continue
        m = core.mean(got)
        b = int(round(m))
        profiles.append({"spot": s, "vals": avgs, "peaks": pks, "mean": m, "base": b})

    # 光效逻辑状态机仿真：每个场所以自己的基线运行，按早→午→晚各 6 帧
    fsm_by_spot, timeline, t, all_events = {}, [], 0, []
    for p in profiles:
        fsm = fsm_by_spot.setdefault(p["spot"], LightAlertFSM(p["base"]))
        for v, pk in zip(p["vals"], p["peaks"]):
            if not v:
                continue
            for f in range(6):
                timeline.append(fsm.step(v, pk, t, check_peak=(f == 0)))
                t += 1
        all_events.extend(fsm.events)
    trans = [e for e in all_events if "->" in e[1]]
    peak_ev = [e for e in all_events if e[1] == "PEAK_FLASH"]
    peaks = peak_ev

    # 状态时间线图：横轴帧序，纵轴档位，直观看不同场所的光效如何随声级切换
    STATE_ORDER = LightAlertFSM.ORDER
    STATE_COLOR = LightAlertFSM.COLOR
    series = []
    for st in STATE_ORDER:
        pts = [(i, STATE_ORDER.index(st)) for i, s in enumerate(timeline) if s == st]
        if pts:
            series.append({"name": st, "color": STATE_COLOR[st], "points": pts})
    core.save_svg(RESULTS / "06_alert_timeline.svg", 680, 280,
                  core.line_chart(series, title="超标提醒光效状态机 · 仿真状态时间线",
                                  xlabel="仿真帧（1 s/帧，按场所连续运行）", ylabel="档位",
                                  width=680, height=300, ymin=-0.4, ymax=3.4))

    # 状态机转移图：把「什么条件 → 什么光效」画成可读的框图
    fsm_states = [
        {"name": "NORMAL", "light": "绿灯常亮", "color": LightAlertFSM.COLOR["NORMAL"],
         "cond": "Leq ≤ 基线 B"},
        {"name": "WATCH", "light": "黄灯常亮", "color": LightAlertFSM.COLOR["WATCH"],
         "cond": "Leq B–B+3"},
        {"name": "WARN", "light": "橙灯慢闪 1 Hz", "color": LightAlertFSM.COLOR["WARN"],
         "cond": "Leq B+3–B+8"},
        {"name": "ALERT", "light": "红灯快闪 2 Hz + 蜂鸣", "color": LightAlertFSM.COLOR["ALERT"],
         "cond": "Leq > B+8"},
    ]
    fsm_edges = [
        {"from": "NORMAL", "to": "WATCH", "label": "连续 3 帧 > B", "style": "up"},
        {"from": "WATCH", "to": "WARN", "label": "连续 3 帧 > B+3", "style": "up"},
        {"from": "WARN", "to": "ALERT", "label": "连续 3 帧 > B+8", "style": "up"},
        {"from": "ALERT", "to": "WARN", "label": "连续 5 帧回落", "style": "down"},
        {"from": "WARN", "to": "WATCH", "label": "连续 5 帧回落", "style": "down"},
        {"from": "WATCH", "to": "NORMAL", "label": "连续 5 帧 ≤ B−3", "style": "down"},
        {"from": "ALERT", "to": "ALERT", "label": f"峰值 ≥ B+{LightAlertFSM.PEAK_DELTA:.0f} 闪一次",
         "style": "peak"},
    ]
    core.save_svg(RESULTS / "06_alert_fsm.svg", 680, 400,
                  core.fsm_diagram(fsm_states, fsm_edges,
                                   title="声学超标自动提醒光效逻辑 · 状态机（B＝场所基线）",
                                   footnote="实现见 analyze_noise.py 的 LightAlertFSM；五套场所基线见 06_alert_profiles.md"))

    md = [
        "# 课题 06 · 声学超标自动提醒光效逻辑", "",
        "> 由 `analyze_noise.py` 生成。本文给出通用光效逻辑与防抖参数；"
        "五个采集场所各自的基线阈值与针对性方案见 `06_alert_profiles.md`。", "",
        "![光效状态机](../results/06_alert_fsm.svg)", "",
        "## 一、设计目标", "",
        "校园噪声提醒最容易失效的方式是「一超就红、一降就绿」：读数在阈值附近来回跳，"
        "灯色反复切换，看的人反而抓不住真正的超标。本逻辑解决三件事：",
        "",
        "1. **不抖**——连续 N 帧确认 + 滞回带，把临界波动滤掉；",
        "2. **看得懂**——四档颜色对应严重程度（绿/黄/橙/红），一眼判断该不该处理；",
        "3. **不漏报**——瞬时尖峰（关门、拖椅、刹车）即使等效声级未超也触发单次闪灯并记录。", "",
        "## 二、阈值来源", "",
        "判据不用跨场所统一的绝对声级，而以**该场所早/午/晚实测均值为基线 B**，"
        "向上叠加固定偏移（+3 / +8 / +12 dB）。五个点位的本底相差 19 dB，"
        "统一阈值会让安静场所终年绿灯、嘈杂场所终年红灯。", "",
        "| 场所 | 早 | 午 | 晚 | 基线 B | 黄灯起 | 橙灯起 | 红灯起 | 峰值触发 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for p in profiles:
        v = [f"{x:.0f}" if x else "—" for x in p["vals"]]
        b = p["base"]
        md.append(f"| {p['spot']} | {v[0]} | {v[1]} | {v[2]} | **{b}** | {b + 3} | {b + 8} | "
                  f">{b + 8} | ≥{b + 12} |")
    md += [
        "",
        "基线取整到 1 dB，便于设备内置参数表。场地功能定位不同，同一基线的含义也不同：",
        "图书馆的 41 dB 是「安静优先」，食堂的 60 dB 是「人声常态」，"
        "两者都用各自本底作参照，越线才代表偏离其正常水平。", "",
        "> 参考：GB 3096-2008《声环境质量标准》1 类区昼间限值 55 dB。"
        "本方案对图书馆、实训室走廊等安静点位的要求严于该限值（基线 41 / 47 dB），"
        "对食堂、主干道则以本底为基准——这两处的 55 dB 会在整个用餐高峰持续被突破，"
        "不具备提醒价值。", "",
        "## 三、四档光效", "",
        "| 档位 | 光效 | 判据（Leq = 滑动 60 s 等效声级） | 动作 |",
        "|---|---|---|---|",
        "| NORMAL | **绿灯常亮** | Leq ≤ B | 仅上报 |",
        "| WATCH | **黄灯常亮** | B < Leq ≤ B+3 | 上报 + 提示 |",
        "| WARN | **橙灯慢闪 1 Hz** | B+3 < Leq ≤ B+8 | 上报 + 记录事件 |",
        "| ALERT | **红灯快闪 2 Hz + 蜂鸣** | Leq > B+8 | 上报 + 记录 + 现场提醒 |",
        "| 峰值 | **红灯闪一次** | 瞬时 max ≥ B+12 | 记录峰值时刻与数值，不改变主状态 |", "",
        f"- 升级确认 {LightAlertFSM.UP_FRAMES} 帧（{LightAlertFSM.UP_FRAMES} s）、"
        f"降级确认 {LightAlertFSM.DOWN_FRAMES} 帧（{LightAlertFSM.DOWN_FRAMES} s）、"
        f"滞回带 {LightAlertFSM.HYSTERESIS:.0f} dB",
        f"- 采样周期 1 s，取滑动 60 s 等效声级；峰值取 1 s 内最大值",
        "- 实现见 `analyze_noise.py` 的 `LightAlertFSM` 类，是可运行代码而非伪代码", "",
        "### 三个参数为什么这么定", "",
        "| 参数 | 取值 | 理由 |", "|---|---|---|",
        "| 升级确认 | 3 帧（3 s） | 单帧可能撞上关门、拖椅；连续 3 帧越线才算真实超标 |",
        "| 降级确认 | 5 帧（5 s） | 比升级慢，是刻意的：超标后不应立刻降级，留出处理时间 |",
        "| 滞回带 | 3.0 dB | 升级线 B、降级线 B−3 分设，两个方向不共用同一条线 |",
        f"| 峰值偏移 | +{LightAlertFSM.PEAK_DELTA:.0f} dB | 差 12 dB 的尖峰在 A 计权下响度相差约 16 倍，不能与稳态声级混为一谈 |", "",
        "![状态时间线](../results/06_alert_timeline.svg)", "",
        "```python",
        "if peak >= B + 12: emit(PEAK_FLASH)          # 闪一次并记录，不改主状态",
        "tgt = NORMAL if leq <= B else WATCH if leq <= B+3 else WARN if leq <= B+8 else ALERT",
        "if tgt > state:                              # 升级：连续 3 帧",
        "    up += 1; down = 0",
        "    if up >= 3: state = tgt; up = 0",
        "elif tgt < state and leq <= upper_of(tgt) - 3:   # 降级：连续 5 帧，且需落入滞回带",
        "    down += 1; up = 0",
        "    if down >= 5: state = tgt; down = 0",
        "```", "",
        "## 四、仿真结果", "",
        f"- 输入：{len(filled)} 组真实实测，按五个场各自的基线运行 {len(timeline)} 帧（1 s/帧）",
        f"- 状态切换 {len(trans)} 次，峰值短闪 {len(peak_ev)} 次", "",
    ]
    if trans:
        md += ["| 帧 | 切换 | 依据 |", "|---|---|---|"]
        md += [f"| {t} | {ev} | {why} |" for t, ev, why in trans[:12]]
        md += [""]
    md += [
        "## 五、数据边界", "",
        "- 手机 App 非专业声级计、未做 A 计权校准：全程同一台设备、同一持握高度与朝向，"
        "系统误差在场所间保持一致，因此「相对基线的偏离」比「绝对声级」更可靠。",
        "- `H04`（min 7 dB）、`H15`（min 18 dB）为 App 启动瞬间麦克风未稳定的爬升假值，"
        "原始记录保留不删不改，已列为排障样本，不参与声级统计。",
        "- 雨天与校园活动会抬高食堂、运动场读数，CSV 的 `weather` / `note` 列留有归因字段。",
        "- 状态机未接真实硬件：仿真由实测数据驱动，光效输出为状态字符串；"
        "接 WS2812 灯环时把 `LIGHT[state]` 映射为 RGB 与闪烁频率，状态机逻辑无需改动。",
    ]
    core.write_text(RESULTS / "06_alert_logic.md", "\n".join(md) + "\n")

    # ---- 五场所个性化光效方案（profiles 已在前面算好并用于状态机仿真） ----
    core.save_svg(RESULTS / "06_alert_profiles.svg", 760, 132 + 62 * len(profiles),
                  profile_chart(profiles, "五场所个性化阈值阶梯（基线＝该场所早午晚均值）"))

    mdp = [
        "# 课题 06 · 五场所个性化声学提醒光效方案", "",
        "> 由 `analyze_noise.py` 生成。状态机通用逻辑见 `06_alert_logic.md`，"
        "本文给出按场所定制的 5 套阈值与运行方案。", "",
        "![五场所阈值阶梯](../results/06_alert_profiles.svg)", "",
        "## 一、设计依据", "",
        "五个点位的声环境本底相差 19 dB（图书馆 41 dB，食堂与主干道 60 dB）。"
        "若全用同一条 55 dB 绝对阈值，图书馆终年绿灯、食堂终年红灯，提醒失去意义。",
        "",
        "本方案改以**该场所早/午/晚实测均值 B** 为基线，向上叠加固定偏移，"
        "判据表达的是「相对该场所正常水平的偏离」，而非跨场所的绝对比较。",
        "",
        "偏移档位五场所统一（+3 / +8 / +12 dB），只有基线 B 随场所变化。"
        "这样 5 套方案参数可比、可解释；同一台设备换点位后只需改一个基线值。", "",
        "## 二、五场所基线与阈值", "",
        "| 场所 | 早 | 午 | 晚 | 均值 | 基线 B | 接近阈值 | 轻度超标 | 严重超标 | 峰值触发 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for p in profiles:
        v = [f"{x:.0f}" if x else "—" for x in p["vals"]]
        b0 = p["base"]
        mdp.append(f"| {p['spot']} | {v[0]} | {v[1]} | {v[2]} | {p['mean']:.1f} | **{b0}** | "
                   f"{b0 + 3} | {b0 + 8} | >{b0 + 8} | ≥{b0 + 12} |")

    mdp += [
        "", "## 三、五档光效（五场所共用）", "",
        "| 档位 | 判据（Leq = 滑动 60 s 等效声级） | 光效 | 动作 |", "|---|---|---|---|",
        "| 正常 | Leq ≤ B | **绿灯常亮** | 仅上报 |",
        "| 接近阈值 | B < Leq ≤ B+3 | **黄灯常亮** | 上报 + 提示 |",
        "| 轻度超标 | B+3 < Leq ≤ B+8 | **橙灯慢闪 1 Hz** | 上报 + 记录事件 |",
        "| 严重超标 | Leq > B+8 | **红灯快闪 2 Hz + 蜂鸣** | 上报 + 记录 + 现场提醒 |",
        "| 峰值突增 | 瞬时 max ≥ B+12 | **红灯闪一次**（不改变主状态） | 记录峰值时刻与数值 |",
        "",
        "升级需连续 3 帧确认、降级需连续 5 帧确认，滞回带 3 dB——与通用状态机同一套防抖参数，"
        "避免临界抖动导致灯色反复跳变。", "",
        "## 四、逐场所方案", "",
    ]
    for p in profiles:
        b0 = p["base"]
        mdp += [
            f"### {p['spot']}（B = {b0} dB）", "",
            SPOT_NOTE.get(p["spot"], ""), "",
            f"- 判定线：≤{b0} 绿常亮｜{b0}–{b0 + 3} 黄常亮｜{b0 + 3}–{b0 + 8} 橙慢闪｜"
            f">{b0 + 8} 红快闪｜峰值 ≥{b0 + 12} 闪一次",
            f"- 布点建议：{'阅览区中央吊顶、避开空调出风口' if p['spot'] == '图书馆' else ''}"
            f"{'售餐窗口上方、距地面 1.5 m' if p['spot'] == '食堂' else ''}"
            f"{'人行道侧立柱、朝向车流' if p['spot'] == '主干道' else ''}"
            f"{'看台或场边立杆、避开扩音' if p['spot'] == '运动场' else ''}"
            f"{'走廊中段、避开实训设备门口' if p['spot'] == '实训室走廊' else ''}",
            "",
        ]

    mdp += ["## 五、实测回放（15 格数据驱动）", "",
            "| 场所 | 时段 | 读数 dB | 档位 | 光效 |", "|---|---|---:|---|---|"]
    tier_cnt = [0, 0, 0, 0]
    for p in profiles:
        for per, v in zip(PERIODS, p["vals"]):
            if not v:
                continue
            t = tier_of(v, p["base"])
            tier_cnt[t] += 1
            mdp.append(f"| {p['spot']} | {per} | {v:.0f} | {TIER_STATE[t][0]} | "
                       f"{TIER_STATE[t][1]} |")
    mdp += [
        "",
        f"15 格实测落在：绿 {tier_cnt[0]} 格、黄 {tier_cnt[1]} 格、"
        f"橙 {tier_cnt[2]} 格、红 {tier_cnt[3]} 格。", "",
        "## 六、局限与优化", "",
        "1. **基线用全日均值，对日内波动大的场所偏严**。实训室走廊三时段为 43 / 59 / 38 dB，"
        "午间下课人流使其偏离均值 12 dB，被判红灯。该点位若长期部署，"
        "建议改为「同时段历史基线」（午间单独取 55 dB），或对午间加 +6 dB 时段偏置。",
        "2. **基线需定期重标定**。学期初与考试周的人流差异会整体抬升本底，"
        "建议每月用连续 3 天数据重算一次 B。",
        "3. **未做 A 计权校准**。全部读数来自同一台手机 App，系统误差在场所间保持一致，"
        "因此「相对偏离」的判据比「绝对声级」更可靠。",
        "4. **峰值判据的边界**：瞬时 max 反映的是单次尖峰（关门、拖椅、刹车），"
        "与 Leq 超标不是同一类事件，故只闪一次并记录，不参与状态升级。", "",
        "## 七、运行方案（硬件）", "",
        "| 环节 | 参数 |", "|---|---|",
        "| 采样 | 1 Hz，麦克风 I2S 数字输出，A 计权 |",
        "| 平滑 | 滑动 60 s 等效声级 Leq；峰值取 1 s 内 max |",
        "| 判据 | 各场所独占基线 B，四档阈值 B / B+3 / B+8 / B+12 |",
        "| 防抖 | 升级 3 帧确认、降级 5 帧确认、滞回带 3 dB |",
        "| 输出 | WS2812 灯环：绿/黄常亮、橙 1 Hz、红 2 Hz + 蜂鸣；峰值单闪 |",
        "| 记录 | 状态切换与峰值事件写入本地 Flash，按场所+时段分文件 |",
        "| 主控 | ESP32-S3，5 个点位共用同一固件，仅基线表不同 |", "",
        "代码实现：`analyze_noise.py` 的 `LightAlertFSM`（通用四态）与 `tier_of()`（五档判定），"
        "两者共用同一套防抖参数。",
    ]
    core.write_text(RESULTS / "06_alert_profiles.md", "\n".join(mdp) + "\n")
    print(f"五场所方案 -> results/06_alert_profiles.md / 06_alert_profiles.svg"
          f"（绿 {tier_cnt[0]} 黄 {tier_cnt[1]} 橙 {tier_cnt[2]} 红 {tier_cnt[3]}）")
    print(f"超标组数：{sum(1 for d in out if d['is_exceed'] == '是')} / {len(out)}")
    print("已输出 06_summary.csv / 06_noise_bars.svg / 06_noise_radar.svg / "
          "06_noise_matrix.svg / 06_alert_timeline.svg / 06_alert_logic.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
