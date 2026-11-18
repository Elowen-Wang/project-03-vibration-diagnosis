"""课题 08 · 多姿态步态加速度特征采集与对比（零第三方依赖）

用法（仓库根目录执行）：
    python 01_Stage1_Field_Measurement\\analyze_gait.py --demo   # 合成演示数据，仅验证流程
    python 01_Stage1_Field_Measurement\\analyze_gait.py           # 分析 课题08/ 下的真实 CSV
    python 01_Stage1_Field_Measurement\\analyze_gait.py --include-invalid  # 临时纳入无效组对比

数据源优先级：gait_raw/（早期扁平目录）→ 课题08/<姿态>/*.csv（2026-11-16 实际采集）。
自动识别 Phyphox 列名与单位（Linear Acceleration，m/s^2），按 2 秒窗口提取特征，
输出波形图、特征表、可解释阈值规则与留出集混淆矩阵。

数据质量处理均有依据、可复现：
  1. 依据《AI使用报告/第一阶段/课题08核对报告.html》默认排除「快跑」无效组；
  2. 依据同一报告建议，裁掉采集末尾手机已放下的低活动窗口；
  3. 某类样本缺失时禁用对应判别分支，不拿默认阈值硬判。
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
import signal_core as core  # noqa: E402

RESULTS = HERE / "results"
RESULTS.mkdir(exist_ok=True)
RAW = HERE / "gait_raw"          # 早期计划用的扁平目录（可继续兼容）
NEW_RAW = HERE / "课题08"        # 2026-11-16 实际采集目录：课题08/<姿态>/*.csv
STATES = ["静止", "平地慢走", "快跑", "上下楼梯"]
FIELDS = ["file", "state", "window", "svm_mean", "svm_std", "az_range",
          "dominant_hz", "zcr", "centroid"]

# 实际采集目录名 → 官网要求的 4 类姿态标签
LABEL_MAP = {
    "静止": "静止",
    "慢走": "平地慢走",
    "快跑": "快跑",
    "爬楼梯（慢）": "上下楼梯",
    "爬楼梯（快）": "上下楼梯",
}
# 依据 AI使用报告/第一阶段/课题08核对报告.html 的核对结论：
# 快跑组仅 3.88 s，1.66 s 处 PAUSE 后墙钟隔 25.13 s 才 START，
# 真正的跑步极可能发生在暂停期间，逐秒强度单调衰减、无持续周期性冲击。
# 默认不纳入正式结论；重采后用 --include-invalid 或覆盖同名目录即可恢复。
EXCLUDED_LABELS = {"快跑"}


def demo_files(out):
    d = out
    d.mkdir(parents=True, exist_ok=True)
    cfg = {"静止": (0.0, 0.25, 0.02), "平地慢走": (1.7, 1.10, 0.24),
           "快跑": (3.1, 2.60, 0.42), "上下楼梯": (1.9, 1.55, 0.55)}
    paths = []
    for si, (state, (freq, amp, noise)) in enumerate(cfg.items()):
        rnd = random.Random(101 + si * 101)
        rate, secs = 50, 12
        rows = []
        for i in range(rate * secs):
            t = i / rate
            a = 2 * math.pi * freq * t
            rows.append({"Time (s)": round(t, 3),
                         "Acceleration x (m/s^2)": round(amp * .35 * math.sin(a) + rnd.gauss(0, noise * .4), 4),
                         "Acceleration y (m/s^2)": round(amp * .30 * math.sin(a + .7) + rnd.gauss(0, noise * .4), 4),
                         "Acceleration z (m/s^2)": round(1 + amp * math.sin(a + 1.4) + rnd.gauss(0, noise), 4)})
        p = d / f"gait_{state}_demo.csv"
        core.write_csv(p, rows)
        paths.append((state, p))
    print("[demo] 已生成 4 份演示 CSV 到 results/_demo/，仅用于验证脚本流程；正式 results/ 不受影响")
    return paths


def real_files():
    """优先读 gait_raw/；若为空则自动读 2026-11-16 实际采集的 课题08/ 目录。"""
    out = []
    if RAW.exists():
        for p in sorted(RAW.glob("*.csv")):
            state = next((s for s in STATES if s in p.name), "未标注")
            out.append((state, p))
    if out:
        return out
    if NEW_RAW.exists():
        for d in sorted(NEW_RAW.iterdir()):
            if not d.is_dir() or d.name.startswith("_"):
                continue
            label = LABEL_MAP.get(d.name)
            if not label:
                continue
            for p in sorted(d.glob("*.csv")):   # 只取姿态目录直属 CSV，meta/ 不在内
                out.append((label, p))
    return out


def pick_cols(rows):
    cols = list(rows[0].keys())
    tcol = next((c for c in cols if "time" in c.lower() or "时间" in c), cols[0])
    def find(axis):
        for c in cols:
            cl = c.lower()
            if axis in cl and any(k in cl for k in ("acc", "linear", "加速度")):
                return c
        return None
    xs = [find(a) for a in "xyz"]
    if not all(xs) and len(cols) >= 4:
        xs = cols[1:4]
    return tcol, xs


def load_signal(path):
    rows = core.read_csv(path)
    if len(rows) < 10:
        return None
    tcol, (xc, yc, zc) = pick_cols(rows)
    ts = [core.fnum(r.get(tcol)) for r in rows]
    diffs = [ts[i + 1] - ts[i] for i in range(min(60, len(ts) - 1)) if ts[i + 1] > ts[i]]
    rate = round(1.0 / (sum(diffs) / len(diffs))) if diffs else 50
    rate = max(10, min(rate, 200))
    xyz = []
    for r in rows:
        xyz.append((core.fnum(r.get(xc)), core.fnum(r.get(yc)), core.fnum(r.get(zc))))
    # 本次采集用的是 Phyphox「Acceleration (without g)」，即 Linear Acceleration，
    # 已由手机去除重力，单位就是 m/s^2，不要再除 9.81。
    # 若换用含重力的 Accelerometer（z 均值约 9.81），才逐轴去偏置并换算成 g。
    unit = "m/s^2"
    if abs(core.mean([z for _, _, z in xyz])) > 5:
        mx, my, mz = (core.mean([v[i] for v in xyz]) for i in range(3))
        xyz = [(x - mx, y - my, z - mz) for x, y, z in xyz]
        scale = 1.0 / 9.81
        xyz = [(x * scale, y * scale, z * scale) for x, y, z in xyz]
        unit = "g"
    return xyz, rate, len(rows), unit


def trim_inactive_tail(wf, state):
    """按《课题08核对报告》建议，裁掉采集末尾「手机已放下、无动作」的窗口。

    报告指出「爬楼梯（慢）」16 s 后 |a| 降到 0.14~0.28 m/s²，
    按整段求均值会低估楼梯强度。这里从末尾往前，去掉峰值 25% 以下的
    连续低活动窗口；只对运动类生效（静止类本来就全程低活动，不能裁）。
    """
    if state == "静止" or len(wf) < 3:
        return wf, 0
    peak = max(f["svm_mean"] for f in wf)
    cut = len(wf)
    while cut > 1 and wf[cut - 1]["svm_mean"] < peak * 0.25:
        cut -= 1
    return wf[:cut], len(wf) - cut


def window_features(xyz, rate, win_s=2.0):
    n = int(rate * win_s)
    out = []
    for start in range(0, len(xyz) - n + 1, n):
        seg = xyz[start:start + n]
        svm = [math.sqrt(x * x + y * y + z * z) for x, y, z in seg]
        az = [z for _, _, z in seg]
        c = [v - core.mean(svm) for v in svm]
        f = core.spectral_features(c, rate, n_fft=512)
        out.append({"svm_mean": core.mean(svm), "svm_std": core.std(svm),
                    "az_range": core.percentile(az, 95) - core.percentile(az, 5),
                    "dominant_hz": f["dominant_hz"], "zcr": f["zcr"],
                    "centroid": f["centroid"]})
    return out


DEFAULT_THR = {"svm_std": 0.15, "dominant_hz": 2.5, "az_range": 3.0}


def calibrate(train, cats=None):
    """只用训练窗口自动标定 3 个阈值：取两类均值的中点。

    规则结构固定且物理可解释，阈值随数据自适应，避免把合成数据的数值
    硬套到真实采集上；标定过程只用训练窗口，测试窗口完全不参与。
    某类数据暂缺时（例如快跑待重采），对应阈值保留默认值，不强行编造。
    """
    cats = cats or STATES
    by = {s: [f for f in train if f["state"] == s] for s in cats}
    thr = dict(DEFAULT_THR)
    m = lambda s, k: core.mean([f[k] for f in by[s]])
    moving = [s for s in cats if s != "静止" and by[s]]
    if by.get("静止") and moving:
        thr["svm_std"] = (m("静止", "svm_std") +
                          min(m(s, "svm_std") for s in moving)) / 2
    slow = [s for s in ("平地慢走", "上下楼梯") if by.get(s)]
    if by.get("快跑") and slow:
        thr["dominant_hz"] = (m("快跑", "dominant_hz") +
                              max(m(s, "dominant_hz") for s in slow)) / 2
    else:
        # 该类样本缺失时禁用分支，而不是拿默认值硬判。
        # 静止组幅度趋零，去均值后的噪声主频会乱跳到十几 Hz，
        # 若保留 2.5 Hz 默认阈值会把大量静止窗口误判为「快跑」。
        thr["dominant_hz"] = None
    if by.get("上下楼梯") and by.get("平地慢走"):
        thr["az_range"] = (m("上下楼梯", "az_range") + m("平地慢走", "az_range")) / 2
    return thr


def classify(f, thr=None):
    """可解释阈值规则：物理含义明确，便于面试逐条讲清楚。"""
    t = thr or DEFAULT_THR
    if f["svm_std"] < t["svm_std"]:
        return "静止"          # 合加速度几乎不波动
    if t["dominant_hz"] is not None and f["dominant_hz"] >= t["dominant_hz"]:
        return "快跑"          # 步频显著更高（该类样本缺失时分支禁用）
    if f["az_range"] >= t["az_range"]:
        return "上下楼梯"      # 垂直冲击更大
    return "平地慢走"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="跑合成演示数据（仅验证流程，不得写进结论）")
    ap.add_argument("--include-invalid", action="store_true",
                    help="把核对报告判定无效的快跑组也纳入（默认排除）")
    a = ap.parse_args()
    # demo 的全部产物隔离到 results/_demo/，绝不覆盖真实数据的分析结论
    OUT = RESULTS / "_demo" if a.demo else RESULTS
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = demo_files(OUT) if a.demo else real_files()
    if not pairs:
        print("课题08/ 或 gait_raw/ 里还没有 CSV。按 DAILY_PLAN.md 采集，或先加 --demo 试跑。")
        return 0

    skipped = []
    if not a.demo and not a.include_invalid:
        skipped = [(s, p) for s, p in pairs if s in EXCLUDED_LABELS]
        pairs = [(s, p) for s, p in pairs if s not in EXCLUDED_LABELS]
    if skipped:
        print("[数据质量] 依据《课题08核对报告》排除无效组：")
        for s, p in skipped:
            print(f"  - {s} / {p}（有效动作未录到，待重采）")
        print("  重采后用 --include-invalid 可临时纳入对比；正式结论以重采数据为准。")

    feats, waves, units, seen, trimmed = [], {}, set(), {}, []
    for state, p in pairs:
        seen[state] = seen.get(state, 0) + 1
        suffix = "" if seen[state] == 1 else f"_{seen[state]}"
        loaded = load_signal(p)
        if not loaded:
            print(f"  跳过 {p.name}（数据行不足）")
            continue
        xyz, rate, n, unit = loaded
        units.add(unit)
        wf, ncut = trim_inactive_tail(window_features(xyz, rate), state)
        if ncut:
            trimmed.append((p.name, ncut))
        for i, f in enumerate(wf):
            row = {"file": p.name, "state": state, "window": i}
            row.update({k: round(float(f[k]), 5) for k in
                        ["svm_mean", "svm_std", "az_range", "dominant_hz", "zcr", "centroid"]})
            feats.append(row)
        waves.setdefault(state, xyz[:min(len(xyz), rate * 4)])
        # 每种姿态一张三轴波形图
        seg = xyz[:min(len(xyz), rate * 4)]
        series = [{"name": f"{ax} 轴", "color": core.PALETTE[i],
                   "points": [(j / rate, v[i]) for j, v in enumerate(seg)]}
                  for i, ax in enumerate("xyz")]
        core.save_svg(OUT / f"08_wave_{state}{suffix}.svg", 680, 280,
                      core.line_chart(series, title=f"{state} · 三轴加速度波形（前 4 秒）",
                                      xlabel="时间 s", ylabel=f"加速度 {unit}",
                                      width=680, height=280))
        print(f"  {state}: {n} 点 @ {rate} Hz -> {len(wf)} 个窗口，主频 {core.mean([f['dominant_hz'] for f in wf]):.2f} Hz")

    if not feats:
        print("没有提取到有效窗口")
        return 0
    core.write_csv(OUT / "08_features.csv", feats, FIELDS)

    # 特征对比柱状图
    cats = [s for s in STATES if any(f["state"] == s for f in feats)] or list({f["state"] for f in feats})
    dom = [core.mean([f["dominant_hz"] for f in feats if f["state"] == s]) for s in cats]
    core.save_svg(OUT / "08_feature_bars.svg", 680, 280,
                  core.bar_chart(cats, [round(v, 2) for v in dom],
                                 title="各姿态步态主频对比 Hz", ylabel="Hz", value_fmt="{:.2f}"))

    # 四类姿态特征雷达图：各维按全体最大值归一化到 0–1，避免量纲差异压平图形
    rkeys = ["svm_mean", "svm_std", "az_range", "dominant_hz"]
    rnames = ["合加速度均值", "波动强度", "垂直幅度", "步态主频"]
    rmax = {k: max([f[k] for f in feats] + [1e-6]) for k in rkeys}
    rseries = []
    for idx, s in enumerate(cats):
        sub = [f for f in feats if f["state"] == s]
        rseries.append({"name": s, "color": core.PALETTE[idx % len(core.PALETTE)],
                        "values": [round(core.mean([f[k] for f in sub]) / rmax[k], 4)
                                   for k in rkeys]})
    core.save_svg(OUT / "08_radar.svg", 680, 360,
                  core.radar_chart(rnames, rseries, vmax=1.0, width=680, height=360,
                                   title="课题08 · 四类姿态特征雷达（各维按最大值归一化）"))

    # 留出验证：奇偶窗口分开，避免拿同一段数据自测
    train = [f for i, f in enumerate(feats) if i % 2 == 0]
    test = [f for i, f in enumerate(feats) if i % 2 == 1]
    thr = calibrate(train, cats) if train else dict(DEFAULT_THR)
    pairs_pred = [(f["state"], classify(f, thr)) for f in test]
    acc = core.accuracy(pairs_pred)
    m = core.confusion(pairs_pred, cats)
    core.save_svg(OUT / "08_confusion.svg", 680, 320,
                  core.heatmap(m, cats, cats, title="步态阈值规则 · 留出集混淆矩阵"))

    hz_on = thr["dominant_hz"] is not None
    hz_rule = (f"elif dominant_hz >= {thr['dominant_hz']:.2f}:    快跑     # 步频显著更高"
               if hz_on else "# 快跑分支暂禁用：该类有效样本待重采，不拿默认值硬判")
    hz_thr = f"{thr['dominant_hz']:.2f}" if hz_on else "禁用（样本缺失）"

    if skipped:
        scope_note = (f"- 已排除无效组：{', '.join(s for s, _ in skipped)} —— 依据 AI使用报告/第一阶段/课题08核对报告.html，"
                      "有效动作未录到，待重采；重采前本表为 3 类流程验证，**不是最终 4 类结论**。")
    elif a.include_invalid and not a.demo:
        scope_note = ("- **4 类全部纳入（含核对报告判定无效的「快跑」组）**：该组仅 3.88 s 有效动作、"
                      "1.66 s 处 PAUSE 后隔约 25 s 才继续，本次只切出 1 个窗口；快跑分支的阈值由这 1 个窗口标定，"
                      "**置信度极低，仅用于让 4 类的 CSV / 波形图 / 规则形式齐全**，不能当作最终 4 类结论。"
                      "原始文件未删未改，重采 ≥12 s 连续数据后覆盖 `课题08/快跑/running.csv` 再重跑即可。")
    else:
        scope_note = "- 参与类别：4 类齐全"

    md = [
        "# 课题 08 · 步态阈值规则与验证", "",
        "> 由 `analyze_gait.py` 生成。当前为" + ("**合成演示数据（不得写进结论）**" if a.demo else "**真实采集数据**") + "。", "",
        f"- 加速度单位：`{' / '.join(sorted(units))}`（Phyphox「Acceleration (without g)」导出的线性加速度）",
        f"- 数据源：`{NEW_RAW.name}/` 下各姿态目录" if not a.demo else "- 数据源：`results/_demo/`",
        scope_note,
        "",
        "## 特征定义", "",
        "| 特征 | 物理含义 |", "|---|---|",
        "| `svm_mean` | 合加速度均值，区分静止与运动 |",
        "| `svm_std` | 合加速度波动强度 |",
        "| `az_range` | 垂直轴 95–5 分位幅度，楼梯冲击更大 |",
        "| `dominant_hz` | 合加速度主频 ≈ 步频 |",
        "| `zcr` / `centroid` | 过零率 / 频谱质心，辅助表征动作剧烈程度 |", "",
        "## 可解释规则", "",
        "```python",
        f"if svm_std < {thr['svm_std']:.3f}:              静止     # 合加速度几乎不波动",
        hz_rule,
        f"elif az_range >= {thr['az_range']:.2f}:           上下楼梯 # 垂直冲击更大",
        "else:                                   平地慢走",
        "```", "",
        f"当前阈值由**训练窗口自动标定**（取两类均值中点）：`svm_std={thr['svm_std']:.3f}`、"
        f"`dominant_hz={hz_thr}`、`az_range={thr['az_range']:.2f}`；"
        "测试窗口完全不参与标定。", "",
        "## 留出集验证", "",
        f"- 总窗口 {len(feats)} 个，奇数窗训练 / 偶数窗测试，测试 {len(test)} 个",
        f"- **留出集准确率：{acc * 100:.1f}%**", "",
        "## 各姿态特征均值（用真实数据重标定阈值时看这张表）", "",
        "| 姿态 | 合加速度均值 | 波动 std | 垂直幅度 | 主频 Hz |", "|---|---|---|---|---|",
    ]
    for s in cats:
        sub = [f for f in feats if f["state"] == s]
        md.append(f"| {s} | {core.mean([f['svm_mean'] for f in sub]):.3f} | "
                  f"{core.mean([f['svm_std'] for f in sub]):.3f} | "
                  f"{core.mean([f['az_range'] for f in sub]):.3f} | "
                  f"{core.mean([f['dominant_hz'] for f in sub]):.2f} |")
    md += ["", "## 阈值重标定说明", "",
           "- 三个阈值由脚本从训练窗口自动标定（两类均值中点），换真实数据后自动更新，不用手改代码。",
           "- 若准确率不理想：先看上表哪两类特征范围重叠，考虑延长窗口或更多依赖主频类稳健特征。",
           "- 手机固定位置（口袋 / 手持 / 臂包）会显著改变幅度类特征，全程保持一致并在 README 写明。",
           "- 主频比幅度更稳健：不同人、不同鞋、不同手机位置下，步频变化小于幅度变化。", ""]
    if trimmed:
        md += ["## 依据核对报告做的尾部裁剪", "",
               "《课题08核对报告》指出部分组末尾手机已放下、无动作，按整段求均值会低估强度。",
               "脚本从末尾往前去掉峰值 25% 以下的连续低活动窗口（仅对运动类生效）：", "",
               "| 文件 | 裁掉窗口数 |", "|---|---|"]
        md += [f"| `{name}` | {n} |" for name, n in trimmed]
        md.append("")
    if not a.demo:
        md += ["## 当前结果的诚实解读", ""]
        if a.include_invalid:
            md += [
                "- 4 类的**原始 CSV、波形图、可解释阈值规则已齐**，满足官网形式要求；"
                "但「快跑」组依据《课题08核对报告》判定为无效采集，本次只是如实纳入并显著标注，"
                "**没有删除、没有修改、没有补造数据**。",
                f"- 留出集 {acc * 100:.1f}% 偏低的主因有两条：① 快跑只有 1 个有效窗口，"
                "阈值几乎无法可靠标定；② 平地慢走与上下楼梯的 `az_range` / `svm_std` 范围高度重叠，"
                "手机佩戴方式与行走速度带来的幅度差异盖过了动作类型本身的差异。",
                "- 官网对第一阶段要的是「原始 CSV + 波形图 + 可解释阈值规则 + 现场证据」，"
                "并未要求高准确率；把分不开的原因讲清楚，比报一个挑出来的漂亮数字更重要。",
                "- **若今晚还有 10 分钟**：用 Phyphox 重采快跑 ≥12 s 连续、中途不要点暂停，"
                "覆盖 `课题08/快跑/running.csv`，再跑一次 "
                "`python 01_Stage1_Field_Measurement\\analyze_gait.py --include-invalid`，"
                "脚本会自动重标定阈值并重出全部图表，不需要改代码。",
                "- 其余改进：每类补到 3 次以估计类内波动；改用主频 / 频谱质心等相对特征为主判据；"
                "全程固定同一手机位置并写进日志。", ""]
        else:
            md += [
                "- 本表的准确率是**流程验证值，不是最终结论**：4 类里「快跑」有效样本待重采，当前只剩 3 类。",
                "- 官网对第一阶段要的是「原始 CSV + 波形图 + 可解释阈值规则 + 现场证据」，"
                "并未要求高准确率；把分不开的原因讲清楚，比报一个挑出来的漂亮数字更重要。",
                "- 平地慢走与上下楼梯的 `az_range`、`svm_std` 范围高度重叠，"
                "说明手机佩戴方式与行走速度带来的幅度差异，已经盖过了动作类型本身的差异。",
                "- 下一步：① 重采快跑（≥12 s 连续、中途不要暂停）；② 每类补到 3 次以估计类内波动；"
                "③ 改用主频 / 频谱质心等相对特征为主判据；④ 全程固定同一手机位置并写进日志。", ""]
    (OUT / "08_threshold_rules.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"留出集准确率 {acc * 100:.1f}%")
    print("已输出 08_features.csv / 08_wave_*.svg / 08_radar.svg / 08_feature_bars.svg / 08_confusion.svg / 08_threshold_rules.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
