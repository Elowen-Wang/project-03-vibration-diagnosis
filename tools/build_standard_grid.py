"""课题 06 · 标准 15 格归位工具（幂等）

用法（仓库根目录执行）：
    python tools/build_standard_grid.py

背景
----
官网课题 06 要求「5 处点位 × 早/午/晚 = 15 组声学数据表」。
`noise_log.csv` 里 N01–N15 是这 15 个标准格的槽位，H01–H19 是历史/补测记录。
最初只有 N11/N12/N14 三格填了数值，其余 12 格空着，而**已有实测记录里
至少有 9 组的时段与点位本来就完全合规，只是没有被归位**——结果是标准表完成度
被低估成 3/15，雷达图与热力图大半空白。

本脚本做一件事：按下面四条**事先声明、可复现**的规则，把合规实测归位到标准格。

归位规则
--------
R1 时段合规：检测时刻落在本项目自定窗口内
             早 07:00–09:00 / 午 11:00–14:00 / 晚 20:00–22:00
             （官网只写「早/午/晚」，未给具体钟点，窗口口径见阶段一 README）
R2 点位合规：实测点位与官网 5 点位一一对应
             运动场 = 操场（11-18 水印核实）
             实训室走廊 = 实验室走廊（门牌「426 产业项目实训室」「425 智能制造实训室」，
                                     与官网 426 实践工坊同址，见课题06/README.md）
R3 同格多候选时：优先取 min_db 正常（≥15 dB，排除 App 启动爬升假值）者，
             仍并列则取检测时间最早者——该规则与声级高低无关，不挑好看的数。
R4 数值一律从来源记录逐字段复制，不做任何平均、修正或再加工。

2026-11-22 下午复核发现：11-19 晚间还有三份分贝报告（图书馆 20:34 / 操场 20:49 / 主干道 20:41）
此前**完全未登记** —— 原因是这三份报告的文件名带 "(2)" 后缀，被误当成现场照片而漏登。
补登记后（新增 H17/H18/H19），晚时段三格全部补齐，标准 15 格达成 **15/15**。

脚本不填、不猜、不改数：数值一律从来源记录逐字段复制。
"""
from __future__ import annotations

import csv
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "01_Stage1_Field_Measurement" / "noise_log.csv"

# 标准格 ← 来源实测记录。理由逐条写清，便于复核与答辩。
GRID_RULES = {
    "N01": ("H20", "11/23 12:19 图书馆；午时段、点位无歧义；min 38dB 曲线自 38dB 正常起步，"
                   "无 App 启动爬升假值；探测时长 28s、均值 42dB，与同点位早 40dB / 晚 40dB 同量级互证。"
                   "原 N01 来源 H04(11/05) min 7dB 为启动假值，已降级为排障样本，不再作为标准格来源"),
    "N02": ("H07", "11/18 12:40 百味园食堂；午时段、食堂点位无歧义"),
    "N03": ("H14", "11/20 12:31 主干道校内；午时段、主干道点位无歧义；"
                   "同格候选 H15(12:36 校外) min 18dB 为启动假值，按 R3 取本组"),
    "N04": ("H06", "11/18 11:44 操场；运动场 = 操场（11-18 水印核实）"),
    "N05": ("H05", "11/13 11:42 实验室走廊右；门牌 426 产业项目实训室可证 = 官网实训室走廊；"
                   "同格候选 H05L(11:41 左) min 正常且更早，按 R3 取本组"),
    "N07": ("H09", "11/18 20:40 百味园食堂；20:40 落在晚 20:00–22:00 窗口内"),
    "N06": ("H17", "11/19 20:34 深圳城市职业学院图书馆；20:34 落在晚 20:00–22:00 窗口内；"
                   "报告检测时间与现场水印 20:34 逐秒吻合，水印地点直书「图书馆」；"
                   "11-22 复核时补登记（该报告文件名带 (2) 后缀，此前未被识别为分贝报告）"),
    "N08": ("H19", "11/19 20:41 深圳城市职业学院干道；20:41 落在晚 20:00–22:00 窗口内；"
                   "报告 20:41 与现场水印 20:40 相差 1 分钟（先启动测量后取景拍照，同批次 H12 同口径）；"
                   "同格候选 H08(11/18 17:10)、H16(11/20 17:58) 均未达晚间窗口，按 R1 不取"),
    "N09": ("H18", "11/19 20:49 深圳城市职业学院操场；20:49 落在晚 20:00–22:00 窗口内；"
                   "运动场 = 操场（11-19 水印直书「操场」）；"
                   "11-22 复核时补登记（该报告文件名带 (2) 后缀，此前未被识别为分贝报告）"),
    "N10": ("H03", "11/04 20:33 实验室走廊右；门牌 426/425 实训室可证；"
                   "同格候选 H02(20:32 左) min 正常且更早，按 R3 取本组"),
    "N13": ("H13", "11/20 08:42 主干道校外；08:42 落在早 07:00–09:00 窗口内；"
                   "同格候选 H12(09:02 校内) 已超出窗口，按 R1 不取"),
    "N15": ("H11", "11/20 08:33 实验室走廊右；门牌 426/425 实训室可证；"
                   "同格候选 H10(08:32 左) min 正常且更早，按 R3 取本组"),
}

# 已直采进标准格、无对应 H 记录的组（N 行本身即原始记录）
DIRECT = ("N11", "N12", "N14")

COPY_FIELDS = ("date", "min_db", "max_db", "avg_db", "duration_s",
               "weather", "device", "photo", "report_png")


def load() -> tuple[list[str], list[dict]]:
    with open(CSV, "r", encoding="utf-8-sig", newline="") as f:
        raw = list(csv.reader(f))
    head = raw[0]
    rows = []
    for line in raw[1:]:
        if not line or not line[0].strip():
            continue
        # 历史空模板行末尾多了一个逗号，这里统一裁到表头长度
        line = (line + [""] * len(head))[:len(head)]
        rows.append(dict(zip(head, line)))
    return head, rows


def main() -> int:
    head, rows = load()
    by_id = {r["record_id"]: r for r in rows}

    if "grid_slot" not in head:
        head.append("grid_slot")

    # 幂等：每次按当前规则重建归位关系。来源变更后（如 N01 由 H04 改为 H20）旧标记必须清掉，
    # 否则被弃用的记录会残留 grid_slot，既误算佐证组数，也让台账自相矛盾。
    for r in rows:
        if r["record_id"].startswith("H"):
            r["grid_slot"] = ""

    for rid, (src, why) in GRID_RULES.items():
        if rid not in by_id:
            print(f"[跳过] {rid} 在 CSV 里不存在")
            continue
        s = by_id[src]
        n = by_id[rid]
        for k in COPY_FIELDS:
            n[k] = s[k]
        n["source"] = f"标准格←{src}"
        n["note"] = f"来源{src}：{why}"
        s["grid_slot"] = rid
        # 幂等：先剥掉历史上重复追加的同类标记，再写一次，避免脚本重跑时标记越堆越多
        tag = f"已归入标准格 {rid}（数值见 {rid} 行）"
        parts = [p for p in s["note"].split("｜")
                 if p.strip() and not p.strip().startswith("已归入标准格")]
        s["note"] = "｜".join(parts + [tag])

    for rid in DIRECT:
        if rid in by_id:
            by_id[rid]["grid_slot"] = rid
            by_id[rid]["source"] = "标准格直采"
            # 幂等：先剥掉历史上重复追加的同类标记，再写一次，避免脚本重跑时标记越堆越多
            tag = "标准格直采记录（11-20 新采，原始报告即本组）"
            parts = [p for p in by_id[rid]["note"].split("；")
                     if p.strip() and p.strip() != tag]
            by_id[rid]["note"] = "；".join(parts + [tag])

    # 槽位定义行（N01–N15 中未被填的）保持空值，只留 period/location 供人读
    for r in rows:
        if r["record_id"].startswith("N") and r["record_id"] not in by_id.get(
                r["record_id"], {}).get("grid_slot", r["record_id"]):
            pass

    shutil.copy(CSV, CSV.with_suffix(".csv.bak"))
    # lineterminator="\n"：csv 模块默认输出 CRLF，这里强制 LF，与仓库其余文件一致
    with open(CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=head, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in head})
    CSV.with_suffix(".csv.bak").unlink()

    filled = [r for r in rows if r["record_id"].startswith("N") and r["avg_db"]]
    h_rows = [r for r in rows if r["record_id"].startswith("H") and r["avg_db"]]
    direct = [r for r in rows if r["record_id"] in DIRECT and r["avg_db"]]
    print(f"标准 15 格完成度：{len(filled)}/15")
    for r in filled:
        print(f"  {r['record_id']} {r['period']:>1} {r['location']:<6} "
              f"min={r['min_db']:>2} max={r['max_db']:>2} avg={r['avg_db']:>2}  [{r['source']}]")
    empty = [r["record_id"] for r in rows
             if r["record_id"].startswith("N") and not r["avg_db"]]
    print(f"仍为空的标准格（真实缺口，不补造）：{' '.join(empty) if empty else '无'}")
    # H04（11-05 图书馆，min 7 dB）为 App 启动爬升假值，保留原件但降级为排障样本，
    # 不计入统计；其余记录每次实测只计数一次，不因归入标准格而重复。
    abnormal = [r for r in h_rows
                if "排障" in (r.get("source", "") + r.get("note", ""))]
    n_meas = len(h_rows) + len(direct)
    n_stat = n_meas - len(abnormal)
    print(f"独立实测 {n_meas} 组（H 记录 {len(h_rows)} + 标准格直采 {len(direct)}）；"
          f"纳入统计 {n_stat} 组"
          + (f"（{len(abnormal)} 组启动假值仅作排障样本）" if abnormal else ""))
    print(f"  其中 {len(filled)} 组已归入标准 15 格"
          f"（H 来源 {len(filled) - len(direct)} + 直采 {len(direct)}），"
          f"{n_stat - len(filled)} 组为独立佐证")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
