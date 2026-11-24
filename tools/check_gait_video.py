"""课题 08 · 录屏与 CSV 的配对验收（零第三方依赖）

用法（仓库根目录执行）：
    python tools/check_gait_video.py

逐组读取 raw_data/gait/<姿态>/ 下的 MP4 与 CSV：
  - 视频时长取自 MP4 的 mvhd（timescale / duration），与播放器显示一致；
  - 编码与分辨率取自 stsd 的 avc1 / hvc1 样本描述；
  - CSV 时长取首末 `Time (s)`。
判三条：CSV 有效时长 ≥ 12 s；视频与 CSV 时长差 ≤ 2 s；编码为 H.264 或 HEVC
（HEVC 可作本地证据，但不能直接嵌网页播放）。

不修改任何原始文件，只打印表格；重录后重跑一次即可知道是否达标。
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAIT = ROOT / "01-Field-Discovery" / "raw_data" / "gait"
sys.path.insert(0, str(ROOT / "tools"))
import signal_core as core  # noqa: E402

MIN_CSV_S = 12.0     # 与 analyze_gait.py 的 SHORT_RUN_MIN_S 保持一致
MAX_DIFF_S = 2.5     # 录屏与采集独立起停，2.5 s 内视为同步（含手动起停延迟）
GOOD_CODEC = {"avc1": "H.264", "hvc1": "HEVC", "hev1": "HEVC"}


def boxes(data, start, end):
    i = start
    while i + 8 <= end:
        size = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        if size == 1:
            size = struct.unpack(">Q", data[i + 8:i + 16])[0]
        if size < 8:
            break
        yield typ, i, min(i + size, end)
        i += size


def walk(data, start, end, want):
    for typ, s, e in boxes(data, start, end):
        if typ in want:
            yield typ, s, e
        if typ in (b"moov", b"trak", b"mdia", b"minf", b"stbl"):
            yield from walk(data, s + 8, e, want)
        elif typ == b"stsd":
            # stsd 头 8 字节（size+type）+ version/flags 4 + entry_count 4
            yield from walk(data, s + 16, e, want)


def mp4_info(path):
    data = path.read_bytes()
    info = {}
    for typ, s, e in walk(data, 0, len(data), {b"mvhd", b"avc1", b"hvc1", b"hev1"}):
        body = s + 8
        if typ == b"mvhd" and "dur" not in info:
            ver = data[body]
            if ver == 0:
                ts, dur = struct.unpack(">II", data[body + 12:body + 20])
            else:
                ts, dur = struct.unpack(">IQ", data[body + 20:body + 32])
            info["dur"] = dur / ts if ts else 0.0
        elif typ.decode() in GOOD_CODEC and "codec" not in info:
            info["codec"] = typ.decode()
            # VisualSampleEntry: 保留位之后第 24 字节起是 width / height
            info["w"], info["h"] = struct.unpack(">HH", data[body + 24:body + 28])
    return info


def csv_span(path):
    rows = core.read_csv(path)
    ts = [core.fnum(r.get("Time (s)") or list(r.values())[0]) for r in rows]
    ts = [t for t in ts if t is not None]
    return (max(ts) - min(ts)) if ts else 0.0


def main():
    if not GAIT.exists():
        print(f"找不到 {GAIT}")
        return 0
    print(f"{'姿态':<12}{'视频':<24}{'视频s':>7}{'CSV s':>7}{'差s':>7}  {'分辨率':<11}{'编码':<6}判定")
    bad = 0
    for d in sorted(p for p in GAIT.iterdir() if p.is_dir()):
        mp4s = sorted(d.glob("*.mp4"))
        csvs = sorted(p for p in d.glob("*.csv") if p.name not in ("device.csv", "time.csv"))
        if not mp4s or not csvs:
            print(f"{d.name:<12}{'缺少 MP4 或 CSV':<24}")
            bad += 1
            continue
        v, c = mp4s[0], csvs[0]
        info = mp4_info(v)
        span = csv_span(c)
        diff = info.get("dur", 0.0) - span
        problems = []
        if span < MIN_CSV_S:
            problems.append(f"数据仅 {span:.1f}s（<{MIN_CSV_S:.0f}s）")
        if abs(diff) > MAX_DIFF_S:
            problems.append(f"时长差 {diff:+.1f}s（>{MAX_DIFF_S:.0f}s）")
        if info.get("codec") not in GOOD_CODEC:
            problems.append("编码未知")
        verdict = "通过" if not problems else "需重录：" + "；".join(problems)
        bad += bool(problems)
        print(f"{d.name:<12}{v.name[:22]:<24}{info.get('dur', 0.0):>7.2f}{span:>7.2f}"
              f"{diff:>+7.2f}  {str(info.get('w', '?')) + 'x' + str(info.get('h', '?')):<11}"
              f"{GOOD_CODEC.get(info.get('codec', ''), '?'):<6}{verdict}")
    print(f"\n{len([p for p in GAIT.iterdir() if p.is_dir()])} 组，需重录 {bad} 组。"
          f"判定口径：CSV ≥{MIN_CSV_S:.0f}s、视频与数据差 ≤{MAX_DIFF_S:.1f}s。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
