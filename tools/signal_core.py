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
    # lineterminator="\n"：csv 模块默认输出 CRLF，这里强制 LF，
    # 避免 Windows 上同一批文件一会儿 CRLF 一会儿 LF，编辑器反复显示「已修改」
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_text(path, text):
    """统一的 LF 文本写入。

    `Path.write_text` 在 Windows 上默认按 os.linesep（CRLF）落盘，
    造成脚本产物与手写文件的换行符不一致。这里统一成 LF。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


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
    w = [0.5 - 0.5 * math.cos(2 * math.pi * i / (m - 1)) for i in range(m)]
    cg = sum(w)            # 窗相干增益（Hann 为 m/2）：单边幅度 = 2|X|/sum(w)
    buf = [signal[i] * w[i] for i in range(m)]
    n = 1
    while n < m:
        n <<= 1
    if n_fft:
        k = 1
        while k < max(m, n_fft):
            k <<= 1
        n = k
    buf += [0.0] * (n - m)
    sp = fft(buf)
    half = n // 2
    mags = [abs(sp[k]) * 2.0 / cg for k in range(half)]
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
    # band1–4 是各频段的**幅度和**占比（线性谱），不是幅度平方的能量；
    # 能量口径见 band_energy_ratios()，两者数值不可互相引用。
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


def _nice_step(span, target=4):
    """取 1/2/2.5/5 × 10^k 作为刻度步长，避免出现 0.57、-5.8 这类读不出的刻度值。"""
    if span <= 0:
        return 1.0
    raw = span / max(target, 1)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def _tick_fmt(step):
    """按刻度间隔决定小数位：0.004 要 3 位，0.25 要 2 位，0.5 要 1 位。

    原先按 step 大小分三档（>=1 取整、>=0.1 一位、其余两位），幅度谱这类
    0.000–0.01 量级的图会全被写成 0.00/0.01，刻度形同没有。
    """
    if not step or step >= 1:
        return "{:.0f}"
    for d in (1, 2, 3):
        if abs(round(step, d) - step) <= step * 1e-6:
            return "{:." + str(d) + "f}"
    return "{:.3f}"


def line_chart(series, title="", xlabel="", ylabel="", width=680, height=280,
               ymin=None, ymax=None, legend=True, legend_pos="bottom"):
    """series: [{'name':str,'points':[(x,y)...],'color':str}, ...]

    legend_pos="top-right" 时图例画在绘图区右上角，避免与底部 x 轴标题抢位置。
    """
    L, R, T = 62, 20, 44 if title else 20
    B = 76 if legend and legend_pos == "bottom" else 46
    all_y = [y for s in series for _, y in s["points"]]
    all_x = [x for s in series for x, _ in s["points"]]
    if not all_y:
        return ""
    step = None
    if ymin is not None and ymax is not None:
        y0, y1 = ymin, ymax
        # 显式范围也走 nice step，否则等分出来的刻度会是 -0 / 1 / 1 / 2 这种读不出的值
        step = _nice_step(y1 - y0, 5)
    else:
        lo, hi = min(all_y), max(all_y)
        if hi - lo < 1e-9:
            hi = lo + 1.0
        pad = (hi - lo) * 0.08
        step = _nice_step((hi + pad) - (lo - pad), 4)
        y0 = math.floor((lo - pad) / step) * step
        y1 = math.ceil((hi + pad) / step) * step
        # 全为非负量（幅度谱、能量占比等）时不要画出负区间：轴底 −0.005 会让
        # 读者以为存在负幅度，也白白压掉一截绘图高度。
        if lo >= 0 and y0 < 0:
            y0 = 0.0
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
    if step:
        ticks, v = [], math.ceil(y0 / step - 1e-9) * step
        while v <= y1 + step * 1e-6:
            ticks.append(v)
            v += step
    else:
        ticks = [y0 + (y1 - y0) * i / 4 for i in range(5)]
    fmt = _tick_fmt(step)
    for v in ticks:
        y = py(v)
        b.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}" stroke="{GRID}" stroke-width="0.5"/>')
        b.append(f'<text x="{L - 8}" y="{y + 4:.1f}" font-size="11" fill="{MUTED}" text-anchor="end">{fmt.format(v)}</text>')
    # x 轴与刻度：没有刻度的时间轴读不出时长，波形图的横轴形同虚设
    b.append(f'<line x1="{L}" y1="{T + ph}" x2="{L + pw}" y2="{T + ph}" stroke="{MUTED}" stroke-width="0.8"/>')
    xstep = _nice_step(x1 - x0, 5)
    xv = math.ceil(x0 / xstep) * xstep
    xfmt = _tick_fmt(xstep)
    while xv <= x1 + xstep * 1e-6:
        x = px(xv)
        b.append(f'<line x1="{x:.1f}" y1="{T + ph}" x2="{x:.1f}" y2="{T + ph + 4}" '
                 f'stroke="{MUTED}" stroke-width="0.8"/>')
        b.append(f'<text x="{x:.1f}" y="{T + ph + 16}" font-size="10.5" fill="{MUTED}" '
                 f'text-anchor="middle">{xfmt.format(xv)}</text>')
        xv += xstep
    if xlabel:
        b.append(f'<text x="{L + pw / 2}" y="{T + ph + (64 if B > 50 else 30)}" font-size="11" '
                 f'fill="{MUTED}" text-anchor="middle">{_esc(xlabel)}</text>')
    if ylabel:
        b.append(f'<text x="14" y="{T + ph / 2}" font-size="11" fill="{MUTED}" text-anchor="middle" '
                 f'transform="rotate(-90 14 {T + ph / 2})">{_esc(ylabel)}</text>')
    for idx, s in enumerate(series):
        color = s.get("color") or PALETTE[idx % len(PALETTE)]
        pts = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in s["points"])
        b.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.8" '
                 f'stroke-linejoin="round"/>')
        if legend:
            if legend_pos == "top-right":
                # 右上图例按行竖排：横排时相邻两项的文字会互相压住
                lx = L + pw - 168
                ly = T + 4 + idx * 17
            else:
                lx = L + idx * 132
                ly = T + ph + 32
            b.append(f'<rect x="{lx}" y="{ly}" width="10" height="10" rx="2" fill="{color}"/>')
            b.append(f'<text x="{lx + 15}" y="{ly + 9}" font-size="11" fill="{MUTED}">{_esc(s["name"])}</text>')
    return "".join(b)


def bar_chart(categories, values, title="", ylabel="", width=680, height=280,
              colors=None, value_fmt="{:.1f}"):
    L, R, T = 62, 20, 44 if title else 20
    # 类别多时横排标签必然互相压字，改为斜排并腾出底部空间
    rot = len(categories) > 12
    B = 88 if rot else 56
    pw, ph = width - L - R, height - T - B
    # 刻度取 1/2/2.5/5 的整数倍，避免出现 1e+02、26、51 这类读不出的刻度
    step = _nice_step(max(values + [1e-9]) * 1.05, 4)
    n_ticks = max(2, int(math.ceil(max(values + [1e-9]) * 1.05 / step)))
    y1 = step * n_ticks
    bw = pw / max(len(categories), 1) * 0.6
    step_x = pw / max(len(categories), 1)
    b = []
    if title:
        b.append(f'<text x="{L}" y="24" font-size="14" font-weight="500" fill="{INK}">{_esc(title)}</text>')
    fmt = "{:.0f}" if step >= 1 else ("{:.1f}" if step >= 0.1 else "{:.2f}")
    for i in range(n_ticks + 1):
        v = step * i
        y = T + ph - v / y1 * ph
        b.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}" stroke="{GRID}" stroke-width="0.5"/>')
        b.append(f'<text x="{L - 8}" y="{y + 4:.1f}" font-size="11" fill="{MUTED}" text-anchor="end">{fmt.format(v)}</text>')
    for i, (c, v) in enumerate(zip(categories, values)):
        x = L + step_x * i + (step_x - bw) / 2
        h = v / y1 * ph
        color = (colors or PALETTE)[i % len(colors or PALETTE)]
        b.append(f'<rect x="{x:.1f}" y="{T + ph - h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="3" fill="{color}"/>')
        b.append(f'<text x="{x + bw / 2:.1f}" y="{T + ph - h - 6:.1f}" font-size="11" fill="{INK}" '
                 f'text-anchor="middle">{_esc(value_fmt.format(v))}</text>')
        if rot:
            b.append(f'<text x="{x + bw / 2:.1f}" y="{T + ph + 12:.1f}" font-size="9.5" fill="{MUTED}" '
                     f'text-anchor="end" transform="rotate(-42 {x + bw / 2:.1f} {T + ph + 12:.1f})">'
                     f'{_esc(c)}</text>')
        else:
            b.append(f'<text x="{x + bw / 2:.1f}" y="{T + ph + 18:.1f}" font-size="11" fill="{MUTED}" '
                     f'text-anchor="middle">{_esc(c)}</text>')
    if ylabel:
        b.append(f'<text x="{L}" y="{T - 8}" font-size="11" fill="{MUTED}">{_esc(ylabel)}</text>')
    return "".join(b)


def radar_chart(categories, series, title="", width=680, height=340, vmax=None,
                vmin=0, ring_labels=None, limits=None, limit_labels=None,
                show_values=True, footnote="", scale_bar=True, value_fmt="{:g}"):
    """5 轴雷达图。

    categories : 5 个轴标签（点位）
    series     : [{'name','values','color'}, ...]，values 与 categories 等长
    vmin/vmax  : 径向标尺范围（dB）
    ring_labels: 每个刻度环对应的数值列表（默认按 vmin→vmax 等分）
    limits     : 与 series 等长的阈值列表（如各时段阈值），画成虚线参考多边形
    limit_labels: 与 limits 等长的阈值名称（如「早 55 dB」）
    scale_bar  : 是否画右上角迷你刻度尺（归一化图设 False）
    value_fmt  : 数值标签格式
    """
    # 布局：标题区在上、图例区在下，中间留给雷达本体。
    # 竖直跨度由轴标签位置精确算出（不手写常数）：
    #   标签统一画在 1.14r 处，dy 系数 = 1.14·sin(-90° + 360°·i/n)
    #   上极值 = 1.14·|min dy|，下极值 = 1.14·max dy，再加字号余量。
    title_h = 44 if title else 10
    legend_h = 78 if limits else 32
    usable_h = height - title_h - legend_h
    dys = [1.14 * math.sin(-math.pi / 2 + 2 * math.pi * i / max(len(categories), 1))
           for i in range(len(categories))]
    vert_span = (max(dys) - min(dys)) + 0.14
    r_h = usable_h / vert_span
    radius = min(r_h, width / 2 - 78)
    cx = width / 2
    cy = title_h - min(dys) * radius
    n = len(categories)
    allv = [v for s in series for v in s["values"]]
    vmax = vmax or (max(allv + [1]) * 1.15)
    if vmin >= vmax:
        vmin = 0.0
    b = []
    if title:
        b.append(f'<text x="24" y="24" font-size="14" font-weight="500" fill="{INK}">{_esc(title)}</text>')

    def pt(i, ratio):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        return cx + radius * ratio * math.cos(ang), cy + radius * ratio * math.sin(ang)

    def pt_ang(i, ang, ratio):
        return cx + radius * ratio * math.cos(ang), cy + radius * ratio * math.sin(ang)

    def val_ratio(v):
        """数值 → 径向比例，vmin 之下压到轴心（未采集格占位）。"""
        return min(max((v - vmin) / (vmax - vmin), 0.0), 1.0)

    # 刻度环（不标数字，数字统一放在右上角迷你标尺上，避免与数据标签打架）
    rings = (0.25, 0.5, 0.75, 1.0)
    if ring_labels is None:
        step = (vmax - vmin) / 4.0
        ring_labels = [round(vmin + step * (i + 1)) for i in range(4)]
    for ring in rings:
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, ring) for i in range(n)))
        b.append(f'<polygon points="{poly}" fill="none" stroke="{GRID}" stroke-width="0.5"/>')
    for i, c in enumerate(categories):
        x, y = pt(i, 1.0)
        b.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{GRID}" stroke-width="0.5"/>')
        lx, ly = pt(i, 1.14)
        anchor = "middle" if abs(lx - cx) < 20 else ("start" if lx > cx else "end")
        b.append(f'<text x="{lx:.1f}" y="{ly + 4:.1f}" font-size="11" fill="{MUTED}" '
                 f'text-anchor="{anchor}">{_esc(c)}</text>')

    # 迷你标尺：把径向刻度换算成一条水平尺，位置对应环的比例
    if ring_labels and scale_bar:
        gx0, gx1, gy = width - 182, width - 30, 58
        b.append(f'<text x="{gx1}" y="{gy - 12}" font-size="9" fill="{MUTED}" '
                 f'text-anchor="end">径向刻度 dB</text>')
        b.append(f'<line x1="{gx0}" y1="{gy}" x2="{gx1}" y2="{gy}" stroke="{GRID}" stroke-width="1"/>')
        ticks = [(0.0, vmin)] + [((i + 1) / 4.0, ring_labels[i]) for i in range(len(ring_labels))]
        for t, val in ticks:
            x = gx0 + (gx1 - gx0) * t
            b.append(f'<line x1="{x:.1f}" y1="{gy - 3}" x2="{x:.1f}" y2="{gy + 3}" '
                     f'stroke="{GRID}" stroke-width="1"/>')
            b.append(f'<text x="{x:.1f}" y="{gy + 14}" font-size="8" fill="{MUTED}" '
                     f'text-anchor="middle">{val:.0f}</text>')

    # 阈值参考多边形（虚线）：各时段阈值不同，画出后才能看出哪些轴越线
    if limits:
        for si, lim in enumerate(limits):
            if lim is None:
                continue
            s = series[si]
            poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in
                            (pt(i, val_ratio(lim)) for i in range(n)))
            b.append(f'<polygon points="{poly}" fill="none" stroke="{s.get("color", MUTED)}" '
                     f'stroke-width="1.1" stroke-dasharray="5 4" stroke-opacity="0.85"/>')

    for idx, s in enumerate(series):
        color = s.get("color") or PALETTE[idx % len(PALETTE)]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in
                        (pt(i, val_ratio(v)) for i, v in enumerate(s["values"])))
        b.append(f'<polygon points="{poly}" fill="{color}" fill-opacity="0.13" stroke="{color}" stroke-width="1.8"/>')
        for i, v in enumerate(s["values"]):
            x, y = pt(i, val_ratio(v))
            b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{color}"/>')

    # 数值标签错位：按「每条轴上的数值从大到小排序」分配径向槽位。
    # 同一轴上，数值大的排外圈、小的排内圈 → 标签天然分层，不会互相压字。
    rank = {}
    for i in range(n):
        order = sorted(range(len(series)), key=lambda j: series[j]["values"][i], reverse=True)
        for slot, j in enumerate(order):
            rank[(j, i)] = slot
    n_slot = len(series)
    for idx, s in enumerate(series):
        color = s.get("color") or PALETTE[idx % len(PALETTE)]
        for i, v in enumerate(s["values"]):
            ang = -math.pi / 2 + 2 * math.pi * i / n
            slot = rank[(idx, i)]
            # 槽位 0 = 最外圈；径向步长 0.09 保证相邻槽位至少差一个标签高度
            rad = val_ratio(v) + 0.075 + (n_slot - 1 - slot) * 0.09
            vx, vy = pt_ang(i, ang, min(rad, 0.985))
            # 切向拉开 16 px；对齐方式按偏移方向取 start/end，
            # 让标签从数据点向两侧展开，而不是三个都居中压在同一点上
            tx, ty = -math.sin(ang), math.cos(ang)
            shift = (slot - (n_slot - 1) / 2.0) * 16.0
            vx += tx * shift
            vy += ty * shift
            vx = min(max(vx, 26), width - 26)
            vy = min(max(vy, 38), height - 44)
            anchor = "start" if vx > x + 2 else ("end" if vx < x - 2 else "middle")
            b.append(f'<text x="{vx:.1f}" y="{vy + 3:.1f}" font-size="9" fill="{color}" '
                     f'font-weight="600" text-anchor="{anchor}">{value_fmt.format(v)}</text>')

    # 图例：色块 + 名称；阈值另起一行做虚线说明
    # 图例放在画布底部；雷达图轴标签可能伸到底部，故按 series 数量分两排排布
    leg_cols = max(len(series), 1)
    leg_rows = 1 if leg_cols <= 4 else 2
    per_row = -(-leg_cols // leg_rows)
    for idx, s in enumerate(series):
        color = s.get("color") or PALETTE[idx % len(PALETTE)]
        row, col = divmod(idx, per_row)
        lx = 24 + col * 140
        ly = height - legend_h + 8 + row * 18
        b.append(f'<rect x="{lx}" y="{ly}" width="10" height="10" rx="2" fill="{color}"/>')
        b.append(f'<text x="{lx + 15}" y="{ly + 9}" font-size="11" fill="{MUTED}">{_esc(s["name"])}</text>')
        if limits and idx < len(limits) and limits[idx] is not None:
            lbl = (limit_labels[idx] if limit_labels and idx < len(limit_labels)
                   else f"阈值 {limits[idx]:.0f} dB")
            b.append(f'<line x1="{lx}" y1="{ly + 17}" x2="{lx + 14}" y2="{ly + 17}" '
                     f'stroke="{color}" stroke-width="1.1" stroke-dasharray="5 4"/>')
            b.append(f'<text x="{lx + 19}" y="{ly + 21}" font-size="9" fill="{MUTED}">{_esc(lbl)}</text>')
    if footnote:
        b.append(f'<text x="{width - 24}" y="{height - 13}" font-size="9" fill="{MUTED}" '
                 f'text-anchor="end">{_esc(footnote)}</text>')
    return "".join(b)


def fsm_diagram(states, transitions, title="", width=680, height=420, footnote=""):
    """状态机转移图（声学超标提醒光效逻辑用）。

    states     : [{'name','light','color','cond'}]
    transitions: [{'from','to','label','style'}]  style: 'up' | 'down' | 'peak'
                 up/down 画实线箭头（升级/降级），peak 画独立旁注箭头。
    """
    b = []
    if title:
        b.append(f'<text x="24" y="24" font-size="14" font-weight="500" fill="{INK}">{_esc(title)}</text>')

    n = len(states)
    box_w, box_h = 132, 84
    gap = (width - 48 - n * box_w) / max(n - 1, 1)
    y0 = 92
    pos = {}
    for i, s in enumerate(states):
        x = 24 + i * (box_w + gap)
        pos[s["name"]] = (x, y0, box_w, box_h)
        b.append(f'<rect x="{x:.1f}" y="{y0}" width="{box_w}" height="{box_h}" rx="10" '
                 f'fill="{s["color"]}" fill-opacity="0.10" stroke="{s["color"]}" stroke-width="1.8"/>')
        b.append(f'<text x="{x + box_w / 2:.1f}" y="{y0 + 24}" font-size="13" font-weight="700" '
                 f'fill="{s["color"]}" text-anchor="middle">{_esc(s["name"])}</text>')
        b.append(f'<text x="{x + box_w / 2:.1f}" y="{y0 + 42}" font-size="10" fill="{INK}" '
                 f'text-anchor="middle">{_esc(s.get("light", ""))}</text>')
        # 条件说明分两行排，避免长文本溢出方框
        cond = s.get("cond", "")
        if len(cond) > 16:
            # 优先在空格处换行，硬切会把 "B+3 < Leq" 断成 "B+3 < L" / "eq ≤ B+8"
            gaps = [i for i, ch in enumerate(cond) if ch == " " and 3 <= i <= len(cond) - 3]
            cut = min(gaps, key=lambda i: abs(i - len(cond) / 2)) if gaps else len(cond) // 2
            c1, c2 = cond[:cut], cond[cut:].lstrip()
        else:
            c1, c2 = cond, ""
        b.append(f'<text x="{x + box_w / 2:.1f}" y="{y0 + 58}" font-size="9" fill="{MUTED}" '
                 f'text-anchor="middle">{_esc(c1)}</text>')
        if c2:
            b.append(f'<text x="{x + box_w / 2:.1f}" y="{y0 + 70}" font-size="9" fill="{MUTED}" '
                     f'text-anchor="middle">{_esc(c2)}</text>')

    def arrow(x1, y1, x2, y2, color, dash=True):
        d = ' stroke-dasharray="4 3"' if dash else ""
        # 箭头头部
        import math as _m
        ang = _m.atan2(y2 - y1, x2 - x1)
        hl = 8
        hx1 = x2 - hl * _m.cos(ang - 0.42)
        hy1 = y2 - hl * _m.sin(ang - 0.42)
        hx2 = x2 - hl * _m.cos(ang + 0.42)
        hy2 = y2 - hl * _m.sin(ang + 0.42)
        return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{color}" stroke-width="1.5"{d}/>'
                f'<polygon points="{x2:.1f},{y2:.1f} {hx1:.1f},{hy1:.1f} {hx2:.1f},{hy2:.1f}" fill="{color}"/>')

    # 横向转移箭头：画在方框之间，标签居中
    for tr in transitions:
        f_, t_ = tr["from"], tr["to"]
        if f_ not in pos or t_ not in pos:
            continue
        style = tr.get("style", "up")
        x1, y1, w1, h1 = pos[f_]
        x2, y2, w2, h2 = pos[t_]
        if style == "peak":
            continue
        yy = y1 - 26 if style == "up" else y1 + h1 + 26
        if x2 > x1:  # 向右
            ax1, ax2 = x1 + w1 + 4, x2 - 6
        else:        # 向左
            ax1, ax2 = x1 - 4, x2 + w2 + 6
        col = "#C2410C" if style == "up" else "#0F766E"
        b.append(arrow(ax1, yy, ax2, yy, col))
        lx = (ax1 + ax2) / 2
        ly = yy - 7 if style == "up" else yy + 13
        b.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="9" fill="{col}" '
                 f'text-anchor="middle">{_esc(tr["label"])}</text>')

    # 峰值短闪：独立旁注
    for tr in transitions:
        if tr.get("style") != "peak":
            continue
        x1, y1, w1, h1 = pos[tr["from"]]
        py = y1 + h1 + 54
        b.append(f'<rect x="{x1:.1f}" y="{py}" width="{w1}" height="40" rx="8" '
                 f'fill="#7C2D12" fill-opacity="0.08" stroke="#7C2D12" stroke-width="1.2" '
                 f'stroke-dasharray="4 3"/>')
        b.append(f'<text x="{x1 + w1 / 2:.1f}" y="{py + 16}" font-size="10" font-weight="600" '
                 f'fill="#7C2D12" text-anchor="middle">{_esc(tr["label"])}</text>')
        b.append(f'<text x="{x1 + w1 / 2:.1f}" y="{py + 30}" font-size="9" fill="{MUTED}" '
                 f'text-anchor="middle">不改变主状态</text>')

    # 图例
    lg = [("升级路径（连续 3 帧确认）", "#C2410C", "solid"),
          ("降级路径（连续 5 帧 + 滞回带）", "#0F766E", "dash"),
          ("瞬时事件（单次触发）", "#7C2D12", "dash")]
    ly0 = height - 58
    for i, (txt, col, _) in enumerate(lg):
        y = ly0 + i * 15
        dash = ' stroke-dasharray="4 3"' if i >= 1 else ""
        b.append(f'<line x1="24" y1="{y}" x2="46" y2="{y}" stroke="{col}" stroke-width="1.5"{dash}/>')
        b.append(f'<text x="52" y="{y + 3}" font-size="9" fill="{MUTED}">{_esc(txt)}</text>')
    if footnote:
        b.append(f'<text x="{width - 24}" y="{height - 12}" font-size="9" fill="{MUTED}" '
                 f'text-anchor="end">{_esc(footnote)}</text>')
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


def band_energy_ratios(signal, sample_rate, edges):
    """按频带统计能量占比，返回与 len(edges)-1 等长的列表，和为 1。

    用幅度平方（能量）而非幅度求和：能量占比才能回答「这段信号的能量主要落在
    哪个频带」，直接加幅度会让宽频带凭空占便宜。
    """
    centered = [x - mean(signal) for x in signal]
    freqs, mags = spectrum(centered, sample_rate)
    if not mags:
        return [0.0] * (len(edges) - 1)
    p = [m * m for m in mags]
    tot = sum(p) or 1e-18
    return [sum(v for f, v in zip(freqs, p) if lo <= f < hi) / tot
            for lo, hi in zip(edges[:-1], edges[1:])]


def _fft_inverse(a):
    """逆 FFT：ifft(X) = conj(fft(conj(X))) / n，复用同一个 radix-2 内核。"""
    n = len(a)
    return [v.conjugate() / n for v in fft([x.conjugate() for x in a])]


def analytic_envelope(signal, sample_rate, band=(500.0, 3500.0), env_rate=200.0):
    """带通 + 解析信号求包络，返回 (包络, env_rate)。

    做法：一次前向 FFT 后只保留 [lo, hi] 内的正频率并乘 2、其余置零，
    逆变换直接得到该频带的解析信号，取模即包络——全程两次 FFT。
    频带边缘加 5% 余弦过渡，避免矩形掩膜在时域产生振铃。
    包络本身是低频量（几 Hz 到几十 Hz），按 env_rate 再降采样即可。
    """
    n = len(signal)
    if n < 64:
        return [], env_rate
    n_fft = 1
    while n_fft < n:
        n_fft <<= 1
    buf = [complex(x - mean(signal)) for x in signal] + [0j] * (n_fft - n)
    sp = fft(buf)
    lo, hi = band
    taper = max((hi - lo) * 0.05, 1.0)

    def gain(f):
        if f < lo or f > hi:
            return 0.0
        edge = min(f - lo, hi - f)
        if edge < taper:
            return 0.5 - 0.5 * math.cos(math.pi * edge / taper)
        return 1.0

    for k in range(1, n_fft // 2):                 # 正频率乘 2 构造解析信号
        g = gain(k * sample_rate / n_fft) * 2.0
        if g:
            sp[k] *= g
        else:
            sp[k] = 0j
        sp[n_fft - k] = 0j                          # 负频率全部置零
    sp[0] = 0j
    sp[n_fft // 2] = 0j
    env = [abs(v) for v in _fft_inverse(sp)[:n]]
    if env_rate < sample_rate:
        step = sample_rate / env_rate
        out, k = [], 0
        while True:
            a = int(k * step)
            if a >= len(env):
                break
            b = max(a + 1, int((k + 1) * step))
            chunk = env[a:b]
            out.append(sum(chunk) / len(chunk))
            k += 1
        return out, env_rate
    return env, sample_rate


def envelope_features(signal, sample_rate, band=(500.0, 3500.0), env_rate=200.0,
                      f_lo=5.0, f_hi=100.0):
    """包络解调特征——摩擦/受阻这类冲击性故障的判别量。

    物理依据：叶片每转一圈刮擦一次，冲击重复率等于转频或其整数倍，
    在包络谱上表现为一根窄峰；而稳态气动噪声的包络是随机的、没有窄峰。
      env_peak_hz —— 包络谱 5–100 Hz 内的最高峰位置（冲击重复率）
      env_snr     —— 该峰与本底中位数之比（峰有多突出）
      env_kurt    —— 包络峭度（冲击越尖锐越大）
      env_cv      —— 包络变异系数（调制深度）
    """
    out = {"env_peak_hz": 0.0, "env_snr": 0.0, "env_kurt": 0.0, "env_cv": 0.0}
    env, er = analytic_envelope(signal, sample_rate, band, env_rate)
    if len(env) < 64:
        return out
    m = mean(env)
    out["env_cv"] = std(env) / (m + 1e-12)
    d = [x - m for x in env]
    m2 = sum(x * x for x in d) / len(d)
    m4 = sum(x ** 4 for x in d) / len(d)
    out["env_kurt"] = m4 / (m2 * m2 + 1e-18) - 3.0
    freqs, mags = spectrum(d, er, n_fft=1024)
    band_idx = [i for i, f in enumerate(freqs) if f_lo <= f <= f_hi]
    if band_idx:
        k = max(band_idx, key=lambda i: mags[i])
        out["env_peak_hz"] = freqs[k]
        ordered = sorted(mags[i] for i in band_idx)
        med = ordered[len(ordered) // 2]
        out["env_snr"] = mags[k] / (med + 1e-12)
    return out


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
