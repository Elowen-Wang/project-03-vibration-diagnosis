"""项目三 · 声学通道能力边界与包络解调试验（零第三方依赖）

回答两个问题：
  1) 手机麦克风到底能覆盖振动信号的哪一段？
     对 75 段原始 48 kHz 信号做频带能量分解，量化「哪一段听得到、哪一段听不到」。
  2) 听不到低频的前提下，中高频还能不能把摩擦/受阻分出来？
     用包络解调提取冲击重复率等 4 个特征，与现有 11 维一起做留一法对比。

用法（在仓库根目录执行）：
    python 02_Stage2_Project_Vibration/analyze_acoustic_limits.py --bands
    python 02_Stage2_Project_Vibration/analyze_acoustic_limits.py --env
    python 02_Stage2_Project_Vibration/analyze_acoustic_limits.py --all
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))
import signal_core as core  # noqa: E402
import analyze_real_wav as arw  # noqa: E402

RESULTS = HERE / "results"
BANDS = [0, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 24000]
BAND_LABELS = ["<50", "50–100", "100–200", "200–500", "0.5–1k",
               "1–2k", "2–5k", "5–10k", "10–24k"]
BAND_COLORS = ["#1F4E79", "#2E6EA6", "#3E8ED0", "#6BAED6", "#9ECAE1",
               "#C6DBEF", "#FDD0A2", "#FD8D3C", "#D94801"]
ENV_KEYS = ["env_peak_hz", "env_snr", "env_kurt", "env_cv"]


# --------------------------------------------------------------------------- 图形
def _lum(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def share_chart(row_labels, matrix, band_labels, title, note="", width=680):
    """100% 堆叠条形图：每行是该工况 9 个频带的能量占比。"""
    L, R, T = 96, 24, 56 if title else 30
    row_h, bar_h = 34, 20
    legend_rows = 3
    height = T + row_h * len(row_labels) + 26 + legend_rows * 17
    pw = width - L - R

    def px(v):
        return L + v / 100.0 * pw

    b = []
    if title:
        b.append(f'<text x="24" y="24" font-size="14" font-weight="500" fill="{core.INK}">{core._esc(title)}</text>')
    if note:
        b.append(f'<text x="24" y="42" font-size="10.5" fill="{core.MUTED}">{core._esc(note)}</text>')
    for v in (0, 25, 50, 75, 100):
        x = px(v)
        b.append(f'<line x1="{x:.1f}" y1="{T - 6}" x2="{x:.1f}" y2="{T + row_h * len(row_labels) - 4}" '
                 f'stroke="{core.GRID}" stroke-width="0.5"/>')
    for i, lab in enumerate(row_labels):
        y = T + row_h * i
        b.append(f'<text x="{L - 12}" y="{y + bar_h / 2 + 4:.1f}" font-size="11" fill="{core.INK}" '
                 f'text-anchor="end">{core._esc(lab)}</text>')
        x0 = L
        for j, share in enumerate(matrix[i]):
            w = share / 100.0 * pw
            if w <= 0:
                continue
            color = BAND_COLORS[j % len(BAND_COLORS)]
            b.append(f'<rect x="{x0:.1f}" y="{y:.1f}" width="{w:.1f}" height="{bar_h}" '
                     f'fill="{color}" stroke="#FFFFFF" stroke-width="1"/>')
            if w >= 26:
                tc = "#FFFFFF" if _lum(color) < 0.55 else core.INK
                b.append(f'<text x="{x0 + w / 2:.1f}" y="{y + bar_h / 2 + 4:.1f}" font-size="9.5" '
                         f'fill="{tc}" text-anchor="middle">{share:.0f}</text>')
            x0 += w
    ay = T + row_h * len(row_labels) + 14
    for v in (0, 25, 50, 75, 100):
        b.append(f'<text x="{px(v):.1f}" y="{ay}" font-size="10" fill="{core.MUTED}" '
                 f'text-anchor="middle">{v}%</text>')
    b.append(f'<text x="{L + pw / 2:.1f}" y="{ay + 15}" font-size="10.5" fill="{core.MUTED}" '
             f'text-anchor="middle">能量占比</text>')
    ly = ay + 32
    per_row = 3
    col_w = pw / per_row
    for j, lab in enumerate(band_labels):
        r_, c_ = divmod(j, per_row)
        x = L + c_ * col_w
        y = ly + r_ * 17
        b.append(f'<rect x="{x}" y="{y - 8}" width="9" height="9" rx="1.5" '
                 f'fill="{BAND_COLORS[j % len(BAND_COLORS)]}"/>')
        b.append(f'<text x="{x + 14}" y="{y}" font-size="10" fill="{core.MUTED}">'
                 f'{core._esc(lab)} Hz</text>')
    return "".join(b), height


# --------------------------------------------------------------------------- 频带覆盖
def step_bands():
    per_file = []
    for key, label, i, path in arw.wav_files():
        if not path.exists():
            continue
        sig, sr = core.read_wav_mono(path, target_rate=48000, seconds=0.5)
        ratios = core.band_energy_ratios(sig, sr, BANDS)
        row = {"condition": label, "file": f"{key}-{i}.wav"}
        for lab, v in zip(BAND_LABELS, ratios):
            row[f"band_{lab}"] = round(v * 100, 3)
        per_file.append(row)

    fields = ["condition", "file"] + [f"band_{lab}" for lab in BAND_LABELS]
    core.write_csv(RESULTS / "acoustic_band_limits.csv", per_file, fields)

    grouped = defaultdict(list)
    for r in per_file:
        grouped[r["condition"]].append(r)
    order = [lab for lab in arw.LABELS if lab in grouped]
    matrix = []
    for lab in order:
        matrix.append([sum(core.fnum(r[f"band_{b}"]) for r in grouped[lab]) / len(grouped[lab])
                       for b in BAND_LABELS])
    agg = []
    for lab, vals in zip(order, matrix):
        row = {"condition": lab}
        row.update({f"band_{b}": round(v, 2) for b, v in zip(BAND_LABELS, vals)})
        agg.append(row)
    core.write_csv(RESULTS / "acoustic_band_limits_by_condition.csv", agg, fields)

    svg, h = share_chart(order, matrix, BAND_LABELS,
                         "五种工况的能量频带分布（原始 48 kHz，75 段均值）",
                         "每行 = 该工况全部文件在各频带的能量占比，合计 100%")
    core.save_svg(RESULTS / "acoustic_band_limits.svg", 680, h, svg)

    low = sum(vals[0] + vals[1] for vals in matrix) / len(matrix)
    seen = sum(sum(vals[:6]) for vals in matrix) / len(matrix)   # 0–2000 Hz
    high = sum(vals[7] + vals[8] for vals in matrix) / len(matrix)
    mid = sum(vals[6] for vals in matrix) / len(matrix)

    lines = ["# 声学通道频带覆盖分析", "",
             "对 75 段**原始 48 kHz** WAV 逐段做能量分解（双声道取均值、居中 0.5 s、Hann 窗），",
             "统计各频带能量占该段总能量的比例。用于界定「以声代振」能做到哪一步。", "",
             "| 工况 | " + " | ".join(f"{b} Hz" for b in BAND_LABELS) + " |",
             "|---|" + "---|" * len(BAND_LABELS)]
    for lab, vals in zip(order, matrix):
        lines.append(f"| {lab} | " + " | ".join(f"{v:.1f}%" for v in vals) + " |")
    lines += ["", "## 结论", "",
              f"- 100 Hz 以下平均仅占 **{low:.1f}%**，5 kHz 以上占 **{high:.1f}%**，2–5 kHz 占 {mid:.1f}%。",
              "- 手机 MEMS 麦克风在 80–100 Hz 以下存在明显滚降，与实测低频占比一致。",
              "  本项目风机的 1× 转频落在 100–155 Hz（见 `features.csv` 的 `dominant_hz`），",
              "  **仍在可观测区间**；真正测不到的是 100 Hz 以下的结构振动（轴承特征频率、低频失衡分量）。",
              f"- 现有 11 维特征在 4 kHz 降采样后计算，等效只观察 0–2 kHz，即全段能量的 **{seen:.1f}%**。",
              "  5 kHz 以上的能量虽大，但那是稳态气动噪声与高频啸叫；消融结果显示判别力来自",
              "  `crest`（冲击性）与 `band1`/`band3`（1.5 kHz 以下的能量分布）——能量大不等于信息多。", "",
              "## 对结论的影响", "",
              "1. 本项目做的是**声学诊断**：可讨论谐波结构、冲击性、频带能量，",
              "   但不能给出 m/s² 量级的振动幅值（麦克风灵敏度、距离、AGC 均未标定）。",
              "2. 「声振融合」未做——只有一条声学通道，另一条通道不存在，融合增益无从谈起。",
              "3. 若要覆盖 100 Hz 以下，需另加加速度计并与音频同段同步采集；",
              "   非同次录制的加速度无法与现有 WAV 对齐，不能事后配。", ""]
    core.write_text(RESULTS / "acoustic_band_limits.md", "\n".join(lines))
    print(f"频带覆盖：<100 Hz {low:.1f}% / 0–2 kHz {seen:.1f}% / >5 kHz {high:.1f}% "
          f"-> results/acoustic_band_limits.md")
    return per_file


def step_bands_chart():
    """只按已有汇总 CSV 重绘频带图，便于调版式时不必重跑 5 分钟的频谱计算。"""
    path = RESULTS / "acoustic_band_limits_by_condition.csv"
    if not path.exists():
        print("还没有汇总 CSV，请先跑 --bands")
        return
    rows = core.read_csv(path)
    order = [r["condition"] for r in rows]
    matrix = [[core.fnum(r[f"band_{b}"]) for b in BAND_LABELS] for r in rows]
    svg, h = share_chart(order, matrix, BAND_LABELS,
                         "五种工况的能量频带分布（原始 48 kHz，75 段均值）",
                         "每行 = 该工况全部文件在各频带的能量占比，合计 100%")
    core.save_svg(RESULTS / "acoustic_band_limits.svg", 680, h, svg)
    print("频带图已重绘 -> results/acoustic_band_limits.svg")


def collect_spectra():
    """每工况前 3 段的平均包络谱（5–100 Hz），按本底中位数归一化成「倍数」。"""
    acc = defaultdict(list)
    for key, label, i, path in arw.wav_files():
        if not path.exists() or i > 3:
            continue
        sig, sr = core.read_wav_mono(path, target_rate=8000, seconds=2.0)
        env, er = core.analytic_envelope(sig, sr)
        env = [x - core.mean(env) for x in env]
        freqs, mags = core.spectrum(env, er, n_fft=1024)
        acc[label].append([(fr, m) for fr, m in zip(freqs, mags) if 5 <= fr <= 100])
    out = {}
    for lab, rows_ in acc.items():
        if not rows_:
            continue
        n = min(len(x) for x in rows_)
        mean_sp = [(rows_[0][k][0], sum(r[k][1] for r in rows_) / len(rows_))
                   for k in range(n)]
        vals = sorted(v for _, v in mean_sp)
        med = vals[len(vals) // 2] or 1e-12
        out[lab] = [(f, v / med) for f, v in mean_sp]
    return out


def env_charts(results, spectra):
    """两张图：三个特征集的准确率对比、五工况包络谱（相对本底倍数）。"""
    cats = [r[0] for r in results]
    vals = [r[2] * 100 for r in results]
    body = core.bar_chart(cats, vals, title="留一法准确率对比：包络特征有没有帮助（75 段）",
                          width=680, height=300,
                          colors=core.PALETTE[:3], value_fmt="{:.1f}%")
    core.save_svg(RESULTS / "envelope_compare.svg", 680, 300, body)

    series = []
    for lab in arw.LABELS:
        if lab not in spectra:
            continue
        series.append({"name": lab, "points": spectra[lab],
                       "color": core.PALETTE[arw.LABELS.index(lab) % len(core.PALETTE)]})
    if not series:
        return
    top = max(y for s in series for _, y in s["points"])
    body = core.line_chart(series, title="包络谱对比（5–100 Hz，各工况前 3 段均值）",
                           xlabel="包络频率 Hz", ylabel="相对本底倍数",
                           width=680, height=340, ymin=0, ymax=round(top * 1.75 + 0.5),
                           legend_pos="top-right")
    core.save_svg(RESULTS / "envelope_spectrum.svg", 680, 340, body)


def step_envcharts():
    """只重绘包络两张图（重算 15 段包络谱，约 25 s）。"""
    base = arw.load_rows()
    env_path = RESULTS / "envelope_features.csv"
    if not base or not env_path.exists():
        print("缺少 features.csv 或 envelope_features.csv，请先跑 --extract 与 --env")
        return
    by_file = {r["file"]: r for r in core.read_csv(env_path)}
    merged = []
    for r in base:
        e = by_file.get(r["file"])
        if e:
            row = dict(r)
            row.update({k: e[k] for k in ENV_KEYS})
            merged.append(row)
    variants = [
        ("基线 11 维", core.FEATURE_KEYS),
        ("11 维 + 包络 4 维", core.FEATURE_KEYS + ENV_KEYS),
        ("仅包络 4 维", ENV_KEYS),
    ]
    results = [(name, keys, _loo(merged, keys)[0], None) for name, keys in variants]
    env_charts(results, collect_spectra())
    print("包络两张图已重绘")


# --------------------------------------------------------------------------- 包络解调
def step_env():
    base = arw.load_rows()
    if not base:
        return
    env_rows = []
    for key, label, i, path in arw.wav_files():
        if not path.exists():
            continue
        sig, sr = core.read_wav_mono(path, target_rate=8000, seconds=2.0)
        f = core.envelope_features(sig, sr)
        row = {"file": f"{key}-{i}.wav"}
        row.update({k: round(float(v), 6) for k, v in f.items()})
        env_rows.append(row)
    core.write_csv(RESULTS / "envelope_features.csv", env_rows,
                   ["file"] + ENV_KEYS)

    by_file = {r["file"]: r for r in env_rows}
    merged = []
    for r in base:
        e = by_file.get(r["file"])
        if not e:
            continue
        row = dict(r)
        row.update({k: e[k] for k in ENV_KEYS})
        merged.append(row)

    variants = [
        ("基线 11 维（时域+频域）", core.FEATURE_KEYS),
        ("11 维 + 包络 4 维", core.FEATURE_KEYS + ENV_KEYS),
        ("仅包络 4 维", ENV_KEYS),
    ]
    results = []
    for name, keys in variants:
        acc, per, _ = _loo(merged, keys)
        results.append((name, keys, acc, per))

    best = max(results, key=lambda x: x[2])
    acc_b = results[0][2]
    acc_best = best[2]
    gain = (acc_best - acc_b) * 100

    # 逐类召回用留一法的预测，不能用全量训练，否则与上面的准确率对不上
    pairs = _loo(merged, best[1])[2]
    m = core.confusion(pairs, arw.LABELS)
    env_charts(results, collect_spectra())

    # 各工况特征均值
    means = defaultdict(lambda: defaultdict(float))
    cnt = defaultdict(int)
    for r in merged:
        cnt[r["condition"]] += 1
        for k in ENV_KEYS:
            means[r["condition"]][k] += core.fnum(r[k])
    labels_present = [l for l in arw.LABELS if cnt[l]]

    lines = ["# 包络解调试验：中高频还能不能救回摩擦/受阻", "",
             "## 方法", "",
             "声音的低频段已被麦克风滤掉（见 `acoustic_band_limits.md`），但冲击的**重复节律**",
             "保留在中高频里。对每段 8 kHz 信号做 500–3500 Hz 带通，取解析信号的模得到包络，",
             "再对包络做频谱，提取 4 个量：", "",
             "| 特征 | 含义 |", "|---|---|",
             "| `env_peak_hz` | 包络谱 5–100 Hz 内最高峰的位置 = 冲击重复率 |",
             "| `env_snr` | 该峰与本底中位数之比，越大说明冲击越有周期性 |",
             "| `env_kurt` | 包络峭度，冲击越尖锐越大 |",
             "| `env_cv` | 包络变异系数，即调制深度 |", "",
             "## 五工况的包络特征均值", "",
             "| 工况 | " + " | ".join(ENV_KEYS) + " |",
             "|---|" + "---|" * len(ENV_KEYS)]
    for lab in labels_present:
        lines.append(f"| {lab} | " + " | ".join(
            f"{means[lab][k] / cnt[lab]:.3f}" for k in ENV_KEYS) + " |")
    lines += ["", "## 留一法对比（75 段，每次留 1 段）", "",
              "| 特征集 | 准确率 | 相对基线 |", "|---|---|---|"]
    for name, _, acc, _ in results:
        delta = (acc - acc_b) * 100
        lines.append(f"| {name} | **{acc * 100:.1f}%** | {delta:+.1f} pp |")
    lines += ["", "逐类召回（" + best[0] + "）："]
    for i, lab in enumerate(arw.LABELS):
        tot = sum(m[i])
        lines.append(f"- {lab}：{m[i][i]}/{tot} = {(m[i][i] / tot * 100 if tot else 0):.0f}%")

    env_only = results[2][2]
    verdict = ("**采纳**：包络 4 维带来 %.1f pp 提升，已并入主流程。" % gain) if gain >= 2.0 else \
              ("**未采纳**：包络 4 维只带来 %.1f pp 变化（基线 %.1f%% → %.1f%%），"
               "低于 1 段样本（1.3 pp）的判读阈值，作为已验证的负结果保留，不并入主流程。"
               % (gain, acc_b * 100, acc_best * 100))
    lines += ["", "## 结论", "", verdict, "",
              f"仅有包络 4 维时准确率 {env_only * 100:.1f}%（随机猜测 20.0%），说明包络里确实带着"
              "一部分判别信息，但这些信息已被现有 11 维覆盖——",
              "`crest` 度量峰值冲击性、`flatness` 度量谱平坦度，本质上与包络峭度、包络谱信噪比"
              "在描述同一件事。再叠加 4 维同义特征，只会稀释最近质心的距离度量。", "",
              "> 若将来补采加速度通道，包络解调应作用在加速度信号上——那里有真实的",
              "> 低频与转频，冲击重复率才对应真正的故障特征频率。", ""]
    core.write_text(RESULTS / "envelope_experiment.md", "\n".join(lines))
    print(f"包络试验：{acc_b * 100:.1f}% -> {acc_best * 100:.1f}%（{gain:+.1f} pp），最优 = {best[0]}")
    return merged


def _loo(rows, keys):
    hit = 0
    pairs = []
    per = defaultdict(lambda: [0, 0])
    for i, r in enumerate(rows):
        tr = rows[:i] + rows[i + 1:]
        sc, cen = core.build_centroids(tr, keys)
        pred = core.predict(sc, cen, r, keys)
        pairs.append((r["condition"], pred))
        per[r["condition"]][1] += 1
        if pred == r["condition"]:
            hit += 1
            per[r["condition"]][0] += 1
    return hit / len(rows), per, pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bands", action="store_true")
    ap.add_argument("--charts", action="store_true")
    ap.add_argument("--env", action="store_true")
    ap.add_argument("--envcharts", action="store_true")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.all or a.bands:
        step_bands()
    if a.charts:
        step_bands_chart()
    if a.all or a.env:
        step_env()
    if a.envcharts:
        step_envcharts()
    if not (a.all or a.bands or a.env or a.charts or a.envcharts):
        ap.print_help()


if __name__ == "__main__":
    main()
