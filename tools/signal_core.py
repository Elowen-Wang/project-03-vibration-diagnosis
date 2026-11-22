"""ICEC 2026 选拔 · 共用内核（零第三方依赖，Python 3.8+）

提供：CSV 读写、radix-2 FFT 与频谱特征、统计量、纯 SVG 图表输出、合成演示数据。
所有分析脚本共用本文件，保证三个课题的数据格式与分析口径一致。
"""
from __future__ import annotations

import csv
import cmath
import html
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

PALETTE = ["#185FA5", "#D85A30", "#1D9E75", "#7F77DD", "#BA7517", "#993556"]
INK = "#2C2C2A"
MUTED = "#5F5E5A"
GRID = "#D3D1C7"
BG = "#FFFFFF"


# --------------------------------------------------------------------------- CSV
def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames=None):
    if not rows:
        return
    fieldnames = fieldnames or list(rows[0].keys())
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def fnum(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- 统计
def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def std(xs):
    xs = list(xs)
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def rms(xs):
    xs = list(xs)
    return math.sqrt(sum(x * x for x in xs) / len(xs)) if xs else 0.0


def zcr(xs):
    """过零率（每秒），xs 为已去直流的采样序列。"""
    xs = list(xs)
    if len(xs) < 2:
        return 0.0
    return sum(1 for i in range(1, len(xs)) if xs[i - 1] * xs[i] < 0) / (len(xs) - 1)


def percentile(xs, p):
    xs = sorted(xs)
    if not xs:
        return 0.0
    k = (len(xs) - 1) * p / 100.0
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return xs[lo] if lo == hi else xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def normalize(xs):
    m, s = mean(xs), std(xs)
    return [(x - m) / (s if s > 1e-12 else 1.0) for x in xs]


# --------------------------------------------------------------------------- FFT
def fft(a):
    """迭代 radix-2 Cooley-Tukey FFT，输入长度必须是 2 的幂。"""
    n = len(a)
    if n == 0 or (n & (n - 1)) != 0:
        raise ValueError("FFT 输入长度必须是 2 的幂")
    a = [complex(v) for v in a]
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    length = 2
    while length <= n:
        wlen = cmath.exp(-2j * math.pi / length)
        for i in range(0, n, length):
            w = 1 + 0j
            for k in range(length // 2):
                u = a[i + k]
                v = a[i + k + length // 2] * w
                a[i + k] = u + v
                a[i + k + length // 2] = u - v
                w *= wlen
        length <<= 1
    return a


def spectrum(signal, sample_rate, n_fft=None):
    """加 Hann 窗、补零到 2 的幂，返回 (freqs, magnitudes) 的单边幅度谱。

    n_fft 可指定更大的 2 的幂做零填充插值，提高主频定位精度（不改变真实分辨率）。
    """
    m = len(signal)
    if m < 4:
        return [], []
    win = [signal[i] * (0.5 - 0.5 * math.cos(2 * math.pi * i / (m - 1))) for i in range(m)]
    n = 1
    while n < m:
        n <<= 1
    if n_fft:
        k = 1
        while k < max(m, n_fft):
            k <<= 1
        n = k
    win += [0.0] * (n - m)
    sp = fft(win)
    half = n // 2
    mags = [abs(sp[k]) * 2.0 / m for k in range(half)]
    freqs = [k * sample_rate / n for k in range(half)]
    return freqs, mags


def spectral_features(signal, sample_rate, n_fft=None):
    """时域 + 频域特征字典，课题 6/8 与项目三共用同一套定义。"""
    dc = mean(signal)
    centered = [x - dc for x in signal]
    r = rms(centered)
    peak = max((abs(x) for x in centered), default=0.0)
    feats = {
        "rms": r,
        "std": std(centered),
        "peak": peak,
        "crest": peak / (r + 1e-12),
        "zcr": zcr(centered) * sample_rate,
    }
    freqs, mags = spectrum(centered, sample_rate)
    if not mags:
        feats.update({"centroid": 0, "dominant_hz": 0, "flatness": 0,
                      "band1": 0, "band2": 0, "band3": 0, "band4": 0})
        return feats
    total = sum(mags[1:]) or 1e-12
    feats["centroid"] = sum(f * m for f, m in zip(freqs, mags)) / total
    kmax = max(range(1, len(mags)), key=lambda k: mags[k])
    feats["dominant_hz"] = freqs[kmax]
    logs = [math.log(m + 1e-12) for m in mags[1:]]
    feats["flatness"] = math.exp(mean(logs)) / (mean(mags[1:]) + 1e-12)
    nyq = sample_rate / 2.0
    for i in range(4):
        lo, hi = nyq * i / 4.0, nyq * (i + 1) / 4.0
        feats[f"band{i + 1}"] = sum(m for f, m in zip(freqs, mags) if lo <= f < hi) / total
    return feats


# --------------------------------------------------------------------------- 步态特征
def cadence_features(az, sample_rate, prominence=1.2, min_gap_s=0.2):
    """从垂直轴加速度提取步态节律特征（课题 08 专用）。

    物理依据：
      步频 cadence —— 每秒落地/蹬离次数，反映动作速率；
      步频规整度 cad_cv —— 相邻步间隔的变异系数。平地行走双脚交替、节奏稳定，
        上下楼梯每级高度不同、需要蹬伸，节奏抖动明显，这是「平地 vs 爬楼」
        最稳健的判据（对手机位置与佩戴方式不敏感）；
      1x/2x 能量比 ratio —— 步频主峰带与其二次谐波带的能量之比。平地行走时
        双脚交替使垂向力主要出现在 2× 步频，比值大；上下楼梯以单脚支撑为主，
        能量集中在 1× 步频，比值小。

    返回 dict：cadence / cad_cv / align / ratio。
    """
    n = len(az)
    out = {"cadence": 0.0, "cad_cv": 2.5, "align": 0.0, "ratio": 0.0}
    if n < 16:
        return out
    centered = [v - mean(az) for v in az]
    sd = std(centered) + 1e-9
    peaks, last = [], -10 ** 9
    gap = max(1, int(sample_rate * min_gap_s))
    for i in range(1, n - 1):
        if centered[i] > prominence * sd and centered[i] >= centered[i - 1] \
                and centered[i] > centered[i + 1]:
            if i - last > gap:
                peaks.append(i)
                last = i
    cad = len(peaks) / (n / sample_rate)
    out["cadence"] = cad
    ivs = [(peaks[i + 1] - peaks[i]) / sample_rate for i in range(len(peaks) - 1)]
    if len(ivs) >= 2 and mean(ivs) > 0:
        out["cad_cv"] = std(ivs) / mean(ivs)
    if cad <= 0.2:
        return out
    step = max(1, n // 4000)
    freqs, mags = spectrum(centered[::step], sample_rate / step, n_fft=1024)
    if not mags:
        return out
    lo1, hi1 = max(0.2, cad * 0.65), cad * 1.35
    b1 = sum(m for f, m in zip(freqs, mags) if lo1 <= f <= hi1)
    b2 = sum(m for f, m in zip(freqs, mags) if cad * 1.65 <= f <= cad * 2.35)
    out["ratio"] = b1 / (b2 + 1e-12)
    peak1 = max((m for f, m in zip(freqs, mags) if lo1 <= f <= hi1), default=0.0)
    out["align"] = peak1 / (max(mags) + 1e-12)
    return out


def matrix_grid(row_labels, col_labels, cells, limits=None, title="",
                width=680, height=340, note=""):
    """点位 × 时段矩阵热力图：缺失格画斜线并标注「未采集」。

    cells[i][j] 为数值或 None（未采集）。
    limits 为每个**行**的阈值（行通常是时段，阈值是时段属性）；超标格描红边。
    """
    L, T = 110, 58
    cell = min((width - L - 30) / max(len(col_labels), 1),
               (height - T - 56) / max(len(row_labels), 1), 74)
    b = []
    if title:
        b.append(f'<text x="24" y="24" font-size="14" font-weight="500" fill="{INK}">{_esc(title)}</text>')
    b.append(f'<text x="24" y="42" font-size="11" fill="{MUTED}">{_esc(note)}</text>')
    for j, c in enumerate(col_labels):
        x = L + cell * j + cell / 2
        b.append(f'<text x="{x:.1f}" y="{T - 12}" font-size="11" fill="{MUTED}" text-anchor="middle">{_esc(c)}</text>')
    mx = max((v for row in cells for v in row if v is not None), default=1) or 1
    for i, r in enumerate(row_labels):
        y = T + cell * i
        lim = limits[i] if limits and i < len(limits) else None
        b.append(f'<text x="{L - 12}" y="{y + cell / 2 + 1:.1f}" font-size="11" fill="{INK}" '
                 f'text-anchor="end">{_esc(r)}</text>')
        if lim is not None:
            b.append(f'<text x="{L - 12}" y="{y + cell / 2 + 14:.1f}" font-size="9" fill="{MUTED}" '
                     f'text-anchor="end">阈值 {lim:.0f} dB</text>')
        for j, c in enumerate(col_labels):
            v = cells[i][j]
            x = L + cell * j
            if v is None:
                b.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell - 3:.1f}" height="{cell - 3:.1f}" '
                         f'rx="4" fill="none" stroke="{GRID}" stroke-width="1" stroke-dasharray="3 3"/>')
                b.append(f'<text x="{x + cell / 2:.1f}" y="{y + cell / 2 + 4:.1f}" font-size="10" '
                         f'fill="{MUTED}" text-anchor="middle">未采集</text>')
                continue
            ratio = min(v / mx, 1.0)
            color = _heat_color(ratio)
            over = lim is not None and v >= lim
            b.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell - 3:.1f}" height="{cell - 3:.1f}" '
                     f'rx="4" fill="{color}" fill-opacity="0.55" stroke="{"#e5484d" if over else color}" '
                     f'stroke-width="{2 if over else 1}"/>')
            b.append(f'<text x="{x + cell / 2:.1f}" y="{y + cell / 2 + 1:.1f}" font-size="14" '
                     f'font-weight="600" fill="{INK}" text-anchor="middle">{v:.0f}</text>')
            b.append(f'<text x="{x + cell / 2:.1f}" y="{y + cell / 2 + 15:.1f}" font-size="9" '
                     f'fill="{MUTED}" text-anchor="middle">dB</text>')
            if over:
                b.append(f'<text x="{x + cell - 8:.1f}" y="{y + 14:.1f}" font-size="10" '
                         f'fill="#e5484d" text-anchor="end">超标</text>')
    ly = T + cell * len(row_labels) + 18
    b.append(f'<rect x="{L}" y="{ly - 10}" width="11" height="11" rx="2" fill="#e5484d" fill-opacity="0.55" '
             f'stroke="#e5484d" stroke-width="2"/>')
    b.append(f'<text x="{L + 17}" y="{ly}" font-size="10" fill="{MUTED}">红框 = 超标</text>')
    b.append(f'<rect x="{L + 110}" y="{ly - 10}" width="11" height="11" rx="2" fill="none" '
             f'stroke="{GRID}" stroke-dasharray="3 3"/>')
    b.append(f'<text x="{L + 127}" y="{ly}" font-size="10" fill="{MUTED}">虚线 = 未采集</text>')
    return "".join(b)


def _heat_color(ratio):
    """低→高：蓝 → 青 → 绿 → 橙 → 红。"""
    stops = [(0.29, 0.63, 0.94), (0.31, 0.85, 0.85), (0.44, 0.80, 0.53),
             (0.98, 0.76, 0.31), (0.93, 0.36, 0.36)]
    r = max(0.0, min(0.999, ratio)) * (len(stops) - 1)
    i = int(r)
    f = r - i
    a, b2 = stops[i], stops[min(i + 1, len(stops) - 1)]
    return "#" + "".join(f"{int((a[k] + (b2[k] - a[k]) * f) * 255):02x}" for k in range(3))


# --------------------------------------------------------------------------- SVG
def _esc(s):
    return html.escape(str(s), quote=True)


def svg_doc(width, height, body):
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" role="img">'
        f'<rect width="{width}" height="{height}" fill="{BG}"/>'
        f'<g font-family="system-ui, -apple-system, Segoe UI, Microsoft YaHei, sans-serif">'
    )
    return head + body + "</g></svg>"


def save_svg(path, width, height, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg_doc(width, height, body), encoding="utf-8")
    return path


def _nice_bounds(vals):
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-9:
        hi = lo + 1.0
    pad = (hi - lo) * 0.12
    return lo - pad, hi + pad


def line_chart(series, title="", xlabel="", ylabel="", width=680, height=280,
               ymin=None, ymax=None, legend=True):
    """series: [{'name':str,'points':[(x,y)...],'color':str}, ...]"""
    L, R, T, B = 62, 20, 44 if title else 20, 48
    all_y = [y for s in series for _, y in s["points"]]
    all_x = [x for s in series for x, _ in s["points"]]
    if not all_y:
        return ""
    y0, y1 = (ymin, ymax) if ymin is not None and ymax is not None else _nice_bounds(all_y)
    x0, x1 = min(all_x), max(all_x)
    if x1 - x0 < 1e-9:
        x1 = x0 + 1
    pw, ph = width - L - R, height - T - B

    def px(x):
        return L + (x - x0) / (x1 - x0) * pw

    def py(y):
        return T + ph - (y - y0) / (y1 - y0) * ph

    b = []
    if title:
        b.append(f'<text x="{L}" y="24" font-size="14" font-weight="500" fill="{INK}">{_esc(title)}</text>')
    for i in range(5):
        v = y0 + (y1 - y0) * i / 4
        y = py(v)
        b.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}" stroke="{GRID}" stroke-width="0.5"/>')
        b.append(f'<text x="{L - 8}" y="{y + 4:.1f}" font-size="11" fill="{MUTED}" text-anchor="end">{v:.2g}</text>')
    b.append(f'<text x="{L}" y="{T + ph + 30}" font-size="11" fill="{MUTED}" text-anchor="middle" '
             f'transform="translate({pw / 2 - L / 2},0)">{_esc(xlabel)}</text>')
    if ylabel:
        b.append(f'<text x="14" y="{T + ph / 2}" font-size="11" fill="{MUTED}" text-anchor="middle" '
                 f'transform="rotate(-90 14 {T + ph / 2})">{_esc(ylabel)}</text>')
    for idx, s in enumerate(series):
        color = s.get("color") or PALETTE[idx % len(PALETTE)]
        pts = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in s["points"])
        b.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.8" '
                 f'stroke-linejoin="round"/>')
        if legend:
            lx = L + idx * 132
            b.append(f'<rect x="{lx}" y="{T + ph + 14}" width="10" height="10" rx="2" fill="{color}"/>')
            b.append(f'<text x="{lx + 15}" y="{T + ph + 23}" font-size="11" fill="{MUTED}">{_esc(s["name"])}</text>')
    return "".join(b)


def bar_chart(categories, values, title="", ylabel="", width=680, height=280,
              colors=None, value_fmt="{:.1f}"):
    L, R, T, B = 62, 20, 44 if title else 20, 56
    pw, ph = width - L - R, height - T - B
    y1 = max(values + [1e-9]) * 1.15
    bw = pw / max(len(categories), 1) * 0.6
    step = pw / max(len(categories), 1)
    b = []
    if title:
        b.append(f'<text x="{L}" y="24" font-size="14" font-weight="500" fill="{INK}">{_esc(title)}</text>')
    for i in range(5):
        v = y1 * i / 4
        y = T + ph - v / y1 * ph
        b.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}" stroke="{GRID}" stroke-width="0.5"/>')
        b.append(f'<text x="{L - 8}" y="{y + 4:.1f}" font-size="11" fill="{MUTED}" text-anchor="end">{v:.2g}</text>')
    for i, (c, v) in enumerate(zip(categories, values)):
        x = L + step * i + (step - bw) / 2
        h = v / y1 * ph
        color = (colors or PALETTE)[i % len(colors or PALETTE)]
        b.append(f'<rect x="{x:.1f}" y="{T + ph - h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="3" fill="{color}"/>')
        b.append(f'<text x="{x + bw / 2:.1f}" y="{T + ph - h - 6:.1f}" font-size="11" fill="{INK}" '
                 f'text-anchor="middle">{_esc(value_fmt.format(v))}</text>')
        b.append(f'<text x="{x + bw / 2:.1f}" y="{T + ph + 18:.1f}" font-size="11" fill="{MUTED}" '
                 f'text-anchor="middle">{_esc(c)}</text>')
    if ylabel:
        b.append(f'<text x="{L}" y="{T - 8}" font-size="11" fill="{MUTED}">{_esc(ylabel)}</text>')
    return "".join(b)


def radar_chart(categories, series, title="", width=680, height=340, vmax=None):
    """series: [{'name':str,'values':[float...],'color':str}, ...]"""
    cx, cy, radius = width / 2, height / 2 + 10, min(width, height) / 2 - 58
    n = len(categories)
    allv = [v for s in series for v in s["values"]]
    vmax = vmax or (max(allv + [1]) * 1.15)
    b = []
    if title:
        b.append(f'<text x="24" y="24" font-size="14" font-weight="500" fill="{INK}">{_esc(title)}</text>')

    def pt(i, ratio):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        return cx + radius * ratio * math.cos(ang), cy + radius * ratio * math.sin(ang)

    for ring in (0.25, 0.5, 0.75, 1.0):
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, ring) for i in range(n)))
        b.append(f'<polygon points="{poly}" fill="none" stroke="{GRID}" stroke-width="0.5"/>')
    for i, c in enumerate(categories):
        x, y = pt(i, 1.0)
        b.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{GRID}" stroke-width="0.5"/>')
        lx, ly = pt(i, 1.14)
        anchor = "middle" if abs(lx - cx) < 20 else ("start" if lx > cx else "end")
        b.append(f'<text x="{lx:.1f}" y="{ly + 4:.1f}" font-size="11" fill="{MUTED}" '
                 f'text-anchor="{anchor}">{_esc(c)}</text>')
    for idx, s in enumerate(series):
        color = s.get("color") or PALETTE[idx % len(PALETTE)]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in
                        (pt(i, min(v / vmax, 1.0)) for i, v in enumerate(s["values"])))
        b.append(f'<polygon points="{poly}" fill="{color}" fill-opacity="0.13" stroke="{color}" stroke-width="1.8"/>')
        for x, y in (pt(i, min(v / vmax, 1.0)) for i, v in enumerate(s["values"])):
            b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{color}"/>')
        lx = 24 + idx * 140
        b.append(f'<rect x="{lx}" y="{height - 22}" width="10" height="10" rx="2" fill="{color}"/>')
        b.append(f'<text x="{lx + 15}" y="{height - 13}" font-size="11" fill="{MUTED}">{_esc(s["name"])}</text>')
    return "".join(b)


def heatmap(matrix, row_labels, col_labels, title="", width=680, height=320, value_fmt="{}"):
    L, T = 96, 52
    cell = min((width - L - 20) / max(len(col_labels), 1), (height - T - 40) / max(len(row_labels), 1), 62)
    b = []
    if title:
        b.append(f'<text x="24" y="24" font-size="14" font-weight="500" fill="{INK}">{_esc(title)}</text>')
    mx = max((v for row in matrix for v in row), default=1) or 1
    for j, c in enumerate(col_labels):
        b.append(f'<text x="{L + cell * j + cell / 2:.1f}" y="{T - 10}" font-size="11" fill="{MUTED}" '
                 f'text-anchor="middle">{_esc(c)}</text>')
    for i, r in enumerate(row_labels):
        b.append(f'<text x="{L - 10}" y="{T + cell * i + cell / 2 + 4:.1f}" font-size="11" fill="{MUTED}" '
                 f'text-anchor="end">{_esc(r)}</text>')
        for j, v in enumerate(matrix[i]):
            alpha = 0.10 + 0.85 * (v / mx)
            x, y = L + cell * j, T + cell * i
            b.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell - 3:.1f}" height="{cell - 3:.1f}" '
                     f'rx="4" fill="#185FA5" fill-opacity="{alpha:.2f}"/>')
            b.append(f'<text x="{x + (cell - 3) / 2:.1f}" y="{y + (cell - 3) / 2 + 4:.1f}" font-size="12" '
                     f'fill="{INK}" text-anchor="middle">{_esc(value_fmt.format(v))}</text>')
    return "".join(b)


# --------------------------------------------------------------------------- 合成演示数据
def synth_noise_rows():
    """课题 6 演示数据：5 点位 × 3 时段 = 15 组。"""
    base = {"图书馆": 38, "食堂": 66, "主干道": 62, "运动场": 58, "实训室走廊": 48}
    period = {"早": -4.0, "午": 5.0, "晚": -1.0}
    rnd = random.Random(6)
    rows = []
    for spot, v in base.items():
        for slot, d in period.items():
            leq = v + d + rnd.uniform(-2.5, 2.5)
            rows.append({
                "record_id": f"N06-{len(rows) + 1:02d}", "date": "2026-11-15",
                "period": slot, "location": spot, "duration_s": 60,
                "leq_db": round(leq, 1), "peak_db": round(leq + rnd.uniform(6, 13), 1),
                "samples": 60, "weather": "晴", "device": "手机分贝计 App",
                "photo": f"raw_data/06-{len(rows) + 1:02d}.jpg",
            })
    return rows


def synth_gait_wave(state, seconds=6.0, rate=50):
    """课题 8 演示波形：4 种姿态的三轴加速度（单位 g）。"""
    seeds = {"静止": 101, "平地慢走": 202, "快跑": 303, "上下楼梯": 404}
    rnd = random.Random(seeds.get(state, 0))
    cfg = {
        "静止": (0.0, 0.25, 0.02),
        "平地慢走": (1.7, 1.10, 0.24),
        "快跑": (3.1, 2.60, 0.42),
        "上下楼梯": (1.9, 1.55, 0.55),
    }
    freq, amp, noise = cfg[state]
    n = int(seconds * rate)
    out = []
    for i in range(n):
        t = i / rate
        a = 2 * math.pi * freq * t
        ax = amp * 0.35 * math.sin(a) + rnd.gauss(0, noise * 0.4)
        ay = amp * 0.30 * math.sin(a + 0.7) + rnd.gauss(0, noise * 0.4)
        az = 1.0 + amp * math.sin(a + 1.4) + rnd.gauss(0, noise)
        out.append({"time_s": round(t, 3), "ax_g": round(ax, 4),
                    "ay_g": round(ay, 4), "az_g": round(az, 4)})
    return out


def synth_machine_signal(condition, seconds=2.0, rate=4000, seed=0):
    """项目三演示信号：5 种工况的声学波形（可用 wave 模块写成 WAV）。"""
    rnd = random.Random(seed * 7919 + 13)
    cfg = {
        "W1-正常低速": (48.0, 0.16, 0.00),
        "W2-正常高速": (96.0, 0.30, 0.00),
        "W3-扇叶失衡": (48.0, 0.20, 0.55),
        "W4-进风遮挡": (48.0, 0.13, 0.20),
        "W5-结构松动": (48.0, 0.23, 0.38),
    }
    f0, amp, mod = cfg[condition]
    n = int(seconds * rate)
    sig = []
    for i in range(n):
        t = i / rate
        env = 1.0 + mod * math.sin(2 * math.pi * (f0 / 6.0) * t)
        v = amp * (math.sin(2 * math.pi * f0 * t)
                   + 0.45 * math.sin(2 * math.pi * 2 * f0 * t)
                   + 0.22 * math.sin(2 * math.pi * 3 * f0 * t)) * env
        v += 0.035 * math.sin(2 * math.pi * (f0 * 7.3) * t)
        v += rnd.gauss(0, 0.02)
        sig.append(v)
    return sig


def write_wav(path, signal, rate=4000):
    """把 [-1,1] 浮点序列写成 16-bit 单声道 PCM WAV（标准库 wave）。"""
    import struct
    import wave
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = [max(-32768, min(32767, int(v * 32767))) for v in signal]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<" + "h" * len(pcm), *pcm))
    return path


def read_wav(path):
    """读 16-bit PCM WAV，返回 (归一化浮点列表, 采样率)。"""
    import struct
    import wave
    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
        n = len(raw) // 2
        vals = struct.unpack("<" + "h" * n, raw[:n * 2])
        return [v / 32768.0 for v in vals], rate


# --------------------------------------------------------------------------- 真实 WAV 读取（双声道 / 降采样）
def read_wav_mono(path, target_rate=4000, seconds=2.0):
    """读取本仓库的 48 kHz 双声道 16-bit WAV，取中间 seconds 秒，
    声道取平均，箱式平均降采样到 target_rate，返回 (浮点列表, target_rate)。

    风扇/电机的判别信息集中在 2 kHz 以下，降到 4000 Hz 既保留主频与谐波，
    又把纯 Python FFT 的长度控制在 8192 点，75 个文件几秒就能跑完。
    """
    import struct
    import wave
    with wave.open(str(path), "rb") as w:
        ch, rate, sw, n = w.getnchannels(), w.getframerate(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError(f"{path}: 只支持 16-bit PCM，当前 sampwidth={sw}")
    bpf = ch * sw
    want = int(rate * seconds)
    start = max(0, (n - want) // 2)
    count = min(want, n - start)
    seg = raw[start * bpf:(start + count) * bpf]
    shorts = struct.unpack("<" + "h" * (len(seg) // 2), seg[:len(seg) // 2 * 2])
    if ch == 1:
        mono = list(shorts)
    else:
        mono = [sum(shorts[i:i + ch]) / ch for i in range(0, len(shorts) - ch + 1, ch)]
    step = rate / float(target_rate)
    if step < 1:
        step = 1.0
    out, k = [], 0
    while True:
        a = int(k * step)
        if a >= len(mono):
            break
        b = max(a + 1, int((k + 1) * step))
        chunk = mono[a:b]
        out.append(sum(chunk) / len(chunk) / 32768.0)
        k += 1
    return out, target_rate


def add_awgn(signal, snr_db, seed=0):
    """按指定信噪比叠加高斯白噪声，用于抗噪鲁棒性实验。"""
    rnd = random.Random(seed)
    ps = sum(x * x for x in signal) / max(len(signal), 1)
    sd = math.sqrt(ps / (10 ** (snr_db / 10.0)))
    return [x + rnd.gauss(0, sd) for x in signal]


# --------------------------------------------------------------------------- 最近质心分类器
FEATURE_KEYS = ["rms", "std", "crest", "zcr", "centroid", "dominant_hz",
                "flatness", "band1", "band2", "band3", "band4"]


def fit_scaler(rows, keys=FEATURE_KEYS):
    out = {}
    for k in keys:
        vals = [fnum(r.get(k)) for r in rows]
        s = std(vals)
        out[k] = (mean(vals), s if s > 1e-12 else 1.0)
    return out


def _vec(row, keys, scaler):
    out = []
    for k in keys:
        m, s = scaler[k]
        out.append((fnum(row.get(k)) - m) / s)
    return out


def build_centroids(train, keys=FEATURE_KEYS, label_key="condition"):
    scaler = fit_scaler(train, keys)
    groups = {}
    for r in train:
        groups.setdefault(r[label_key], []).append(_vec(r, keys, scaler))
    centroids = {lab: [mean(col) for col in zip(*vs)] for lab, vs in groups.items()}
    return scaler, centroids


def predict(scaler, centroids, row, keys=FEATURE_KEYS):
    v = _vec(row, keys, scaler)
    return min(centroids, key=lambda lab: sum((a - b) ** 2 for a, b in zip(v, centroids[lab])))


def confusion(pairs, labels):
    idx = {l: i for i, l in enumerate(labels)}
    m = [[0] * len(labels) for _ in labels]
    for truth, pred in pairs:
        if truth in idx and pred in idx:
            m[idx[truth]][idx[pred]] += 1
    return m


def accuracy(pairs):
    return sum(1 for t, p in pairs if t == p) / len(pairs) if pairs else 0.0


if __name__ == "__main__":
    import math as _m
    _sig = [_m.sin(2 * _m.pi * 100 * i / 4000) for i in range(4096)]
    _f = spectral_features(_sig, 4000)
    print("signal_core self-check")
    print("  FFT dominant = %.1f Hz (expected 100)" % _f["dominant_hz"])
    print("  RMS = %.3f  centroid = %.1f Hz" % (_f["rms"], _f["centroid"]))
    _n = add_awgn(_sig, 10, seed=1)
    print("  AWGN 10dB -> RMS %.3f (clean %.3f)" % (rms(_n), rms(_sig)))
    print("  SVG helpers:", len(line_chart([{"name": "x", "points": [(0, 1), (1, 2)]}])) > 0)
    print("OK - no third-party package needed")
