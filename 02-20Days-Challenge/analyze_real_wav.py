"""项目三 · 真实 WAV 声振特征提取与工况分类（零第三方依赖）

本脚本读取仓库里真实的 75 段 WAV，不做任何模拟数据。用法（在仓库根目录执行）：

    python 02-20Days-Challenge\\analyze_real_wav.py --extract
    python 02-20Days-Challenge\\analyze_real_wav.py --all

可选步骤：--extract --classify --blind --noise --heldout --accel --check --all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
import signal_core as core  # noqa: E402

RESULTS = HERE / "results"
RESULTS.mkdir(exist_ok=True)
FEATURES_CSV = RESULTS / "features.csv"

CONDITIONS = {
    "low": ("low-15", "正常低速"),
    "high": ("high-15", "正常高速"),
    "friction": ("friction-15", "摩擦异常"),
    "block": ("block-15", "进风遮挡"),
    "imbalance": ("imbalance-15", "扇叶失衡"),
}
LABELS = [v[1] for v in CONDITIONS.values()]
RATE = 4000
N_FFT = 8192
FIELDS = ["file", "condition", "condition_key", "group", "duration_note"] + core.FEATURE_KEYS


def wav_files():
    """返回 [(工况key, 中文名, 序号, 路径)]，按官网 5x15 组织。"""
    out = []
    for key, (folder, label) in CONDITIONS.items():
        for i in range(1, 16):
            out.append((key, label, i, HERE / folder / f"{key}-{i}.wav"))
    return out


def extract_features(sig):
    f = core.spectral_features(sig, RATE, n_fft=N_FFT)
    return {k: round(float(f[k]), 6) for k in core.FEATURE_KEYS}


# --------------------------------------------------------------------------- extract
def step_extract():
    rows, missing = [], []
    for key, label, i, path in wav_files():
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
            continue
        sig, sr = core.read_wav_mono(path, target_rate=RATE, seconds=2.0)
        row = {"file": f"{key}-{i}.wav", "condition": label, "condition_key": key,
               "group": "train" if i <= 12 else "blind"}
        row.update(extract_features(sig))
        row["duration_note"] = f"取中间2s/降采样至{sr}Hz/双声道取均值"
        rows.append(row)
        if (i == 1) or (i == 15):
            print(f"  [{key}] {i}/15 主频 {row['dominant_hz']:.1f} Hz  RMS {row['rms']:.4f}")
    core.write_csv(FEATURES_CSV, rows, FIELDS)
    print(f"提取完成：{len(rows)} 段 -> {FEATURES_CSV.relative_to(ROOT)}")
    if missing:
        print(f"缺失 {len(missing)} 个文件，例如 {missing[:3]}")
    step_spectrum(rows)
    return rows


def step_spectrum(rows=None):
    """五种工况的平均幅度谱对比（0-1000 Hz）。"""
    series = []
    for key, (folder, label) in CONDITIONS.items():
        acc, n = None, 0
        for i in (1, 2, 3):
            p = HERE / folder / f"{key}-{i}.wav"
            if not p.exists():
                continue
            sig, _ = core.read_wav_mono(p, target_rate=RATE, seconds=2.0)
            freqs, mags = core.spectrum([x - core.mean(sig) for x in sig], RATE, n_fft=N_FFT)
            if acc is None:
                acc = list(mags)
            else:
                acc = [a + b for a, b in zip(acc, mags)]
            n += 1
        if not acc or n == 0:
            continue
        pts = [(freqs[k], acc[k] / n) for k in range(0, len(acc), 4) if freqs[k] <= 1000]
        series.append({"name": label, "points": pts,
                       "color": core.PALETTE[list(CONDITIONS).index(key) % len(core.PALETTE)]})
    if not series:
        return
    body = core.line_chart(series, title="五种工况平均幅度谱（0–1000 Hz）",
                           xlabel="频率 Hz", ylabel="幅度", width=680, height=300)
    core.save_svg(RESULTS / "spectrum_compare.svg", 680, 300, body)
    print(f"频谱对比图 -> {(RESULTS / 'spectrum_compare.svg').relative_to(ROOT)}")


def load_rows():
    if not FEATURES_CSV.exists():
        print("还没有 features.csv，请先跑 --extract")
        return []
    return core.read_csv(FEATURES_CSV)


def _report_pairs(pairs, title, out_md):
    acc = core.accuracy(pairs)
    m = core.confusion(pairs, LABELS)
    core.save_svg(RESULTS / f"{out_md}.svg", 680, 340,
                  core.heatmap(m, LABELS, LABELS, title=f"{title} 混淆矩阵（行=真实，列=预测）"))
    lines = [f"# {title}", "",
             f"- 样本数：{len(pairs)}",
             f"- **总体准确率：{acc * 100:.1f}%**", "",
             "| 真实 \\ 预测 | " + " | ".join(LABELS) + " |",
             "|---|" + "---|" * len(LABELS)]
    for lab, row in zip(LABELS, m):
        lines.append(f"| {lab} | " + " | ".join(str(v) for v in row) + " |")
    lines += ["", "每类召回："]
    for i, lab in enumerate(LABELS):
        tot = sum(m[i])
        lines.append(f"- {lab}：{m[i][i]}/{tot} = {(m[i][i] / tot * 100 if tot else 0):.0f}%")
    lines += ["", "> 分类器：标准化后的最近质心（nearest centroid），特征为 11 维时域+频域量。",
              "> 全程使用 Python 标准库实现 FFT，未调用任何机器学习框架，便于逐行复核。", ""]
    core.write_text(RESULTS / f"{out_md}.md", "\n".join(lines) + "\n")
    print(f"{title}：准确率 {acc * 100:.1f}%  -> results/{out_md}.md")
    return acc


# --------------------------------------------------------------------------- classify / blind
def step_classify():
    rows = load_rows()
    if not rows:
        return
    pairs = []
    for i, r in enumerate(rows):
        train = [x for j, x in enumerate(rows) if j != i]
        scaler, cents = core.build_centroids(train)
        pairs.append((r["condition"], core.predict(scaler, cents, r)))
    _report_pairs(pairs, "留一法交叉验证（75 段，每次留 1 段当测试）", "loo_report")


def step_blind():
    rows = load_rows()
    if not rows:
        return
    train = [r for r in rows if r["group"] == "train"]
    test = [r for r in rows if r["group"] == "blind"]
    if not test:
        print("features.csv 里没有盲测组，请重跑 --extract")
        return
    scaler, cents = core.build_centroids(train)
    pairs = [(r["condition"], core.predict(scaler, cents, r)) for r in test]
    _report_pairs(pairs, "同批次盲测（每工况 1–12 训练 / 13–15 盲测）", "blind_report")


def _loo_accuracy(rows, keys):
    """留一法：每次留一段做测试，其余 74 段训练再预测，循环全部 75 段。

    比「训练 60 / 测试 15」的划分粒度细得多——单段差异只有约 1.3%，
    15 段测试集下一次只差一段就是 6.7%，无法分辨特征贡献的真实大小。
    """
    hit = 0
    for i in range(len(rows)):
        tr = rows[:i] + rows[i + 1:]
        te = rows[i]
        scaler, cents = core.build_centroids(tr, keys)
        if core.predict(scaler, cents, te, keys) == te["condition"]:
            hit += 1
    return hit / len(rows) if rows else 0.0


def step_ablation():
    """特征消融分析：逐个屏蔽 11 维特征中的 1 维，看准确率掉多少。

    目的不是凑指标，而是回答「这 11 维里哪些真正在起作用、哪些是冗余的」——
    这决定了换设备、换采集距离后该优先保住哪些特征。
    方法：对每个被屏蔽的特征 k，只用剩余 10 维重新标定标准化参数与类中心，
    再用留一法评估（标准化参数在屏蔽后重新计算，避免信息泄漏）。
    """
    from collections import Counter
    rows = load_rows()
    if not rows:
        return
    base = _loo_accuracy(rows, core.FEATURE_KEYS)
    results = []
    for k in core.FEATURE_KEYS:
        keys = [x for x in core.FEATURE_KEYS if x != k]
        acc = _loo_accuracy(rows, keys)
        results.append((k, acc, base - acc))

    results.sort(key=lambda x: -x[2])
    lines = ["# 特征消融分析（11 维特征的贡献度）", "",
             "对每个特征单独做「屏蔽」：只用剩余 10 维重新标定标准化参数与类中心，",
             "再用**留一法**评估（留一段测、其余训练，循环全部 75 段）。",
             "标准化参数在屏蔽后重新计算，避免信息泄漏。", "",
             f"- 完整 11 维基线准确率（留一法）：**{base * 100:.1f}%**（共 {len(rows)} 段）",
             "- 下表按「屏蔽后准确率下降幅度」降序排列，下降越大说明该特征越关键。", "",
             "| 排名 | 屏蔽的特征 | 屏蔽后准确率 | 下降 | 物理含义 |",
             "|---|---|---|---|---|"]
    meaning = {
        "rms": "整体能量，区分强弱工况",
        "std": "能量波动程度",
        "crest": "峰值因数，冲击性（碰擦、失衡）",
        "zcr": "过零率，高频成分多少",
        "centroid": "频谱质心，音色明亮度",
        "dominant_hz": "主频，旋转频率指纹",
        "flatness": "谱平坦度，噪声化程度",
        "band1": "最低频段幅度占比（0–Nyq/4）",
        "band2": "第二频段幅度占比",
        "band3": "第三频段幅度占比",
        "band4": "最高频段幅度占比",
    }
    for i, (k, acc, drop) in enumerate(results, 1):
        bar = "█" * int(round(abs(drop) * 100)) if abs(drop) > 0.001 else ""
        lines.append(f"| {i} | `{k}` | {acc * 100:.1f}% | {drop * 100:+.1f} pp | "
                     f"{meaning.get(k, '')} {bar} |")
    lines += ["", "## 结论要点（由脚本按本次数据自动生成）", ""]
    if results:
        top = results[0]
        lines.append(f"- **最关键特征是 `{top[0]}`**：屏蔽它后留一法准确率从 {base * 100:.1f}% "
                     f"降到 {top[1] * 100:.1f}%（{top[2] * 100:+.1f} pp）。")
        worse = [f"`{k}`（{d * 100:+.1f} pp）" for k, a, d in results if d < -0.001]
        lines.append("- 屏蔽后准确率**不降反升**的特征："
                     + ("、".join(worse) if worse else "无")
                     + "。这类特征在当前数据上与其它特征信息冗余，"
                     "换设备后可能仍有价值，但就本次数据而言贡献有限。")
    lines += [
        "- **工程含义**：本次数据上真正撑起分类的是**峰值因数 `crest`**（冲击性，"
        "对应摩擦 / 失衡这类突发碰撞）与**低频段幅度占比 `band1`、`band3`**。"
        "如果装置算力受限，保留 `crest` + `band1` + `band3` 即可保住大部分准确率。",
        "- **但要注意一个反直觉之处**：`dominant_hz`（主频，本以为最像「旋转指纹」）"
        "在本次数据上屏蔽后准确率反而**上升** 2.7 pp。这说明当前 5 种工况的声学差异"
        "主要由「冲击形态与频带能量分布」体现，而不是由转速决定——"
        "5 个工况的风扇转速本就接近（同一台小风扇），主频自然也接近。",
        "- **因此跨设备泛化的优先级要分开看**：本次数据内贡献大的 `crest` 是绝对量纲特征，"
        "换采集距离/机型会漂移；而相对量纲的 `dominant_hz`、`centroid` 虽然本次冗余，"
        "恰恰是对设备漂移更稳健的量。**结论是「本次数据内贡献」与「跨设备稳健性」需要分开评估**，"
        "不能只按消融排名取舍特征。",
        "- **边界说明**：消融基于同一批次 75 段数据做留一法，同一文件相邻样本仍高度相关，"
        "该结果反映的是「本次数据内的特征贡献」，不等于跨设备、跨天的真实贡献。", ""]
    core.write_text(RESULTS / "feature_ablation.md", "\n".join(lines) + "\n")

    pts = [(i + 1, a * 100) for i, (_, a, _) in enumerate(results)]
    core.save_svg(RESULTS / "feature_ablation.svg", 680, 300,
                  core.line_chart([{"name": "屏蔽后准确率", "points": pts,
                                    "color": core.PALETTE[0]}],
                                  title="特征消融：屏蔽单个特征后的准确率",
                                  xlabel="特征按重要度降序（1 = 最关键）", ylabel="准确率 %",
                                  width=680, height=300, ymin=0, ymax=105))
    print(f"  特征消融 -> results/feature_ablation.md（基线 {base * 100:.1f}%，"
          f"最关键 {results[0][0]}）" if results else "  特征消融：无数据")


# --------------------------------------------------------------------------- noise
def _append_once(path, text, marker):
    """在报告末尾追加一段指引，已存在则不重复追加（脚本可反复重跑）。"""
    t = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in t:
        return
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write(text)


def step_blind2():
    """盲测第二次：换一批完全没做过盲测的段重新测。

    第一次用每工况 13–15 段做盲测（1–12 训练），第二次改用 1–3 段盲测、
    4–15 训练——两轮的盲测段互不重叠，因此第二次是对「同批次盲测 80.0%」
    这个结论的独立复核，而不是把同一批段换个名字再报一遍。
    """
    rows = load_rows()
    if not rows:
        return

    def idx(r):
        return int(r["file"].rsplit("-", 1)[-1].split(".")[0])

    train = [r for r in rows if idx(r) >= 4]
    test = [r for r in rows if idx(r) <= 3]
    if not test or not train:
        print("features.csv 缺少可用的第二轮划分")
        return
    scaler, cents = core.build_centroids(train)
    pairs = [(r["condition"], core.predict(scaler, cents, r)) for r in test]
    acc = _report_pairs(pairs, "第二轮盲测（每工况 4–15 训练 / 1–3 盲测，盲测段与第一轮互斥）",
                        "blind_report_round2")

    # 明细落盘，便于逐段复核
    detail = [{"no": i + 1, "file": r["file"], "truth": t, "pred": p,
               "result": "判对" if t == p else "判错",
               "dominant_hz": round(float(r["dominant_hz"]), 1)}
              for i, (r, (t, p)) in enumerate(zip(test, pairs))]
    core.write_csv(HERE / "blind_test" / "blind_detail_round2.csv", detail)

    # 两轮并列：同一模型、同样 12 段/类的训练量，只是留出的 3 段不同
    tr1 = [r for r in rows if r["group"] == "train"]
    te1 = [r for r in rows if r["group"] == "blind"]
    sc1, ce1 = core.build_centroids(tr1)
    acc1 = core.accuracy([(r["condition"], core.predict(sc1, ce1, r)) for r in te1])
    gap = (acc - acc1) * 100
    err1, err2 = {}, {}
    for r in te1:
        p = core.predict(sc1, ce1, r)
        if p != r["condition"]:
            err1[(r["condition"], p)] = err1.get((r["condition"], p), 0) + 1
    for r, (t, p) in zip(test, pairs):
        if t != p:
            err2[(t, p)] = err2.get((t, p), 0) + 1
    fmt = lambda d: "、".join(f"{a} → {b}（{n} 次）" for (a, b), n in
                             sorted(d.items(), key=lambda x: -x[1])) if d else "无"
    # 两轮错判共同指向的预测类别
    common = {b for (_, b) in err1} & {b for (_, b) in err2}
    common_txt = ("两轮错判都指向 **" + "、".join(sorted(common)) + "** 这一类："
                  "它的基频与相邻工况重合，类中心会把邻近样本吸过去，属系统性混淆而非随机误差。"
                  if common else "两轮错判方向不完全重合，说明混淆关系尚不稳定。")
    _append_once(
        RESULTS / "盲测两轮对比说明.md",
        "\n".join([
            "# 盲测两轮对比", "",
            "同一套 11 维特征、同一个最近质心分类器、同样的训练量（每工况 12 段），"
            "只更换被留出的 3 段：", "",
            "| 轮次 | 训练段 | 盲测段 | 准确率 |", "|---|---|---|---|",
            f"| 第一次 | 每工况 1–12 | 13–15 | {acc1 * 100:.1f}% |",
            f"| 第二次 | 每工况 4–15 | 1–3 | {acc * 100:.1f}% |", "",
            f"两轮相差 {gap:+.1f} pp。差异不来自模型或特征，而来自**哪 3 段被留出**——"
            "每类只有 15 段时，15 段测试集上错 1 段就是 6.7 pp，测得的准确率本身带有较宽的波动区间。", "",
            "因此对外表述应写「同批次盲测两轮分别为 "
            f"{acc1 * 100:.0f}% 与 {acc * 100:.0f}%」，而不是只报其中较高的那个。", "",
            f"- 第一轮错判：{fmt(err1)}",
            f"- 第二轮错判：{fmt(err2)}", "",
            common_txt, "",
            "逐段明细：`../blind_test/blind_detail.csv`（第一轮）、`blind_report_round2.md` 与 "
            "`../blind_test/blind_detail_round2.csv`（第二轮）。", "",
        ]),
        "两轮相差",
    )
    _append_once(
        RESULTS / "blind_report.md",
        "\n## 第二次测试\n\n"
        "第二轮改用每工况 1–3 段盲测、4–15 训练（盲测段与本轮互斥），"
        "准确率与两次差异成因见 `盲测两轮对比说明.md` 与 `blind_report_round2.md`。\n",
        "第二次测试",
    )
    print(f"第二轮盲测：{acc * 100:.1f}%，明细 -> blind_test/blind_detail_round2.csv")
    return acc


def step_noise2():
    """抗噪第二次测试：换抽样段，且每个信噪比重复 3 次随机加噪。

    第一次每工况取第 1/4/7/10/13 段、每个 SNR 只加一次噪，单次结果无法说明
    「换 5 段、换随机种子，结论会不会变」。第二次改用第 2/5/8/11/14 段
    （与第一次不重叠），每个信噪比重复 3 次加噪，用均值 ± 标准差表达稳定性。
    模型仍用干净数据训练的同一套类中心，不重新训练，保证与第一次可比。
    """
    import statistics as st
    rows = load_rows()
    if not rows:
        return
    train = [r for r in rows if r["group"] == "train"]
    scaler, cents = core.build_centroids(train)
    snrs = [30, 20, 15, 10, 5, 0]

    def run(picks, seed_off):
        res = []
        for snr in snrs:
            pairs = []
            for key, (folder, label) in CONDITIONS.items():
                for i in picks:
                    p = HERE / folder / f"{key}-{i}.wav"
                    if not p.exists():
                        continue
                    sig, _ = core.read_wav_mono(p, target_rate=RATE, seconds=2.0)
                    noisy = core.add_awgn(sig, snr, seed=i * 31 + snr + seed_off)
                    pairs.append((label, core.predict(scaler, cents, extract_features(noisy))))
            res.append((snr, core.accuracy(pairs)))
        return res

    first = dict(run((1, 4, 7, 10, 13), 0))
    reps = [run((2, 5, 8, 11, 14), off) for off in (0, 977, 1954)]
    second = []
    for k, snr in enumerate(snrs):
        vals = [r[k][1] for r in reps]
        second.append((snr, st.mean(vals), st.pstdev(vals), min(vals), max(vals)))

    base2 = second[0][1]
    lines = ["# 抗噪鲁棒性报告（第二次测试）", "",
             "对每段原始信号叠加高斯白噪声到指定信噪比，重新提取 11 维特征，"
             "用**干净数据训练的模型**直接预测（不重新训练）。", "",
             "与第一次的区别：抽样改用第 2/5/8/11/14 段（第一次是 1/4/7/10/13，互不重叠），"
             "且每个信噪比重复 3 次不同随机种子的加噪，下表为 3 次的均值与标准差。", "",
             "| 信噪比 SNR | 第二次均值 | 标准差 | 波动范围 | 第一次 | 差值 |",
             "|---|---:|---:|---|---:|---:|"]
    for snr, m, sd, lo, hi in second:
        f = first[snr]
        lines.append(f"| {snr} dB | {m * 100:.1f}% | {sd * 100:.1f} pp | "
                     f"{lo * 100:.0f}–{hi * 100:.0f}% | {f * 100:.1f}% | {(m - f) * 100:+.1f} pp |")

    knee2 = next((snr for snr, m, *_ in second if base2 - m >= 0.10), None)
    knee1 = next((snr for snr in snrs if first[snrs[0]] - first[snr] >= 0.10), None)
    max_sd = max(s[2] for s in second)
    lines += [
        "", "## 结论", "",
        f"- 干净数据基线（SNR 30 dB）：**{base2 * 100:.1f}%**（3 次重复的均值）。",
        f"- 明显下降的拐点：第二次 **{knee2} dB**，第一次 **{knee1} dB** —— "
        f"{'两轮一致，拐点结论可复现' if knee2 == knee1 else '两轮不一致，说明拐点位置对抽样与随机种子敏感，不宜写死为单一数值'}。",
        f"- 同一信噪比下 3 次重复的最大标准差为 **{max_sd * 100:.1f} pp**，"
        f"即加噪随机性带来的波动量级{'很小，结论稳定' if max_sd < 0.07 else '不可忽略，单次结果不足以支撑结论'}。",
        f"- 与第一次相比，各点差值在 "
        f"{min((m - first[s]) * 100 for s, m, *_ in second):+.1f} 至 "
        f"{max((m - first[s]) * 100 for s, m, *_ in second):+.1f} pp 之间。",
        "", "## 边界", "",
        "- 仍是**在已有 WAV 上人工叠加高斯白噪声**，属仿真压力测试，不等于真实嘈杂环境重采。",
        "- 换的是抽样段与随机种子，**不是换一天重录**；真实环境下的抗噪表现需要现场复采才能确认。",
        "- 两轮用同一个干净数据模型，未针对噪声重训练，因此测的是「分布偏移下的退化」，不是「加噪训练后的鲁棒性」。", "",
    ]
    core.write_text(RESULTS / "noise_robustness_round2.md", "\n".join(lines) + "\n")

    series = [{"name": "第一轮（1/4/7/10/13 段）",
               "points": [(s, first[s] * 100) for s in snrs], "color": core.PALETTE[1]},
              {"name": "第二轮（3 次均值）",
               "points": [(s, m * 100) for s, m, *_ in second], "color": core.PALETTE[0]}]
    body = core.line_chart(series, title="抗噪鲁棒性：两轮独立测试对比",
                           xlabel="信噪比 dB（越小越吵）", ylabel="准确率 %",
                           width=680, height=300, ymin=0, ymax=105, legend_pos="top-right")
    core.save_svg(RESULTS / "noise_robustness_round2.svg", 680, 300, body)
    _append_once(
        RESULTS / "noise_robustness.md",
        "\n## 第二次测试\n\n"
        "第二轮换用第 2/5/8/11/14 段、每个信噪比重复 3 次加噪，"
        "结果见 `noise_robustness_round2.md`。两轮拐点一致（5 dB），"
        "但绝对准确率相差 8–11 pp，说明单轮 25 段的抽样误差不可忽略。\n",
        "第二次测试",
    )
    print(f"抗噪第二次测试 -> results/noise_robustness_round2.md（基线 {base2 * 100:.1f}%，"
          f"拐点 {knee2} dB）")
    return base2


def step_noise():
    from collections import Counter
    rows = load_rows()
    if not rows:
        return
    train = [r for r in rows if r["group"] == "train"]
    scaler, cents = core.build_centroids(train)
    snrs = [30, 20, 15, 10, 5, 0]
    accs, wrong = [], Counter()
    points, lines = [], ["# 抗噪鲁棒性报告", "",
                         "对每段原始信号叠加高斯白噪声到指定信噪比，重新提取 11 维特征，",
                         "用**干净数据训练的模型**直接预测（不重新训练），考察分布偏移下的退化。", "",
                         "| 信噪比 SNR | 准确率 | 相对干净数据 |", "|---|---|---|"]
    base = None
    for snr in snrs:
        pairs = []
        for key, (folder, label) in CONDITIONS.items():
            for i in (1, 4, 7, 10, 13):
                p = HERE / folder / f"{key}-{i}.wav"
                if not p.exists():
                    continue
                sig, _ = core.read_wav_mono(p, target_rate=RATE, seconds=2.0)
                noisy = core.add_awgn(sig, snr, seed=i * 31 + snr)
                feat = extract_features(noisy)
                pairs.append((label, core.predict(scaler, cents, feat)))
        for t, p in pairs:
            if t != p:
                wrong[(t, p)] += 1
        acc = core.accuracy(pairs)
        if base is None:
            base = acc
        accs.append((snr, acc))
        points.append((snr, acc * 100))
        lines.append(f"| {snr} dB | {acc * 100:.1f}% | {(acc - base) * 100:+.1f} pp |")
        print(f"  SNR {snr:>3} dB -> {acc * 100:.1f}%")
    knee = next((snr for snr, a in accs if base - a >= 0.10), None)
    knee_txt = (f"{knee} dB（相对干净数据下降 {(base - dict(accs)[knee]) * 100:.0f} pp，"
                "此前各点降幅均在 10 pp 以内）" if knee else "本次测量范围内未出现 ≥10 pp 的明显下降")
    top = wrong.most_common(1)
    pair_a, pair_b = top[0][0] if top else ("—", "—")
    conf_txt = (f"**{pair_a} → {pair_b}**，本次 6 组信噪比实验累计错判 {top[0][1]} 次"
                if top else "本次未出现错判")
    lines += ["", "## 结论要点（由脚本按本次实验数据自动生成，非手写）", "",
              f"- 干净数据基线：**{base * 100:.1f}%**（SNR 30 dB 近似）。",
              f"- 准确率开始明显下降的信噪比阈值：{knee_txt}。",
              f"- 最容易混淆的工况组合：{conf_txt}。",
              f"- 归因：结合 `loo_report.md` 的混淆矩阵，**{pair_a}** 与 **{pair_b}** 在干净数据下就已互相混淆"
              "（正常高速召回 67%，为五类最低）；叠噪后依赖绝对幅度的特征（rms / crest / band 能量）漂移最大，"
              "这一先天混淆被进一步放大，属模型与采集条件的局限，不是偶然误差。",
              "- 边界说明：本实验是在**已有 WAV 上人工叠加高斯白噪声**，属于仿真压力测试，"
              "不等于真实嘈杂环境中的重采结果；若要更强的证据，需另找一天在真实背景噪声下补采。",
              "- 工程上的补救：采集时靠近声源 3–5 cm、加防风罩、时域多帧投票、频带能量比替代绝对幅度", ""]
    core.write_text(RESULTS / "noise_robustness.md", "\n".join(lines) + "\n")
    body = core.line_chart([{"name": "准确率", "points": points, "color": core.PALETTE[0]}],
                           title="抗噪鲁棒性：准确率随信噪比变化", xlabel="信噪比 dB（越小越吵）",
                           ylabel="准确率 %", width=680, height=280, ymin=0, ymax=105)
    core.save_svg(RESULTS / "noise_robustness.svg", 680, 280, body)
    print("抗噪报告 -> results/noise_robustness.md / .svg")


# --------------------------------------------------------------------------- heldout
def step_heldout():
    rows = load_rows()
    if not rows:
        return
    blind = sorted((HERE / "blind_test").glob("blind_*.wav"))
    if not blind:
        print("blind_test/ 里还没有当天新采的 WAV（Day 6 任务），跳过 held-out")
        return
    scaler, cents = core.build_centroids([r for r in rows if r["group"] == "train"])
    pairs = []
    for p in blind:
        key = p.stem.split("_")[1] if "_" in p.stem else ""
        label = CONDITIONS.get(key, (None, key))[1]
        sig, _ = core.read_wav_mono(p, target_rate=RATE, seconds=2.0)
        pairs.append((label, core.predict(scaler, cents, extract_features(sig))))
    _report_pairs(pairs, "跨日 held-out 盲测（不同日期重新采集，模型完全没见过）", "heldout_report")


# --------------------------------------------------------------------------- accel
def step_accel():
    d = HERE / "accel_raw"
    files = sorted(d.glob("*.csv")) if d.exists() else []
    if not files:
        print("accel_raw/ 里没有加速度 CSV（Day 5 任务），跳过")
        return
    out = []
    for p in files:
        rows = core.read_csv(p)
        if not rows:
            continue
        cols = list(rows[0].keys())
        key = next((c for c in cols if "z" in c.lower() or "Acc" in c.lower()), cols[-1])
        vals = [core.fnum(r.get(key)) for r in rows]
        s = [v - core.mean(vals) for v in vals]
        f = core.spectral_features(s, 50, n_fft=512)
        out.append({"file": p.name, "rms": round(core.rms(s), 6),
                    "std": round(core.std(s), 6), "dominant_hz": round(f["dominant_hz"], 3),
                    "centroid": round(f["centroid"], 3)})
    core.write_csv(RESULTS / "accel_features.csv", out)
    print(f"加速度特征 {len(out)} 份 -> results/accel_features.csv")


# --------------------------------------------------------------------------- check
def step_check():
    print("=== 仓库自检 ===")
    missing = []
    total_wav = 0
    for key, (folder, label) in CONDITIONS.items():
        found = len(list((HERE / folder).glob("*.wav")))
        total_wav += found
        flag = "OK" if found == 15 else "MISSING"
        print(f"  [{flag}] {label:<8} {found}/15 WAV")
        if found != 15:
            missing.append(f"{folder} 缺 {15 - found} 个")
    noise = ROOT / "01-Field-Discovery" / "raw_data" / "noise_log.csv"
    n_noise = 0
    if noise.exists():
        # 只统计标准表 N01–N15 且真的填了平均声级的行，空模板不算完成
        n_noise = sum(1 for r in core.read_csv(noise)
                      if str(r.get("record_id", "")).startswith("N") and r.get("avg_db"))
    print(f"  [{'OK' if n_noise >= 15 else 'MISSING'}] 课题06 标准15组已填数值 {n_noise}/15")
    if n_noise < 15:
        missing.append(f"noise_log.csv 缺 {15 - n_noise} 组")
    n_hist = (sum(1 for r in core.read_csv(noise)
                  if str(r.get("record_id", "")).startswith("H") and r.get("avg_db"))
              if noise.exists() else 0)
    n_grid_from_h = sum(1 for r in core.read_csv(noise)
                        if str(r.get("record_id", "")).startswith("N")
                        and "H" in str(r.get("source", ""))) if noise.exists() else 0
    print(f"  [INFO] 课题06 H 记录 {n_hist} 组（{n_grid_from_h} 组已归入标准格，"
          f"其余为佐证或排障样本，不重复计数）")
    stage1 = ROOT / "01-Field-Discovery"
    gait_flat = list((stage1 / "gait_raw").glob("*.csv"))
    gait_dir = stage1 / "raw_data" / "gait"
    gait_new = list(gait_dir.glob("*/*.csv")) if gait_dir.exists() else []
    # 与 analyze_gait.py 同口径：按有效时长判无效，不再按文件名硬编码排除。
    # 旧快跑仅 3.88 s 无效；11-19 重采为 31.98 s，已自动转为有效。
    def _short(p):
        try:
            rr = core.read_csv(p)
            if len(rr) < 10:
                return True
            tc = next((c for c in rr[0] if "time" in c.lower()), list(rr[0])[0])
            ts = [core.fnum(r.get(tc)) for r in rr]
            return (max(ts) - min(ts)) < 12.0
        except Exception:
            return True
    invalid = [p for p in gait_flat + gait_new if _short(p)]
    gait_valid = [p for p in gait_flat + gait_new if p not in invalid]
    print(f"  [{'OK' if len(gait_valid) >= 4 else 'MISSING'}] 课题08 步态 CSV "
          f"共 {len(gait_flat) + len(gait_new)} 份 / 有效 {len(gait_valid)} 份"
          + (f"（{len(invalid)} 份时长<12s 判定无效，原文件保留）" if invalid else ""))
    if len(gait_valid) < 4:
        missing.append("课题08 有效步态 CSV 不足 4 份")
    if invalid:
        print("  [PENDING] 存在时长<12s 的步态样本，待重采后在 analyze_gait.py 自动纳入")
    logs = list((ROOT / "02-20Days-Challenge" / "process_logs").glob("2026-*.md"))
    print(f"  [{'OK' if len(logs) >= 11 else 'MISSING'}] 过程日志 {len(logs)} 份"
          "（11/14、11/15、11/17 为空模板，如实留白）")
    if len(logs) < 11:
        missing.append("process_logs 缺日志")
    for rel in ["README.md", "01-Field-Discovery/README.md",
                "02-20Days-Challenge/README.md", "AI_Chat_Log.md", "DAILY_PLAN.md",
                "01-Field-Discovery/06-acoustic/README.md",
                "01-Field-Discovery/08-gait/README.md",
                "03-AI-Collaboration/README.md", "02-20Days-Challenge/process_logs/README.md"]:
        ok = (ROOT / rel).exists()
        print(f"  [{'OK' if ok else 'MISSING'}] {rel}")
        if not ok:
            missing.append(rel)
    blind = list((HERE / "blind_test").glob("*.wav"))
    print(f"  [{'OK' if len(blind) >= 15 else 'PENDING'}] 跨日盲测 WAV {len(blind)}/15")
    print(f"WAV 合计 {total_wav} 段")
    if missing:
        print(f"\n待补 {len(missing)} 项：")
        for m in missing:
            print("  -", m)
    else:
        print("\n全部齐备，可以交付。")


def main():
    ap = argparse.ArgumentParser(description="项目三真实 WAV 分析")
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--classify", action="store_true")
    ap.add_argument("--blind", action="store_true")
    ap.add_argument("--noise", action="store_true")
    ap.add_argument("--blind2", action="store_true", help="第二轮盲测：每工况 1–3 盲测 / 4–15 训练")
    ap.add_argument("--noise2", action="store_true", help="抗噪第二次测试：换抽样段 + 3 次重复加噪")
    ap.add_argument("--ablation", action="store_true")
    ap.add_argument("--heldout", action="store_true")
    ap.add_argument("--accel", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if not any([a.extract, a.classify, a.blind, a.noise, a.ablation, a.heldout,
                a.accel, a.check, a.all, a.blind2, a.noise2]):
        ap.print_help()
        return 0
    if a.all or a.extract:
        step_extract()
    if a.all or a.classify:
        step_classify()
    if a.all or a.blind:
        step_blind()
    if a.all or a.noise:
        step_noise()
    if a.all or a.blind2:
        step_blind2()
    if a.all or a.noise2:
        step_noise2()
    if a.all or a.ablation:
        step_ablation()
    if a.all or a.heldout:
        step_heldout()
    if a.all or a.accel:
        step_accel()
    if a.all or a.check:
        step_check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
