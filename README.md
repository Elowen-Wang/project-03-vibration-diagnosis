# ICEC 2026 级选拔 · 过程数据报告

**学号**：2027094　**姓名**：王宇婷　**层次**：2026 级高职 · 人工智能专业
**仓库**：`Elowen-Wang/project-03-vibration-diagnosis`　**周期**：2026-11-01 → 11-23

---

## 一、选题

| 阶段 | 选题 | 分值 |
|---|---|---|
| 第一阶段 · 基础素养实地测评（10 选 2） | 课题 06 校园昼夜声学噪声地图测绘 | 20 分（两题合计） |
| 第一阶段 · 基础素养实地测评 | 课题 08 多姿态步态加速度特征采集与对比 | 同上 |
| 第二阶段 · 工坊开放式项目挑战（8 选 1） | 项目三 手机传感器异常声振诊断仪 | 60 分 |

三题共用一条技术链：声学采集与阈值（课题 06）→ 加速度波形与特征（课题 08）→ 声振融合与工况分类（项目三）。采集方法、数据格式与代码逐题复用。

## 二、成果导航

| 成果 | 位置 |
|---|---|
| 第一阶段总报告 | [01_Stage1_Field_Measurement/README.md](./01_Stage1_Field_Measurement/README.md) |
| ├ 课题 06 原始材料与分贝报告 | [课题06/README.md](./01_Stage1_Field_Measurement/课题06/README.md) |
| └ 课题 08 数据字典与逐组核对 | [课题08/README.md](./01_Stage1_Field_Measurement/课题08/README.md) · [交付清单](./01_Stage1_Field_Measurement/课题08/交付清单.md) |
| 第二阶段项目三完整报告 | [02_Stage2_Project_Vibration/README.md](./02_Stage2_Project_Vibration/README.md) · [交付清单](./02_Stage2_Project_Vibration/交付清单.md) · [实验照索引](./02_Stage2_Project_Vibration/实验照索引.md) · [工况定义](./02_Stage2_Project_Vibration/protocol.md) |
| 盲测演示 | [盲测演示页](./02_Stage2_Project_Vibration/blind_test/盲测演示.html) · [录屏指引](./02_Stage2_Project_Vibration/blind_test/README.md) · [15 段明细](./02_Stage2_Project_Vibration/blind_test/blind_detail.csv) |
| AI 使用报告 | [AI使用报告/README.md](./AI使用报告/README.md) · [文字索引](./AI_Chat_Log.md) |
| 过程日志 | [process_logs/README.md](./process_logs/README.md)（14 份） |
| 任务表 | [DAILY_PLAN.md](./DAILY_PLAN.md) |
| 提交操作指引 | [提交指引.md](./提交指引.md)（11/24 23:59 截止） |

## 三、技术路线

三个选题共用同一流程：**真实采集 → 可解释特征 → 最近质心分类 → 对照验证**。

| 层 | 实现 |
|---|---|
| 采集 | 声学 48 kHz / 双声道 / 16 bit（OPPO Reno 15）；三轴加速度 100 Hz（iPhone + phyphox）。设备分列记录 |
| 特征 | 纯 Python 标准库手写 FFT；课题三 11 维时域/频域特征，阈值由训练窗口自动标定 |
| 分类 | 标准化 + 最近质心。可手算复核，逐条可解释 |
| 验证 | 留一法 → 同批次盲测 → 抗噪压力测试；跨日 held-out 未采 |

依赖：仅 Python 标准库（csv / wave / struct / math / cmath），图表输出 SVG。

## 四、关键结果

| 指标 | 数值 | 来源 |
|---|---|---|
| 课题 06 标准声学数据 | **15/15 格全满**；23 组独立实测，11 组超时段阈值（集中食堂与主干道） | [`06_summary.csv`](./01_Stage1_Field_Measurement/results/06_summary.csv) |
| 课题 06 场所化光效 | 五套基线 **41 / 60 / 60 / 50 / 47 dB**；15 格回放绿 10 · 黄 3 · 橙 1 · 红 1 | [`06_alert_profiles.md`](./01_Stage1_Field_Measurement/results/06_alert_profiles.md) |
| 课题 08 四类步态 | K 折 **88.3%** / 留一整份源文件 **63.3%** | [`08_threshold_rules.md`](./01_Stage1_Field_Measurement/results/08_threshold_rules.md) |
| 项目三 WAV | 75 段（5 工况 × 15），48 kHz / 双声道 / 16 bit / 10.3–11.9 s | 脚本核验 |
| 项目三留一法 | **89.3%**（75 段） | [`loo_report.md`](./02_Stage2_Project_Vibration/results/loo_report.md) |
| 项目三盲测（两轮） | 第一轮 **80.0%**（12/15）· 第二轮 **93.3%**（14/15），盲测段互斥 | [`盲测两轮对比说明.md`](./02_Stage2_Project_Vibration/results/盲测两轮对比说明.md) |
| 项目三抗噪（两轮） | 30 → 0 dB：第一轮 88.0%→48.0%，第二轮 96.0%→48.0%；**两轮拐点均 5 dB** | [`noise_robustness_round2.md`](./02_Stage2_Project_Vibration/results/noise_robustness_round2.md) |
| 特征消融 | `crest` 最关键（+4.0 pp），`dominant_hz` 冗余（−2.7 pp） | [`feature_ablation.md`](./02_Stage2_Project_Vibration/results/feature_ablation.md) |

数字口径：课题 08 的 88.3% 衡量同次采集窗口可分性（偏乐观），63.3% 为留一整份源文件结果（更接近泛化）。项目三盲测两轮相差 13.3 pp，差异来自「哪 3 段被留出」而非模型变化；抗噪两轮拐点一致但绝对值相差 8–11 pp，说明单轮 25 段的抽样误差不可忽略。上述差异均写入对应报告，不取单次最优值对外表述。

## 五、图表速览

**课题 06 · 五点位 × 三时段噪声地图**（五轴 = 五点位，三折线 = 早/午/晚，虚线 = 时段阈值）：

![校园五点位 × 三时段噪声地图](./01_Stage1_Field_Measurement/results/06_noise_radar.svg)

**课题 06 · 五场所个性化阈值阶梯**（基线＝该场所早午晚均值，色带即四档判定区间）：

![五场所个性化阈值阶梯](./01_Stage1_Field_Measurement/results/06_alert_profiles.svg)

**课题 06 · 声学超标自动提醒光效状态机**（绿/黄/橙/红四档 + 峰值单闪，实现见 `analyze_noise.py` 的 `LightAlertFSM`）：

![声学超标自动提醒光效逻辑 · 状态机](./01_Stage1_Field_Measurement/results/06_alert_fsm.svg)

**课题 08 · 步态波形**（平地慢走；取活动段中部 8 s，非文件开头，1×/2× 步频能量比为区分判据）：

![四类步态波形](./01_Stage1_Field_Measurement/results/08_wave_平地慢走.svg)

**项目三 · 五工况幅度谱对比**：

![五种工况平均幅度谱](./02_Stage2_Project_Vibration/results/spectrum_compare.svg)

## 六、目录结构

```
project-03-vibration-diagnosis/
├── README.md · DAILY_PLAN.md · AI_Chat_Log.md · 提交指引.md
├── AI使用报告/                   README + 三阶段截图 + 课题08核对报告.html
├── process_logs/                 14 份日志 + README
├── tools/                        signal_core.py · build_standard_grid.py · normalize_text.py · make_templates.py · make_blind_demo.py
├── 01_Stage1_Field_Measurement/
│   ├── README.md · noise_log.csv
│   ├── analyze_noise.py · analyze_gait.py
│   ├── 课题06/                   24 份分贝报告 + 现场 JPG/MP4
│   ├── 课题08/                   5 组 CSV/MP4/meta
│   └── results/                  06_*（含五套场所方案）/ 08_* 图表与报告；archive_1116/ 迭代证据
└── 02_Stage2_Project_Vibration/
    ├── README.md · protocol.md · experiment_log.csv · 交付清单.md · 实验照索引.md
    ├── analyze_real_wav.py · fft_feature_extraction.py
    ├── low-15/ high-15/ friction-15/ block-15/ imbalance-15/   75 段 WAV
    ├── blind_test/               盲测演示.html + 录屏指引 + 明细 + 视频
    ├── results/                  features.csv / 频谱图 / 报告 / 抗噪曲线 / 消融 / 混淆矩阵
    └── *.png · *.mp4 · day*.jpg  分贝报告、演示视频、现场照
```

## 七、官网评分对照

**第二阶段 60 分**（逐条见 [交付清单](./02_Stage2_Project_Vibration/交付清单.md)）：

| 官网要求 | 对应文件 | 状态 |
|---|---|---|
| ① 5 工况 × 15 组原始 WAV/CSV 及实验照（20 分） | `*-15/` 75 段 WAV、`experiment_log.csv`、`day*.jpg`、`*.png`、`*.mp4`、`实验照索引.md` | 数据齐；摩擦/失衡只有设备本体照（已标注） |
| ② 时域/频域特征提取代码（20 分） | `analyze_real_wav.py`、`tools/signal_core.py`、`results/features.csv`、`spectrum_compare.svg` | 已跑通 75 段 |
| ③ 盲测准确率视频与抗噪报告（20 分） | `results/loo_report.md`、`blind_report.md`、`noise_robustness.md`、`feature_ablation.md`、`blind_test/` | 视频、抗噪报告、消融分析齐 |
| 跨多日过程数据 | `process_logs/` 14 份、Git 提交历史、`AI使用报告/` | 齐 |
| `03-AI-Collaboration` | `AI使用报告/` 截图 + HTML 核对报告 + `AI_Chat_Log.md` | 齐 |

**第一阶段 20 分**：`noise_log.csv`（标准格 15/15 + 8 组佐证）、`results/06_*`、`课题08/` 5 组 CSV、`results/08_*`、`AI使用报告/第一阶段/课题08核对报告.html`；逐条见 [交付清单](./01_Stage1_Field_Measurement/课题08/交付清单.md)。

## 八、诚信与数据口径

- **设备分列**：课题 06 与项目三声学用 OPPO Reno 15（PLW110 分贝 App、原生录音机）；课题 08 用 iPhone17,2 + phyphox 1.2.1，11/19 重采快跑为 iPhone18,3。幅度类特征存在系统差异，分列说明。
- **原始数据**：音频、照片、视频均为本人真实环境采集；原始音频、分贝报告、传感器 CSV 保留不删。MP3 → WAV 仅换容器，不恢复高频。
- **异常值**：11-05 的 7 dB、11-20 的 18 dB 判为 App 启动爬升假值，保留记录并标注，平均值可用、最小值不纳入统计。
- **无效样本**：课题 08 快跑旧版（3.88 s）判无效，文件由本人移除，数值与判定理由以文字留存；11/19 重采后纳入。
- **时间依据**：分贝报告以 App「检测时间」为准，逐张与现场水印核对；App 场景标签为模板文案，不作点位依据。
- **归位规则**：标准 15 格由 `tools/build_standard_grid.py` 按四条事先声明规则归位（时段窗口、点位对应、同格择优、数值不加工），与声级高低无关。
- **局限**：跨日 held-out 0/15、加速度通道未采、课题 08 每类仅一次采集；均已标注，不补造数据。
- **AI 使用**：允许并鼓励 AI 辅助编码与排障，记录见 `AI使用报告/` 与 `AI_Chat_Log.md`；数据、结论与代码均经本人核对。

## 九、逐日完成记录

> 只记有据可查的事实（文件、时间戳、Git 提交）；空模板日期如实标注。

| 日期 | 完成内容 |
|---|---|
| 11/01 | 项目三预实验：低速/高速/受阻分贝报告（16:49/16:50/16:55，平均 52→57→61 dB）；git 建仓 |
| 11/02–03 | 整理目录，写 README 与 `AI_Chat_Log.md`，上传 D2 声学预调研照片与数据 |
| 11/04 | 课题 06 首测三组（图书馆 41、走廊左 39、走廊右 38 dB）；项目三 D1 采 low/high/friction 各 15 组 |
| 11/05 | 课题 06 图书馆 11:50（7/53/41），7 dB 判为启动假值；该组已于 11-23 重测替代，原件留作排障样本 |
| 11/06 | 项目三 D3 补 block 与 imbalance 各 15 组，5 工况 × 15 齐全；记录低电量失衡震动观察（未做对照实验） |
| 11/13 | 搭建 Python / Phyphox / GitHub Desktop 环境；课题 06 补测走廊左右两组（60/59 dB） |
| 11/14–15 | 日志为空模板，无当日可核验产出 |
| 11/16 | 课题 08 采 5 组三轴加速度（iPhone17,2 + phyphox 1.2.1）；完成 CSV ↔ 视频核对；3 类版阈值规则（50.0%） |
| 11/17 | 日志为空模板；held-out 与加速度通道未采 |
| 11/18 | 项目三 4 类整合分析、抗噪结论、特征消融、盲测演示页 + 15 段明细 + 录屏（12/15 = 80.0%）；课题 06 新增 H06–H09 四组 |
| 11/19 | 逐张核对全部分贝报告时间与水印；补录 H05L；课题 08 快跑重采（31.98 s / 100 Hz / 无暂停） |
| 11/20 | 课题 06 补采 10 份分贝报告，3 份填标准格 N11/N12/N14，7 份登记佐证 |
| 11/21 | 复核全部数据；两处脚本按文件名判定改为按时长客观判定；项目三主频说明更正为基频/谐波双峰 |
| 11/22 | 课题 08 判据升级（K 折 48.0% → 88.3%，留一文件 63.3%）；课题 06 雷达图改 5×3 矩阵、新增热力图与光效时间线；标准格归位 3/15 → 12/15 → 15/15；补登记 11-19 晚间三份报告；门牌证据确认实训室走廊点位；项目三特征消融；仓库编码与换行规范化，清理草稿 |
| 11/23 | 课题 06 重测图书馆午间（12:19，38/48/42 dB），N01 由 41 更新为 42，原 7 dB 组降级为排障样本；新增五场所个性化光效方案（5 套基线，绿/黄/橙/红四档 + 峰值单闪）；课题 08 波形图改取活动段中部并修刻度与图例，补标定法对比实验（中点法留一 63.3% 优于最优切分 60.0%）；项目三第二轮盲测 93.3%、第二轮抗噪（拐点仍 5 dB） |

## 十、复现命令

```bat
cd /d C:\Users\wangy\Desktop\project-03-vibration-diagnosis
python tools\signal_core.py
python tools\build_standard_grid.py
python 01_Stage1_Field_Measurement\analyze_noise.py
python 01_Stage1_Field_Measurement\analyze_gait.py
python 02_Stage2_Project_Vibration\analyze_real_wav.py --all
python 02_Stage2_Project_Vibration\analyze_real_wav.py --blind2 --noise2
python tools\make_blind_demo.py
python 02_Stage2_Project_Vibration\analyze_real_wav.py --check
python tools\normalize_text.py
```

`analyze_gait.py --demo` 的合成产物写入系统临时目录，不进仓库。
