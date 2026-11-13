# 智能·创造者 创新实验班（ICEC）· 2026 级选拔过程数据

**学号**：2027094　**姓名**：王宇婷　**层次**：2026 级高职 · 人工智能专业
**仓库**：`Elowen-Wang/project-03-vibration-diagnosis`
**交付目标**：2026-11-20 前完成（官网 11/24 封仓，留 4 天缓冲）

---

## 一、选题说明

| 阶段 | 选题 | 分值 | 状态 |
|---|---|---|---|
| 第一阶段 · 基础素养实地测评（10 选 2） | **课题 06** 校园昼夜声学噪声地图测绘 | 20 分（两题合计） | 🟡 已有 4 组报告，待补齐 15 组 |
| 第一阶段 · 基础素养实地测评 | **课题 08** 多姿态步态加速度特征采集与对比 | 同上 | ⬜ 待采集（Day 2） |
| 第二阶段 · 工坊开放式项目挑战（8 选 1） | **项目三** 基于手机内置传感器的日常旋转机械/电器异常声振诊断仪 | 60 分 | 🟡 75 段 WAV 与分析已完成，盲测/抗噪待补 |

> 三个选题是一条递进的能力链：**课题 06 练声学采集与阈值 → 课题 08 练加速度波形与特征 → 项目三做声振融合与工况分类**。
> 前两题的采集经验、数据格式和代码都直接复用到项目三，避免重复造轮子。

## 二、作品集导航

1. [第一阶段：实地测评数据与报告](./01_Stage1_Field_Measurement/README.md) — 课题 06 / 08
2. [第二阶段：实操项目源码与数据](./02_Stage2_Project_Vibration/README.md) — 项目三（[工况定义](./02_Stage2_Project_Vibration/protocol.md)｜[实验登记表](./02_Stage2_Project_Vibration/experiment_log.csv)）
3. [AI 提问与排障对话记录](./AI_Chat_Log.md)
4. [每日过程日志 process_logs](./process_logs/README.md) — 12 份
5. [11/13 → 11/20 每日任务表](./DAILY_PLAN.md) — 含软件/APP 下载清单与逐日操作

## 三、进度看板

| 任务 | 11/13 | 11/14 | 11/15 | 11/16 | 11/17 | 11/18 | 11/19 | 11/20 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 环境与 APP 搭建 | ⬜ | | | | | | | |
| 课题 06：15 组噪声数据 | ⬜ | ⬜ | | | | | | |
| 课题 06：雷达图 / 光效逻辑 | | ⬜ | ⬜ | | | | | |
| 课题 08：4 姿态采集与阈值 | | ⬜ | ⬜ | | | | | |
| 项目三：75 段真实 WAV 特征 | | | | ⬜ | | | | |
| 项目三：留一法 / 盲测准确率 | | | | | ⬜ | | | |
| 项目三：加速度通道 / 抗噪 / held-out | | | | | ⬜ | ⬜ | | |
| 全部 README 与 AI 记录定稿 | | | | | | | ⬜ | |
| 自检 + 面试演练 + 最终 push | | | | | | | | ⬜ |

> 每天收工把对应格子改成 ✅，并在 `process_logs/` 写当天日志、做一次带日期说明的 commit。

## 四、目录结构

```
project-03-vibration-diagnosis/
├── README.md                     本文件（总览 / 进度 / 评分对照 / 诚信声明）
├── DAILY_PLAN.md                 8 天每日任务（含 APP 下载与逐步操作）
├── AI_Chat_Log.md                AI 协作问答与排障记录
├── process_logs/                 每日过程日志（8 份正式 + 4 份历史补记）
├── tools/
│   ├── signal_core.py            零依赖内核：FFT / 频谱特征 / SVG 图表 / 分类器
│   └── make_templates.py         生成日志模板与 75 行实验登记表
├── 01_Stage1_Field_Measurement/
│   ├── README.md                 课题 06 + 08 报告
│   ├── noise_log.csv             课题 06 数据表（4 组已有 + 15 组待填）
│   ├── analyze_noise.py          课题 06 分析脚本
│   ├── analyze_gait.py           课题 08 分析脚本
│   ├── gait_raw/                 课题 08 原始 CSV（待采）
│   ├── results/                  两课题的图表与报告
│   └── 11-4*/11-5*              11/04–11/05 现场 JPG / MP4 / 分贝报告 PNG
└── 02_Stage2_Project_Vibration/
    ├── README.md                 项目三完整报告（含 D1–D3 原始日志）
    ├── protocol.md               5 工况可复现定义
    ├── experiment_log.csv        75 段 WAV 登记表（日期取自 Git 历史）
    ├── analyze_real_wav.py       真实 WAV 分析主脚本
    ├── fft_feature_extraction.py 早期演示框架（模拟数据，仅留作过程记录）
    ├── low-15/ high-15/ friction-15/ block-15/ imbalance-15/   75 段 WAV
    ├── accel_raw/                加速度 CSV（Day 5 待采）
    ├── blind_test/               11/18 当天重采的 held-out 数据（Day 6）
    ├── results/                  特征表 / 频谱图 / 混淆矩阵 / 各类报告
    └── *.png / *.mp4 / day*.jpg  现场照、分贝报告、演示视频
```

## 五、快速复现（零第三方依赖）

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
> 图表输出为 SVG，GitHub 可直接渲染。旧的 `fft_feature_extraction.py` 依赖 numpy/scipy/matplotlib 且跑的是模拟正弦波，保留仅为记录早期探索过程，**不作为交付依据**。

## 六、官网评分对照（第二阶段 60 分）

| 官网要求 | 对应文件 | 状态 |
|---|---|---|
| ① 5 种工况 × 15 组原始 WAV/CSV 及实验照（20 分） | `*-15/` 共 75 段 WAV、`experiment_log.csv`、`day*.jpg`、`*.png`、`*.mp4` | ✅ 数据齐，登记表待补照片列 |
| ② 时域/频域特征提取代码（20 分） | `analyze_real_wav.py`、`tools/signal_core.py`、`results/features.csv`、`results/spectrum_compare.svg` | ✅ 已跑通 75 段 |
| ③ 盲测准确率视频与抗噪报告（20 分） | `results/loo_report.md`、`blind_report.md`、`noise_robustness.md`、`heldout_report.md`、`blind_test/*.mp4` | 🟡 前三项已完成，held-out 数据与视频待 Day 6 |
| 跨多日连续过程数据 | `process_logs/` 12 份、Git 提交历史 | 🟡 模板与历史补记已建，8 天正式日志待逐日填写 |

**第一阶段 20 分**：`noise_log.csv`（15 组）、`results/06_*`、`gait_raw/`、`results/08_*`。

## 七、当前关键结果（真实数据，非模拟）

| 指标 | 数值 | 来源 |
|---|---|---|
| WAV 总段数 | 75（5 工况 × 15） | 脚本核验 |
| WAV 格式 | 48 000 Hz / 双声道 / 16 bit / 约 10.4–11.9 s | `experiment_log.csv` |
| 留一法交叉验证准确率 | **89.3%**（75 段） | `results/loo_report.md` |
| 同批次盲测准确率 | **80.0%**（1–12 训练 / 13–15 盲测，15 段） | `results/blind_report.md` |
| 各工况主频（样例） | 低速 97–100 Hz、高速 154 Hz、摩擦 120 Hz、遮挡 147 Hz、失衡 151 Hz | `results/features.csv` |
| 声级交叉佐证 | 低速 52 → 高速 57 → 受阻 61 dB（平均分贝） | 11/01 三份分贝报告 |
| 抗噪鲁棒性 | SNR 30 dB 88% → 10 dB 80% → 5 dB 64% → 0 dB 48% | `results/noise_robustness.md` |

> 交叉验证准确率高于盲测是正常且健康的：说明按编号切分后 13–15 号与训练段存在分布差异。
> 这正是 Day 6 要**换一天重新采 15 段**做 held-out 的原因，不能只报好看的那个数。

## 八、诚信声明

- 所有原始音频、照片、视频均为本人使用 OPPO Reno 15 在真实环境采集，未使用合成数据充当实测结果。
- `analyze_gait.py --demo` 生成的合成 CSV 仅用于验证脚本流程，存放于 `results/_demo/`，**不计入任何报告结论**；课题 08 的正式结论必须基于 `gait_raw/` 的真实采集。
- `fft_feature_extraction.py` 中的正弦波为早期演示框架，已明确标注，不参与结果计算。
- MP3 → WAV 只是更换容器，**不恢复有损压缩已丢失的高频**，报告中如实说明，不宣称"无损音质"。
- 11-05 分贝报告中的最小 7 dB 判定为 App 启动爬升假值，**保留原始记录 + 标注归因 + 安排重测**，不删除、不静默改数。
- 事后补记的 4 份历史日志均在文首注明"事后补记"，依据分贝报告时间戳、现场影像与 Git 提交历史还原。
- 加速度计通道如最终未能采集，将在报告中如实列为已知局限，并说明改用声学单通道完成分类的理由。
- 允许并鼓励使用 AI 辅助编码与排障，过程记录见 `AI_Chat_Log.md`；所有实测数据、结论与代码均经本人核对。

---

**最后更新**：2026-11-13　**下一次更新**：Day 1 收工后
