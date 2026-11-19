# 智能·创造者 创新实验班（ICEC）· 2026 级选拔过程数据

**学号**：2027094　**姓名**：王宇婷　**层次**：2026 级高职 · 人工智能专业
**仓库**：`Elowen-Wang/project-03-vibration-diagnosis`
**过程记录**：2026-11-13 起逐日记录，见「四、每日完成状态汇报」

---

## 一、选题说明

| 阶段 | 选题 | 分值 |
|---|---|---|
| 第一阶段 · 基础素养实地测评（10 选 2） | **课题 06** 校园昼夜声学噪声地图测绘 | 20 分（两题合计） |
| 第一阶段 · 基础素养实地测评 | **课题 08** 多姿态步态加速度特征采集与对比 | 同上 |
| 第二阶段 · 工坊开放式项目挑战（8 选 1） | **项目三** 手机传感器异常声振诊断仪 | 60 分 |

三题是一条递进的能力链：**课题 06 练声学采集与阈值 → 课题 08 练加速度波形与特征 → 项目三做声振融合与工况分类**。
前两题的采集经验、数据格式与代码直接复用到项目三，不重复造轮子。各题当前状态见第四节逐日记录。

## 二、作品集导航

1. [第一阶段总报告](./01_Stage1_Field_Measurement/README.md) — 课题 06 / 08
   - [课题 06 原始材料与分贝报告](./01_Stage1_Field_Measurement/课题06/README.md)
   - [课题 08 数据字典与逐组核对](./01_Stage1_Field_Measurement/课题08/README.md) · [交付清单](./01_Stage1_Field_Measurement/课题08/交付清单.md)
2. [第二阶段项目三完整报告](./02_Stage2_Project_Vibration/README.md) — [交付清单](./02_Stage2_Project_Vibration/交付清单.md)｜[实验照索引](./02_Stage2_Project_Vibration/实验照索引.md)｜[工况定义](./02_Stage2_Project_Vibration/protocol.md)｜[实验登记表](./02_Stage2_Project_Vibration/experiment_log.csv)
   - [盲测演示页](./02_Stage2_Project_Vibration/blind_test/盲测演示.html) · [录屏指引](./02_Stage2_Project_Vibration/blind_test/README.md) · [15 段逐条明细](./02_Stage2_Project_Vibration/blind_test/blind_detail.csv)
3. [AI 使用报告 · 截图与核对证据](./AI使用报告/README.md) — 内含 [课题08核对报告 HTML](./AI使用报告/第一阶段/课题08核对报告.html)
4. [AI 提问与排障文字索引](./AI_Chat_Log.md)
5. [每日过程日志 process_logs](./process_logs/README.md) — 12 份
6. [11/13 → 11/20 每日任务表](./DAILY_PLAN.md) — 含软件/APP 下载清单与实况校准

## 三、分析主线

三个选题共享同一条方法论：**真实采集 → 可解释特征 → 最近质心分类 → 对照验证**。

- **采集层**：手机麦克风采声学（48 kHz / 双声道 / 16 bit），Phyphox 采三轴加速度；设备分列记录，不用"一台设备全包"的笼统说法。
- **特征层**：纯 Python 标准库手写 FFT，提取 11 维时域 + 频域量；阈值由训练窗口自动标定，不用拍脑袋的常数。
- **分类层**：标准化 + 最近质心。不用深度学习的原因是可解释、可手算复核，适合现场答辩逐条讲清"为什么判成这一类"。
- **验证层**：留一法 → 同批次盲测 → 抗噪压力测试 → 跨日 held-out。四个数字各有含义，不挑好看的报。

这条链的关键判断：**数据质量比模型复杂度更决定结果**。课题 08 只有 52.6%，不是算法弱，而是手机位置与动作幅度差异盖过了动作类型本身；项目三能到 89.3%，是五个工况主频本来就分得开。把分不开的原因讲清楚，比刷分重要。

## 四、每日完成状态汇报

> 只记有据可查的事实（文件、时间戳、Git 提交）。空模板日期如实标注，不补造、不代填。

### 11/13（Day 1）
- ✅ 搭建 Python / Phyphox / GitHub Desktop 环境。
- ✅ 课题 06 补测实验室走廊右（H05，55/66/59 dB），拍左右两侧水印照；左侧无报告未计入。
- 📌 同点位比 11/04 晚高约 20 dB，无对照实验，标注待核对，不写成昼夜规律。

### 11/14（Day 2）
- ⬜ 日志为空模板，无当日可核验产出。

### 11/15（Day 3）
- ⬜ 日志为空模板，无当日可核验产出。

### 11/16（Day 4）
- ✅ 课题 08 用 iPhone17,2 + phyphox 1.2.1 采 5 组三轴加速度（17:02–17:16），各含 CSV / MP4 / meta。
- ✅ 做传感器 ↔ 视频核对报告，查出快跑组仅 3.88 s、中途暂停，判定无效；原始文件全部保留。
- ✅ 3 类版阈值规则跑通（50.0%），备份在 `results/archive_1116/`。

### 11/17（Day 5）
- ⬜ 日志为空模板；held-out 与加速度补采未执行。

### 11/18（Day 6）
- ✅ 项目三：4 类整合分析、抗噪结论自动生成（拐点 5 dB）、盲测演示页 + 15 段明细 + **录屏视频**（18 MB，12/15 = 80.0%）。
- ✅ 课题 06：新增 H06–H09 四组（操场/食堂/主干道/食堂）；H07–H09 报告描述与现场照矛盾，标注存疑、不进标准格。
- ✅ 第二阶段 README 补入「电量影响失衡震动」发现的摘要与对照实验设计。
- ⬜ 跨日 held-out 15 段未采（0/15）、加速度通道未采，已写进局限。
- 📌 快跑组按本人计划 11/19 重录。

### 11/19（Day 7）
- 🟡 根 README 按「分析文档 + 逐日记录」重构；选题表去掉状态列，收尾指南移入项目三 README。
- ⬜ 快跑待本人重录；现有 `running.csv` 仍为 11/16 版（389 行），未动。

## 五、目录结构（11/19 实际）

```
project-03-vibration-diagnosis/
├── README.md · DAILY_PLAN.md · AI_Chat_Log.md · 今晚收尾指南.md
├── AI使用报告/                   README + 三阶段截图 + 课题08核对报告.html
├── process_logs/                 8 份正式日志 + 4 份历史补记 + README
├── tools/                        signal_core.py（零依赖内核）· make_templates.py · make_blind_demo.py
├── 01_Stage1_Field_Measurement/
│   ├── README.md · noise_log.csv
│   ├── analyze_noise.py · analyze_gait.py
│   ├── 课题06/                   README + 9 份分贝报告（5 PNG + 4 JPG）+ 现场 JPG/MP4
│   ├── 课题08/                   README + 交付清单.md + 5 组 CSV/MP4/meta
│   ├── gait_raw/                 空（兼容早期 flat 目录计划）
│   └── results/                  06_* / 08_* 图表与报告；archive_1116/ 旧版；_demo/ 合成演示产物
└── 02_Stage2_Project_Vibration/
    ├── README.md · protocol.md · experiment_log.csv（75 行）· 交付清单.md · 实验照索引.md
    ├── analyze_real_wav.py      真实 WAV 分析主脚本
    ├── fft_feature_extraction.py 早期模拟数据演示框架（不作交付依据）
    ├── low-15/ high-15/ friction-15/ block-15/ imbalance-15/   75 段 WAV
    ├── blind_test/               盲测演示.html + README + blind_detail.csv + 盲测准确率演示.mp4
    ├── results/                  features.csv / 频谱图 / 报告 / 抗噪曲线 / 混淆矩阵
    └── *.png · *.mp4 · day*.jpg  分贝报告、演示视频、现场照
```

## 六、快速复现（零第三方依赖）

```bat
cd /d C:\Users\wangy\Desktop\project-03-vibration-diagnosis
python tools\signal_core.py
python 01_Stage1_Field_Measurement\analyze_noise.py
python 01_Stage1_Field_Measurement\analyze_gait.py --include-invalid
python 02_Stage2_Project_Vibration\analyze_real_wav.py --all
python tools\make_blind_demo.py
python 02_Stage2_Project_Vibration\analyze_real_wav.py --check
```

只用 Python 标准库（csv / wave / struct / math / cmath），**无需 pip install numpy / scipy / matplotlib**；图表输出 SVG，GitHub 原生渲染。
`analyze_gait.py --demo` 的合成产物只写 `results/_demo/`，不覆盖真实结论。旧 `fft_feature_extraction.py` 跑的是模拟正弦波，仅作早期探索记录，不作交付依据。

## 七、官网评分对照

**第二阶段 60 分**（逐条见 [交付清单](./02_Stage2_Project_Vibration/交付清单.md)）

| 官网要求 | 对应文件 | 状态 |
|---|---|---|
| ① 5 工况 × 15 组原始 WAV/CSV 及实验照（20 分） | `*-15/` 75 段 WAV、`experiment_log.csv`、`day*.jpg`、`*.png`、`*.mp4`、`实验照索引.md` | ✅ 数据齐；3 工况有专属照，摩擦/失衡只有设备本体照（已标注） |
| ② 时域/频域特征提取代码（20 分） | `analyze_real_wav.py`、`tools/signal_core.py`、`results/features.csv`、`spectrum_compare.svg` | ✅ 已跑通 75 段 |
| ③ 盲测准确率视频与抗噪报告（20 分） | `results/loo_report.md`、`blind_report.md`、`noise_robustness.md`、`blind_test/` | ✅ 视频已录、抗噪结论已填；held-out 未采已写局限 |
| 跨多日连续过程数据 | `process_logs/` 12 份、Git 提交历史、`AI使用报告/` | 🟡 模板与历史补记已建，逐日填写待本人完成 |
| `03-AI-Collaboration` | `AI使用报告/` 79 张 JPG + 1 份 HTML 核对报告 + `AI_Chat_Log.md` | 🟡 截图齐，文字索引待补逐条记录 |

**第一阶段 20 分**：`noise_log.csv`（15 组待填）、`results/06_*`、`课题08/` 5 组 CSV、`results/08_*`、`AI使用报告/第一阶段/课题08核对报告.html`；逐条见 [课题08交付清单](./01_Stage1_Field_Measurement/课题08/交付清单.md)。

## 八、关键结果（真实数据，非模拟）

| 指标 | 数值 | 来源 |
|---|---|---|
| 项目三 WAV 总段数 | 75（5 工况 × 15），48 kHz / 双声道 / 16 bit / 约 10.4–11.9 s | 脚本核验 |
| 留一法交叉验证准确率 | **89.3%**（75 段） | `results/loo_report.md` |
| 同批次盲测准确率 | **80.0%**（1–12 训练 / 13–15 盲测，12/15） | `results/blind_report.md`、`blind_test/blind_detail.csv` |
| 抗噪 SNR 30 → 0 dB | **88.0% → 48.0%**，拐点 5 dB | `results/noise_robustness.md` |
| 各工况主频 | 低速 97–100、高速 154、摩擦 120、遮挡 147、失衡 151 Hz | `results/features.csv` |
| 声级交叉佐证 | 低速 52 → 高速 57 → 受阻 61 dB（平均分贝，11/01） | 3 份分贝报告 |
| 课题 06 分贝报告 | 9 组（36–62 dB 平均），含 1 组 7 dB 异常、4 组 11/18 新增（3 组存疑） | `课题06/` |
| 课题 08 采集 | 5 组 · 100 Hz · Linear Acceleration (m/s²) · iPhone17,2 + phyphox 1.2.1 | `课题08/*/meta/` |
| 课题 08 四类姿态留出集 | **52.6%**（4 类纳入，快跑仅 1 窗口；11/16 的 3 类版 50.0%） | `results/08_threshold_rules.md`、`results/archive_1116/` |

留一法 89.3% 高于盲测 80.0% 是正常的：按编号切分后 13–15 号与训练段存在分布差异，这也是要换一天重采 15 段做 held-out 的原因。
课题 08 的 52.6% 不是最终结论：快跑只有 3.88 s / 1 个有效窗口，平地慢走与上下楼梯的 `az_range`（8.68 vs 8.26）高度重叠。

## 九、诚信声明

- **设备如实分列**：课题 06 与项目三的声学/照片用 **OPPO Reno 15**（分贝仪 PLW110、原生录音机）；课题 08 的步态数据用 **iPhone17,2 + phyphox 1.2.1**。
- 所有原始音频、照片、视频均为本人在真实环境采集，未用合成数据充当实测结果。
- 课题 08「快跑」组经核对判定无效：原始 CSV / MP4 / meta 全保留，11/18 纳入分析只为让 4 类形式齐全，并显著标注「1 个窗口、置信度极低」，不静默剔除、不改数。
- 依据 [核对报告](./AI使用报告/第一阶段/课题08核对报告.html) 裁掉采集末尾低活动窗口，数量在 `08_threshold_rules.md` 逐文件列出，可复现。
- 合成 CSV 与图表隔离在 `results/_demo/`，不计入结论；MP3 → WAV 只换容器、不恢复已丢失的高频。
- 11-05 的 7 dB 判定为 App 启动爬升假值，保留原始记录 + 标注归因 + 安排重测；11/13 的 59 dB 与 11/04 同点位 38 dB 差约 20 dB，无对照实验，不写成昼夜规律。
- 事后补记的历史日志均在文首注明；`process_logs/` 里仍为空的日志不代填、不编造。
- 加速度计通道如最终未采，如实列为已知局限并说明改用声学单通道的影响，不编数据。
- 允许并鼓励使用 AI 辅助编码与排障，记录见 `AI使用报告/` 与 `AI_Chat_Log.md`；所有实测数据、结论与代码均经本人核对。
