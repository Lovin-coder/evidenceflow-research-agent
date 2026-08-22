# EvidenceFlow Contribution Map

## Document Purpose / Status

| Field | Value |
|---|---|
| Status | **Living Contribution Ledger** |
| Snapshot date | 2026-08-21 |
| Frozen upstream baseline | `20aaa0d422bd290c83f93574810ef1244e8d5955` |
| Current repository HEAD | `a87a1ddd8f2c1e04923798649e15d72e087d02cb`；P2-S4 implementation / closeout diff 尚未提交 |
| Current EvidenceFlow stage | **P2-S4 CLOSEOUT CANDIDATE / POST-REVIEW CORRECTED / DETERMINISTICALLY VALIDATED**；model、Tavily 与 structured executor smoke 已通过，single Researcher timeout；full graph 经人工授权跳过但仍记为未完成 |
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

P2-S3 当前状态：**IMPLEMENTED / VALIDATED / CLOSED**。Domain/State/runtime contract migration、accepted
Review triage、typed Thinking policy、regression tests 与 closeout documentation 已进入历史 commits；41 个
targeted tests 和 controlled real-model Brief → ConductResearch → Host Task smoke 已通过。

| Contribution ID | Original contribution | Current outcome | Status | Evidence |
|---|---|---|---|---|
| `EF-P2S3-001` | Medical planning contract | 严格 `MedicalResearchBrief` schema 已实现；runtime 直接 structured-output，并由 host renderer dual-write legacy brief | `VALIDATED` | [Contracts §3.1–3.2](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#31-medicalresearchbrief)；[`domain_models.py`](src/open_deep_research/domain_models.py)；[`write_research_brief`](src/open_deep_research/deep_researcher.py)；[smoke record](docs/plans/P2_S3_RETRO.md#33-controlled-real-model-smoke--pass) |
| `EF-P2S3-002` | EvidenceNeed placement | `EvidenceNeed` 仅作为 Brief/Task nested object；topology regression test 确认没有独立 channel/node | `VALIDATED` | [`domain_models.py`](src/open_deep_research/domain_models.py)；[`test_state_contracts.py`](tests/test_state_contracts.py) |
| `EF-P2S3-003` | Domain task contract | Host 从 structured `ConductResearch` envelope 构造 run-local Task ID，并保持 Supervisor 0/1/N 动态 delegation | `VALIDATED` | [`state.py`](src/open_deep_research/state.py)；[`materialize_medical_research_task`](src/open_deep_research/deep_researcher.py)；[`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py)；[smoke record](docs/plans/P2_S3_RETRO.md#33-controlled-real-model-smoke--pass) |
| `EF-P2S3-004` | Evidence data chain | P2-S3 实现严格 Source/Evidence/Finding schemas、normalized raw-metadata guard、compactness bounds 与 Researcher-local provenance validation；P2-S4 已继续实现真实 population 与 self-contained cross-boundary resolution | `VALIDATED` | [`domain_models.py`](src/open_deep_research/domain_models.py)；[`test_domain_models.py`](tests/test_domain_models.py)；[`test_p2_s4_runtime.py`](tests/test_p2_s4_runtime.py) |
| `EF-P2S3-005` | Cross-graph output | Researcher dual-write shadow `ResearchTaskResult` 与 legacy compression；publish gate 拒绝 invalid provenance；admission/execution failure 产生 task-correlated failed result | `VALIDATED` | [`compress_research`/`supervisor_tools`](src/open_deep_research/deep_researcher.py)；[`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py) |
| `EF-P2S3-006` | State schema | Parent/Supervisor/Researcher structured channels 已映射；Researcher output 只投影 Result 和 legacy outputs | `VALIDATED` | [`state.py`](src/open_deep_research/state.py)；[`test_state_contracts.py`](tests/test_state_contracts.py) |
| `EF-P2S3-007` | Artifact boundary | structured contracts 拒绝 normalized content-bearing metadata keys，并对 metadata serialized total 与 Evidence excerpt 执行 8000-character runtime compactness guards；legacy raw-notes fallback 保持临时例外 | `VALIDATED` | [Contracts §4.4](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#44-artifact-boundary)；[`test_domain_models.py`](tests/test_domain_models.py) |
| `EF-P2S3-008` | Identity/provenance rules | I1–I10、local publication validation、ID/reference/process-artifact/derived-field invariants 均有 deterministic tests | `VALIDATED` | [Contracts §6](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#6-identity--provenance-invariants)；[`test_domain_models.py`](tests/test_domain_models.py)；[`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py) |
| `EF-P2S3-009` | Concurrent update semantics | ID-aware reducers 保留 distinct results，dedup identical replay，并拒绝相同 ID 的 conflicting payload | `VALIDATED` | [`state.py`](src/open_deep_research/state.py)；[`test_state_contracts.py`](tests/test_state_contracts.py) |
| `EF-P2S3-010` | Migration/versioning | contract constant、deterministic Markdown adapters、structured+legacy 同执行 dual-write 和迁移例外已实现并记录 | `VALIDATED` | [`domain_models.py`](src/open_deep_research/domain_models.py)；[`deep_researcher.py`](src/open_deep_research/deep_researcher.py)；[Contracts §8–§10](docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md#8-legacy-compatibility) |
| `EF-P2S3-011` | Typed research-model Thinking policy | `bool | None` typed setting 在 model boundary 最小映射为 provider `extra_body.enable_thinking`；`None` 保留 provider default，任意 runtime `extra_body` 无法绕过 typed boundary | `VALIDATED` | [`configuration.py`](src/open_deep_research/configuration.py)；[`deep_researcher.py`](src/open_deep_research/deep_researcher.py)；[`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py)；[smoke record](docs/plans/P2_S3_RETRO.md#33-controlled-real-model-smoke--pass) |

### P2-S4 — Evidence-native Researcher

P2-S4 当前状态：`CLOSEOUT CANDIDATE / POST-REVIEW CORRECTED / DETERMINISTICALLY VALIDATED`。72 个项目主测试覆盖 frozen
Source/Evidence ingestion、D15 self-contained Result、Publication Gate、failure preservation、run-scoped
Artifact identity、structured execution issues 与 provenance admission；外部 structured executor 已通过，
但 single Researcher 超时；full graph 经人工授权在本次 closeout 跳过并继续记为未完成，不能声称完整
real-provider runtime 已验证。

| Contribution ID | EvidenceFlow work | Actual outcome | Status | Implementation evidence |
|---|---|---|---|---|
| `EF-P2S4-001` | Tavily structured ingestion | usable `raw_content` 经确定性 normalize/chunk、LLM Candidate-ID selection 与 Host Evidence materialization，输出 `SearchExecutionResult` 双通道 | `VALIDATED` | [`utils.py`](src/open_deep_research/utils.py)；[`evidence_ingestion.py`](src/open_deep_research/evidence_ingestion.py)；[`test_tavily_evidence_search.py`](tests/test_tavily_evidence_search.py) |
| `EF-P2S4-002` | Evidence-native D15 Result | `ResearchTaskResult` inline compact Source/Evidence ledger，并保留 exact ordered ID projections；Publication Gate 拒绝 dangling references | `VALIDATED` | [`domain_models.py`](src/open_deep_research/domain_models.py)；[`deep_researcher.py`](src/open_deep_research/deep_researcher.py)；[`test_domain_models.py`](tests/test_domain_models.py) |
| `EF-P2S4-003` | Provenance-preserving compression | structured compression 仅引用已有 Evidence IDs；invalid Finding batch 原子拒绝并保全 Source/Evidence；真正 provenance failure 仍由 Gate 拒绝 | `VALIDATED` | [`deep_researcher.py`](src/open_deep_research/deep_researcher.py)；[`prompts.py`](src/open_deep_research/prompts.py)；[`test_p2_s4_runtime.py`](tests/test_p2_s4_runtime.py) |
| `EF-P2S4-004` | Data Plane / Model Context separation | 同一次 Search/Compression dual-write；bounded structured execution issue 与 sticky Host failure fact 决定 status，不扫描 ToolMessage 文本 | `VALIDATED` | [`state.py`](src/open_deep_research/state.py)；[`utils.py`](src/open_deep_research/utils.py)；[`deep_researcher.py`](src/open_deep_research/deep_researcher.py)；[`test_p2_s4_runtime.py`](tests/test_p2_s4_runtime.py) |
| `EF-P2S4-005` | Minimal ArtifactStore | owning-run ID 由显式 override、root runtime ID 或 UUID bootstrap，并经内部 State 跨 Supervisor/Researcher 迭代传递；相同 thread 的独立 run 默认隔离 | `VALIDATED` | [`artifact_store.py`](src/open_deep_research/artifact_store.py)；[`state.py`](src/open_deep_research/state.py)；[`deep_researcher.py`](src/open_deep_research/deep_researcher.py)；[`test_p2_s4_runtime.py`](tests/test_p2_s4_runtime.py) |
| `EF-P2S4-006` | Deterministic provenance capacity | Domain、State admission 与 Publication Gate 共用 canonical serialized-size measurement；溢出记录 structured issue 并保留合法有序前缀 | `VALIDATED` | [`domain_models.py`](src/open_deep_research/domain_models.py)；[`deep_researcher.py`](src/open_deep_research/deep_researcher.py)；[`test_domain_models.py`](tests/test_domain_models.py)；[`test_p2_s4_runtime.py`](tests/test_p2_s4_runtime.py) |

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

P2-S3 core runtime 已进入历史 commit；当前 worktree 在 frozen P2-S4 design HEAD 上包含尚未提交的 S4
implementation 与 closeout。下表只记录有源码和测试证据的实际行为。

| File | Baseline responsibility | EvidenceFlow modification | Reason | Evidence state |
|---|---|---|---|---|
| [`configuration.py`](src/open_deep_research/configuration.py) | typed application runtime configuration | typed model policy、Artifact override/bounds，并拒绝小于 empty provenance envelope 的配置 | 保持可发布 Result 的配置下限与 narrow runtime boundary | `IMPLEMENTED / VALIDATED`; closeout diff pending |
| [`domain_models.py`](src/open_deep_research/domain_models.py) | upstream 无领域合同模块 | v1 contracts、compactness/provenance validators 与 canonical Result provenance measurement | 将领域对象与 Process State 分离，并统一 admission/Gate 度量 | `IMPLEMENTED / VALIDATED`; closeout diff pending |
| [`state.py`](src/open_deep_research/state.py) | generic tool schemas 与 Parent/Supervisor/Researcher State | typed channels、ID reducers、internal artifact run identity、bounded execution issue ledger 与 sticky failure reducer | 最小映射 frozen State/update/status semantics | `IMPLEMENTED / VALIDATED`; corrective evidence added |
| [`deep_researcher.py`](src/open_deep_research/deep_researcher.py) | brief、delegation、Researcher loop、compression、final writer | run identity propagation、deterministic admission、structured status、Finding failure taxonomy、publication/failure isolation | 建立真实 Task → Result boundary且保留原拓扑 | `IMPLEMENTED / VALIDATED`; corrective evidence added |
| [`prompts.py`](src/open_deep_research/prompts.py) | generic brief/Supervisor/Researcher prompts | 对齐 MedicalResearchBrief 和 structured delegation semantics | 防止 prompt/schema drift | `IMPLEMENTED / VALIDATED` |
| [`test_domain_models.py`](tests/test_domain_models.py) | 无 deterministic contract tests | strict schema、status、provenance、raw/process artifact 与 compactness boundary tests | 将 I1–I10 与 runtime guards 转成回归检查 | `VALIDATED`; closeout diff pending |
| [`test_state_contracts.py`](tests/test_state_contracts.py) | 无 deterministic State tests | reducer replay/conflict、channel 和 frozen topology tests | 验证 State freeze 未改拓扑 | `VALIDATED` |
| [`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py) | 无 deterministic runtime contract tests | brief dual-write、task identity、0/1/N、failure isolation、publish gate、Thinking policy/bypass tests | 验证真实 adapter functions；外部调用只在独立 controlled smoke 中进行 | `VALIDATED`; closeout diff pending |
| [`artifact_store.py`](src/open_deep_research/artifact_store.py) | upstream 无 Source artifact store | 新增 run-scoped Store，并以 pure resolver 接收 State-carried owning-run ID；不依赖 config mutation/thread ID | 让 exact normalized artifact 保持在 Graph State 外并支持跨节点/Researcher replay | `IMPLEMENTED / VALIDATED`; uncommitted |
| [`evidence_ingestion.py`](src/open_deep_research/evidence_ingestion.py) | upstream 无确定性 Evidence ingestion core | normalize、paragraph-first chunk、structured selection validation、Host IDs/locator/hash/materialization 与 model renderer | 建立 Candidate/Evidence trust boundary | `IMPLEMENTED / VALIDATED`; uncommitted |
| [`utils.py`](src/open_deep_research/utils.py) | Tavily formatted-string search | structured Tavily executor、bounded typed issues、per-result failure isolation、bounded model projection、agent-visible Tool compatibility | 分离 Data Plane、Host control facts 与 Model Context | `IMPLEMENTED / VALIDATED`; uncommitted |
| [`test_evidence_ingestion.py`](tests/test_evidence_ingestion.py)、[`test_tavily_evidence_search.py`](tests/test_tavily_evidence_search.py)、[`test_p2_s4_runtime.py`](tests/test_p2_s4_runtime.py) | upstream 无 S4 deterministic suite | ingestion boundaries、four corrective regressions、compiled child boundary 与 full fixture chain | 冻结 S4 correctness without network/LLM | `VALIDATED`; uncommitted |

### Planned Upstream Touchpoints

下表同时保留已触达和后续计划，以便继续追踪 upstream responsibility。

| Upstream file / component | Baseline responsibility | Planned EvidenceFlow modification | Reason | Phase | Current status |
|---|---|---|---|---|---|
| `src/open_deep_research/state.py` | 定义 ConductResearch、ResearchQuestion、Agent/Supervisor/Researcher State 和 legacy output | 引用 v1 domain contracts；将 Parent/Supervisor/Researcher logical channels 映射到冻结 State semantics | 让 Task、Source、Evidence、Finding、TaskResult 成为一等公民，同时保留 legacy channels | P2-S3 | `IMPLEMENTED / VALIDATED` |
| `deep_researcher.py::write_research_brief` | 生成 generic `research_brief: str` | 生成 schema-valid MedicalResearchBrief，并由 deterministic renderer dual-write legacy brief | 将医学语义从 prompt-only 文本升级为稳定 domain input | P2-S3 | `IMPLEMENTED / VALIDATED` |
| `deep_researcher.py::supervisor` | 根据 brief/messages 动态产生 ConductResearch calls | 继续原算法并绑定升级后的 structured tool schema；未修改 planning loop | 显式化 task semantics，不破坏 upstream agentic behavior | P2-S3 | `PRESERVED / VALIDATED SCHEMA` |
| `deep_researcher.py::supervisor_tools` | 限制并发、`gather()` Researcher、将 compressed text 包装成 ToolMessage、聚合 raw_notes | Host materialize Task，接收/merge shadow TaskResult，隔离 per-task failure，并继续输出 legacy ToolMessage | 建立稳定 Parent ↔ Researcher contract，避免 Supervisor 依赖完整 ResearcherState | P2-S3 | `IMPLEMENTED / VALIDATED` |
| `deep_researcher.py::researcher` / `researcher_tools` | 运行隔离 Model–Tool–Observation loop | Tavily structured results 直接写入 Researcher Source/Evidence channels；非 Tavily path 保持 generic execution | 分离 Process Artifacts 与 Evidence Artifacts | P2-S4 | `IMPLEMENTED / VALIDATED` |
| `deep_researcher.py::compress_research` | 生成 compressed_research 和 raw_notes | structured compression materialize Findings，assemble self-contained Result 并 legacy dual-write | 保留 Evidence IDs 通过 compression/publication | P2-S3/P2-S4 | `IMPLEMENTED / VALIDATED` |
| `deep_researcher.py::final_report_generation` | 从 notes 生成最终报告 | 继续消费 Supervisor bounded Result projections；P2-S5 才接入 Claim/Citation contracts | 保留 legacy final writer，不在 S4 重构 | P2-S4/P2-S5 | `PRESERVED / DETERMINISTIC REGRESSION` |
| `utils.py::tavily_search` / `tavily_search_async` | 调用 Tavily、按 URL 去重、总结网页、返回 formatted string | agent-visible wrapper 保持 schema，内部返回 structured `SearchExecutionResult` 并投影 bounded text | Tavily 是首个 Evidence-native vertical slice | P2-S4 | `IMPLEMENTED / VALIDATED` |
| `utils.py::summarize_webpage` | 将 raw page content 压缩为 summary/key excerpts，失败时回退原文 | structured path 改用 Candidate selection；legacy helper 失败不再回退 raw content | 防止大型 raw fallback 进入 model/state path | P2-S4 | `IMPLEMENTED / VALIDATED` |
| `utils.py::get_notes_from_tool_calls` | 收集所有 ToolMessage 内容作为 notes | 保持 legacy compatibility；structured records 始终走独立 State/Result path | 不把任意 ToolMessage 当作 Evidence | P2-S4 | `PRESERVED / VALIDATED BY INTEGRATION` |
| `src/open_deep_research/prompts.py` | 定义 generic clarify、brief、Supervisor、Researcher、compression、writer prompts | 新增 Candidate-ID selector 与 structured Finding compression semantics；Host 继续执行 invariants | Prompt 只拥有 semantic selection/synthesis | P2-S3/P2-S4 | `IMPLEMENTED / VALIDATED` |
| `tests/evaluators.py` | Final artifact eval；Groundedness 对 final_report + raw_notes 一次性判定 | 保留 V1，对照新增 Claim/Citation/Evidence-aware V2 pipeline | 拆分 Claim extraction、resolution、entailment、aggregation，消除粗粒度循环自证 | P2-S5 | `PLANNED` |
| `tests/run_evaluate.py` | 运行现有 evaluator 集合 | 加入 frozen fixtures、V1/V2 shadow experiment 和有效配置记录 | 为“改善”提供可重复实验依据 | P2-S5/P2-S6 | `PLANNED` |
| `tests/supervisor_parallel_evaluation.py` | 局部检查 Supervisor 产生的并发 Tool Calls 数量 | 作为 topology regression 保留，并补充 Task/Result merge contract tests | 确认 contract migration 未破坏 upstream agentic parallelism | P2-S4/P2-S6 | `PLANNED` |

### Planned New EvidenceFlow Components

已落地组件记录实际路径；其余条目继续只记录职责。

| Planned component | Responsibility | Phase | Status | Required evidence before status upgrade |
|---|---|---|---|---|
| [`domain_models.py`](src/open_deep_research/domain_models.py) | 承载 MedicalResearchBrief、MedicalResearchTask、Source/Evidence/Finding/TaskResult schemas | P2-S3 | `IMPLEMENTED / VALIDATED` | P2-S3 commits `ab34591`、`624c25d`、`13d6abf`；当前另有尚未提交的 S4 carrier/bound corrections |
| [`test_domain_models.py`](tests/test_domain_models.py)、[`test_state_contracts.py`](tests/test_state_contracts.py)、[`test_p2_s3_runtime.py`](tests/test_p2_s3_runtime.py) | 验证 I1–I10、invalid references、merge/dedup、artifact exclusion、topology、compiled Researcher boundary、Thinking policy 和 legacy coexistence | P2-S3 | `VALIDATED` | P2-S3 closeout 已提交；当前另有尚未提交的 S4 regressions |
| [`evidence_ingestion.py`](src/open_deep_research/evidence_ingestion.py)、`utils.py::execute_tavily_search_structured` | 将 usable provider results 映射为 SourceRecord/EvidenceRecord 与 bounded projection | P2-S4 | `IMPLEMENTED / VALIDATED` | frozen provider fixtures、exact provenance、failure tests |
| [`artifact_store.py`](src/open_deep_research/artifact_store.py) | 保存 exact normalized artifacts，Graph State 只携带 opaque `artifact_ref` | P2-S4 | `IMPLEMENTED / VALIDATED` | run-scope、round-trip、compiled boundary tests |
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
| `CLAIM-005` | “我实现了 MedicalResearchTask → ResearchTaskResult 的跨图 contract boundary，使 Parent 不依赖 Researcher internal State。” | `VALIDATED` | Contracts §3.7/§5、P2-S3 shadow tests 与 P2-S4 populated D15 boundary tests |
| `CLAIM-006` | “我实现并验证了 Parent/Supervisor/Researcher State ownership 与按 ID 幂等/冲突拒绝的 reducer 语义。” | `VALIDATED` | Contracts §4/§7、state contract tests |
| `CLAIM-007` | “我实现了 legacy text 与 structured contracts 的 dual-write 迁移，并通过真实模型 smoke 验证 Brief → Tool Call → Host Task 路径。” | `VALIDATED` | Contracts §8、runtime tests、P2-S3 Retro smoke record |
| `CLAIM-008` | “我将 Claim/Citation 冻结推迟到 P2-S5，并把 Evidence Store/RAG 明确为 Future layer，控制首个 vertical slice 的范围。” | `DESIGNED` | Contracts §10、Master Plan §10–§11 |
| `CLAIM-009` | “我用 typed nullable policy 控制 Qwen research-model Thinking，保持 provider default，并阻止 arbitrary extra_body 绕过配置边界。” | `VALIDATED` | `configuration.py`、model-boundary tests、controlled smoke provider observation |
| `CLAIM-010` | “我实现了 Tavily Evidence-native 双通道：usable raw content 外置为 run-scoped artifact，Host 生成 exact locator/hash Evidence，模型只选择 Candidate IDs。” | `VALIDATED (deterministic + staged external)` | `evidence_ingestion.py`、`utils.py`、S4 deterministic tests；real Tavily 与 structured executor smoke 通过，compiled Researcher/full graph 未完成 |
| `CLAIM-011` | “我实现了 self-contained ResearchTaskResult D15 carrier 与 Publication Gate，使 Source/Evidence/Finding 引用在 compiled Researcher 边界后仍可解析，同时 Supervisor 只观察有界 Finding projection。” | `VALIDATED (deterministic)` | Contracts/D15、`domain_models.py`、`deep_researcher.py`、compiled boundary integration test |

上述 P2-S3/P2-S4 implementation claims 已由历史 commits、当前 S4 closeout diff、deterministic tests 与
controlled/staged smoke 支撑。真实 Source/Evidence population 与 deterministic cross-boundary resolver 已在
P2-S4 实现；引用时仍需说明 compiled Researcher/full-graph real runtime 尚未完成，以及 finalization boundary
之外的 hard child exception 仍没有 checkpoint/state-aware recovery。

### Claims Not Yet Supported

在相应 contribution 升级为 `IMPLEMENTED` 或 `VALIDATED` 前，不得使用以下表述：

- “我已通过真实 provider smoke 验证完整 evidence-native Tavily runtime。”
- “我实现了 durable EvidenceStore / RAG / Vector Index。”
- “我实现了 Claim-level Groundedness V2。”
- “我的方案提升了 groundedness、citation accuracy、coverage 或 reliability。”
- “EvidenceFlow 已经支持生产级医学研究、完整 PubMed 或医学 RAG。”

不得将 P2-S4 deterministic validation 外推为真实 provider reliability、P2-S5/P2-S6 能力或医学质量提升。

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
| 2026-08-19 | `EF-P2S4-001`–`EF-P2S4-005` | deterministic ingestion、ArtifactStore、dual-channel search、structured compression、D15 Result 与 Publication Gate | `artifact_store.py`; `evidence_ingestion.py`; `domain_models.py`; `utils.py`; `deep_researcher.py`; S4 tests/docs | `UNCOMMITTED` | project tests 65 passed；targeted Ruff、7-file scoped mypy、compileall、`git diff --check` pass | real smoke attempt 1 blocked by SOCKS dependency；attempt 2 externally stalled and was terminated without final state | `IMPLEMENTED / DETERMINISTICALLY VALIDATED` |
| 2026-08-14 | Contribution ledger | 创建并更新 upstream attribution 与 resume claim ledger | `CONTRIBUTION_MAP.md` | `4af35e3` + worktree sync | document review | N/A | `DESIGNED` |
| 2026-08-20 | `EF-P2S4-003`–`EF-P2S4-006` | post-review correction：owning-run Artifact identity、Finding failure preservation、structured issues/status、deterministic provenance admission | `artifact_store.py`; `state.py`; `domain_models.py`; `utils.py`; `deep_researcher.py`; corrective tests/docs | `UNCOMMITTED` | project tests 72 passed；targeted Ruff、7-file scoped mypy、compileall、`git diff --check` pass | model/Tavily endpoints 与 structured executor pass；single Researcher 60s timeout；full graph not attempted | `POST-REVIEW CORRECTED / DETERMINISTICALLY VALIDATED` |

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
| 2026-08-19 | 记录 P2-S4 implementation、65-test deterministic validation、D15 cross-boundary carrier 与 environment-blocked real smoke |
| 2026-08-21 | 校准 P2-S3/S4 陈旧声明与 S4 runtime evidence：structured executor 已通过，single Researcher timeout，full graph 经人工授权跳过但保持未完成 |
