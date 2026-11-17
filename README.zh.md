# Maat：用于市场中性对冲的证据门控新闻–价格智能体

[English](README.md) | 中文

本仓库是 **FinProbeBench** 队伍在 [FinReason Cup 2026](https://the-finai.github.io/IEEE-bigdata-cup/) Task 2（市场中性对冲）中所用系统 **Maat** 的代码、配置与存档记录，
对应的 Working Notes 论文为
*Maat at FinReason Cup 2026 Task 2: An Evidence-Gated News–Price Agent for Market-Neutral Hedging*。

任务要求在每一轮对十只大盘股中的两只建立等金额多空头寸，或保持空仓。语言模型分析师把每次发布的新闻摘要转为经过校验的逐股证据（情绪、置信度、事件类型、理由）；
确定性分支计算价格动量；覆盖感知的合格性、广度与分差门控决定是否交易；一个在实盘前声明并计算哈希的部署策略选择评分规则。
三个变体在计算任何收益之前即已冻结：新闻主导（`full`）、动量路由（`no_news`，实盘部署）与无门控（`no_risk`）。

| | 结果 |
|---|---|
| 十月回放，37 个公开区间，新闻主导 | CR 0.30%，18 个活跃区间 |
| 十月回放，动量路由 | CR 4.96%，36 个活跃区间 |
| 2026 年 11 月 2 日实盘，动量路由 | 六轮 CR 2.33%，Phase III 排名第一（主办方报告） |

## 包含内容

| 路径 | 内容 |
|---|---|
| `prompt/system_prompt.txt` | 分析师系统提示词原文（即 `src/agent.py` 中的 `SYSTEM`） |
| `preregistration.json`、`preregistration.sha256` | 冻结的模型、温度、权重与阈值 |
| `live_policy.json`、`live_policy.sha256` | 实盘部署策略（v2），2026 年 11 月 1 日声明并计算哈希，SHA-256 为 `6142a54f4a2866115c2c2890511942793adc61a13163f5996368aeaeb6a930ce`（*待补入*，见下文） |
| `src/agent.py` | 分析师请求、响应校验、缓存与决策函数 `decide()` |
| `src/experiment.py`、`src/scoring.py` | 三个冻结变体的回放；式 (1)、入场/离场时间与指标 |
| `src/replay_baselines.py` | 用同一评估器回放主办方基线；图表换算只用于一致性检查 |
| `src/diagnostics.py`、`src/semantic_audit.py` | 事后诊断（门控、新闻项置零、集中度）与描述性信号审计 |
| `src/report.py` | 表 II、图 2 与 token 用量 |
| `src/live.py` | 本地实盘辅助程序（只生成建议，不含提交代码），2026 年 11 月 1 日版本 |
| `src/prepare_data.py` | 把下载的数据集整理为 `data/raw/<release>/` |
| `src/camera_ready_stats.py` | 终稿中的 bootstrap 区间、检验与门控隔离诊断 |
| `logs/llm/<sha256>/` | 每次分析师调用：`request.json`（精确请求体）、`response-1.json`（服务商原始响应）、`validated.json`、`metadata.json` |
| `logs/decisions/{full,no_news,no_risk}/` | 每次发布、每个变体一条记录：每只股票的证据、合格性、得分、动作与理由 |
| `logs/live/phase3_post/` | 赛后在六次实盘发布上对三个变体的记录（*待补入*，见下文） |
| `live/` | 提交六个实盘动作的无人值守脚本、演练用门户及其记录（`phase3/`：每轮的决策、下载哈希、门户回执与运行日志） |
| `results/` | 论文表格背后的逐轮动作与收益、基线回放、诊断、信号审计与 token 用量；`camera_ready_stats.json` 与 `camera_ready_macros.tex` 为终稿新增的全部区间、检验与诊断 |
| `tests/` | 计分、决策函数、实盘历史规则与缓存回放的单元测试 |

请求体只包含载荷；从未存储任何凭据或 HTTP 头。

### 待补入

以下三项保存在实验室服务器上，待服务器可访问后补入本仓库：
`live_policy.json` 及 `live_policy.sha256`（所声明的实盘策略，SHA-256 为 `6142a54f4a2866115c2c2890511942793adc61a13163f5996368aeaeb6a930ce`）、
三个变体在六次实盘发布上的赛后记录（`logs/live/phase3_post/`），
以及计算表 III 按事件类型细分的脚本（`src/paper_extras.py`）。
论文中其余内容均可由本仓库现有文件重新计算。

## 数据

本仓库**不包含**主办方的价格与新闻文件。请从公开数据集
[CarolynJiang/Market-Neutral-Hedging-live-trading](https://huggingface.co/datasets/CarolynJiang/Market-Neutral-Hedging-live-trading)
下载，并整理为回放所需的目录：

```bash
pip install huggingface_hub pandas pyarrow numpy matplotlib
huggingface-cli download CarolynJiang/Market-Neutral-Hedging-live-trading \
    --repo-type dataset --local-dir data/hf
python src/prepare_data.py          # data/raw/<YYYY-MM-DD_HH-MM>/{price,news}.parquet
```

脚本还需读取主办方十月的实盘状态文件 `sources/live-state.json`（含入场与离场时间的发布时间表及基线公布的动作）和基线收益图 `sources/return-paths.svg`，二者均发布于主办方实盘页面（<https://carolyn-jiang.github.io/Market-Neutral-Hedging-live-trading/>），本仓库不再分发。实盘下载文件的 SHA-256 见 `live/phase3/*/fetch.json`，十月各文件的 SHA-256 见 `results/data_manifest.json`。

## 无需调用模型即可复现论文

分析师缓存以精确请求体的 SHA-256 为键。数据就位后，回放会重建每个请求，在 `logs/llm/` 中找到它并复用已存储的标注，因此不会发起调用，也不需要密钥。在仓库根目录运行：

```bash
python src/experiment.py            # 三个变体的回放 -> results/agent_rounds.csv
python src/replay_baselines.py      # 用同一评估器回放主办方基线
python src/diagnostics.py           # 收益来源诊断
python src/semantic_audit.py        # 描述性信号审计
python src/report.py                # 表 II、图 2、token 用量
python src/camera_ready_stats.py --strict   # 区间、检验、固定股票池比较
python -m unittest discover -s tests
python live/test_decide.py          # 随附的 decide() 复现全部 41 个动量路由决策
```

`camera_ready_stats.py` 会先复现论文中的回放数字，并列出任何不一致。需要 Python 3.10 及以上，以及 `numpy`、`pandas`、`pyarrow`（`src/report.py` 另需 `matplotlib`）。

## 冻结文件的完整性

```bash
sha256sum preregistration.json        # live_policy.json 补入后同样核对
cat preregistration.sha256
```

## 与实际运行文件的差异

为避免公开本地路径或凭据位置，有两行与实际运行的文件不同：`src/agent.py`（及其随附副本 `live/vendor/agent.py`）从环境变量 `MAAT_API_KEY` 读取 API 密钥，而非从服务器上的文件读取；
`live/run_phase3.py` 将门户的队伍令牌保存在 `MAAT_PORTAL_TOKEN_FILE` 指定的文件中。提示词、校验器和 `decide()` 均未改动；`live/test_decide.py` 改用相对于仓库的路径。
`src/report.py` 去掉了原文件最后生成内部运行报告（含服务器路径）的部分，并自行创建输出目录。`src/camera_ready_stats.py` 为终稿统计脚本，其 `--root`、`--data-root`、`--results-root` 选项可在仓库之外的存档副本上运行。

## 引用

```bibtex
@inproceedings{finprobebench2026maat,
  title     = {Maat at {FinReason Cup 2026} Task 2: An Evidence-Gated News--Price Agent for Market-Neutral Hedging},
  author    = {Cao, Run and Kuang, Ziyan and Xie, Qianqian},
  booktitle = {2026 IEEE International Conference on Big Data (BigData), FinReason Cup Working Notes},
  year      = {2026}
}
```

## 许可

代码以 MIT 许可证发布（见 `LICENSE`）。存档请求体中引用的新闻摘要来自主办方数据集，仍受其条款约束。
