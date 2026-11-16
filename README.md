# 智能·创造者 创新实验班（ICEC）· 2026 级选拔过程数据

**学号**：2027094　**姓名**：王宇婷　**层次**：2026 级高职 · 人工智能专业
**仓库**：`Elowen-Wang/project-03-vibration-diagnosis`
**交付目标**：2026-11-20 前完成（官网 11/24 封仓，留 4 天缓冲）
**最后更新**：2026-11-16（Day 4 收工）

---

## 一、选题说明

| 阶段 | 选题 | 分值 | 状态（11/16） |
|---|---|---|---|
| 第一阶段 · 基础素养实地测评（10 选 2） | **课题 06** 校园昼夜声学噪声地图测绘 | 20 分（两题合计） | 🟡 5 组报告（含 1 组异常、1 组 11/13 补测）；标准 15 组仍 0/15 |
| 第一阶段 · 基础素养实地测评 | **课题 08** 多姿态步态加速度特征采集与对比 | 同上 | 🟡 **5 组真实 CSV + 录屏 + meta 已采到**；波形图/特征表/阈值规则已出；快跑组判定无效待重采 |
| 第二阶段 · 工坊开放式项目挑战（8 选 1） | **项目三** 手机传感器异常声振诊断仪 | 60 分 | 🟡 75 段 WAV + 全套分析已跑通；缺 held-out、加速度通道、盲测视频 |

> 三个选题是一条递进的能力链：**课题 06 练声学采集与阈值 → 课题 08 练加速度波形与特征 → 项目三做声振融合与工况分类**。
> 前两题的采集经验、数据格式和代码都直接复用到项目三，避免重复造轮子。

## 二、作品集导航

1. [第一阶段总报告](./01_Stage1_Field_Measurement/README.md) — 课题 06 / 08
   - [课题 06 原始材料与分贝报告](./01_Stage1_Field_Measurement/课题06/README.md)
   - [课题 08 数据字典与逐组核对](./01_Stage1_Field_Measurement/课题08/README.md)
2. [第二阶段项目三完整报告](./02_Stage2_Project_Vibration/README.md) — [工况定义](./02_Stage2_Project_Vibration/protocol.md)｜[实验登记表](./02_Stage2_Project_Vibration/experiment_log.csv)
3. [AI 使用报告 · 截图与核对证据](./AI使用报告/README.md) — 内含 [课题08核对报告 HTML](./AI使用报告/第一阶段/课题08核对报告.html)
4. [AI 提问与排障文字索引](./AI_Chat_Log.md)
5. [每日过程日志 process_logs](./process_logs/README.md) — 12 份
6. [11/13 → 11/20 每日任务表](./DAILY_PLAN.md) — 含软件/APP 下载清单与剩余 4 天重排

## 三、进度看板

> ✅ 只标**有文件可核验**的项；日志没填、数据没采的格子保持 ⬜/🟡，不代为打勾。

| 任务 | 11/13 | 11/14 | 11/15 | 11/16 | 11/17 | 11/18 | 11/19 | 11/20 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 环境与 APP 搭建（Python / Phyphox） | 🟡 | | | ✅ | | | | |
| 课题 06：15 组标准噪声数据 | ⬜ | ⬜ | | 🟡 仅 1 组补测 | | | | |
| 课题 06：雷达图 / 光效逻辑 | | | | ✅ 逻辑已完成 | | | | |
| 课题 08：姿态采集与阈值 | | | | ✅ 5 组已采，快跑无效 | | | | |
| 项目三：75 段真实 WAV 特征 | | | | ✅ | | | | |
| 项目三：留一法 / 盲测准确率 | | | | ✅ | | | | |
| 项目三：加速度通道 / 抗噪 / held-out | | | | ✅ 抗噪(11/13跑通) | ⬜ | ⬜ | | |
| AI 证据链 / 数据核对报告 | | | | ✅ | | | | |
| 全部 README 与 AI 记录定稿 | | | | 🟡 本次补充 | | | ⬜ | |
| 自检 + 面试演练 + 最终 push | | | | | | | | ⬜ |

## 四、11/16 状态快照

**已完成（有文件）**
- 课题 08：5 组 Phyphox 原始 CSV + 5 段录屏 + `meta/{device,time}.csv`，采集时段 17:02–17:16；并做了 [传感器 ↔ 视频核对报告](./AI使用报告/第一阶段/课题08核对报告.html)。
- 课题 08 分析：`analyze_gait.py` 已能直接读 `课题08/` 真实数据，产出波形图、特征表、混淆矩阵、阈值规则。
- 课题 06：11/13 中午补测 1 份分贝报告（55/66/59 dB）+ 现场水印照，已录入 [`noise_log.csv`](./01_Stage1_Field_Measurement/noise_log.csv) 为 H05。
- 素材按课题重组到 `课题06/`、`课题08/`，新增 `AI使用报告/` 三阶段截图。
- 项目三：`results/` 下 8 个分析产物齐全，抗噪曲线已跑通。

**未完成（照实列）**
- 课题 06 标准 15 组数值 **0/15**；H04 的 7 dB 异常重测 `R01` 未做。
- 课题 08「快跑」有效数据待重采；每类目前只有 1 次，未达计划的 3 次。
- 项目三：`accel_raw/` 加速度通道、`blind_test/` 跨日 held-out 15 段、5 段盲测视频均未做。
- `process_logs/2026-11-13.md` ~ `11-15.md` 仍是空模板，`11-16.md` 已按可核验事实补写。

**风险**：距离 11/20 只剩 4 天，优先级是「重采快跑 + 15 组噪声 + held-out 15 段」这三件必须真人到场的事；文字材料可以最后两天集中补。

## 五、目录结构（11/16 实际）

```
project-03-vibration-diagnosis/
├── README.md · DAILY_PLAN.md · AI_Chat_Log.md
├── AI使用报告/                   README + 三阶段截图 + 课题08核对报告.html
├── process_logs/                 8 份正式日志 + 4 份历史补记 + README
├── tools/                        signal_core.py（零依赖内核）· make_templates.py
├── 01_Stage1_Field_Measurement/
│   ├── README.md · noise_log.csv
│   ├── analyze_noise.py · analyze_gait.py
│   ├── 课题06/                   README + 5 份分贝报告 PNG + 现场 JPG/MP4
│   ├── 课题08/                   README + 5 组 CSV/MP4/meta
│   ├── gait_raw/                 空（兼容早期 flat 目录计划）
│   └── results/                  06_* 与 08_* 图表、报告；_demo/ 为合成演示产物
└── 02_Stage2_Project_Vibration/
    ├── README.md · protocol.md · experiment_log.csv（75 行）
    ├── analyze_real_wav.py      真实 WAV 分析主脚本
    ├── fft_feature_extraction.py 早期模拟数据演示框架（不作交付依据）
    ├── low-15/ high-15/ friction-15/ block-15/ imbalance-15/   75 段 WAV
    ├── blind_test/               空，Day 6 当日新采
    ├── results/                  features.csv / 频谱图 / 三份报告 / 抗噪曲线
    └── *.png · *.mp4 · day*.jpg  分贝报告、演示视频、现场照
```

## 六、快速复现（零第三方依赖）

装好 Python 3.12+ 后，在仓库根目录依次执行：

```bat
cd /d C:\Users\wangy\Desktop\project-03-vibration-diagnosis
python tools\signal_core.py
python 01_Stage1_Field_Measurement\analyze_noise.py
python 01_Stage1_Field_Measurement\analyze_gait.py
python 02_Stage2_Project_Vibration\analyze_real_wav.py --all
python 02_Stage2_Project_Vibration\analyze_real_wav.py --check
```

> 全部脚本只用 Python 标准库（csv / wave / struct / math / cmath），**不需要 pip install numpy、scipy 或 matplotlib**。
> 图表输出 SVG，GitHub 原生渲染。
> `analyze_gait.py --demo` 的合成产物**只写 `results/_demo/`**，不会覆盖真实结论，也绝不能写进报告。
> 旧的 `fft_feature_extraction.py` 依赖 numpy/scipy/matplotlib 且跑的是 `np.sin` 模拟正弦波，保留仅为记录早期探索，**不作为交付依据**。

## 七、官网评分对照

**第二阶段 60 分**

| 官网要求 | 对应文件 | 状态 |
|---|---|---|
| ① 5 工况 × 15 组原始 WAV/CSV 及实验照（20 分） | `*-15/` 75 段 WAV、`experiment_log.csv`、`day*.jpg`、`*.png`、`*.mp4` | ✅ 数据齐，登记表照片列待补 |
| ② 时域/频域特征提取代码（20 分） | `analyze_real_wav.py`、`tools/signal_core.py`、`results/features.csv`、`spectrum_compare.svg` | ✅ 已跑通 75 段 |
| ③ 盲测准确率视频与抗噪报告（20 分） | `results/loo_report.md`、`blind_report.md`、`noise_robustness.md`、`heldout_report.md`、`blind_test/*.mp4` | 🟡 前三项完成，held-out 数据与视频待 Day 6 |
| 跨多日连续过程数据 | `process_logs/` 12 份、Git 提交历史、`AI使用报告/` | 🟡 模板与历史补记已建，逐日填写待本人完成 |
| `03-AI-Collaboration` | `AI使用报告/` 79 张 JPG + 1 份 HTML 核对报告 + `AI_Chat_Log.md` | 🟡 截图齐，文字索引待 Day 7 补逐条记录 |

**第一阶段 20 分**：`noise_log.csv`（15 组待填）、`results/06_*`、`课题08/` 5 组 CSV、`results/08_*`、`AI使用报告/第一阶段/课题08核对报告.html`。

## 八、当前关键结果（真实数据，非模拟）

| 指标 | 数值 | 来源 |
|---|---|---|
| 项目三 WAV 总段数 | 75（5 工况 × 15），48 kHz / 双声道 / 16 bit / 约 10.4–11.9 s | 脚本核验 |
| 留一法交叉验证准确率 | **89.3%**（75 段） | `results/loo_report.md` |
| 同批次盲测准确率 | **80.0%**（1–12 训练 / 13–15 盲测） | `results/blind_report.md` |
| 各工况主频 | 低速 97–100、高速 154、摩擦 120、遮挡 147、失衡 151 Hz | `results/features.csv` |
| 抗噪鲁棒性 | SNR 30 dB 88% → 10 dB 80% → 5 dB 64% → 0 dB 48% | `results/noise_robustness.md` |
| 声级交叉佐证 | 低速 52 → 高速 57 → 受阻 61 dB（平均分贝，11/01） | 3 份分贝报告 |
| 课题 06 分贝报告 | 5 组（36–59 dB 平均），含 1 组 7 dB 异常、1 组 11/13 补测 | `课题06/` |
| 课题 08 采集 | 5 组 · 100 Hz · Linear Acceleration (m/s²) · iPhone17,2 + phyphox 1.2.1 | `课题08/*/meta/` |
| 课题 08 流程验证 | 37 个有效 2 s 窗口，留出集 **50.0%**（裁尾前 40.0%），仅 3 类 | `results/08_threshold_rules.md` |

> 项目三留一法 89.3% 高于盲测 80.0% 是正常且健康的：按编号切分后 13–15 号与训练段存在分布差异，
> 这正是 Day 6 要**换一天重新采 15 段**做 held-out 的原因，不能只报好看的那个数。
>
> 课题 08 的 50.0% **不是最终结论**：4 类里「快跑」有效样本待重采，当前只剩 3 类，且平地慢走与上下楼梯的
> `az_range`（8.68 vs 8.26）、`svm_std`（2.70 vs 3.30）高度重叠。官网对第一阶段要的是
> 「原始 CSV + 波形图 + 可解释阈值规则 + 现场证据」，并不要求高准确率；把分不开的原因讲清楚比刷分重要。

## 九、诚信声明

- **设备如实分列**：课题 06 与项目三的声学/照片用 **OPPO Reno 15**（分贝仪 PLW110、原生录音机）；课题 08 的步态数据用 **iPhone17,2 + phyphox 1.2.1**。不统一写成「全部由一台设备采集」。
- 所有原始音频、照片、视频均为本人在真实环境采集，未使用合成数据充当实测结果。
- **课题 08「快跑」组经核对判定无效**：原始 CSV / MP4 / meta 全部保留不删，分析脚本默认排除并打印依据，安排重采；不静默剔除、不改数。
- 依据 [核对报告](./AI使用报告/第一阶段/课题08核对报告.html) 建议裁掉采集末尾的低活动窗口，裁掉数量在 `08_threshold_rules.md` 里逐文件列出，可复现。
- `analyze_gait.py --demo` 的合成 CSV 与图表隔离在 `results/_demo/`，**不计入任何报告结论**；`fft_feature_extraction.py` 中的正弦波为早期演示框架，不参与结果计算。
- MP3 → WAV 只是更换容器，**不恢复有损压缩已丢失的高频**，报告中如实说明，不宣称「无损音质」。
- 11-05 分贝报告中的最小 7 dB 判定为 App 启动爬升假值，**保留原始记录 + 标注归因 + 安排重测**，不删除、不静默改数。
- 11/13 补测的 59 dB 与 11/04 同点位 38 dB 差约 20 dB，**目前无对照实验，不写成昼夜规律**，已标注待核对。
- 事后补记的 4 份历史日志均在文首注明「事后补记」；`process_logs/` 里仍为空的日志不代填、不编造。
- 加速度计通道如最终未能采集，将在报告中如实列为已知局限，并说明改用声学单通道完成分类的理由。
- 允许并鼓励使用 AI 辅助编码与排障，截图与文字记录见 `AI使用报告/` 与 `AI_Chat_Log.md`；所有实测数据、结论与代码均经本人核对。

---

**下一次更新**：Day 5（11/17）收工后，重点补 fast running 重采与加速度通道。
