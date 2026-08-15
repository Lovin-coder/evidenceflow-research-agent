# EvidenceFlow Contribution Map

## Document Purpose / Status

| Field | Value |
|---|---|
| Status | **Living Contribution Ledger** |
| Snapshot date | 2026-08-15 |
| Frozen upstream baseline | `20aaa0d422bd290c83f93574810ef1244e8d5955` |
| Current repository HEAD | `4af35e38b0096a82522d86eb96be1a4cbda71e81`（baseline 后仅有 documentation commits） |
| Current EvidenceFlow stage | P2-S3 implementation candidate；deterministic validation complete，real runtime smoke blocked，human review / commit pending |
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
| Verification | 当前 committed `src/`/`tests/` 仍与 frozen commit 一致；HEAD 另含 documentation commits；P2-S3 runtime/test diff 当前位于未提交工作树 |

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

P2-S3 当前状态：设计已同步，runtime 和 deterministic tests 已在工作树实现；在完成真实 runtime smoke、
human core diff review 和 closeout commit 前，正式状态仍不升级为 `IMPLEMENTED/VALIDATED`。

| Contribution ID | Original contribution | Current outcome | Status | Evidence |
|---|---|---|---|---|
| `EF-P2S3-001` | Medical planning contract | 严格 `MedicalResearchBrief` schema 已实现；runtime 直接 structured-output，并由 host renderer dual-write legacy brief | `DESIGNED` + worktree implementation | [Contracts §3.1–3.2](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#31-medicalresearchbrief)；[`domain_models.py`](src/open_deep_research/domain_models.py)；[`write_research_brief`](src/open_deep_research/deep_researcher.py) |
| `EF-P2S3-002` | EvidenceNeed placement | `EvidenceNeed` 仅作为 Brief/Task nested object；topology regression test 确认没有独立 channel/node | `DESIGNED` + worktree implementation | [`domain_models.py`](src/open_deep_research/domain_models.py)；[`test_state_contracts.py`](tests/test_state_contracts.py) |
| `EF-P2S3-003` | Domain task contract | Host 从 structured `ConductResearch` envelope 构造 run-local Task ID，并保持 Supervisor 0/1/N 动态 delegation | `DESIGNED` + worktree implementation | [`state.py`](src/open_deep_research/state.py)；[`materialize_medical_research_task`](src/open_deep_research/deep_researcher.py)；[`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py) |
| `EF-P2S3-004` | Evidence data chain | 严格 Source/Evidence/Finding schemas、raw-metadata guard 和 cross-record provenance validator 已实现；runtime population 延后 P2-S4 | `DESIGNED` + worktree implementation | [`domain_models.py`](src/open_deep_research/domain_models.py)；[`test_domain_models.py`](tests/test_domain_models.py) |
| `EF-P2S3-005` | Cross-graph output | Researcher runtime dual-write shadow `ResearchTaskResult` 与 legacy compression；admission/execution failure 均产生 task-correlated failed result | `DESIGNED` + worktree implementation | [`compress_research`/`supervisor_tools`](src/open_deep_research/deep_researcher.py)；[`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py) |
| `EF-P2S3-006` | State schema | Parent/Supervisor/Researcher structured channels 已映射；Researcher output 只投影 Result 和 legacy outputs | `DESIGNED` + worktree implementation | [`state.py`](src/open_deep_research/state.py)；[`test_state_contracts.py`](tests/test_state_contracts.py) |
| `EF-P2S3-007` | Artifact boundary | 新 structured contracts 拒绝已知 raw payload metadata 和 process-message excerpt；legacy raw-notes fallback 作为 P2-S3 临时例外 | `DESIGNED` + worktree validation | [Contracts §4.4](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#44-artifact-boundary)；[`test_domain_models.py`](tests/test_domain_models.py) |
| `EF-P2S3-008` | Identity/provenance rules | I1–I10 已同步；ID、Source/Evidence/Finding reference、process-artifact rejection 和 derived-field exclusion 有 deterministic tests | `DESIGNED` + worktree validation | [Contracts §6](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#6-identity--provenance-invariants)；[`test_domain_models.py`](tests/test_domain_models.py) |
| `EF-P2S3-009` | Concurrent update semantics | ID-aware reducers 保留 distinct results，dedup identical replay，并拒绝相同 ID 的 conflicting payload | `DESIGNED` + worktree validation | [`state.py`](src/open_deep_research/state.py)；[`test_state_contracts.py`](tests/test_state_contracts.py) |
| `EF-P2S3-010` | Migration/versioning | contract constant、deterministic Markdown adapters、structured+legacy 同执行 dual-write 和迁移例外已实现并记录 | `DESIGNED` + worktree validation | [`domain_models.py`](src/open_deep_research/domain_models.py)；[`deep_researcher.py`](src/open_deep_research/deep_researcher.py)；[Contracts §8–§10](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#8-legacy-compatibility) |

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

截至本快照，P2-S3 已产生可定位的 runtime 和 test diff，但尚未完成真实 smoke、人工核心 diff 审阅与
closeout commit。因此下表证明“工作树中已有实现候选并通过 deterministic validation”，不把它提前写成
已提交或已完成阶段。

| File | Baseline responsibility | EvidenceFlow modification | Reason | Evidence state |
|---|---|---|---|---|
| [`domain_models.py`](src/open_deep_research/domain_models.py) | upstream 无领域合同模块 | 新增七个 v1 contracts、status enum、contract version、raw-artifact guard 和 provenance graph validator | 将领域对象与 LangGraph process State 分离 | `WORKTREE`; schema tests pass |
| [`state.py`](src/open_deep_research/state.py) | generic tool schemas 与 Parent/Supervisor/Researcher State | structured ConductResearch envelope、typed channels、TaskResult output、ID-aware reducers | 最小映射 frozen State/update semantics | `WORKTREE`; reducer/topology tests pass |
| [`deep_researcher.py`](src/open_deep_research/deep_researcher.py) | brief、delegation、Researcher loop、compression、final writer | typed brief/task/result wiring、host IDs、deterministic legacy rendering、per-task failure isolation | 建立真实 Task → Result boundary且保留原拓扑 | `WORKTREE`; mocked runtime tests pass |
| [`prompts.py`](src/open_deep_research/prompts.py) | generic brief/Supervisor/Researcher prompts | 对齐 MedicalResearchBrief 和 structured delegation semantics | 防止 prompt/schema drift | `WORKTREE`; Ruff pass |
| [`test_domain_models.py`](tests/test_domain_models.py) | 无 deterministic contract tests | strict schema、status、provenance、raw/process artifact rejection tests | 将 I1–I10 转成可回归检查 | `WORKTREE`; pass |
| [`test_state_contracts.py`](tests/test_state_contracts.py) | 无 deterministic State tests | reducer replay/conflict、channel 和 frozen topology tests | 验证 State freeze 未改拓扑 | `WORKTREE`; pass |
| [`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py) | 无 deterministic runtime contract tests | brief dual-write、task identity、0/1/N、failure isolation、shadow Result tests | 验证真实 adapter functions，不调用外部服务 | `WORKTREE`; pass |

### Planned Upstream Touchpoints

下表同时保留已触达和后续计划，以便继续追踪 upstream responsibility；`WORKTREE` 仍需 commit 才能升级
为正式 `IMPLEMENTED`。

| Upstream file / component | Baseline responsibility | Planned EvidenceFlow modification | Reason | Phase | Current status |
|---|---|---|---|---|---|
| `src/open_deep_research/state.py` | 定义 ConductResearch、ResearchQuestion、Agent/Supervisor/Researcher State 和 legacy output | 引用 v1 domain contracts；将 Parent/Supervisor/Researcher logical channels 映射到冻结 State semantics | 让 Task、Source、Evidence、Finding、TaskResult 成为一等公民，同时保留 legacy channels | P2-S3 | `WORKTREE` |
| `deep_researcher.py::write_research_brief` | 生成 generic `research_brief: str` | 生成 schema-valid MedicalResearchBrief，并由 deterministic renderer dual-write legacy brief | 将医学语义从 prompt-only 文本升级为稳定 domain input | P2-S3 | `WORKTREE` |
| `deep_researcher.py::supervisor` | 根据 brief/messages 动态产生 ConductResearch calls | 继续原算法并绑定升级后的 structured tool schema；未修改 planning loop | 显式化 task semantics，不破坏 upstream agentic behavior | P2-S3 | `PRESERVED / WORKTREE SCHEMA` |
| `deep_researcher.py::supervisor_tools` | 限制并发、`gather()` Researcher、将 compressed text 包装成 ToolMessage、聚合 raw_notes | Host materialize Task，接收/merge shadow TaskResult，隔离 per-task failure，并继续输出 legacy ToolMessage | 建立稳定 Parent ↔ Researcher contract，避免 Supervisor 依赖完整 ResearcherState | P2-S3 | `WORKTREE` |
| `deep_researcher.py::researcher` / `researcher_tools` | 运行隔离 Model–Tool–Observation loop | 在 local state 中累积 SourceRecord、EvidenceRecord、ResearchFinding | 分离 Process Artifacts 与 Evidence Artifacts | P2-S4 | `PLANNED` |
| `deep_researcher.py::compress_research` | 生成 compressed_research 和 raw_notes | P2-S3 生成 shadow TaskResult 并 legacy dual-write；P2-S4 再 population structured records | 先验证跨图合同，避免提前实现 Evidence extraction | P2-S3/P2-S4 | `WORKTREE / POPULATION PLANNED` |
| `deep_researcher.py::final_report_generation` | 从 notes 生成最终报告 | P2-S4 shadow 消费 structured Findings；P2-S5 接入 Claim/Citation contracts | 降低对混合 legacy text 的依赖，并支持可审计引用 | P2-S4/P2-S5 | `PLANNED` |
| `utils.py::tavily_search` / `tavily_search_async` | 调用 Tavily、按 URL 去重、总结网页、返回 formatted string | 增加 structured ingestion adapter，生成 Source/Evidence records 和 retrieval metadata；原文本路径保留 | Tavily 是首个 Evidence-native vertical slice 的已验证主路径 | P2-S4 | `PLANNED` |
| `utils.py::summarize_webpage` | 将 raw page content 压缩为 summary/key excerpts，失败时回退原文 | 保证 summary 与 source-derived excerpt 分层，禁止大 raw fallback 进入 Graph State | 执行 Artifact boundary，避免完整 HTML/PDF 或大型 payload 污染 State | P2-S4 | `PLANNED` |
| `utils.py::get_notes_from_tool_calls` | 收集所有 ToolMessage 内容作为 notes | 限定为 legacy compatibility；structured results 使用独立 contract/merge path | 避免把 reflection/error/任意 ToolMessage 当成 Evidence | P2-S4 | `PLANNED` |
| `src/open_deep_research/prompts.py` | 定义 generic clarify、brief、Supervisor、Researcher、compression、writer prompts | P2-S3 适配 MedicalResearchBrief/Task；structured Finding prompt 延后 P2-S4；invariants 由代码执行 | Prompt 表达语义目标，不能替代 schema、ID resolution 或 reducer enforcement | P2-S3/P2-S4 | `WORKTREE / FINDING PLANNED` |
| `tests/evaluators.py` | Final artifact eval；Groundedness 对 final_report + raw_notes 一次性判定 | 保留 V1，对照新增 Claim/Citation/Evidence-aware V2 pipeline | 拆分 Claim extraction、resolution、entailment、aggregation，消除粗粒度循环自证 | P2-S5 | `PLANNED` |
| `tests/run_evaluate.py` | 运行现有 evaluator 集合 | 加入 frozen fixtures、V1/V2 shadow experiment 和有效配置记录 | 为“改善”提供可重复实验依据 | P2-S5/P2-S6 | `PLANNED` |
| `tests/supervisor_parallel_evaluation.py` | 局部检查 Supervisor 产生的并发 Tool Calls 数量 | 作为 topology regression 保留，并补充 Task/Result merge contract tests | 确认 contract migration 未破坏 upstream agentic parallelism | P2-S4/P2-S6 | `PLANNED` |

### Planned New EvidenceFlow Components

已落地组件记录实际路径；其余条目继续只记录职责。

| Planned component | Responsibility | Phase | Status | Required evidence before status upgrade |
|---|---|---|---|---|
| [`domain_models.py`](src/open_deep_research/domain_models.py) | 承载 MedicalResearchBrief、MedicalResearchTask、Source/Evidence/Finding/TaskResult schemas | P2-S3 | `WORKTREE` | schema/provenance tests 已通过；commit pending |
| [`test_domain_models.py`](tests/test_domain_models.py)、[`test_state_contracts.py`](tests/test_state_contracts.py)、[`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py) | 验证 I1–I10、invalid references、merge/dedup、artifact exclusion、topology、compiled Researcher boundary 和 legacy coexistence | P2-S3 | `WORKTREE` | 24 deterministic tests pass；commit pending |
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
| `CLAIM-003` | “我设计了 MedicalResearchBrief，将 EvidenceNeed 保留为 nested domain object，并让 Supervisor 动态生成 MedicalResearchTask。” | `DESIGNED` | Contracts §3.1–§3.3 |
| `CLAIM-004` | “我设计了 Source → Evidence → Finding 的最小可追溯 contract，并定义了 stable identity/provenance invariants。” | `DESIGNED` | Contracts §3.4–§3.6、§6 |
| `CLAIM-005` | “我设计了 MedicalResearchTask → ResearchTaskResult 的跨图接口，使 Parent 不依赖 Researcher internal State。” | `DESIGNED` | Contracts §3.7、§5 |
| `CLAIM-006` | “我冻结候选了 Parent/Supervisor/Researcher State ownership、Artifact boundary 和并发 reducer 业务语义。” | `DESIGNED` | Contracts §4、§7 |
| `CLAIM-007` | “我设计了 legacy text 与 structured evidence 的 dual-write 迁移，避免一次破坏现有报告链路。” | `DESIGNED` | Contracts §8、Master Plan §9 |
| `CLAIM-008` | “我将 Claim/Citation 冻结推迟到 P2-S5，并把 Evidence Store/RAG 明确为 Future layer，控制首个 vertical slice 的范围。” | `DESIGNED` | Contracts §10、Master Plan §10–§11 |

当前工作树还为下列未来 claim 提供了源码和 deterministic test 证据，但在 closeout commit 前不得把它们
写入正式简历版本：

- “我实现了严格的 EvidenceFlow v1 domain schemas 和 provenance validators。”
- “我在不改变 Supervisor–Researcher topology 的前提下接通了 structured Brief、host-assigned Task 和
  shadow TaskResult。”
- “我实现了按 task identity 聚合、幂等 replay 和 conflicting replay rejection，并隔离并发 admission /
  execution failures。”

### Claims Not Yet Supported

在相应 contribution 升级为 `IMPLEMENTED` 或 `VALIDATED` 前，不得使用以下表述：

- “我已经提交并完成了 MedicalResearchBrief / MedicalResearchTask runtime。”（当前仅 worktree）
- “我实现了 evidence-native Tavily researcher。”
- “我实现了 ArtifactStore / Evidence Store / RAG。”
- “我实现了 Claim-level Groundedness V2。”
- “我的方案提升了 groundedness、citation accuracy、coverage 或 reliability。”
- “EvidenceFlow 已经支持生产级医学研究、完整 PubMed 或医学 RAG。”

当前允许的替代表述是：“已完成设计并形成通过 deterministic tests 的 implementation candidate；真实
runtime smoke、人工 review 和 closeout commit 尚未完成。”

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
| 2026-08-15 | `EF-P2S3-001`–`EF-P2S3-010` | strict domain models、State reducers、structured Brief/Task/shadow Result、legacy adapters、failure isolation | `src/open_deep_research/domain_models.py`; `state.py`; `deep_researcher.py`; `prompts.py`; `tests/test_*contract*`; `tests/test_p2_s3_runtime.py` | `UNCOMMITTED WORKTREE` | targeted `pytest`: 24 passed；Ruff pass；targeted mypy pass；bare repo pytest additionally hits pre-existing legacy option error | external endpoint timed out before Brief; no search call | `DESIGNED` + implementation candidate |
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
