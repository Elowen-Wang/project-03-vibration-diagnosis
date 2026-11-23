"""生成本仓库的每日 README 模板、历史补记、实验登记表与工况定义模板。

用法（仓库根目录）：python tools\\make_templates.py
已有文件默认不覆盖，避免抹掉你写过的日志；要重置加 --force。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import signal_core as core  # noqa: E402

DAYS = [
    ("2026-11-13", "周五", 1, "搭环境 + 课题06 补测第一批",
     ["装 Python（勾 PATH）、VS Code、GitHub Desktop；手机装 Phyphox（官网 APK）",
      "跑 python tools\\signal_core.py 自检通过",
      "课题06 午间 5 组、晚间 5 组补测，导出分贝报告 PNG + 现场同框 JPG",
      "把已有 4 组报告数值核对进 noise_log.csv"],
     ["10 份分贝 PNG + 10 张现场 JPG", "noise_log.csv 前 14 行", "process_logs/2026-11-13.md", "1 次 commit"],
     "2026-11-13 补测课题06午晚共10组，录入分贝报告"),
    ("2026-11-14", "周六", 2, "课题06 收尾 + 课题08 采集",
     ["课题06 早间 5 组补测；重测 11-05 的 7dB 异常组",
      "跑 analyze_noise.py 出雷达图与光效逻辑",
      "Phyphox 采集 4 姿态 × 3 次 × ≥12 秒，导出 12 份 CSV 到 gait_raw/",
      "每种姿态拍 1 张现场照"],
     ["15 组噪声数据齐 + 1 份重测", "12 份 gait CSV + 4 张 JPG", "课题06 的 4 个分析产物", "process_logs/2026-11-14.md"],
     "2026-11-14 课题06补齐15组并出图，课题08完成12份步态采集"),
    ("2026-11-15", "周日", 3, "阶段一两课题定稿",
     ["跑 analyze_gait.py 出波形图、特征表、混淆矩阵、阈值规则",
      "写完整 01-Field-Discovery/README.md",
      "主 README 进度表把raw_data/acoustic/08 两行打勾"],
     ["阶段一完整报告", "08_* 系列分析产物", "process_logs/2026-11-15.md"],
     "2026-11-15 阶段一两课题报告定稿，含异常值归因与阈值验证"),
    ("2026-11-16", "周一", 4, "项目三真实 WAV 特征提取",
     ["跑 analyze_real_wav.py --extract，拿到 75 行 features.csv 与频谱对比图",
      "写 protocol.md：5 工况可复现定义",
      "补写 11/01、11/04、11/05、11/06 历史日志（注明事后补记）",
      "核对 experiment_log.csv 75 行"],
     ["results/features.csv（75 行）", "results/spectrum_compare.svg", "protocol.md", "4 份历史补记", "experiment_log.csv"],
     "2026-11-16 真实WAV特征提取跑通，补全工况定义与历史过程日志"),
    ("2026-11-17", "周二", 5, "分类 + 盲测 + 补加速度",
     ["跑 --classify（留一法）与 --blind（1–12 训练 / 13–15 盲测）",
      "Phyphox 补采 5 工况 × 3 段加速度 CSV 到 accel_raw/，拍固定方式照",
      "跑 --accel 合并声振双通道特征",
      "把三个准确率写进阶段二 README"],
     ["results/loo_report.md / blind_report.md / confusion SVG", "15 份加速度 CSV", "accel_features.csv"],
     "2026-11-17 完成声振双通道特征、留一法分类与13-15号盲测"),
    ("2026-11-18", "周三", 6, "抗噪实验 + 跨日 held-out 盲测",
     ["跑 --noise 出抗噪曲线与报告",
      "当天重新录 5 工况 × 3 段 = 15 段全新 WAV 到 blind_test/",
      "拍带时间水印现场照，转 WAV 并核对格式",
      "跑 --heldout，录 5 段盲测演示视频"],
     ["results/noise_robustness.md / .svg", "blind_test/ 15 个 WAV + 1 张照", "results/heldout_report.md", "5 段 MP4"],
     "2026-11-18 抗噪曲线完成，当天新采15段held-out盲测及演示视频"),
    ("2026-11-19", "周四", 7, "报告定稿 + AI 记录 + 主 README 收尾",
     ["阶段二 README 八个章节全部写完，逐项打勾",
      "补 AI_Chat_Log.md 至少 5 条真实问答（含我改了什么、验证结果）",
      "主 README 补复现步骤、评分对照表、诚信声明",
      "理顺 D1/D2/D3 日志结构，内容一字不删"],
     ["02-20Days-Challenge/README.md 定稿", "AI_Chat_Log.md", "根 README.md 定稿"],
     "2026-11-19 全部报告定稿，AI协作记录与诚信声明补齐"),
    ("2026-11-20", "周五", 8, "自检 + 面试演练 + 最终推送",
     ["跑 --check，确认无 MISSING",
      "对照主 README 评分对照表逐项打勾",
      "12 分钟面试 6 题自问自答演练",
      "GitHub 网页检查文件与图片可见，最后一次 Push"],
     ["--check 全 OK", "6 题面试提纲能讲 90 秒", "process_logs/2026-11-20.md", "最终 commit"],
     "2026-11-20 全部材料交付完成，自检通过"),
]

HISTORY = [
    ("2026-11-01", "项目三预实验与声级交叉测量",
     ["用分贝仪 App 记录三种工况的环境声级：低速 47/58/52 dB、高速 43/62/57 dB、受阻 44/72/61 dB（最小/最大/平均）",
      "报告时间为 16:49 / 16:50 / 16:55，地点位于校内西北约 252–254 米",
      "结论：平均声级随低速→高速→受阻递增（52→57→61 dB），可作为独立于 FFT 的物理交叉佐证"],
     "低速.png / 高速.png / 受阻.png 三份分贝测试报告"),
    ("2026-11-04", "课题06 首轮实地测量 + 项目三 D1 采集",
     ["图书馆一楼 17:46：36 / 54 / 41 dB（最小/最大/平均）",
      "实验室走廊左 20:32：35 / 46 / 39 dB；右 20:33：35 / 44 / 38 dB",
      "项目三用 OPPO Reno 15 麦克风、距离 3–5 cm，采集 low / high / friction 各 15 组 10 秒音频",
      "踩坑：应用商店搜不到 Phyphox 只有广告 → 先用手机原生录音机保住核心数据；NCH Switch 弹付费 → 改用免费在线转换"],
     "01-Field-Discovery 的 3 组 JPG/PNG/MP4；02 目录 day1.jpg 等现场照"),
    ("2026-11-05", "课题06 第二轮 + 项目三 D2",
     ["图书馆一楼 11:50：7 / 53 / 41 dB",
      "⚠️ 最小 7 dB 是异常值：曲线从约 6 dB 起步，判断为 App 启动瞬间麦克风尚未稳定的爬升假值，保留原始记录并安排重测",
      "项目三继续采集与 MP3→WAV 格式统一"],
     "11-5中午图书馆一楼 一组 JPG/PNG/MP4；day2.jpg"),
    ("2026-11-06", "项目三 D3：补齐剩余两种工况",
     ["补充遮挡 block 与失衡 imbalance 各 15 组音频，至此 5 工况 × 15 = 75 组齐全",
      "反直觉发现：失衡工况在风扇低电量时震动异常强烈，满电拔出充电线后同倾角震动反而减弱",
      "初步归因：低电量转速下降恰与底座固有频率重合引发共振；满电扭矩大可克服偏心；重新垫书存在毫米级支点位移",
      "价值：同一工况内自然包含强震/弱震两类样本，提升数据多样性与模型泛化"],
     "block-15/ 与 imbalance-15/ 共 30 段 WAV；阶段二 README 的 D3 记录"),
]


def daily_md(date, week, n, title, goals, outputs, commit):
    g = "\n".join(f"- [ ] {x}" for x in goals)
    o = "\n".join(f"| {x} | | ⬜ |" for x in outputs)
    return f"""# {date}（{week}）· Day {n} · {title}

> **状态**：⬜ 未开始 ／ 🟡 进行中 ／ ✅ 已完成　（收工时把这一个改成 ✅，另两个删掉）
> **天气**：________　**设备**：OPPO Reno 15 ＋ 分贝仪噪音检测 PLW110 ＋ Phyphox
> **工作时段**：____:____ – ____:____　**地点**：________

## 今日目标（来自 DAILY_PLAN.md Day {n}）
{g}

## 今日实际完成
- [ ]
- [ ]

## 产出文件
| 文件 / 目录 | 说明 | 已 push |
|---|---|---|
{o}

## 踩坑与排障（Debug Log）
| 现象 | 我判断的原因 | 怎么解决的 | 怎么验证解决了 |
|---|---|---|---|
| | | | |

## 数据 / 参数记录
- 采样参数：________
- 手机固定位置与距离：________
- 当天异常数据及处理：________
- 和昨天相比改了什么、为什么：________

## 今日 Git 提交
```
{commit}
```

## 收工验收
- [ ] 上面「状态 / 天气 / 时段 / 地点」都填了
- [ ] 「今日实际完成」与「产出文件」都填了，没做的如实留空并写明原因
- [ ] GitHub Desktop 已 Commit **并** Push origin
- [ ] 主 README.md 的进度表对应格子改成 ✅

## 明日准备
-
"""


def history_md(date, title, items, evidence):
    body = "\n".join(f"- {x}" for x in items)
    return f"""# {date} · {title}

> ⚠️ **本文件为 {date} 的事后补记**，补记于 2026-11-16（Day 4）。
> 内容依据当时留存的分贝测试报告时间戳、现场照片/视频与 Git 提交历史还原，
> 未添加任何当时不存在的测量结果。可核对的原始证据列在文末。

## 当日记录
{body}

## 原始证据
- {evidence}

## 补记说明
- 补记人：王宇婷（学号 2027094）
- 还原依据：分贝测试报告 PNG 上的检测时间/GPS、现场 JPG 与 MP4、Git 提交时间
- 未能还原的字段（天气、具体设备朝向等）留空，不做推测填写
"""


def git_first_add_dates():
    """一次性解析 git log，得到每个文件首次加入仓库的日期。"""
    mapping = {}
    try:
        r = subprocess.run(
            ["git", "log", "--diff-filter=A", "--name-only",
             "--format=@@%ad", "--date=short"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        cur = ""
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("@@"):
                cur = line[2:].strip()
            elif line and cur:
                mapping[line] = cur
    except Exception as e:
        print("  git 历史解析失败，日期列留待核对：", e)
    return mapping


def make_experiment_log():
    import wave
    dates = git_first_add_dates()
    cond = {"low": "正常低速", "high": "正常高速", "friction": "摩擦异常",
            "block": "进风遮挡", "imbalance": "扇叶失衡"}
    rows = []
    for key, label in cond.items():
        for i in range(1, 16):
            rel = f"02-20Days-Challenge/{key}-15/{key}-{i}.wav"
            p = ROOT / rel
            dur, rate, ch, sw = "", "", "", ""
            if p.exists():
                try:
                    with wave.open(str(p), "rb") as w:
                        rate, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth() * 8
                        dur = round(w.getnframes() / w.getframerate(), 2)
                except Exception:
                    pass
            rows.append({
                "sample_id": f"{key}-{i:02d}", "condition": key, "condition_cn": label,
                "file": f"{key}-15/{key}-{i}.wav",
                "date_recorded": dates.get(rel, "待核对"),
                "duration_s": dur, "sample_rate": rate, "channels": ch, "bit_depth": sw,
                "mic_distance_cm": "3-5", "device": "OPPO Reno 15 内置麦克风",
                "photo": "", "note": "日期取自 git 首次提交时间，如与拍摄时间不符请照实修正",
            })
    out = ROOT / "02-20Days-Challenge" / "experiment_log.csv"
    core.write_csv(out, rows)
    known = sum(1 for r in rows if r["date_recorded"] != "待核对")
    print(f"experiment_log.csv：75 行，其中 {known} 行日期已从 git 历史还原")


def make_protocol():
    p = ROOT / "02-20Days-Challenge" / "protocol.md"
    if p.exists() and not ARGS.force:
        return
    p.write_text("""# 项目三 · 五种工况可复现定义（Day 4 核对填写）

> 面试「项目真实性与过程数据溯源」会追问：你这 5 种工况到底怎么造出来的？
> 别人照这份文档能不能复现？把下面的空格填具体，别写"稍微挡一下""有点失衡"这种模糊描述。

## 通用采样设置（所有工况必须一致）

| 项 | 值 | 备注 |
|---|---|---|
| 设备 | OPPO Reno 15 内置麦克风 | 全程同一台手机，不换 |
| 麦克风距声源 | 3–5 cm | 实测值：____ cm |
| 手机固定方式 | | 手持 / 支架 / 胶带贴底座，写清楚 |
| 录音 App | 手机原生录音机 → MP3 → WAV | 转换工具：____ |
| WAV 格式 | 48 000 Hz / 双声道 / 16 bit / 约 11 s | 已用脚本核验 75 段全部一致 |
| 每组时长 | 10 s | |
| 采样环境 | | 室内/是否有他人说话、空调、背景音乐 |
| 分析取段 | 每段取中间 2 s，双声道取均值，降采样至 4000 Hz | `analyze_real_wav.py` 固定逻辑 |

> ⚠️ MP3 是有损格式，转成 WAV **不会恢复已丢失的高频**，只是换成不压缩的容器。
> 报告中如实写明这一点，不要写成"转换为无损音质"。

## 五种工况

| 编号 | 目录 | 中文 | 怎么造出来（填具体参数） | 照片/视频 |
|---|---|---|---|---|
| W1 | `low-15/` | 正常低速 | 风扇 ____ 档、无遮挡、无外加配重 | `低速.png` / `低速10s.mp4` |
| W2 | `high-15/` | 正常高速 | 风扇 ____ 档、其余同 W1 | `高速.png` / `高速10s.mp4` |
| W3 | `friction-15/` | 摩擦异常 | 用 ____ 轻触 ____ 部位，持续/间歇：____ | day1.jpg |
| W4 | `block-15/` | 进风遮挡 | 用 ____ 遮挡进风口约 ____%，遮挡面积 ____ cm² | `受阻.png` / `受阻10s.mp4` |
| W5 | `imbalance-15/` | 扇叶失衡 | 在扇叶 ____ 位置贴 ____ g 配重（胶带/橡皮泥），或底座垫 ____ mm | day2.jpg |

### W5 特别说明（已有的反直觉发现，写进报告）
- 低电量时震动明显强于满电，已记录于原 D3 日志。
- 三条候选归因：① 转速下降与底座固有频率重合引发共振；② 满电扭矩大可克服偏心；③ 重新垫书导致支点毫米级位移。
- **诚实写法**：这是观察 + 假设，没有做转速实测，所以不宣称"已证实共振"；
  若要证实，需补采一段转速（可用 Phyphox 麦克风主频估计）与电量对照，写在「局限」里。

## 安全
- 只在**断电状态**下贴配重、垫书、改变摆位；通电后不再触碰扇叶。
- 手机与风扇保持固定距离，远离水源；不要用金属物靠近进风口。
- 每次改变工况前先停机，等扇叶完全静止。

## 数据划分（防止自测）
- 训练：每工况 **1–12 号**（60 段）
- 同批次盲测：每工况 **13–15 号**（15 段）
- 跨日 held-out：**11/18 当天重新采集** 15 段，存 `blind_test/`，完全不参与任何训练与调参
- 留一法交叉验证：75 段每次留 1 段
""", encoding="utf-8")
    print("protocol.md 已生成")


def main():
    logs = ROOT / "process_logs"
    logs.mkdir(exist_ok=True)
    for date, week, n, title, goals, outputs, commit in DAYS:
        p = logs / f"{date}.md"
        if p.exists() and not ARGS.force:
            print(f"  跳过（已存在）{p.name}")
            continue
        p.write_text(daily_md(date, week, n, title, goals, outputs, commit), encoding="utf-8")
        print(f"  生成 {p.name}")
    for date, title, items, evidence in HISTORY:
        p = logs / f"{date}.md"
        if p.exists() and not ARGS.force:
            print(f"  跳过（已存在）{p.name}")
            continue
        p.write_text(history_md(date, title, items, evidence), encoding="utf-8")
        print(f"  生成 {p.name}（历史补记）")
    idx = logs / "README.md"
    if not idx.exists() or ARGS.force:
        idx.write_text("""# process_logs · 每日过程证据

官网要求「跨多日连续过程数据（process_logs/）」，并明确以 GitHub 提交历史核验真实性。
本目录每天一份 README，**当天写、当天提交**，是 60 分工坊挑战里最容易被忽视、也最能防"摆拍"质疑的部分。

| 文件 | 说明 |
|---|---|
| `2026-11-13.md` ~ `2026-11-20.md` | 8 天正式每日日志（模板已生成，逐日填写） |
| `2026-11-01.md` / `11-04.md` / `11-05.md` / `11-06.md` | 已发生日期的**事后补记**，依据分贝报告时间戳、照片与 Git 历史还原，均已在文内注明"事后补记" |

## 写日志的三条规矩
1. 没做完就如实留空，写清楚卡在哪、明天怎么补；**不要补写没发生的事**。
2. 异常数据（比如 11-05 的 7 dB）保留原值 + 标注原因 + 安排重测，不删不改。
3. 每天至少一次 commit，说明里带日期和当天实际动作，不写 "update"。
""", encoding="utf-8")
        print("  生成 process_logs/README.md")
    make_experiment_log()
    make_protocol()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="覆盖已存在的模板（会抹掉已填内容，慎用）")
    ARGS = ap.parse_args()
    raise SystemExit(main())
