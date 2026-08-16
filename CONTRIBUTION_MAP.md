# EvidenceFlow Contribution Map

## Document Purpose / Status

| Field | Value |
|---|---|
| Status | **Living Contribution Ledger** |
| Snapshot date | 2026-08-16 |
| Frozen upstream baseline | `20aaa0d422bd290c83f93574810ef1244e8d5955` |
| Current repository HEAD | `f6dd746de2704be803bc4e14634a956403fc843f`；P2-S3 implementation commit `ab34591`，accepted-review / Thinking-policy closeout diff 尚未提交 |
| Current EvidenceFlow stage | **P2-S3 IMPLEMENTED / VALIDATED**；controlled real-model smoke 通过，等待 human core-diff review 与 closeout commit |
| Update rule | 每次设计冻结、代码提交、测试或实验完成后追加证据，不把 planned/design 写成 implemented |

本文记录 open_deep_research upstream baseline 与 EvidenceFlow 原创设计、实现、测试和实验之间的边界。
它是简历、面试、项目复盘和技术决策的 claim-to-evidence 索引，不是功能 Wish List。

任何“我分析 / 我设计 / 我实现 / 我验证 / 我提升”的表述，都必须能在本文找到：

1. 明确的 contribution ID。
2. 准确的状态。
3. 对应设计文档、源码、测试、commit/PR 或实验结果。
4. 与 upstream baseline 的差异和修改理由。

### Status Vocabulary

| Status | Meaning | 可使用的表述 |
|---|---|---|
| `UPSTREAM` | 冻结 commit 已有能力，不属于 EvidenceFlow 原创 | “基于 / 复用 upstream …” |
| `VERIFIED` | 已完成源码、运行或 notes 核验，但未修改能力 | “核验 / 分析 / 定位 …” |
| `DESIGNED` | 设计文档已形成，代码尚未落地 | “设计 / 定义 / 冻结候选 …” |
| `IMPLEMENTED` | 已有可定位源码 diff 和 commit/PR | “实现 …” |
| `VALIDATED` | 实现已有可复现测试或实验结果 | “验证 …”；只有对比实验充分时才能声称“提升” |
| `PLANNED` | 已进入 roadmap，尚无完整设计或代码 | “计划 / 下一阶段 …” |
| `DEFERRED` | 明确不在当前 vertical slice 范围内 | “延期 / Future Work …” |

状态升级必须保留前一阶段证据。`DESIGNED → IMPLEMENTED` 至少需要代码路径和 commit；
`IMPLEMENTED → VALIDATED` 至少需要测试或实验命令、fixture/dataset 版本和结果记录。

## Frozen Upstream Baseline

| Field | Value |
|---|---|
| Repository | `langchain-ai/open_deep_research` |
| Local upstream remote | `git@github.com:langchain-ai/open_deep_research.git` |
| Frozen commit | `20aaa0d422bd290c83f93574810ef1244e8d5955` |
| Short commit | `20aaa0d` |
| Commit subject | `Bump cryptography in the uv group across 1 directory (#331)` |
| Local fork | `Lovin-coder/evidenceflow-research-agent` |
| Verification | P2-S3 core implementation 已进入 `ab34591`；当前 branch 叠加 accepted-review fixes、typed Thinking policy、regression tests 与 closeout documentation diff |

Attribution rule：该 commit 已存在的 Agent topology、search、compression、final writer、state/reducer
和 evaluation harness 均记为 `UPSTREAM`。EvidenceFlow 可以说明“复用并保留”这些机制，不能将其描述为
原创实现。EvidenceFlow 的贡献从 baseline 核验、问题定义、contract-first redesign 和后续可定位 diff
开始计算。

Primary baseline evidence：

- [`src/open_deep_research/state.py`](src/open_deep_research/state.py)
- [`src/open_deep_research/deep_researcher.py`](src/open_deep_research/deep_researcher.py)
- [`src/open_deep_research/utils.py`](src/open_deep_research/utils.py)
- [`tests/evaluators.py`](tests/evaluators.py)
- [`notes/p2_s2/closeout/P2_S2_CLOSEOUT.md`](notes/p2_s2/closeout/P2_S2_CLOSEOUT.md)

## Baseline Capabilities

| Capability | Frozen upstream behavior | EvidenceFlow ownership | Known boundary relevant to EvidenceFlow |
|---|---|---|---|
| Clarify | `clarify_with_user` 使用 structured output 判断是否追问，并在需要时结束当前 run | `UPSTREAM` | 仍是 generic clarification，不提供医学 contract |
| Research Brief | `write_research_brief` 将用户消息转为单个详细 `research_brief: str` | `UPSTREAM` | Brief 不是多个 topics；没有 question type、临床元素或 nested EvidenceNeed |
| Agentic Supervisor | Supervisor 运行 `Plan → Delegate → Observe → Re-evaluate` Tool Loop | `UPSTREAM` | Task 隐含在 `ConductResearch` tool call 和 messages 中 |
| Runtime task generation | Supervisor 每轮动态产生 0/1/N 个 `ConductResearch` calls，并通过 `ResearchComplete`、无 Tool Call 或迭代上限终止 | `UPSTREAM` | 没有一等公民 task lifecycle；这是保留 topology、升级 contract 的起点 |
| Concurrent Researchers | Host 将允许的 calls 转为隔离 Researcher Subgraph invocations，并用 `asyncio.gather()` 并发 | `UPSTREAM` | 超额任务被拒绝而非排队；单个异常可能结束整批结果处理 |
| Researcher loop | 每个 Researcher 独立运行 Model–Tool–Observation 循环，支持 search、reflection 和 MCP tools | `UPSTREAM` | 内部过程与外部 Evidence 尚未形成结构化分层 |
| Tavily path | Tavily 是默认主路径；执行多 query 搜索、按 URL 去重、网页总结并返回 formatted text | `UPSTREAM` | 输出以字符串为中心；完整 Source/Evidence identity 和 query provenance 不稳定 |
| Provider capability | 配置层还支持 Anthropic/OpenAI native search、MCP 和无搜索模式 | `UPSTREAM` | EvidenceFlow 首个 vertical slice 只承诺 Tavily structured ingestion |
| Compression | `compress_research` 将 Researcher 局部上下文压缩为 `compressed_research`，并聚合 `raw_notes` | `UPSTREAM` | Supervisor 看到 bounded text，但 Source/Evidence IDs 尚未穿过 compression boundary |
| Legacy notes | `notes` 来自 Supervisor ToolMessages；`raw_notes` 聚合 Researcher AI/Tool 文本，两者不是同一条路径 | `UPSTREAM` | 两者都不是 clean Evidence Ledger；AIMessage 进入 `raw_notes` 会带来循环自证风险 |
| Final Writer | `final_report_generation` 主要消费 `notes`，生成 `final_report` | `UPSTREAM` | 写作依赖压缩文本，不能确定性解析 Claim → Evidence provenance |
| State/reducers | Agent、Supervisor、Researcher 使用分层 State；消息/list channel 支持追加或 override | `UPSTREAM` | 没有 MedicalResearchBrief、Source/Evidence/Finding/TaskResult contracts |
| Existing Eval | 已有 overall quality、relevance、structure、correctness、groundedness、completeness、pairwise 和局部 Supervisor parallelism eval | `UPSTREAM` | Eval 以 final artifact 为主；Groundedness 同时抽 Claim 并对混合 `raw_notes` 做粗粒度判断 |

Baseline capability source map：

| Baseline component | Primary implementation |
|---|---|
| Clarify / Brief / Supervisor / Researcher / Compression / Final Writer | [`deep_researcher.py`](src/open_deep_research/deep_researcher.py) |
| Baseline schemas and State | [`state.py`](src/open_deep_research/state.py) |
| Tavily, provider tools, webpage summarization, legacy notes extraction | [`utils.py`](src/open_deep_research/utils.py) |
| Final artifact and Groundedness evaluators | [`evaluators.py`](tests/evaluators.py) |
| Supervisor parallelism prototype | [`supervisor_parallel_evaluation.py`](tests/supervisor_parallel_evaluation.py) |

## EvidenceFlow Original Work

### Cross-phase Architecture Design

| Contribution ID | Original contribution | Status | Evidence |
|---|---|---|---|
| `EF-DES-001` | 将 baseline 限制收敛为 Task/Runtime Explicitness、Text-centric Evidence、Evaluation Granularity、Domain Adaptation 四类 | `DESIGNED` | [Master Plan §3](docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#3-four-baseline-limitation-categories) |
| `EF-DES-002` | 定义三个核心 Track：Domain-aware Medical Planning、Evidence-native Research Pipeline、Claim-level Grounding/Evaluation | `DESIGNED` | [Master Plan §5](docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#5-three-improvement-tracks) |
| `EF-DES-003` | 决定首版保留 Agentic Supervisor–Researcher Tool Loop，不迁移 Plan + Send、RAG 或 Durable Queue | `DESIGNED` | [Master Plan §5/§10](docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#5-three-improvement-tracks) |
| `EF-DES-004` | 将 P2-S3～P2-S6 拆为 contracts、evidence-native researcher、claim grounding、evaluation/reliability 四阶段 | `DESIGNED` | [Master Plan §11](docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#11-p2-s3p2-s6-roadmap) |

这些条目证明的是 architecture/design work，不证明相关 runtime 已经实现。

### P2-S2 — Baseline Verification / Problem Framing

| Contribution ID | Original contribution | Status | Evidence |
|---|---|---|---|
| `EF-VER-001` | 对 frozen upstream 的主图、Supervisor、Researcher、并发、Compression 和 State 数据流做源码级核验 | `VERIFIED` | [`notes/p2_s2/source/`](notes/p2_s2/source/)；[`P2_S2_CLOSEOUT.md`](notes/p2_s2/closeout/P2_S2_CLOSEOUT.md) |
| `EF-VER-002` | 核验 `notes` 与 `raw_notes` 是不同路径，Final Writer 主要消费 `notes` | `VERIFIED` | [`04_supervisor_researcher_deep_dive.md`](notes/p2_s2/source/04_supervisor_researcher_deep_dive.md) |
| `EF-VER-003` | 定位现有 Groundedness 使用混合 `raw_notes`、存在 AIMessage 循环自证与粒度不足的问题 | `VERIFIED` | [`07_evaluation_harness.md`](notes/p2_s2/source/07_evaluation_harness.md)；[`groundedness_evidence_harness.md`](notes/p2_s2/improvements/groundedness_evidence_harness.md) |

### P2-S3 — Domain & Evidence Contracts

P2-S3 当前状态：**IMPLEMENTED / VALIDATED**。Domain/State/runtime contract migration 已进入实现 commit，
accepted Review triage、typed Thinking policy 与 regression tests 位于 closeout diff；41 个 targeted tests 和
controlled real-model Brief → ConductResearch → Host Task smoke 已通过。当前仅剩 human core-diff review 与
closeout commit。

| Contribution ID | Original contribution | Current outcome | Status | Evidence |
|---|---|---|---|---|
| `EF-P2S3-001` | Medical planning contract | 严格 `MedicalResearchBrief` schema 已实现；runtime 直接 structured-output，并由 host renderer dual-write legacy brief | `VALIDATED` | [Contracts §3.1–3.2](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#31-medicalresearchbrief)；[`domain_models.py`](src/open_deep_research/domain_models.py)；[`write_research_brief`](src/open_deep_research/deep_researcher.py)；[smoke record](docs/plans/P2_S3_RETRO.md#33-controlled-real-model-smoke--pass) |
| `EF-P2S3-002` | EvidenceNeed placement | `EvidenceNeed` 仅作为 Brief/Task nested object；topology regression test 确认没有独立 channel/node | `VALIDATED` | [`domain_models.py`](src/open_deep_research/domain_models.py)；[`test_state_contracts.py`](tests/test_state_contracts.py) |
| `EF-P2S3-003` | Domain task contract | Host 从 structured `ConductResearch` envelope 构造 run-local Task ID，并保持 Supervisor 0/1/N 动态 delegation | `VALIDATED` | [`state.py`](src/open_deep_research/state.py)；[`materialize_medical_research_task`](src/open_deep_research/deep_researcher.py)；[`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py)；[smoke record](docs/plans/P2_S3_RETRO.md#33-controlled-real-model-smoke--pass) |
| `EF-P2S3-004` | Evidence data chain | 严格 Source/Evidence/Finding schemas、normalized raw-metadata guard、8000-character compactness bounds 与 Researcher-local provenance validation 已实现；真实 population 与 cross-boundary resolver 延后 P2-S4 | `VALIDATED` | [`domain_models.py`](src/open_deep_research/domain_models.py)；[`test_domain_models.py`](tests/test_domain_models.py) |
| `EF-P2S3-005` | Cross-graph output | Researcher dual-write shadow `ResearchTaskResult` 与 legacy compression；publish gate 拒绝 invalid provenance；admission/execution failure 产生 task-correlated failed result | `VALIDATED` | [`compress_research`/`supervisor_tools`](src/open_deep_research/deep_researcher.py)；[`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py) |
| `EF-P2S3-006` | State schema | Parent/Supervisor/Researcher structured channels 已映射；Researcher output 只投影 Result 和 legacy outputs | `VALIDATED` | [`state.py`](src/open_deep_research/state.py)；[`test_state_contracts.py`](tests/test_state_contracts.py) |
| `EF-P2S3-007` | Artifact boundary | structured contracts 拒绝 normalized content-bearing metadata keys，并对 metadata serialized total 与 Evidence excerpt 执行 8000-character runtime compactness guards；legacy raw-notes fallback 保持临时例外 | `VALIDATED` | [Contracts §4.4](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#44-artifact-boundary)；[`test_domain_models.py`](tests/test_domain_models.py) |
| `EF-P2S3-008` | Identity/provenance rules | I1–I10、local publication validation、ID/reference/process-artifact/derived-field invariants 均有 deterministic tests | `VALIDATED` | [Contracts §6](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#6-identity--provenance-invariants)；[`test_domain_models.py`](tests/test_domain_models.py)；[`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py) |
| `EF-P2S3-009` | Concurrent update semantics | ID-aware reducers 保留 distinct results，dedup identical replay，并拒绝相同 ID 的 conflicting payload | `VALIDATED` | [`state.py`](src/open_deep_research/state.py)；[`test_state_contracts.py`](tests/test_state_contracts.py) |
| `EF-P2S3-010` | Migration/versioning | contract constant、deterministic Markdown adapters、structured+legacy 同执行 dual-write 和迁移例外已实现并记录 | `VALIDATED` | [`domain_models.py`](src/open_deep_research/domain_models.py)；[`deep_researcher.py`](src/open_deep_research/deep_researcher.py)；[Contracts §8–§10](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#8-legacy-compatibility) |
| `EF-P2S3-011` | Typed research-model Thinking policy | `bool | None` typed setting 在 model boundary 最小映射为 provider `extra_body.enable_thinking`；`None` 保留 provider default，任意 runtime `extra_body` 无法绕过 typed boundary | `VALIDATED` | [`configuration.py`](src/open_deep_research/configuration.py)；[`deep_researcher.py`](src/open_deep_research/deep_researcher.py)；[`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py)；[smoke record](docs/plans/P2_S3_RETRO.md#33-controlled-real-model-smoke--pass) |

### P2-S4 — Evidence-native Researcher

P2-S4 当前状态：`PLANNED`。以下是已在 Master Plan/Contracts 中划定的实现目标，不得在完成代码和测试前
写成“已实现”。

| Contribution ID | Planned EvidenceFlow work | Intended outcome | Status | Design evidence |
|---|---|---|---|---|
| `EF-P2S4-001` | Tavily structured ingestion | 将 formatted search text 同步投影为 SourceRecord/EvidenceRecord，保留 stable IDs 与 provenance | `PLANNED` | [Master Plan §5 Track B](docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#track-b--evidence-native-research-pipeline) |
| `EF-P2S4-002` | Evidence-native Result population | 在 P2-S3 shadow Result boundary 中填入实际 ResearchFinding、Evidence IDs 和 Source IDs | `PLANNED` | [Contracts §3.6–§5](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#36-researchfinding) |
| `EF-P2S4-003` | Provenance through compression | Source/Evidence IDs 穿过 compression 和 Supervisor observation boundary | `PLANNED` | [Contracts I1–I10](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#6-identity--provenance-invariants) |
| `EF-P2S4-004` | Evidence-native dual-write | 在已实现的 shadow/legacy adapter 上增加实际 structured ledger population，旧报告继续生成 | `PLANNED` | [Contracts §8](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#8-legacy-compatibility) |
| `EF-P2S4-005` | Minimal Artifact Store | 实现 `ArtifactStore Protocol → LocalArtifactStore`，移除 P2-S3 legacy raw-content exception | `PLANNED` | [Contracts §4.4/§10](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#44-artifact-boundary) |

### P2-S5 — Claim–Evidence Grounding

P2-S5 当前状态：`PLANNED`。P2-S3 只保留完整目标链中的位置，不冻结其全部实现细节。

| Contribution ID | Planned EvidenceFlow work | Intended outcome | Status | Design evidence |
|---|---|---|---|---|
| `EF-P2S5-001` | Claim contracts | 冻结 ClaimRecord、EvidenceSupport/ClaimEvidenceLink 和 Citation representation | `PLANNED` | [Master Plan §7/§11](docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#7-key-domain-contracts) |
| `EF-P2S5-002` | Groundedness V2 | 分离 Claim Extraction、deterministic Citation Resolution、Entailment、Materiality Aggregation | `PLANNED` | [Master Plan Track C](docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#track-c--claim-level-grounding--evaluation) |
| `EF-P2S5-003` | Metric separation | 独立衡量 Claim Groundedness、Citation Correctness、Citation Completeness 和 Factual Correctness | `PLANNED` | [Master Plan Track C](docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#track-c--claim-level-grounding--evaluation) |
| `EF-P2S5-004` | Shadow comparison | Groundedness V1/V2 并行评估，保留旧 evaluator 作为对照 | `PLANNED` | [Master Plan §11](docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#11-p2-s3p2-s6-roadmap) |

### P2-S6 — Evaluation & Reliability

| Contribution ID | Planned EvidenceFlow work | Intended outcome | Status | Design evidence |
|---|---|---|---|---|
| `EF-P2S6-001` | Frozen regression fixtures | 对 contract、citation、support/contradiction 和 failure cases 做可重复回归 | `PLANNED` | [Master Plan §9/§11](docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#9-mvp-scope) |
| `EF-P2S6-002` | Judge calibration / hard gates | 基于人工校准数据确定阈值，不在设计阶段臆定 release threshold | `PLANNED` | [Master Plan §12/§13](docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#12-acceptance-criteria) |
| `EF-P2S6-003` | Partial-failure observability | 在既有三条 Track 内改善 per-task result/error 的可见性 | `PLANNED` | [Master Plan §11](docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#11-p2-s3p2-s6-roadmap) |

## Modified Upstream Components

### Current Actual Modifications

P2-S3 core runtime 已进入 `ab34591`，accepted-review fixes、typed Thinking policy、additional tests 与
closeout documentation 位于当前未提交 diff。下表记录已经实现并验证的行为；`closeout diff pending`
只描述提交状态，不降低已取得的 deterministic 与 controlled-smoke evidence。

| File | Baseline responsibility | EvidenceFlow modification | Reason | Evidence state |
|---|---|---|---|---|
| [`configuration.py`](src/open_deep_research/configuration.py) | typed application runtime configuration | 新增 narrow `research_model_enable_thinking: bool | None`，不开放 generic provider kwargs | 为 Qwen Thinking policy 提供可验证的最小 typed boundary | `IMPLEMENTED / VALIDATED`; closeout diff pending |
| [`domain_models.py`](src/open_deep_research/domain_models.py) | upstream 无领域合同模块 | 新增七个 v1 contracts、status enum、contract version、normalized raw-artifact guard、compactness bounds 和 provenance graph validator | 将领域对象与 LangGraph process State 分离 | `IMPLEMENTED / VALIDATED`; closeout diff pending |
| [`state.py`](src/open_deep_research/state.py) | generic tool schemas 与 Parent/Supervisor/Researcher State | structured ConductResearch envelope、typed channels、TaskResult output、ID-aware reducers | 最小映射 frozen State/update semantics | `IMPLEMENTED / VALIDATED` |
| [`deep_researcher.py`](src/open_deep_research/deep_researcher.py) | brief、delegation、Researcher loop、compression、final writer | typed brief/task/result wiring、host IDs、publication validation、failure isolation、legacy rendering 与 narrow Thinking model config | 建立真实 Task → Result boundary且保留原拓扑 | `IMPLEMENTED / VALIDATED`; closeout diff pending |
| [`prompts.py`](src/open_deep_research/prompts.py) | generic brief/Supervisor/Researcher prompts | 对齐 MedicalResearchBrief 和 structured delegation semantics | 防止 prompt/schema drift | `IMPLEMENTED / VALIDATED` |
| [`test_domain_models.py`](tests/test_domain_models.py) | 无 deterministic contract tests | strict schema、status、provenance、raw/process artifact 与 compactness boundary tests | 将 I1–I10 与 runtime guards 转成回归检查 | `VALIDATED`; closeout diff pending |
| [`test_state_contracts.py`](tests/test_state_contracts.py) | 无 deterministic State tests | reducer replay/conflict、channel 和 frozen topology tests | 验证 State freeze 未改拓扑 | `VALIDATED` |
| [`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py) | 无 deterministic runtime contract tests | brief dual-write、task identity、0/1/N、failure isolation、publish gate、Thinking policy/bypass tests | 验证真实 adapter functions；外部调用只在独立 controlled smoke 中进行 | `VALIDATED`; closeout diff pending |

### Planned Upstream Touchpoints

下表同时保留已触达和后续计划，以便继续追踪 upstream responsibility。

| Upstream file / component | Baseline responsibility | Planned EvidenceFlow modification | Reason | Phase | Current status |
|---|---|---|---|---|---|
| `src/open_deep_research/state.py` | 定义 ConductResearch、ResearchQuestion、Agent/Supervisor/Researcher State 和 legacy output | 引用 v1 domain contracts；将 Parent/Supervisor/Researcher logical channels 映射到冻结 State semantics | 让 Task、Source、Evidence、Finding、TaskResult 成为一等公民，同时保留 legacy channels | P2-S3 | `IMPLEMENTED / VALIDATED` |
| `deep_researcher.py::write_research_brief` | 生成 generic `research_brief: str` | 生成 schema-valid MedicalResearchBrief，并由 deterministic renderer dual-write legacy brief | 将医学语义从 prompt-only 文本升级为稳定 domain input | P2-S3 | `IMPLEMENTED / VALIDATED` |
| `deep_researcher.py::supervisor` | 根据 brief/messages 动态产生 ConductResearch calls | 继续原算法并绑定升级后的 structured tool schema；未修改 planning loop | 显式化 task semantics，不破坏 upstream agentic behavior | P2-S3 | `PRESERVED / VALIDATED SCHEMA` |
| `deep_researcher.py::supervisor_tools` | 限制并发、`gather()` Researcher、将 compressed text 包装成 ToolMessage、聚合 raw_notes | Host materialize Task，接收/merge shadow TaskResult，隔离 per-task failure，并继续输出 legacy ToolMessage | 建立稳定 Parent ↔ Researcher contract，避免 Supervisor 依赖完整 ResearcherState | P2-S3 | `IMPLEMENTED / VALIDATED` |
| `deep_researcher.py::researcher` / `researcher_tools` | 运行隔离 Model–Tool–Observation loop | 在 local state 中累积 SourceRecord、EvidenceRecord、ResearchFinding | 分离 Process Artifacts 与 Evidence Artifacts | P2-S4 | `PLANNED` |
| `deep_researcher.py::compress_research` | 生成 compressed_research 和 raw_notes | P2-S3 生成 shadow TaskResult 并 legacy dual-write；P2-S4 再 population structured records | 先验证跨图合同，避免提前实现 Evidence extraction | P2-S3/P2-S4 | `IMPLEMENTED / POPULATION PLANNED` |
| `deep_researcher.py::final_report_generation` | 从 notes 生成最终报告 | P2-S4 shadow 消费 structured Findings；P2-S5 接入 Claim/Citation contracts | 降低对混合 legacy text 的依赖，并支持可审计引用 | P2-S4/P2-S5 | `PLANNED` |
| `utils.py::tavily_search` / `tavily_search_async` | 调用 Tavily、按 URL 去重、总结网页、返回 formatted string | 增加 structured ingestion adapter，生成 Source/Evidence records 和 retrieval metadata；原文本路径保留 | Tavily 是首个 Evidence-native vertical slice 的已验证主路径 | P2-S4 | `PLANNED` |
| `utils.py::summarize_webpage` | 将 raw page content 压缩为 summary/key excerpts，失败时回退原文 | 保证 summary 与 source-derived excerpt 分层，禁止大 raw fallback 进入 Graph State | 执行 Artifact boundary，避免完整 HTML/PDF 或大型 payload 污染 State | P2-S4 | `PLANNED` |
| `utils.py::get_notes_from_tool_calls` | 收集所有 ToolMessage 内容作为 notes | 限定为 legacy compatibility；structured results 使用独立 contract/merge path | 避免把 reflection/error/任意 ToolMessage 当成 Evidence | P2-S4 | `PLANNED` |
| `src/open_deep_research/prompts.py` | 定义 generic clarify、brief、Supervisor、Researcher、compression、writer prompts | P2-S3 适配 MedicalResearchBrief/Task；structured Finding prompt 延后 P2-S4；invariants 由代码执行 | Prompt 表达语义目标，不能替代 schema、ID resolution 或 reducer enforcement | P2-S3/P2-S4 | `IMPLEMENTED / FINDING PLANNED` |
| `tests/evaluators.py` | Final artifact eval；Groundedness 对 final_report + raw_notes 一次性判定 | 保留 V1，对照新增 Claim/Citation/Evidence-aware V2 pipeline | 拆分 Claim extraction、resolution、entailment、aggregation，消除粗粒度循环自证 | P2-S5 | `PLANNED` |
| `tests/run_evaluate.py` | 运行现有 evaluator 集合 | 加入 frozen fixtures、V1/V2 shadow experiment 和有效配置记录 | 为“改善”提供可重复实验依据 | P2-S5/P2-S6 | `PLANNED` |
| `tests/supervisor_parallel_evaluation.py` | 局部检查 Supervisor 产生的并发 Tool Calls 数量 | 作为 topology regression 保留，并补充 Task/Result merge contract tests | 确认 contract migration 未破坏 upstream agentic parallelism | P2-S4/P2-S6 | `PLANNED` |

### Planned New EvidenceFlow Components

已落地组件记录实际路径；其余条目继续只记录职责。

| Planned component | Responsibility | Phase | Status | Required evidence before status upgrade |
|---|---|---|---|---|
| [`domain_models.py`](src/open_deep_research/domain_models.py) | 承载 MedicalResearchBrief、MedicalResearchTask、Source/Evidence/Finding/TaskResult schemas | P2-S3 | `IMPLEMENTED / VALIDATED` | schema/provenance/compactness tests 已通过；core commit `ab34591`，closeout diff pending |
| [`test_domain_models.py`](tests/test_domain_models.py)、[`test_state_contracts.py`](tests/test_state_contracts.py)、[`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py) | 验证 I1–I10、invalid references、merge/dedup、artifact exclusion、topology、compiled Researcher boundary、Thinking policy 和 legacy coexistence | P2-S3 | `VALIDATED` | 41 deterministic tests pass；closeout diff pending |
| Tavily structured adapter | 将 provider results 映射到 SourceRecord/EvidenceRecord | P2-S4 | `PLANNED` | source path、frozen provider fixtures、provenance tests |
| ArtifactStore Protocol / LocalArtifactStore | 保存 raw artifacts，Graph State 只携带 opaque artifact_ref | P2-S4 | `PLANNED` | protocol tests、local round-trip test、State-size/artifact exclusion test |
| Groundedness V2 components | Claim extraction、Citation resolution、entailment、materiality aggregation | P2-S5 | `PLANNED` | calibrated fixtures、deterministic resolver tests、V1/V2 run evidence |

### Upstream Components Intentionally Preserved

除非后续证据和 ADR 改变决定，以下 upstream 机制属于复用边界而非重写目标：

- Clarify → Brief → Supervisor → Final Writer 的主图阶段。
- Agentic Supervisor runtime re-planning。
- 一个 compiled Researcher Subgraph definition 对应多个隔离 invocations。
- 首版 Supervisor Tool Loop 和 Host-side concurrency cap。
- Researcher Model–Tool–Observation loop。
- Legacy final report path，在 dual-write 迁移完成前继续可用。
- Search/MCP provider capability boundary；首版只深化 Tavily structured path。

## Resume / Interview Claim Ledger

### Claims Supported Now

| Claim ID | 可安全使用的表述 | Status | Required evidence present |
|---|---|---|---|
| `CLAIM-001` | “我在固定 upstream commit 上完成了 ODR Supervisor–Researcher、并发、State、Compression 和 Eval 的源码级核验。” | `VERIFIED` | frozen commit、P2-S2 source notes、closeout |
| `CLAIM-002` | “我识别了 task 隐式、Evidence 文本化、Eval 粒度和医学领域契约四类结构性缺口，并设计了三个改进 Track。” | `DESIGNED` | Master Plan §3–§5 |
| `CLAIM-003` | “我实现并验证了 MedicalResearchBrief，将 EvidenceNeed 保留为 nested domain object，并让 Supervisor 动态生成 Host-owned MedicalResearchTask。” | `VALIDATED` | Contracts §3.1–§3.3、runtime tests、controlled smoke |
| `CLAIM-004` | “我实现了 Source → Evidence → Finding 的严格 contract、Researcher-local provenance publish gate 和 structured-State compactness guards。” | `VALIDATED` | Contracts §3.4–§3.6/§6、domain/runtime tests |
| `CLAIM-005` | “我实现了 MedicalResearchTask → ResearchTaskResult 的跨图 shadow boundary，使 Parent 不依赖 Researcher internal State。” | `VALIDATED` | Contracts §3.7/§5、runtime tests；真实 record population 属于 P2-S4 |
| `CLAIM-006` | “我实现并验证了 Parent/Supervisor/Researcher State ownership 与按 ID 幂等/冲突拒绝的 reducer 语义。” | `VALIDATED` | Contracts §4/§7、state contract tests |
| `CLAIM-007` | “我实现了 legacy text 与 structured contracts 的 dual-write 迁移，并通过真实模型 smoke 验证 Brief → Tool Call → Host Task 路径。” | `VALIDATED` | Contracts §8、runtime tests、P2-S3 Retro smoke record |
| `CLAIM-008` | “我将 Claim/Citation 冻结推迟到 P2-S5，并把 Evidence Store/RAG 明确为 Future layer，控制首个 vertical slice 的范围。” | `DESIGNED` | Contracts §10、Master Plan §10–§11 |
| `CLAIM-009` | “我用 typed nullable policy 控制 Qwen research-model Thinking，保持 provider default，并阻止 arbitrary extra_body 绕过配置边界。” | `VALIDATED` | `configuration.py`、model-boundary tests、controlled smoke provider observation |

上述 P2-S3 implementation claims 已由 core commit、当前 closeout diff、deterministic tests 与 controlled
smoke 支撑；引用时仍需说明真实 Source/Evidence population、cross-boundary resolver 与 hard-exception
state-aware recovery 尚未实现。

### Claims Not Yet Supported

在相应 contribution 升级为 `IMPLEMENTED` 或 `VALIDATED` 前，不得使用以下表述：

- “我实现了 evidence-native Tavily researcher。”
- “我实现了 ArtifactStore / Evidence Store / RAG。”
- “我实现了 Claim-level Groundedness V2。”
- “我的方案提升了 groundedness、citation accuracy、coverage 或 reliability。”
- “EvidenceFlow 已经支持生产级医学研究、完整 PubMed 或医学 RAG。”

不得将 P2-S3 的 validated contract migration 外推为 P2-S4/P2-S5/P2-S6 能力或医学质量提升。

### Evidence Standard for Future Claims

| Claim verb | Minimum evidence |
|---|---|
| “分析 / 定位” | frozen baseline、源码/运行证据、可复核 notes |
| “设计 / 定义” | versioned design doc、decision rationale、scope/non-goals、review/freeze status |
| “实现” | exact source paths、diff、commit/PR、相关 tests |
| “验证” | test command、fixture/dataset version、raw result 或 CI/run link |
| “提升 X%” | 同配置 baseline/variant、指标定义、样本量、重复次数、结果与局限 |
| “生产可用” | release evidence、failure handling、observability、security/privacy 和真实运行记录 |

## Implementation Evidence Log

后续开发只追加行；不得用计划替换历史状态。

| Date | Contribution ID | Change summary | Source files | Commit / PR | Tests / command | Eval / run artifact | Status |
|---|---|---|---|---|---|---|---|
| 2026-08-14 | `EF-DES-001`–`EF-DES-004` | Improvement Master Plan 整理与阶段边界收敛 | `docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md` | `UNCOMMITTED` | document structure checks | N/A | `DESIGNED` |
| 2026-08-14 | `EF-P2S3-001`–`EF-P2S3-010` | Contracts v1：domain/state/boundary/invariants/reducers/compatibility/versioning | `docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md` | `b944aa6` + worktree sync | document review | N/A | `DESIGNED` |
| 2026-08-15 | `EF-P2S3-001`–`EF-P2S3-010` | strict domain models、State reducers、structured Brief/Task/shadow Result、legacy adapters、failure isolation | `src/open_deep_research/domain_models.py`; `state.py`; `deep_researcher.py`; `prompts.py`; `tests/test_*contract*`; `tests/test_p2_s3_runtime.py` | `ab34591` | targeted deterministic suite、Ruff、scoped mypy | initial external endpoint attempt timed out before Brief；no search call | `IMPLEMENTED` |
| 2026-08-16 | `EF-P2S3-001`–`EF-P2S3-011` | accepted-review fixes、publish validation、compactness guards、typed Thinking policy 与 final closeout evidence | `configuration.py`; `domain_models.py`; `deep_researcher.py`; `tests/test_domain_models.py`; `tests/test_p2_s3_runtime.py`; P2-S3 docs | `ab34591` + uncommitted closeout diff | targeted `pytest`: 41 passed；Ruff、scoped mypy、compileall、`git diff --check` pass | controlled Qwen `qwen3.7-plus-2026-05-26` smoke PASS in 24.161s；Thinking=False observed；stopped before Researcher/Tavily | `VALIDATED` |
| 2026-08-14 | Contribution ledger | 创建并更新 upstream attribution 与 resume claim ledger | `CONTRIBUTION_MAP.md` | `4af35e3` + worktree sync | document review | N/A | `DESIGNED` |

## Maintenance Rules

1. 每个实现 PR 必须引用一个或多个 contribution ID；新范围先新增 ID。
2. 修改 upstream 文件时记录 baseline responsibility、实际 diff、原因和保留的不变量。
3. 新增源码文件时记录其 ownership，不能只写模糊的“优化 agent”。
4. Contract test、integration test、eval 分开记录；测试通过不自动等于指标提升。
5. 每次修改状态都填写 commit/PR。未提交工作必须标记 `UNCOMMITTED`。
6. 外部服务、dataset、Judge model 和 effective runtime config 必须版本化，否则实验不可作为简历量化依据。
7. 失败、partial result 和 negative experiment 也要追加，不能只保留成功结果。
8. 若实现偏离 Master Plan 或 Contracts v1，先更新设计或新增 ADR，再更新本 Map。
9. 删除 legacy path、迁移 Plan + Send、引入 Evidence Store/RAG 等范围扩张必须新增独立 contribution ID。
10. 面试材料只引用 `VERIFIED`、`DESIGNED`、`IMPLEMENTED`、`VALIDATED` 的准确含义，不跨状态夸大。

## Change Log

| Date | Change |
|---|---|
| 2026-08-14 | 初始化 frozen upstream baseline、capability attribution、P2-S3～P2-S6 contribution、planned touchpoints 和 claim ledger |
| 2026-08-15 | 记录 P2-S3 implementation candidate、deterministic validation、legacy raw-artifact exception 和 blocked runtime smoke |
| 2026-08-16 | 记录 accepted Review triage、typed Thinking policy、41-test validation 与 controlled real-model smoke PASS；P2-S3 升级为 `IMPLEMENTED / VALIDATED` |
