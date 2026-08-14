# EvidenceFlow Contribution Map

## Document Purpose / Status

| Field | Value |
|---|---|
| Status | **Living Contribution Ledger** |
| Snapshot date | 2026-08-14 |
| Current code baseline | `20aaa0d422bd290c83f93574810ef1244e8d5955` |
| Current EvidenceFlow stage | P2-S3 design freeze candidate；implementation not started |
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
| Verification | 当前 `HEAD` 与 frozen commit 完全一致；工作树只有未跟踪的 `docs/` 设计产物 |

Attribution rule：该 commit 已存在的 Agent topology、search、compression、final writer、state/reducer
和 evaluation harness 均记为 `UPSTREAM`。EvidenceFlow 可以说明“复用并保留”这些机制，不能将其描述为
原创实现。EvidenceFlow 的贡献从 baseline 核验、问题定义、contract-first redesign 和后续可定位 diff
开始计算。

Primary baseline evidence：

- [`src/open_deep_research/state.py`](../src/open_deep_research/state.py)
- [`src/open_deep_research/deep_researcher.py`](../src/open_deep_research/deep_researcher.py)
- [`src/open_deep_research/utils.py`](../src/open_deep_research/utils.py)
- [`tests/evaluators.py`](../tests/evaluators.py)
- [`notes/p2_s2/closeout/P2_S2_CLOSEOUT.md`](../notes/p2_s2/closeout/P2_S2_CLOSEOUT.md)

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
| Clarify / Brief / Supervisor / Researcher / Compression / Final Writer | [`deep_researcher.py`](../src/open_deep_research/deep_researcher.py) |
| Baseline schemas and State | [`state.py`](../src/open_deep_research/state.py) |
| Tavily, provider tools, webpage summarization, legacy notes extraction | [`utils.py`](../src/open_deep_research/utils.py) |
| Final artifact and Groundedness evaluators | [`evaluators.py`](../tests/evaluators.py) |
| Supervisor parallelism prototype | [`supervisor_parallel_evaluation.py`](../tests/supervisor_parallel_evaluation.py) |

## EvidenceFlow Original Work

### Cross-phase Architecture Design

| Contribution ID | Original contribution | Status | Evidence |
|---|---|---|---|
| `EF-DES-001` | 将 baseline 限制收敛为 Task/Runtime Explicitness、Text-centric Evidence、Evaluation Granularity、Domain Adaptation 四类 | `DESIGNED` | [Master Plan §3](application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#3-four-baseline-limitation-categories) |
| `EF-DES-002` | 定义三个核心 Track：Domain-aware Medical Planning、Evidence-native Research Pipeline、Claim-level Grounding/Evaluation | `DESIGNED` | [Master Plan §5](application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#5-three-improvement-tracks) |
| `EF-DES-003` | 决定首版保留 Agentic Supervisor–Researcher Tool Loop，不迁移 Plan + Send、RAG 或 Durable Queue | `DESIGNED` | [Master Plan §5/§10](application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#5-three-improvement-tracks) |
| `EF-DES-004` | 将 P2-S3～P2-S6 拆为 contracts、evidence-native researcher、claim grounding、evaluation/reliability 四阶段 | `DESIGNED` | [Master Plan §11](application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#11-p2-s3p2-s6-roadmap) |

这些条目证明的是 architecture/design work，不证明相关 runtime 已经实现。

### P2-S2 — Baseline Verification / Problem Framing

| Contribution ID | Original contribution | Status | Evidence |
|---|---|---|---|
| `EF-VER-001` | 对 frozen upstream 的主图、Supervisor、Researcher、并发、Compression 和 State 数据流做源码级核验 | `VERIFIED` | [`notes/p2_s2/source/`](../notes/p2_s2/source/)；[`P2_S2_CLOSEOUT.md`](../notes/p2_s2/closeout/P2_S2_CLOSEOUT.md) |
| `EF-VER-002` | 核验 `notes` 与 `raw_notes` 是不同路径，Final Writer 主要消费 `notes` | `VERIFIED` | [`04_supervisor_researcher_deep_dive.md`](../notes/p2_s2/source/04_supervisor_researcher_deep_dive.md) |
| `EF-VER-003` | 定位现有 Groundedness 使用混合 `raw_notes`、存在 AIMessage 循环自证与粒度不足的问题 | `VERIFIED` | [`07_evaluation_harness.md`](../notes/p2_s2/source/07_evaluation_harness.md)；[`groundedness_evidence_harness.md`](../notes/p2_s2/improvements/groundedness_evidence_harness.md) |

### P2-S3 — Domain & Evidence Contracts

P2-S3 当前状态：`DESIGNED / FREEZE CANDIDATE`，尚无 `src/` 或 `tests/` 实现 diff。

| Contribution ID | Original contribution | Frozen design outcome | Status | Evidence |
|---|---|---|---|---|
| `EF-P2S3-001` | Medical planning contract | 用 `MedicalResearchBrief` 聚合 normalized question、question type、clinical elements/PICO、constraints、intent 和 nested evidence needs | `DESIGNED` | [Contracts §3.1–3.2](evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md#31-medicalresearchbrief) |
| `EF-P2S3-002` | EvidenceNeed placement | 保留 EvidenceNeed 领域语义，但不新增独立 Graph Stage | `DESIGNED` | [Contracts §3.2](evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md#32-evidenceneed) |
| `EF-P2S3-003` | Domain task contract | 定义具有 stable `task_id` 的 `MedicalResearchTask`，与 runtime `tool_call_id` 分离 | `DESIGNED` | [Contracts §3.3](evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md#33-medicalresearchtask) |
| `EF-P2S3-004` | Evidence data chain | 冻结最小 `SourceRecord`、`EvidenceRecord` 和 `ResearchFinding` 职责与字段 | `DESIGNED` | [Contracts §3.4–3.6](evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md#34-sourcerecord) |
| `EF-P2S3-005` | Cross-graph output | 新增 topology-neutral `ResearchTaskResult`，使 Parent 不依赖完整 ResearcherState | `DESIGNED` | [Contracts §3.7/§5](evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md#37-researchtaskresult) |
| `EF-P2S3-006` | State schema | 冻结 Parent、Supervisor、Researcher-local 的逻辑 State ownership 和最小 channel | `DESIGNED` | [Contracts §4](evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md#4-state-boundaries) |
| `EF-P2S3-007` | Artifact boundary | 禁止 Graph State 持久化完整 HTML/PDF、binary、完整大型 provider payload 或 immutable snapshots | `DESIGNED` | [Contracts §4.4](evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md#44-artifact-boundary) |
| `EF-P2S3-008` | Identity/provenance rules | 冻结 I1–I8：stable IDs、引用可解析、AIMessage 非 Evidence、locator+hash 可审计、跨图隔离和 dual-write | `DESIGNED` | [Contracts §6](evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md#6-identity--provenance-invariants) |
| `EF-P2S3-009` | Concurrent update semantics | 冻结 replace、append/merge、append/dedup 业务语义，禁止并发 ResearchTaskResult whole-channel overwrite | `DESIGNED` | [Contracts §7](evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md#7-reducer--update-semantics) |
| `EF-P2S3-010` | Migration/versioning | 定义 legacy dual-write、breaking changes、contract version 和 deferred contracts | `DESIGNED` | [Contracts §8–§10](evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md#8-legacy-compatibility) |

### P2-S4 — Evidence-native Researcher

P2-S4 当前状态：`PLANNED`。以下是已在 Master Plan/Contracts 中划定的实现目标，不得在完成代码和测试前
写成“已实现”。

| Contribution ID | Planned EvidenceFlow work | Intended outcome | Status | Design evidence |
|---|---|---|---|---|
| `EF-P2S4-001` | Tavily structured ingestion | 将 formatted search text 同步投影为 SourceRecord/EvidenceRecord，保留 stable IDs 与 provenance | `PLANNED` | [Master Plan §5 Track B](application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#track-b--evidence-native-research-pipeline) |
| `EF-P2S4-002` | Evidence-native Researcher output | Researcher 生成 ResearchFinding 和 ResearchTaskResult，Supervisor 消费 bounded structured result | `PLANNED` | [Contracts §3.6–§5](evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md#36-researchfinding) |
| `EF-P2S4-003` | Provenance through compression | Source/Evidence IDs 穿过 compression 和 Supervisor observation boundary | `PLANNED` | [Contracts I1–I8](evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md#6-identity--provenance-invariants) |
| `EF-P2S4-004` | Legacy dual-write | structured ledger 与 `raw_notes`/`notes`/`compressed_research` 并存，旧报告继续生成 | `PLANNED` | [Contracts §8](evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md#8-legacy-compatibility) |
| `EF-P2S4-005` | Minimal Artifact Store | 实现 `ArtifactStore Protocol → LocalArtifactStore`；Graph State 只保留 opaque `artifact_ref` | `PLANNED` | [Contracts §4.4/§10](evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md#44-artifact-boundary) |

### P2-S5 — Claim–Evidence Grounding

P2-S5 当前状态：`PLANNED`。P2-S3 只保留完整目标链中的位置，不冻结其全部实现细节。

| Contribution ID | Planned EvidenceFlow work | Intended outcome | Status | Design evidence |
|---|---|---|---|---|
| `EF-P2S5-001` | Claim contracts | 冻结 ClaimRecord、EvidenceSupport/ClaimEvidenceLink 和 Citation representation | `PLANNED` | [Master Plan §7/§11](application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#7-key-domain-contracts) |
| `EF-P2S5-002` | Groundedness V2 | 分离 Claim Extraction、deterministic Citation Resolution、Entailment、Materiality Aggregation | `PLANNED` | [Master Plan Track C](application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#track-c--claim-level-grounding--evaluation) |
| `EF-P2S5-003` | Metric separation | 独立衡量 Claim Groundedness、Citation Correctness、Citation Completeness 和 Factual Correctness | `PLANNED` | [Master Plan Track C](application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#track-c--claim-level-grounding--evaluation) |
| `EF-P2S5-004` | Shadow comparison | Groundedness V1/V2 并行评估，保留旧 evaluator 作为对照 | `PLANNED` | [Master Plan §11](application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#11-p2-s3p2-s6-roadmap) |

### P2-S6 — Evaluation & Reliability

| Contribution ID | Planned EvidenceFlow work | Intended outcome | Status | Design evidence |
|---|---|---|---|---|
| `EF-P2S6-001` | Frozen regression fixtures | 对 contract、citation、support/contradiction 和 failure cases 做可重复回归 | `PLANNED` | [Master Plan §9/§11](application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#9-mvp-scope) |
| `EF-P2S6-002` | Judge calibration / hard gates | 基于人工校准数据确定阈值，不在设计阶段臆定 release threshold | `PLANNED` | [Master Plan §12/§13](application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#12-acceptance-criteria) |
| `EF-P2S6-003` | Partial-failure observability | 在既有三条 Track 内改善 per-task result/error 的可见性 | `PLANNED` | [Master Plan §11](application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md#11-p2-s3p2-s6-roadmap) |

## Modified Upstream Components

### Current Actual Modifications

截至本快照，`src/` 与 `tests/` 相对 frozen upstream commit 没有修改。不能声称已经实现 domain contracts、
evidence-native researcher、Artifact Store 或 Claim Grounding。

当前原创文件只有设计/归属文档，且尚未进入 Git commit：

| File | Contribution | Status | Commit / PR |
|---|---|---|---|
| [`docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md`](application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md) | Improvement Master Plan、三条 Track、phase boundary、MVP/non-goals | `DESIGNED` | `UNCOMMITTED` |
| [`docs/evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md`](evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md) | P2-S3 domain/state/boundary/invariant/reducer contracts | `DESIGNED` | `UNCOMMITTED` |
| [`docs/CONTRIBUTION_MAP.md`](CONTRIBUTION_MAP.md) | Upstream attribution 与 claim-to-evidence ledger | `DESIGNED` | `UNCOMMITTED` |

### Planned Upstream Touchpoints

下表是实现阶段的 traceability map，不代表文件已经修改。实际 diff 出现后，必须追加 commit、tests 和
validation evidence；若最终选择新模块而非修改原文件，也要更新“实际落点”。

| Upstream file / component | Baseline responsibility | Planned EvidenceFlow modification | Reason | Phase | Current status |
|---|---|---|---|---|---|
| `src/open_deep_research/state.py` | 定义 ConductResearch、ResearchQuestion、Agent/Supervisor/Researcher State 和 legacy output | 引入或引用 v1 domain contracts；将 Parent/Supervisor/Researcher logical channels 映射到冻结 State semantics | 让 Task、Source、Evidence、Finding、TaskResult 成为一等公民，同时保留 legacy channels | P2-S3/P2-S4 | `PLANNED` |
| `deep_researcher.py::write_research_brief` | 生成 generic `research_brief: str` | 生成 schema-valid MedicalResearchBrief，并 dual-write/适配旧 brief 文本 | 将医学语义从 prompt-only 文本升级为稳定 domain input | P2-S3 | `PLANNED` |
| `deep_researcher.py::supervisor` | 根据 brief/messages 动态产生 ConductResearch calls | 让 delegation 携带 MedicalResearchTask；保留 Agentic re-planning 和现有 Tool Loop | 显式化 task identity/constraints，不破坏 upstream 拓扑 | P2-S3/P2-S4 | `PLANNED` |
| `deep_researcher.py::supervisor_tools` | 限制并发、`gather()` Researcher、将 compressed text 包装成 ToolMessage、聚合 raw_notes | 将 Task 投影到 Researcher input，接收/merge ResearchTaskResult，并继续输出 legacy ToolMessage | 建立稳定 Parent ↔ Researcher contract，避免 Supervisor 依赖完整 ResearcherState | P2-S4 | `PLANNED` |
| `deep_researcher.py::researcher` / `researcher_tools` | 运行隔离 Model–Tool–Observation loop | 在 local state 中累积 SourceRecord、EvidenceRecord、ResearchFinding | 分离 Process Artifacts 与 Evidence Artifacts | P2-S4 | `PLANNED` |
| `deep_researcher.py::compress_research` | 生成 compressed_research 和 raw_notes | 生成 ResearchTaskResult.summary/findings/IDs，同时 legacy dual-write | 让 provenance 穿过 compression，而不是只返回无身份文本 | P2-S4 | `PLANNED` |
| `deep_researcher.py::final_report_generation` | 从 notes 生成最终报告 | P2-S4 shadow 消费 structured Findings；P2-S5 接入 Claim/Citation contracts | 降低对混合 legacy text 的依赖，并支持可审计引用 | P2-S4/P2-S5 | `PLANNED` |
| `utils.py::tavily_search` / `tavily_search_async` | 调用 Tavily、按 URL 去重、总结网页、返回 formatted string | 增加 structured ingestion adapter，生成 Source/Evidence records 和 retrieval metadata；原文本路径保留 | Tavily 是首个 Evidence-native vertical slice 的已验证主路径 | P2-S4 | `PLANNED` |
| `utils.py::summarize_webpage` | 将 raw page content 压缩为 summary/key excerpts，失败时回退原文 | 保证 summary 与 source-derived excerpt 分层，禁止大 raw fallback 进入 Graph State | 执行 Artifact boundary，避免完整 HTML/PDF 或大型 payload 污染 State | P2-S4 | `PLANNED` |
| `utils.py::get_notes_from_tool_calls` | 收集所有 ToolMessage 内容作为 notes | 限定为 legacy compatibility；structured results 使用独立 contract/merge path | 避免把 reflection/error/任意 ToolMessage 当成 Evidence | P2-S4 | `PLANNED` |
| `src/open_deep_research/prompts.py` | 定义 generic clarify、brief、Supervisor、Researcher、compression、writer prompts | 适配 MedicalResearchBrief/Task 和 structured Finding output，但 deterministic invariants 仍由代码执行 | Prompt 表达语义目标，不能替代 schema、ID resolution 或 reducer enforcement | P2-S3/P2-S4 | `PLANNED` |
| `tests/evaluators.py` | Final artifact eval；Groundedness 对 final_report + raw_notes 一次性判定 | 保留 V1，对照新增 Claim/Citation/Evidence-aware V2 pipeline | 拆分 Claim extraction、resolution、entailment、aggregation，消除粗粒度循环自证 | P2-S5 | `PLANNED` |
| `tests/run_evaluate.py` | 运行现有 evaluator 集合 | 加入 frozen fixtures、V1/V2 shadow experiment 和有效配置记录 | 为“改善”提供可重复实验依据 | P2-S5/P2-S6 | `PLANNED` |
| `tests/supervisor_parallel_evaluation.py` | 局部检查 Supervisor 产生的并发 Tool Calls 数量 | 作为 topology regression 保留，并补充 Task/Result merge contract tests | 确认 contract migration 未破坏 upstream agentic parallelism | P2-S4/P2-S6 | `PLANNED` |

### Planned New EvidenceFlow Components

准确文件名和模块布局尚未冻结，因此这里记录职责，不虚构不存在的源码路径。

| Planned component | Responsibility | Phase | Status | Required evidence before status upgrade |
|---|---|---|---|---|
| Domain contract module | 承载 MedicalResearchBrief、MedicalResearchTask、Source/Evidence/Finding/TaskResult schemas | P2-S3 | `PLANNED` | source path、schema tests、serialization/version tests、commit |
| Contract fixtures/tests | 验证 I1–I8、invalid references、merge/dedup、artifact exclusion 和 legacy coexistence | P2-S3/P2-S4 | `PLANNED` | fixture version、test command、pass result、commit |
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

### Claims Not Yet Supported

在相应 contribution 升级为 `IMPLEMENTED` 或 `VALIDATED` 前，不得使用以下表述：

- “我实现了 MedicalResearchBrief / MedicalResearchTask runtime。”
- “我实现了 evidence-native Tavily researcher。”
- “我实现了 ArtifactStore / Evidence Store / RAG。”
- “我实现了 Claim-level Groundedness V2。”
- “我的方案提升了 groundedness、citation accuracy、coverage 或 reliability。”
- “EvidenceFlow 已经支持生产级医学研究、完整 PubMed 或医学 RAG。”

允许的替代表述是：“已完成设计 / contract freeze candidate，下一阶段实现并通过 frozen fixtures 验证。”

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
| 2026-08-14 | `EF-P2S3-001`–`EF-P2S3-010` | Contracts v1：domain/state/boundary/invariants/reducers/compatibility/versioning | `docs/evidenceflow_contract/EVIDENCEFLOW_CONTRACTS_V1.md` | `UNCOMMITTED` | document structure checks | N/A | `DESIGNED` |
| 2026-08-14 | Contribution ledger | 创建 upstream attribution 与 resume claim ledger | `docs/CONTRIBUTION_MAP.md` | `UNCOMMITTED` | document structure checks | N/A | `DESIGNED` |

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
