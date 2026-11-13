"""课题 08 · 多姿态步态加速度特征采集与对比（零第三方依赖）

用法（仓库根目录执行）：
    python 01_Stage1_Field_Measurement\\analyze_gait.py --demo   # 没采数据时先跑通流程
    python 01_Stage1_Field_Measurement\\analyze_gait.py           # 分析 gait_raw/ 里的真实 CSV

自动识别 Phyphox 导出的列名，按 2 秒窗口提取特征，输出波形图、
特征表、可解释阈值规则与留出集混淆矩阵。
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
RAW = HERE / "gait_raw"
STATES = ["静止", "平地慢走", "快跑", "上下楼梯"]
FIELDS = ["file", "state", "window", "svm_mean", "svm_std", "az_range",
          "dominant_hz", "zcr", "centroid"]


def demo_files():
    d = RESULTS / "_demo"
    d.mkdir(exist_ok=True)
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
    print("[demo] 已生成 4 份演示 CSV 到 results/_demo/，仅用于验证脚本流程")
    return paths


def real_files():
    if not RAW.exists():
        return []
    out = []
    for p in sorted(RAW.glob("*.csv")):
        state = next((s for s in STATES if s in p.name), "未标注")
        out.append((state, p))
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
    # Phyphox 常用 m/s^2 且含重力：若 z 均值大于 5，逐轴去均值去掉重力偏置
    if abs(core.mean([z for _, _, z in xyz])) > 5:
        mx, my, mz = (core.mean([v[i] for v in xyz]) for i in range(3))
        xyz = [(x - mx, y - my, z - mz) for x, y, z in xyz]
        scale = 1.0 / 9.81
        xyz = [(x * scale, y * scale, z * scale) for x, y, z in xyz]
    return xyz, rate, len(rows)


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


def calibrate(train):
    """只用训练窗口自动标定 3 个阈值：取两类均值的中点。

    规则结构固定且物理可解释，阈值随数据自适应，避免把合成数据的数值
    硬套到真实采集上；标定过程只用训练窗口，测试窗口完全不参与。
    """
    by = {s: [f for f in train if f["state"] == s] for s in STATES}
    if any(not by[s] for s in STATES):
        return dict(DEFAULT_THR)
    m = lambda s, k: core.mean([f[k] for f in by[s]])
    return {
        "svm_std": (m("静止", "svm_std") +
                    min(m(s, "svm_std") for s in STATES[1:])) / 2,
        "dominant_hz": (m("快跑", "dominant_hz") +
                        max(m(s, "dominant_hz") for s in ("平地慢走", "上下楼梯"))) / 2,
        "az_range": (m("上下楼梯", "az_range") + m("平地慢走", "az_range")) / 2,
    }


def classify(f, thr=None):
    """可解释阈值规则：物理含义明确，便于面试逐条讲清楚。"""
    t = thr or DEFAULT_THR
    if f["svm_std"] < t["svm_std"]:
        return "静止"          # 合加速度几乎不波动
    if f["dominant_hz"] >= t["dominant_hz"]:
        return "快跑"          # 步频显著更高
    if f["az_range"] >= t["az_range"]:
        return "上下楼梯"      # 垂直冲击更大
    return "平地慢走"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    pairs = demo_files() if a.demo else real_files()
    if not pairs:
        print("gait_raw/ 里还没有 CSV。按 DAILY_PLAN.md Day2 采集，或先加 --demo 试跑。")
        return 0

    feats, waves = [], {}
    for state, p in pairs:
        loaded = load_signal(p)
        if not loaded:
            print(f"  跳过 {p.name}（数据行不足）")
            continue
        xyz, rate, n = loaded
        wf = window_features(xyz, rate)
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
        core.save_svg(RESULTS / f"08_wave_{state}.svg", 680, 280,
                      core.line_chart(series, title=f"{state} · 三轴加速度波形（前 4 秒）",
                                      xlabel="时间 s", ylabel="加速度 g", width=680, height=280))
        print(f"  {state}: {n} 点 @ {rate} Hz -> {len(wf)} 个窗口，主频 {core.mean([f['dominant_hz'] for f in wf]):.2f} Hz")

    if not feats:
        print("没有提取到有效窗口")
        return 0
    core.write_csv(RESULTS / "08_features.csv", feats, FIELDS)

    # 特征对比柱状图
    cats = [s for s in STATES if any(f["state"] == s for f in feats)] or list({f["state"] for f in feats})
    dom = [core.mean([f["dominant_hz"] for f in feats if f["state"] == s]) for s in cats]
    core.save_svg(RESULTS / "08_feature_bars.svg", 680, 280,
                  core.bar_chart(cats, [round(v, 2) for v in dom],
                                 title="各姿态步态主频对比 Hz", ylabel="Hz", value_fmt="{:.2f}"))

    # 留出验证：奇偶窗口分开，避免拿同一段数据自测
    train = [f for i, f in enumerate(feats) if i % 2 == 0]
    test = [f for i, f in enumerate(feats) if i % 2 == 1]
    thr = calibrate(train) if train else dict(DEFAULT_THR)
    pairs_pred = [(f["state"], classify(f, thr)) for f in test]
    acc = core.accuracy(pairs_pred)
    m = core.confusion(pairs_pred, cats)
    core.save_svg(RESULTS / "08_confusion.svg", 680, 320,
                  core.heatmap(m, cats, cats, title="步态阈值规则 · 留出集混淆矩阵"))

    md = [
        "# 课题 08 · 步态阈值规则与验证", "",
        "> 由 `analyze_gait.py` 生成。当前为" + ("演示数据" if a.demo else "真实采集数据") + "。", "",
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
        f"elif dominant_hz >= {thr['dominant_hz']:.2f}:    快跑     # 步频显著更高",
        f"elif az_range >= {thr['az_range']:.2f}:           上下楼梯 # 垂直冲击更大",
        "else:                                   平地慢走",
        "```", "",
        f"当前阈值由**训练窗口自动标定**（取两类均值中点）：`svm_std={thr['svm_std']:.3f}`、"
        f"`dominant_hz={thr['dominant_hz']:.2f}`、`az_range={thr['az_range']:.2f}`；"
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
    (RESULTS / "08_threshold_rules.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"留出集准确率 {acc * 100:.1f}%")
    print("已输出 08_features.csv / 08_wave_*.svg / 08_feature_bars.svg / 08_confusion.svg / 08_threshold_rules.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
