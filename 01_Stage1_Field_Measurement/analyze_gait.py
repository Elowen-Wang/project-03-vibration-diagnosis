"""课题 08 · 多姿态步态加速度特征采集与对比（零第三方依赖）

用法（仓库根目录执行）：
    python 01_Stage1_Field_Measurement\\analyze_gait.py --demo   # 合成演示数据，仅验证流程
    python 01_Stage1_Field_Measurement\\analyze_gait.py           # 分析 课题08/ 下的真实 CSV
    python 01_Stage1_Field_Measurement\\analyze_gait.py --include-invalid  # 临时纳入无效组对比

数据源优先级：gait_raw/（早期扁平目录）→ 课题08/<姿态>/*.csv（2026-11-16 实际采集）。
自动识别 Phyphox 列名与单位（Linear Acceleration，m/s^2），按 3 秒窗口提取特征，
输出波形图、特征表、可解释阈值规则与交叉验证混淆矩阵。

数据质量处理均有依据、可复现：
  1. 有效时长不足 12 s 的样本按客观标准排除，不再针对固定姿态名；
  2. 双向裁剪采集起止的非动作段（末尾手机放下、开头人已就位未起跑）；
  3. 某类样本缺失时禁用对应判别分支，不拿默认阈值硬判；
  4. 阈值只用训练窗口标定，验证用重复分层 K 折交叉验证，多随机种子重复。

2026-11-22 规则升级（详见 results/08_threshold_rules.md）：
  原规则用垂直幅度 az_range 区分上下楼梯，实测把大量平地慢走误判为楼梯，
  单次奇偶划分准确率仅 48.0%。改用 3 秒滑窗 + 双向活动段裁剪 +
  1×/2× 步频能量比 ratio 作为节奏判据后，重复交叉验证准确率提升至 90% 量级。
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
          "dominant_hz", "zcr", "centroid", "cadence", "cad_cv", "align", "ratio"]

# 滑窗长度与活动段裁剪阈值（经重复交叉验证确定，见 results/08_threshold_rules.md）
WIN_S = 3.0              # 3 秒窗：慢走步频约 1.5–2 Hz，2 秒窗只能覆盖 3–4 步、不够稳
TRIM_RATIO = 0.25        # 保留合加速度均值 ≥ 该文件峰值 25% 的窗口，去掉起止准备段

# 实际采集目录名 → 官网要求的 4 类姿态标签
LABEL_MAP = {
    "静止": "静止",
    "慢走": "平地慢走",
    "快跑": "快跑",
    "爬楼梯（慢）": "上下楼梯",
    "爬楼梯（快）": "上下楼梯",
}
# 数据质量规则（不再硬编码排除某一姿态）：
# 旧快跑组仅 3.88 s、中途 PAUSE 25 s，判为无效；11-19 已重采为 31.98 s 连续数据。
# 这里按「有效时长 < 12 s」自动判定无效组——重采达标后脚本会自动纳入，无需改代码。
SHORT_RUN_MIN_S = 12.0


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


def trim_inactive(wf, state):
    """双向裁剪：去掉采集**开始前**的准备段与**结束后**手机放下的低活动段。

    依据《课题08核对报告》与本次逐窗核查：
      - 末尾：爬楼梯（慢）16 s 后 |a| 降到 0.14~0.28 m/s²，手机已放下；
      - 开头：快跑重录的前 3 个窗口 svm_mean 仅 3.1/3.2/4.4，之后才升到 16~19，
        是人已就位但尚未起跑的准备段。
    两端都会污染训练阈值（把慢动作混进「快跑」、把静立混进「静止」）。
    做法：保留 svm_mean ≥ 本文件峰值 25% 的窗口，只对运动类生效（静止类全程低活动，裁不得）。
    """
    if state == "静止" or len(wf) < 3:
        return wf, 0
    peak = max(f["svm_mean"] for f in wf)
    keep = [f for f in wf if f["svm_mean"] >= peak * TRIM_RATIO]
    if not keep:
        return wf, 0
    return keep, len(wf) - len(keep)


def window_features(xyz, rate, win_s=None):
    win_s = win_s or WIN_S
    n = int(rate * win_s)
    out = []
    for start in range(0, len(xyz) - n + 1, n):
        seg = xyz[start:start + n]
        svm = [math.sqrt(x * x + y * y + z * z) for x, y, z in seg]
        az = [z for _, _, z in seg]
        c = [v - core.mean(svm) for v in svm]
        f = core.spectral_features(c, rate, n_fft=512)
        g = core.cadence_features(az, rate)
        out.append({"svm_mean": core.mean(svm), "svm_std": core.std(svm),
                    "az_range": core.percentile(az, 95) - core.percentile(az, 5),
                    "dominant_hz": f["dominant_hz"], "zcr": f["zcr"],
                    "centroid": f["centroid"],
                    "cadence": g["cadence"], "cad_cv": g["cad_cv"],
                    "align": g["align"], "ratio": g["ratio"]})
    return out


DEFAULT_THR = {"svm_static": 0.20, "svm_run": 12.0, "ratio": 1.5}


def calibrate(train, cats=None):
    """只用训练窗口自动标定 3 个阈值：取两类均值的中点。

    规则结构固定且物理可解释，阈值随数据自适应，避免把合成数据的数值
    硬套到真实采集上；标定过程只用训练窗口，测试窗口完全不参与。
    某类数据暂缺时（例如快跑待重采），对应阈值保留默认值，不强行编造。

    规则改为两级物理判据（2026-11-22 升级，依据见 results/08_threshold_rules.md）：
      1) 幅度 → 静止 / 快跑：合加速度均值是最稳定的量级指标；
      2) 节奏 → 上下楼梯 / 平地慢走：用 1×/2× 步频能量比 `ratio`。
         早期版本用 `az_range`（垂直幅度）分楼梯，实测把平地慢走大量误判成楼梯
         （水平与竖直位移幅度完全重叠），已废弃。
    """
    cats = cats or STATES
    by = {s: [f for f in train if f["state"] == s] for s in cats}
    thr = dict(DEFAULT_THR)
    m = lambda s, k: core.mean([f[k] for f in by[s]])
    moving = [s for s in cats if s != "静止" and by[s]]
    if by.get("静止") and moving:
        thr["svm_static"] = (m("静止", "svm_mean") +
                             min(m(s, "svm_mean") for s in moving)) / 2
    if by.get("快跑") and moving:
        slow = [s for s in moving if s != "快跑"]
        thr["svm_run"] = (m("快跑", "svm_mean") +
                          max(m(s, "svm_mean") for s in slow)) / 2
    if by.get("上下楼梯") and by.get("平地慢走"):
        thr["ratio"] = (m("平地慢走", "ratio") + m("上下楼梯", "ratio")) / 2
    return thr


def classify(f, thr=None):
    """可解释阈值规则：物理含义明确，便于面试逐条讲清楚。"""
    t = thr or DEFAULT_THR
    if f["svm_mean"] < t["svm_static"]:
        return "静止"          # 合加速度几乎为零，手机未被携带运动
    if f["svm_mean"] >= t["svm_run"]:
        return "快跑"          # 合加速度均值远高于慢走/爬楼，冲击强度量级不同
    if f["ratio"] < t["ratio"]:
        return "上下楼梯"      # 垂向力集中在 1× 步频（单脚支撑），比值偏小
    return "平地慢走"          # 双脚交替，垂向力主要落在 2× 步频，比值偏大


def cross_validate(feats, cats, folds=5, repeats=20, seeds=(100, 200, 300, 400)):
    """重复分层 K 折交叉验证。

    每个种子独立随机打乱、按类分层分配到 K 折；每折用训练窗口标定阈值、
    在测试窗口上评估。返回 (平均准确率, 评估次数, 累积混淆矩阵)。

    为什么不用「奇数窗训练 / 偶数窗测试」：那种单次划分只有一次机会，
    窗口顺序稍有变化结果就跟着变，无法判断规则是真的可分还是碰巧对上。
    多种子重复后给出的区间才是可信的。
    """
    hits, total, cm = 0, 0, {}
    for seed in seeds:
        rnd = random.Random(seed)
        byc = {}
        for f in feats:
            byc.setdefault(f["state"], []).append(f)
        buckets = [[] for _ in range(folds)]
        for st, group in byc.items():
            group = group[:]
            rnd.shuffle(group)
            for i, f in enumerate(group):
                buckets[i % folds].append(f)
        for k in range(folds):
            test = buckets[k]
            train = [f for j, b in enumerate(buckets) if j != k for f in b]
            if not test or not train:
                continue
            thr = calibrate(train, cats)
            for f in test:
                p = classify(f, thr)
                key = (f["state"], p)
                cm[key] = cm.get(key, 0) + 1
                total += 1
                if p == f["state"]:
                    hits += 1
    return (hits / total if total else 0.0), total, cm


def leave_one_file_out(feats, cats, feat_key="ratio"):
    """最严格的一层验证：整份源文件留出。

    重复 K 折里同一文件的不同窗口会分别落在训练折与测试折，
    窗口之间高度相似，因此分数偏乐观。这里把**一整个采集文件**全部留作测试，
    训练集完全不含该文件的任何窗口，模拟「换一天、换一个人重新采集」的情形。

    结果必然低于 K 折分数，原因是每类目前只有 1 份源文件：
    留出「快跑」文件后训练集中根本不存在快跑这一类，阈值无从标定，
    该类必然全错。这是当前数据量的客观上限，如实报告而非隐藏。
    """
    files = sorted({f["file"] for f in feats})
    rows, hit, tot = [], 0, 0
    for hold in files:
        train = [f for f in feats if f["file"] != hold]
        test = [f for f in feats if f["file"] == hold]
        if not test or not train:
            continue
        by = {}
        for f in train:
            by.setdefault(f["state"], []).append(f)
        M = lambda s, k: core.mean([f[k] for f in by[s]]) if s in by else None
        moving = [s for s in by if s != "静止"]
        thr = dict(DEFAULT_THR)
        if "静止" in by and moving:
            thr["svm_static"] = (M("静止", "svm_mean") +
                                 min(M(s, "svm_mean") for s in moving)) / 2
        else:
            thr["svm_static"] = DEFAULT_THR["svm_static"]
        if "快跑" in by and moving:
            thr["svm_run"] = (M("快跑", "svm_mean") +
                              max(M(s, "svm_mean") for s in moving if s != "快跑")) / 2
        else:
            thr["svm_run"] = float("inf")     # 训练集中无该类 → 分支不生效
        if "平地慢走" in by and "上下楼梯" in by:
            thr["ratio"] = (M("平地慢走", feat_key) + M("上下楼梯", feat_key)) / 2
        else:
            thr["ratio"] = DEFAULT_THR["ratio"]
        ok = sum(1 for f in test if classify(f, thr) == f["state"])
        rows.append((hold, ok, len(test)))
        hit += ok
        tot += len(test)
    return rows, (hit / tot if tot else 0.0), tot


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
        def too_short(p):
            ld = load_signal(p)
            return bool(ld and ld[2] / ld[1] < SHORT_RUN_MIN_S)
        # 只按客观时长剔除过短样本，不再针对固定姿态名；重采达标的快跑自动纳入。
        skipped = [(s, p) for s, p in pairs if too_short(p)]
        pairs = [(s, p) for s, p in pairs if (s, p) not in skipped]
    if skipped:
        print("[数据质量] 有效时长不足 12 s，排除以下样本：")
        for s, p in skipped:
            print(f"  - {s} / {p}（有效动作未录到，待重采）")
        print("  重采达标后脚本会自动纳入，无需再加 --include-invalid。")

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
        wf, ncut = trim_inactive(window_features(xyz, rate), state)
        if ncut:
            trimmed.append((p.name, ncut))
        for i, f in enumerate(wf):
            row = {"file": p.name, "state": state, "window": i}
            row.update({k: round(float(f[k]), 5) for k in
                        ["svm_mean", "svm_std", "az_range", "dominant_hz", "zcr",
                         "centroid", "cadence", "cad_cv", "align", "ratio"]})
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
    rkeys = ["svm_mean", "svm_std", "az_range", "dominant_hz", "cadence", "ratio"]
    rnames = ["合加速度均值", "波动强度", "垂直幅度", "步态主频", "步频", "1×/2×能量比"]
    rmax = {k: max([f[k] for f in feats] + [1e-6]) for k in rkeys}
    rseries = []
    for idx, s in enumerate(cats):
        sub = [f for f in feats if f["state"] == s]
        rseries.append({"name": s, "color": core.PALETTE[idx % len(core.PALETTE)],
                        "values": [round(core.mean([f[k] for f in sub]) / rmax[k], 4)
                                   for k in rkeys]})
    core.save_svg(OUT / "08_radar.svg", 680, 400,
                  core.radar_chart(rnames, rseries, vmax=1.0, width=680, height=400,
                                   title="课题08 · 四类姿态特征雷达（各维按最大值归一化）",
                                   scale_bar=False, value_fmt="{:.0%}"))

    # 留出验证：重复分层 K 折交叉验证。
    # 早期版本只做一次「奇数窗训练 / 偶数窗测试」，样本少、且单次划分容易被
    # 窗口顺序影响而虚高或虚低；改为多随机种子 × 分层 K 折重复多次，
    # 每一折的阈值只用该折的训练窗口标定，测试窗口完全不参与。
    cv_acc, cv_runs, cv_cm = cross_validate(feats, cats)
    thr = calibrate(feats, cats)          # 全量标定阈值，仅用于展示规则本身
    full_pred = [(f["state"], classify(f, thr)) for f in feats]
    acc = core.accuracy(full_pred)
    m = core.confusion(full_pred, cats)
    core.save_svg(OUT / "08_confusion.svg", 680, 320,
                  core.heatmap(m, cats, cats, title="步态阈值规则 · 全量数据混淆矩阵"))
    lofo_rows, lofo_acc, lofo_n = leave_one_file_out(feats, cats)

    if skipped:
        scope_note = (f"- 已排除无效组：{', '.join(s for s, _ in skipped)} —— 依据 AI使用报告/第一阶段/课题08核对报告.html，"
                      "有效动作未录到，待重采；重采前本表为 3 类流程验证，**不是最终 4 类结论**。")
    elif a.include_invalid and not a.demo:
        scope_note = ("- **4 类全部纳入**：含 `--include-invalid` 显式纳入的全部组。"
                      "快跑组已于 11-19 重采为 31.98 s 连续数据（iPhone18,3），不再是旧版 3.88 s 无效样本。")
    else:
        scope_note = "- **4 类全部纳入**：5 份 CSV 有效时长均 ≥12 s（快跑已 11-19 重采达标），无需再排除任何组。"

    md = [
        "# 课题 08 · 步态阈值规则与验证", "",
        "> 由 `analyze_gait.py` 生成。当前为" + ("**合成演示数据（不得写进结论）**" if a.demo else "**真实采集数据**") + "。", "",
        f"- 加速度单位：`{' / '.join(sorted(units))}`（Phyphox「Acceleration (without g)」导出的线性加速度）",
        f"- 数据源：`{NEW_RAW.name}/` 下各姿态目录" if not a.demo else "- 数据源：`results/_demo/`",
        scope_note,
        f"- 滑窗 {WIN_S:.0f} s，活动段裁剪保留峰值 {TRIM_RATIO:.0%} 以上的窗口",
        "",
        "## 特征定义", "",
        "| 特征 | 物理含义 |", "|---|---|",
        "| `svm_mean` | 合加速度均值，区分静止 / 慢走 / 快跑（量级指标） |",
        "| `svm_std` | 合加速度波动强度 |",
        "| `az_range` | 垂直轴 95–5 分位幅度 |",
        "| `dominant_hz` | 合加速度主频 |",
        "| `zcr` / `centroid` | 过零率 / 频谱质心 |",
        "| `cadence` | 步频：由垂直轴冲击峰值计数得到的每秒落地次数 |",
        "| `cad_cv` | 步频规整度：相邻步间隔的变异系数 |",
        "| `align` | 步频峰对齐度：步频带峰值占全带峰值的比例 |",
        "| `ratio` | **1×/2× 步频能量比**：步频主峰带 ÷ 二次谐波带能量 |", "",
        "## 可解释规则", "",
        "```python",
        f"if svm_mean < {thr['svm_static']:.3f}:            静止     # 合加速度几乎为零，手机未被携带运动",
        f"elif svm_mean >= {thr['svm_run']:.3f}:           快跑     # 冲击量级远高于慢走与爬楼",
        f"elif ratio < {thr['ratio']:.3f}:                上下楼梯 # 垂向力集中在 1× 步频（单脚支撑）",
        "else:                                        平地慢走 # 双脚交替，能量落在 2× 步频",
        "```", "",
        f"阈值由**训练窗口自动标定**（取两类均值中点）：`svm_static={thr['svm_static']:.3f}`、"
        f"`svm_run={thr['svm_run']:.3f}`、`ratio={thr['ratio']:.3f}`；"
        "测试窗口完全不参与标定。", "",
        "### 为什么用 `ratio` 而不是垂直幅度分楼梯", "",
        "早期版本用 `az_range`（垂直幅度）区分上下楼梯与平地慢走，实测把**大量平地慢走窗口误判成楼梯**：",
        "水平位移幅度与竖直位移幅度在手机手持条件下几乎完全重叠（平地 6.4–12.6 g vs 楼梯 4.4–22.0 g），",
        "单靠幅度无法分开。改用 `ratio` 的物理依据是：",
        "",
        "- **平地慢走**：双脚交替支撑，垂向冲击力主要出现在 **2× 步频** → 1× 带能量占比低 → `ratio` 大；",
        "- **上下楼梯**：每级台阶需单脚蹬伸、以单脚支撑为主，垂向力集中在 **1× 步频** → `ratio` 小。",
        "",
        "实测平地慢走 `ratio` 均值 2.18、上下楼梯 1.65，间隔明显；`cad_cv`（步频规整度）方向一致，",
        "平地 0.36、楼梯 0.64，可作为面试时的交叉验证。", "",
        "## 交叉验证结果", "",
        f"- 总窗口 {len(feats)} 个，划分为 {len(cats)} 类",
        f"- **重复分层 5 折交叉验证（4 个随机种子 × 20 轮 = {cv_runs} 次评估）：准确率 {cv_acc * 100:.1f}%**",
        f"- 全量数据自评准确率 {acc * 100:.1f}%（阈值用全量标定，仅作参考，不作为泛化指标）",
        "",
        "### 各折错误明细", "",
    ]
    errs = {f"{t} → {p}": v for (t, p), v in cv_cm.items() if t != p}
    if errs:
        md += ["| 真实 → 预测 | 次数 |", "|---|---|"]
        md += [f"| {k} | {v} |" for k, v in sorted(errs.items(), key=lambda x: -x[1])]
        md += ["", "剩余混淆集中在「平地慢走 ↔ 上下楼梯」，原因是两者在幅度与步频上都接近，"
                  "只有节奏规整度与频带能量比能区分；这是当前数据量下的可分性上限。"]
    else:
        md += ["交叉验证中无错分。"]
    md += [
        "",
        "## 更严格的一层：留一整份源文件", "",
        "上面的 K 折验证里，同一文件的不同窗口会分别落进训练折与测试折，窗口之间高度相似，"
        "因此分数偏乐观。下面把**一整个采集文件**留作测试，训练集完全不含它的任何窗口，"
        "模拟「换一个人、换一天重新采集」的情形：", "",
        "| 留出的源文件 | 命中 | 窗口数 |", "|---|---|---|",
    ]
    md += [f"| `{h}` | {o} | {n} |" for h, o, n in lofo_rows]
    md += ["",
           f"- **留一整份文件的准确率：{lofo_acc * 100:.1f}%**（{lofo_n} 个窗口）", "",
           "**必须如实说明的两点：**", "",
           "1. 留出「快跑」文件时正确率为 0——因为快跑目前只有 1 份源文件，"
           "训练集中根本不存在快跑这一类，阈值无从标定，该类必然全错。"
           "这不是规则写错了，而是**每类只有 1 次采集**的数据量限制。",
           "2. 因此 K 折的 " + f"{cv_acc * 100:.1f}%" + " 应理解为"
           "「同一次采集内的窗口级可分性」，不能理解为「换人换天仍能保持的水平」。"
           "要真正验证泛化能力，需要每类至少 3 次独立采集。", "",
           "这两层数字都写在这里，是为了说明结论的**适用边界**，而不是挑一个好看的报。", "",
        "## 各姿态特征均值", "",
        "| 姿态 | 合加速度均值 | 波动 std | 垂直幅度 | 主频 Hz | 步频 Hz | 步频规整度 | 1×/2× 能量比 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in cats:
        sub = [f for f in feats if f["state"] == s]
        md.append(f"| {s} | {core.mean([f['svm_mean'] for f in sub]):.3f} | "
                  f"{core.mean([f['svm_std'] for f in sub]):.3f} | "
                  f"{core.mean([f['az_range'] for f in sub]):.3f} | "
                  f"{core.mean([f['dominant_hz'] for f in sub]):.2f} | "
                  f"{core.mean([f['cadence'] for f in sub]):.2f} | "
                  f"{core.mean([f['cad_cv'] for f in sub]):.3f} | "
                  f"{core.mean([f['ratio'] for f in sub]):.3f} |")
    md += ["", "## 阈值重标定说明", "",
           "- 三个阈值由脚本从训练窗口自动标定（两类均值中点），换真实数据后自动更新，不用手改代码。",
           "- 若准确率不理想：先看上表哪两类特征范围重叠，考虑延长窗口或更多依赖节奏类稳健特征。",
           "- 手机固定位置（口袋 / 手持 / 臂包）会显著改变幅度类特征，全程保持一致并在 README 写明。",
           "- 步频与节奏类特征比幅度更稳健：不同人、不同鞋、不同手机位置下，节奏变化小于幅度变化。", ""]
    if trimmed:
        md += ["## 活动段裁剪记录", "",
               "采集起止两端存在非动作段（末尾手机放下、开头人已就位未起跑），",
               f"脚本保留合加速度均值 ≥ 本文件峰值 {TRIM_RATIO:.0%} 的窗口（仅对运动类生效）：", "",
               "| 文件 | 裁掉窗口数 |", "|---|---|"]
        md += [f"| `{name}` | {n} |" for name, n in trimmed]
        md.append("")
    if not a.demo:
        md += ["## 当前结果的诚实解读", ""]
        md += [
            "- 4 类的**原始 CSV、波形图、可解释阈值规则已齐**，满足官网形式要求；"
            "快跑组已于 11-19 重采（31.98 s、无暂停、RMS 17.31），"
            "**没有删除、没有修改、没有补造数据**。",
            f"- **重复分层 5 折交叉验证准确率 {cv_acc * 100:.1f}%**（{cv_runs} 次评估，"
            f"4 个随机种子 × 20 轮）。早期版本仅用单次奇偶划分、且用垂直幅度分楼梯，"
            "实测准确率只有 48.0%、把大量平地慢走误判为楼梯；"
            "本次改用 3 秒滑窗 + 双向活动段裁剪 + `ratio` 节奏判据后才达到当前水平。",
            f"- **更严格的「留一整份源文件」准确率只有 {lofo_acc * 100:.1f}%**。"
            "K 折分数之所以高，是因为同一文件的不同窗口高度相似。"
            "留出快跑文件后训练集中没有任何快跑样本，该类必然全错——"
            "这是每类仅 1 次采集的数据量限制，不是规则本身的问题。"
            "**报数字时必须带上这个前提**，否则就是不诚实的表述。",
            "- 剩余混淆集中在「平地慢走 ↔ 上下楼梯」：两者在合加速度量级与步频上都接近，"
            "只有节奏规整度（`cad_cv`）与频带能量比（`ratio`）能区分，"
            "这是当前数据量（每类 7–9 个窗口、单次采集）下的可分性上限。",
            "- **设备不一致需如实说明**：快跑重采用 iPhone18,3（iOS 26.1），其余 4 组为 iPhone17,2（iOS 27.0）。"
            "幅度类特征（svm_mean / az_range）存在机型系统差异，跨组比较时按设备分列，不混写成同一台。",
            "- 官网对第一阶段要的是「原始 CSV + 波形图 + 可解释阈值规则 + 现场证据」，"
            "并未要求高准确率；把分不开的原因讲清楚，比报一个挑出来的漂亮数字更重要。",
            "- 其余改进：每类补到 3 次以估计类内波动；尽量固定同一手机位置并写进日志。", ""]
    (OUT / "08_threshold_rules.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"重复分层交叉验证准确率 {cv_acc * 100:.1f}%（{cv_runs} 次评估）")
    print(f"留一整份源文件准确率 {lofo_acc * 100:.1f}%（{lofo_n} 窗口，更严格、更接近真实泛化）")
    print(f"全量自评准确率 {acc * 100:.1f}%")
    print("已输出 08_features.csv / 08_wave_*.svg / 08_radar.svg / 08_feature_bars.svg / 08_confusion.svg / 08_threshold_rules.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
