# EvidenceFlow Contracts v1

## 1. Purpose

| Field | Value |
|---|---|
| Status | **P2-S4 D15 PROMOTED — v1 evidence-native boundary** |
| Scope | EvidenceFlow domain contracts、Graph State boundaries、cross-graph contract 与 update semantics |
| Architecture baseline | ODR Agentic Supervisor–Researcher Tool Loop |
| Governing design | `docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md` |
| Contract version | `evidenceflow.contracts.v1` |

本文是 P2-S3/P2-S4 的 implementation-neutral contract specification。它冻结领域对象的职责、最小字段、
State 所有权、Parent 与 Researcher 的输入输出边界、identity/provenance invariants 以及并发更新的业务
语义；它不冻结 Pydantic/TypedDict/dataclass 选择、LangGraph reducer 写法、数据库结构或具体存储产品。

v1 保留现有 Supervisor–Researcher 拓扑，只替换跨边界的数据合同：

```text
Medical Question
  → MedicalResearchBrief
  → Agentic Supervisor
  → MedicalResearchTask
  → Researcher Subgraph
  → ResearchTaskResult
  → Supervisor observe / re-evaluate
```

完整目标链仍为 `Source → Evidence → Finding → Claim → Grounding`，但 P2-S3 只冻结：

- `MedicalResearchBrief`
- `MedicalResearchTask`
- `SourceRecord`
- `EvidenceRecord`
- `ResearchFinding`
- `ResearchTaskResult`

`EvidenceNeed` 是 `MedicalResearchBrief` 和 `MedicalResearchTask` 内的 nested domain object，不是独立
Graph Stage。Claim、Claim–Evidence Link 与 Citation 的实现级 contract 延至 P2-S5。

本文使用 `MUST`、`MUST NOT`、`SHOULD` 表达冻结要求；使用 `MAY` 表达允许但不强制的选择。

## 2. Contract Design Principles

1. **Responsibility before representation**：先冻结对象负责表达什么，再决定 Python 类型或序列化格式。
2. **Preserve topology**：v1 不迁移 Plan + Send，不把 EvidenceNeed 新增为 Graph Stage。
3. **Stable boundary, local freedom**：Parent 只依赖 `MedicalResearchTask → ResearchTaskResult`；Researcher
   内部消息、Tool Loop 与搜索步骤可以独立演进。
4. **Evidence is source-derived**：外部 Evidence 必须来自可定位 Source；模型生成文本不是外部 Evidence。
5. **Compact Graph State**：State 只保存 IDs、领域对象、紧凑 excerpt、summary 与 runtime status。
6. **Provenance survives compression**：Compression 可以压缩文本，但不得破坏 Source/Evidence identity。
7. **Business semantics before reducer mechanics**：先冻结 replace、append、merge、dedup 语义，不提前绑定
   某一种 LangGraph reducer 实现。
8. **Migration by dual-write**：结构化 contract 与 legacy text channels 在迁移期并存，且角色必须分离。
9. **No premature retrieval layer**：Artifact boundary 是当前架构约束；Evidence Store / RAG 不是首个
   Evidence-native vertical slice 的依赖。

## 3. Domain Models

下列字段是 v1 的 conceptual schema。字段存在性和职责在本文件冻结；精确 Python 类型、JSON Schema、
医学 enum、时间格式、hash 算法与 ID 生成算法由实现设计补齐，但不得改变这里的语义。

### 3.1 MedicalResearchBrief

`MedicalResearchBrief` 是医学问题进入 Supervisor 前的规范化研究规格。它是一个整体输入，不预先展开为
固定 topic 列表；具体任务仍由 Agentic Supervisor 根据 Brief 和已有结果动态生成或收敛。

| Field | Presence | Contract meaning |
|---|---|---|
| `normalized_question` | Required | 保留用户意图的规范化医学问题；不是未经说明的任务拆分 |
| `question_type` | Required | 问题的领域类型；v1 冻结字段，不冻结完整医学 enum |
| `clinical_elements` | Optional | 结构化临床元素，可表达 PICO；v1 不强制把所有 PICO 子字段或 enum 设计死 |
| `constraints` | Required, may be empty | 时间、语言、地域、人群、输出或其他研究约束的紧凑表达 |
| `research_intent` | Required | 本次研究希望支持的决策、比较、解释或探索目标 |
| `evidence_needs` | Required list | 一个或多个 nested `EvidenceNeed`；不创建额外 Graph Stage |

Contract rules：

- Brief MUST 能独立提供 Supervisor 规划任务所需的领域语义。
- Brief MUST NOT 预先固化为一组不可调整的 research topics。
- 对 Brief 的更新语义是整体 replace；局部 patch 或历史版本保留不属于 v1 State contract。
- `clinical_elements` MAY 使用 PICO，但 v1 不要求所有问题都能完整映射到 PICO。

### 3.2 EvidenceNeed

`EvidenceNeed` 描述“需要哪类证据以及需要覆盖什么”，只作为 nested domain object 出现在 Brief 或
Task 中。v1 不为它建立独立 State channel、Node、生命周期或全局 identity。

| Conceptual field | Presence | Contract meaning |
|---|---|---|
| `evidence_types` | Optional | 需要的证据类别；精确 enum 延后由领域样本校准 |
| `study_types` | Optional | 偏好或要求的研究设计类型；不等同于自动质量判断 |
| `source_policy` | Optional | 必须使用、允许使用或排除的来源类别规则 |
| `date_constraints` | Optional | 证据检索与纳入的时间边界 |
| `coverage_dimensions` | Optional | 必须覆盖的人群、干预、对照、结局、风险或其他维度 |

Contract rules：

- `EvidenceNeed` MUST 保持领域语义，不得退化为没有约束的通用搜索关键词。
- `source_policy` 表达约束；`MedicalResearchTask.source_preferences` 只是执行偏好，两者不得混同。
- 精确 enum、字段内部结构和医学证据层级仍是 P2-S3 的领域校准项，不得凭通用医学常识臆定。

### 3.3 MedicalResearchTask

`MedicalResearchTask` 是 Supervisor 对一次 Researcher invocation 的稳定输入合同。它不是
`ResearcherState`，也不暴露 Researcher 内部运行方式。

| Field | Presence | Contract meaning |
|---|---|---|
| `task_id` | Required | 一次 EvidenceFlow run 内稳定且唯一的领域任务 ID |
| `research_question` | Required | 单个 Researcher 可执行、边界清晰的研究问题 |
| `evidence_needs` | Required list | 从 Brief 继承或由 Supervisor 收敛出的 nested EvidenceNeed 子集 |
| `source_preferences` | Required, may be empty | 非强制的来源或 provider 偏好；不得覆盖 source policy |
| `priority` | Required | Supervisor 的相对调度/覆盖优先级；不是完成顺序保证 |

Contract rules：

- 同一逻辑任务在 retry、re-dispatch 或结果 merge 时 MUST 保持同一个 `task_id`。
- Task MUST 足够自包含，使 Researcher 不需要读取完整 Parent/Supervisor State 才能执行。
- Supervisor MAY 根据已有 `ResearchTaskResult` 动态新增或收敛 Task。
- Task identity 由 Host/Dispatcher 创建，MUST NOT 由模型生成。P2-S3 正常路径采用
  `task:{encoded_tool_call_id}`；encoding MUST deterministic 且 lossless/injective，两个不同的原始
  `tool_call_id` 不得映射到同一个 `task_id`。缺失 provider call ID 时采用
  `task:iteration:{supervisor_iteration}:call:{ordinal}`。该 namespaced derivation 使领域 ID 与 runtime
  call ID 保持概念分离，同时提供 run-local 可追踪性；P2-S3 不承诺跨 run global identity。

### 3.4 SourceRecord

`SourceRecord` 表示一个被 Host 接纳进入 Evidence pipeline 的外部来源。v1 顶层字段严格保持最小化：

P2-S4 real population 对“接纳”冻结以下 content gate：provider-level `SearchResult` 只是 discovery/process
observation，不会自动成为 authoritative `SourceRecord`。只有具有 usable normalized source content、能够持久化为
可检查 Artifact 并支持后续 provenance audit 的 result，才 materialize 为 `SourceRecord`。缺少或无法提供 usable
source content 的 result 只记录 retrieval/ingestion warning 或 trace，不生成 `SourceRecord` / `EvidenceRecord`。

| Field | Presence | Contract meaning |
|---|---|---|
| `source_id` | Required | 稳定 Source identity；同一 run 内用于 dedup 与 provenance 引用 |
| `artifact_ref` | Optional | 指向原始 Artifact 的 opaque reference；P2-S3 不要求可解析或真实 Store |
| `metadata` | Required | 紧凑来源描述与 retrieval provenance；不得承载完整原始 Artifact |

`metadata` v1 至少支持以下基础信息；它们是 nested metadata，不增加 SourceRecord 顶层字段：

| Metadata key | Contract meaning |
|---|---|
| `url` | 可用时保存外部定位 URL |
| `title` | Provider 返回或可靠提取的来源标题 |
| `provider` | 产生该检索结果的 provider/source adapter 标识 |
| `retrieved_at` | 本次 retrieval 的时间信息 |

Contract rules：

- `source_id` 一经发布 MUST NOT 因压缩、排序或跨 State merge 而改变。
- Canonicalization 和 ID 生成算法可以后定，但同一算法在一个 contract version 内必须确定性使用。
- `artifact_ref` 是 optional / opaque reference；它不得被解释为 P2-S3 已实现 Artifact Store。
- `metadata` MAY 向后兼容地增加字段，但 MUST 保持紧凑且可序列化。
- `metadata` 的 canonical compact JSON serialization MUST NOT 超过 8000 characters。P2-S3 使用
  `json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))` 后的 Python
  character count 作为 deterministic runtime guardrail。
- Metadata keys MUST 经过 case/separator-insensitive normalization 后拒绝已知 content-bearing aliases，
  包括 `content`、`page_content` 和 raw/full-payload variants。该 denylist 是 defense-in-depth，不替代
  serialized total bound。
- 8000-character limit 是 Graph State compactness guardrail，不表示 source quality、medical relevance
  或 evidence sufficiency。

### 3.5 EvidenceRecord

`EvidenceRecord` 表示从一个 Source 中选择的、可定位且可审计的紧凑证据片段。

| Field | Presence | Contract meaning |
|---|---|---|
| `evidence_id` | Required | 稳定 Evidence identity |
| `source_id` | Required | 指向已经存在的 `SourceRecord` |
| `locator` | Required | 片段在来源中的页码、section、字符区间或其他可复核位置 |
| `excerpt` | Required | 来自 Source 的紧凑原文片段，不是模型改写或摘要 |
| `hash` | Required | 所选片段的 content hash，用于审计和变化检测 |

为与 Master Plan 的 v1 顶层 schema 保持一致，canonical field name 是 `hash`；`content_hash` 只描述其
语义，不是第二个 v1 字段。Hash 算法、文本规范化和 locator 的具体编码在实现设计中确定。

Contract rules：

- `EvidenceRecord.source_id` MUST 能解析到 validation scope 中的 SourceRecord。P2-S3 的 scope 是
  Researcher-local records；P2-S4 populated publication 的 scope 是同一个 self-contained
  `ResearchTaskResult`，不得依赖 Parent sibling registry。
- `excerpt` MUST 是 compact、source-derived content，且 MUST NOT 超过 8000 characters；完整 HTML/PDF
  文本不得放入该字段。
- `locator + hash` MUST 支持把所选 Evidence 回查到对应 Source Artifact。
- Evidence extraction 可以由模型辅助，但模型生成的解释不得替代 source-derived `excerpt`。
- 8000-character excerpt limit 只控制 structured Graph State payload 大小，不表达医学证据质量、支持
  强度或临床语义完整性。

### 3.6 ResearchFinding

`ResearchFinding` 是 Researcher 基于一条或多条 Evidence 得出的局部研究结论。它是可供 Supervisor
观察和全局综合的 domain object，不等于最终报告 Claim。

| Field | Presence | Contract meaning |
|---|---|---|
| `finding_id` | Required | 稳定 Finding identity |
| `task_id` | Required | 产生该 Finding 的 MedicalResearchTask |
| `text` | Required | 有边界、可读的局部结论 |
| `evidence_ids` | Required list | 支持或约束该 Finding 的 Evidence references |
| `limitations` | Required, may be empty | 证据不足、适用范围、方法限制和不确定性 |
| `conflicts` | Required, may be empty | 与该 Finding 冲突或方向不一致的已发现证据 |

Contract rules：

- 普通事实性 Finding MUST 引用至少一个有效 `evidence_id`。
- 若 `evidence_ids` 为空，Finding MUST 在 `limitations` 中显式标记为 `evidence-insufficient`，且不得
  被上层当作已获证据支持的事实。
- `conflicts` MUST 保持显式可见，不得通过 summary 或 compression 静默丢弃。
- Finding 是 local synthesis；Claim 的生成和 Claim-level Grounding 属于 P2-S5。

### 3.7 ResearchTaskResult

`ResearchTaskResult` 是 Researcher Subgraph 唯一稳定的领域输出边界。Supervisor 消费 Result，而不是
完整 `ResearcherState`。

```text
MedicalResearchTask
        ↓
Researcher Subgraph
        ↓
ResearchTaskResult
```

| Field | Presence | Contract meaning |
|---|---|---|
| `contract_version` | Required | serialized v1 固定值为 `evidenceflow.contracts.v1`；由 canonical code constant 提供 |
| `task_id` | Required | 与输入 Task 相同的稳定 ID |
| `status` | Required | 当前 invocation 的 execution/termination outcome；Python enum members 为 `SUCCESS/PARTIAL/FAILED`，serialized values 为 `success/partial/failed` |
| `source_records` | Required for S4 publication; legacy read default empty | 本 Task Result 发布的 compact Source ledger；包含解析 `source_ids` 与 Evidence provenance 所需的全部 Source targets，不得包含 raw Source artifact |
| `evidence_records` | Required for S4 publication; legacy read default empty | 本 Task Result 发布的 bounded Evidence ledger；包含解析 `evidence_ids` 与 Finding references 所需的全部 Evidence targets |
| `findings` | Required | Inline bounded structured Findings；每个 Evidence reference 必须在同一 Result 解析 |
| `evidence_ids` | Required list | `evidence_records` identities 的 deterministic ordered projection |
| `source_ids` | Required list | `source_records` identities 的 deterministic ordered projection |
| `summary` | Required | 给 Supervisor 模型观察的 bounded summary；不是 provenance source |
| `limitations` | Required, may be empty | 整个任务级别的范围限制和证据缺口 |
| `conflicts` | Required, may be empty | 整个任务级别需要上层继续处理的冲突 |
| `error` | Optional | partial/failed 的结构化错误说明；成功结果通常为空 |

Contract rules：

- `ResearchTaskResult` MUST 在序列化结果中携带 `contract_version=evidenceflow.contracts.v1`；不新增
  外层 Result envelope，也不把该字段复制到每个 Domain Model。
- 每个成功 materialize 的 Task MUST 产生一个可关联的 Result，包括成功、partial、执行失败或并发准入
  失败。无法通过 `ConductResearch` schema validation 的 Tool Call 尚未形成 Task，只返回明确的 legacy
  contract-validation ToolMessage。
- `ResearchTaskResult.task_id` MUST 与输入 `MedicalResearchTask.task_id` 相同。
- P2-S4 populated Result MUST be a self-contained task-level provenance aggregate。所有公开的 Finding、Evidence
  与 Source references MUST 在同一个 Result envelope 中解析；bare dangling IDs 不构成 evidence-native Result。
- **P2-S3 phase limitation**：shadow Result 正常 runtime 尚不 population Source/Evidence/Finding，且
  `ResearcherOutputState` 不携带 Source/Evidence registries。P2-S3 只保证 candidate Result references
  在 Researcher finalization 时能对 Researcher-local `source_records` / `evidence_records` 完成一致性
  validation，不保证 populated IDs 在 Parent boundary 可解析，也不新增 Parent registry 或
  EvidenceStore。
- **P2-S4 promotion**：`source_records` / `evidence_records` inline carry 是唯一 canonical Parent-visible carrier。
  P2-S4 MUST NOT 新增 Parent sibling Source/Evidence registries，也不得用 external EvidenceStore 替代 Result
  自包含性。
- `source_ids` MUST exactly equal the deterministic ordered identity projection of `source_records`；
  `evidence_ids` MUST exactly equal the deterministic ordered identity projection of `evidence_records`。
- Every `EvidenceRecord.source_id` MUST resolve within the same Result。Every identity in
  `ResearchFinding.evidence_ids` MUST resolve within the same Result。
- 每个 P2-S4 published `SourceRecord` MUST 持有可由同一 Run 的 ArtifactStore 解析的 `artifact_ref`。Raw
  normalized Source artifact MUST NOT inline 到 Result。
- Result provenance payload MUST 具有与 Researcher search iteration count 独立的明确总量 bounds。
- Parent/Supervisor MAY 将 `summary` 放入模型上下文，但 provenance 判断 MUST 使用结构化 IDs/records。
- Supervisor model rendering MUST be an explicit bounded projection；完整 inline ledger 不得因存在于 State 而
  自动进入 model context。
- `error` 不得吞掉 finalization/failure boundary 已经能够取得且通过 validation 的 partial
  Source/Evidence/Findings records；可用 records 必须和错误同时保留在 `PARTIAL` / `FAILED` Result 中。
- 该接口不得依赖当前 Tool Loop 的内部消息格式，因此未来 Plan + Send 可以复用同一合同。
- normal、partial 和 failed candidate Result MUST 在 Researcher publish/finalization boundary 调用
  provenance validation；invalid Source/Evidence/Finding references MUST NOT 跨过 structured boundary。

Status rules：

- P2-S3 status 只描述 execution / termination semantics，不代表独立验证过的 Evidence sufficiency、
  Evidence quality、coverage、grounding 或医学正确性。
- `SUCCESS` 表示 Researcher 正常终止并成功产生 compression / result output；正常终止可以由没有后续
  tool call 或显式 `ResearchComplete` 表达。若同一步同时到达 budget boundary，显式
  `ResearchComplete` 优先。
- `PARTIAL` 表示因 tool-call budget 或已识别 tool failure 被迫终止，但仍产生可使用的 partial output。
- `FAILED` 表示 admission、child execution 或 compression failure 阻止正常完成 result boundary；它不
  允许丢弃 finalization/failure boundary 已经能够取得且通过 validation 的 compact Source/Evidence/Finding
  records。
- **P2-S3 known limitation**：hard child exception 若在 `researcher_subgraph.ainvoke()` 返回 State 前
  逃逸，Parent catch 无法取得 child-local partial records。P2-S3 此时只保证 task-correlated FAILED
  Result 与 error visibility；state-aware recovery 延后到 P2-S4/P2-S6，且不在 P2-S3 引入 checkpoint、
  retry/attempt lifecycle、新 persistence 或 topology change。
- P2-S3 shadow Result 的 structured collections 可以为空，因此 `SUCCESS` 不得被解释为 Evidence-native
  quality verification 已通过。

## 4. State Boundaries

State freeze 同时规定“谁拥有字段”和“哪些内容不进入 State”。以下是逻辑 State schema，不是具体
Python class 定义。

### 4.1 Parent Graph State

Parent Graph 保存跨阶段需要的最小 run state：

| Channel | Role |
|---|---|
| `messages` | 用户对话与 Parent process messages；不是 external Evidence |
| `medical_research_brief` | 当前有效的 `MedicalResearchBrief` |
| `research_results` | 一个或多个 self-contained `ResearchTaskResult`，按 task identity append/merge；compact Source/Evidence records inline 于各自 Result，不存在 Parent sibling registry |
| `final_report` | 当前 run 的最终报告文本 |

`claim_manifest` 不进入 P2-S3 State；它在 P2-S5 冻结。迁移期 Parent MAY 继续携带 `raw_notes` 和
`notes` legacy channels，但它们不是 v1 structured evidence contract。

v1 evidence-native end-state 中，每个 `ResearchTaskResult` 自己拥有解析其公开 references 所需的 compact
Source/Evidence/Finding records。P2-S3 shadow Result 的 collections 为空；P2-S4 populated Result 使用 inline
record carry，并明确不增加 Parent Source/Evidence registry。

### 4.2 Supervisor State

Supervisor State 只保存运行时再规划所需的信息：

| Channel | Role |
|---|---|
| `medical_research_brief` | Supervisor 的领域规划输入 |
| `supervisor_messages` | Tool planning、observations 与 termination process artifacts |
| `research_results` | 已完成、部分完成或失败的结构化任务结果 |
| `research_iterations` | Supervisor 当前迭代计数 |
| `notes` / `raw_notes` | 仅用于 legacy dual-write 与既有 Final Writer 兼容 |

Supervisor 可以通过 Tool Calls 动态生成 `MedicalResearchTask`，但 v1 不要求新增独立 Task Graph Stage
或把所有 Task 预先写入固定 plan。Supervisor MUST NOT 依赖 Researcher 的内部 messages 或 Tool Loop。

### 4.3 Researcher-local State

每个 Researcher invocation 拥有隔离的 local state：

| Channel | Role |
|---|---|
| `task` | 本 invocation 的 `MedicalResearchTask` |
| `researcher_messages` | Researcher Model–Tool–Observation process artifacts |
| `tool_call_iterations` | 本地 Tool Loop 迭代计数 |
| `source_records` | 本任务发现的紧凑 SourceRecords |
| `evidence_records` | 从 Sources 提取的 EvidenceRecords |
| `findings` | 本任务形成的 ResearchFindings |
| `compressed_research` | Legacy bounded text output；迁移期 dual-write |
| `raw_notes` | Legacy/debug text aggregation；迁移期 dual-write |

完整 Researcher-local State MUST NOT 穿过 Parent boundary。离开子图的领域输出必须先通过 publication gate，
再投影为包含 compact Source/Evidence ledger 的 `ResearchTaskResult`；`researcher_messages`、Candidate、raw
provider payload 与内部 Tool observations 留在 local/process scope。

P2-S3 provenance validation 使用同一次 finalization 可见的 `source_records` 与 `evidence_records`，只
保证 Researcher-local graph consistency。P2-S4 publication gate MUST 将通过验证的 compact records 组装进
Result，并重新验证 Result 内 projection、reference、artifact、locator、hash 与 bounds 后才能发布。

### 4.4 Artifact Boundary

New EvidenceFlow structured Graph State channels MUST NOT persist：

- full raw HTML
- full PDF text
- binary documents
- complete large search-provider payloads
- large immutable source snapshots

Graph State 只保存：

- stable IDs
- domain objects
- compact excerpts
- bounded summaries
- runtime status
- optional opaque `artifact_ref`

P2-S3 对新 structured contracts 额外冻结两个 runtime compactness guardrails：

- `EvidenceRecord.excerpt` 最大 8000 characters；
- `SourceRecord.metadata` canonical compact JSON serialization 最大 8000 characters。

这些 limits 只控制 State payload 大小，不是 medical evidence semantics。Normalized content-bearing-key
rejection 作为 defense-in-depth 继续生效。

> **Invariant:** New EvidenceFlow structured Graph State channels MUST NOT persist raw source artifacts such as
> full HTML, full PDF text, large search-provider payloads, or binary documents.

P2-S3 对该 invariant 采用一个明确且不可扩大的迁移例外：现有 ODR summarization failure path 仍可能把
raw webpage content 写入 legacy `ToolMessage/raw_notes`。新的 `medical_research_brief`、
`research_results`、`source_records`、`evidence_records`、`findings` 与 `research_task_result` channels
MUST NOT 保存这些 raw artifacts。P2-S3 不修改既有 Tavily fallback；P2-S4 在引入 ArtifactStore boundary
时必须移除该例外。

Artifact storage 是已冻结的 architectural boundary，但不是 P2-S3 implementation target。P2-S3 的
`artifact_ref` 可以为空或保持 opaque；P2-S4 再实现 `ArtifactStore Protocol → LocalArtifactStore`。
Artifact Store 与未来 Evidence Store / RAG 不等价：前者保存原始 Artifact，后者是建立在稳定
Source/Evidence contracts 之上的跨 run 复用与检索层。

P2-S4 ArtifactStore scope 是 **run-scoped**，不是 Researcher-call-scoped。一个 Run 中发布到 Result 的每个
`artifact_ref` MUST 在 originating Researcher 返回后继续可解析，至少覆盖 downstream publication validation、
debug/audit 与该 Run 后续 system stages。Store instance 或 raw artifact 不进入 Graph State；State 只保存 opaque
reference。Run 结束后的 retention、garbage collection、object-storage migration 与 transactional durability 不属于
v1/P2-S4 contract。

## 5. Parent ↔ Researcher Contract

跨图接口只包含一个输入和一个输出：

```text
Parent / Supervisor
  │
  ├── input:  MedicalResearchTask
  │               ↓
  │         Researcher Subgraph
  │               ↓
  └── output: ResearchTaskResult
```

Boundary rules：

1. Parent MUST 通过 `MedicalResearchTask` 提供任务语义，不传递完整 Parent/Supervisor State。
2. Researcher MUST 通过 `ResearchTaskResult` 返回业务结果，不返回完整 `ResearcherState`。
3. 输入和输出 MUST 使用相同 `task_id`；runtime `tool_call_id` 只负责调用关联。
4. Supervisor 可以观察 bounded `summary` 与 Findings，但不得读取 Researcher internal messages 来推断
   业务结果。
5. P2-S4 Result MUST inline the compact Source/Evidence targets needed to resolve all published IDs；Compression
   MUST NOT 生成不存在的新 Evidence ID。
6. Publication gate MUST validate deterministic ID projections、same-Result reference resolution、run-scoped
   artifact resolution、locator/excerpt equality、hash equality 与 total payload bounds。
7. Partial/failed Result MUST 保留 status、error 和 finalization/failure boundary 已经能够取得且通过
   validation 的 compact Source/Evidence/Finding records。P2-S3 hard child exception 无法恢复未返回的 child State；state-aware
   recovery 延后到 P2-S4/P2-S6。
8. Supervisor 只接收 Result 的 explicit bounded projection；完整 inline Evidence ledger 不自动进入 model context。
9. 当前 Tool Loop 与未来 Plan + Send MUST 能复用这一逻辑接口；调度拓扑不得改变合同含义。

## 6. Identity & Provenance Invariants

“Stable”在 v1 中表示：ID 在一次 run 内唯一，在对象生命周期、重试、压缩、State merge 和跨图传递中
保持不变。跨 run 的全局 canonical identity、具体 ID 格式和生成算法不在本文件冻结。

| ID | Frozen invariant | Contract-test interpretation |
|---|---|---|
| I1 | Every `MedicalResearchTask` has a stable `task_id`. | Task 创建后 ID 非空、run 内唯一，retry/Result 保持同值 |
| I2 | Every `SourceRecord` has a stable `source_id`. | Source 被接受后 ID 非空，dedup/merge/compression 不改 ID |
| I3 | Every `EvidenceRecord` references an existing `SourceRecord`. | P2-S4 populated Result 在同一 inline `source_records` ledger 中解析；不得依赖 Parent sibling registry |
| I4 | Every `EvidenceRecord` preserves auditable source provenance through `source_id + locator + hash / artifact_ref`. | P2-S4 publication gate 从 Result Source target 解析 run-scoped artifact，并验证 locator exact slice 与 hash |
| I5 | AIMessage / model-generated content cannot become external Evidence. | Message 或模型摘要不得直接构造为 source-derived excerpt |
| I6 | Every normal `ResearchFinding` references valid Evidence IDs; evidence-insufficient output is explicit. | P2-S4 populated Result 在同一 inline `evidence_records` ledger 中解析；空列表必须显式标记 `evidence-insufficient` |
| I7 | Parent Graph does not depend on Researcher internal messages/tool loop. | Parent contract test 只使用 Task/Result 也能完成聚合与关联 |
| I8 | Raw source artifacts do not enter new structured Graph State channels. | P2-S3 对 excerpt/metadata 执行 8000-character guards，legacy `ToolMessage/raw_notes` 例外被隔离且不得扩展；P2-S4 移除 |
| I9 | Legacy `raw_notes`/`compressed_research` and structured contracts can coexist during migration. | dual-write 不覆盖结构化 records，关闭任一路径时行为边界明确 |
| I10 | Deterministically derived counts are not persisted as contract facts. | `source_count`/`evidence_count` 等由 ID collections 计算 |
| I11 | Parent-visible provenance references are self-contained and non-dangling. | `source_ids` / `evidence_ids` exactly project inline records，且 Source/Evidence/Finding references 全部在同一 Result 解析 |
| I12 | Model context is independent from the full structured Result payload. | Supervisor renderer 只显式投影 bounded status/summary/Findings/limitations/conflicts，不 dump inline ledger |

P2-S4 对 I2 的 real-population acceptance 补充：`SearchResult ≠ SourceRecord`。只有通过 usable source-content
gate 的 accepted、inspectable result 才能进入 authoritative Source collection；rejected result 仅存在于 warning/trace。

这些 invariants 优先于便利性字段或某种具体框架写法。实现若无法满足，必须修改本 contract 或新增
ADR，不能通过 prompt 约定静默绕过。

## 7. Reducer / Update Semantics

v1 冻结业务更新语义，不冻结这些语义必须由 LangGraph reducer、节点内 merge 还是独立 adapter 实现。

| Channel | Scope | Frozen update semantics |
|---|---|---|
| `medical_research_brief` | Parent / Supervisor | **replace**：新完整 Brief 替换旧值，不做列表追加 |
| `research_results` | Parent / Supervisor | **append/merge**：不同 `task_id` 全部保留；相同 ID 的 identical replay 幂等去重，不同 payload 报 contract conflict |
| `source_records` | Researcher | **append/dedup**：按 `source_id` 去重，不允许静默覆盖不同内容 |
| `evidence_records` | Researcher | **append/dedup**：按 `evidence_id` 去重，并保持 `source_id` 引用有效 |
| `findings` | Researcher | **append**：保留独立 Findings；重复 ID 的不一致内容视为 contract conflict |
| `tool_call_iterations` | Researcher | **replace/increment**：单调更新当前计数，不使用列表追加 |
| `compressed_research` | Legacy / Researcher | **replace**：每次完成 compression 后保存当前 bounded text result |
| `raw_notes` | Legacy | **append**：保留迁移/debug 输出，不参与 structured dedup |
| `notes` | Legacy / Supervisor | **append or explicit clear**：维持现有 Final Writer 消费语义，不作为 Evidence registry |

Reducer rules：

- 并发 R1/R2/R3 的 `research_results` MUST 合并，MUST NOT 发生 whole-channel overwrite。
- Dedup 只合并同一 identity 的同一逻辑对象；相同 ID 对应不一致 immutable content 时必须显式报错或
  记录 conflict，不能采用静默 last-write-wins。
- Result 不执行 field-wise merge。同一 `task_id` 的不同 immutable payload MUST 报 contract conflict；未来若
  引入 retry，必须先区分 logical `task_id` 与 execution `attempt_id`。
- 具体 reducer API、并发锁、排序和序列化实现不属于 P2-S3 contract freeze。

## 8. Legacy Compatibility

P2-S3/P2-S4 采用 dual-write，确保现有 ODR report path 可继续运行，同时让 structured evidence path
可以 shadow 验证。

| Legacy channel | Baseline role | v1 migration role |
|---|---|---|
| `raw_notes` | 聚合 Researcher AIMessage 与 ToolMessage 文本，并汇总到上层 | 保留为 process/debug artifact；MUST NOT 作为 external Evidence 或 Ground Truth |
| `compressed_research` | Researcher 返回给 Supervisor 的 bounded 文本，通常进入 ToolMessage | 与 `ResearchTaskResult.summary/findings` 并行输出；不承担 Source/Evidence identity |
| `notes` | 从 Supervisor ToolMessages 收集并供 Final Writer 使用；不是从 `raw_notes` 过滤得到 | 暂时维持 legacy report generation；不得被重新定义为 Evidence registry |

Compatibility rules：

1. Legacy report generation SHOULD 在 structured path 引入期间继续可用。
2. Legacy 与 structured outputs SHOULD 来源于同一次 Researcher execution，避免两次独立研究造成不可比。
3. Structured Source/Evidence/Finding IDs 是 provenance 的权威路径；legacy text 不得覆盖或伪造这些 ID。
4. v1 不要求 legacy text 与 structured summary 逐字符一致，但必须能按 `task_id` 关联同一次任务结果。
5. 删除 `raw_notes`、`notes` 或 `compressed_research` 需要单独迁移决策、回归证据和必要的 ADR；不属于
   P2-S3 contract freeze。
6. P2-S3 shadow Result 的空 `findings/evidence_ids/source_ids` 表示 structured Evidence population 尚未实现，
   不能被解释为当前 legacy Researcher 没有使用任何来源或证据。
7. legacy raw-content fallback 是 P2-S3 临时例外，不得复制到任何新 structured channel；P2-S4 必须移除。

## 9. Versioning

v1 的逻辑版本标识为 `evidenceflow.contracts.v1`，模块级 contract version constant 是 canonical code
constant。`ResearchTaskResult` 是 P2-S3 cross-graph result contract，MUST 通过自身的
`contract_version` 字段序列化该值；不新增外层 `ResearchTaskResultEnvelope`，也不要求其他每个 Domain
Model 重复保存版本字段。

S4-D15 将 `source_records` / `evidence_records` 作为 additive inline fields 提升到 v1，完成本文从 P2-S3 已
预留的 Parent-visible evidence-native end-state。新 consumer MUST 为这两个字段提供 empty-list defaults，以读取
S3 shadow Result；但 populated P2-S4 Result MUST enforce exact non-dangling projections，不能借 legacy defaults
省略 records。

当前 strict S3 consumer 会拒绝新增字段，因此不声明 old-consumer/new-producer forward compatibility。P2-S4
producer 与 consumer MUST atomic upgrade，并通过 serialized consumer contract tests。该限制不触发 v2，是因为
v1 尚处于本仓库内的 staged migration，且 Parent-visible record resolution 已在原 v1 contract 中明确保留为 S4
mandatory completion。

未来 persisted Source/Evidence artifacts 的版本机制延后到引入其 storage boundary 的 phase；P2-S3 不
为尚未持久化的 Source/Evidence contracts 提前增加 storage-version fields。

以下变化属于 breaking contract change，需要新版本或显式 migration：

- 删除或重命名冻结字段。
- 改变字段的领域含义、identity scope 或 provenance 责任。
- 将 nested `EvidenceNeed` 改为独立 Graph Stage。
- 将 Parent ↔ Researcher 边界改为依赖完整 `ResearcherState`。
- 将 append/merge channel 改为 overwrite，或放宽任一 I1–I12 invariant。
- 放宽 self-contained Result、exact ID projection 或 same-Result reference resolution invariant。
- 让 raw artifacts 进入新的 structured Graph State channels，或扩大 P2-S3 legacy migration exception。

以下变化 MAY 在保持 v1 compatibility 的前提下追加：

- `SourceRecord.metadata` 中新增可选 metadata。
- 在不改变既有语义的情况下补充可选 diagnostics。
- 实现层选择或替换等价的 schema/reducer/storage adapter。

新增 enum 值、Requiredness 变化和不同 ID canonicalization 是否兼容，必须通过 consumer contract tests
验证，不能默认视为 non-breaking。Legacy adapter 与 structured schema 应分别标识版本和测试。

## 10. Explicitly Deferred Contracts

| Deferred item | Target / boundary |
|---|---|
| `ClaimRecord` | P2-S5 冻结；由 Global Synthesis 产生，不属于 Researcher-local Finding contract |
| `EvidenceSupport / ClaimEvidenceLink` | P2-S5 冻结 support labels、reason 与 Claim–Evidence 关系 |
| Citation representation | P2-S5 冻结 stable citation format 与 deterministic resolution |
| `claim_manifest` Parent State | 随 P2-S5 Claim contract 冻结后再加入 |
| `ArtifactStore Protocol → LocalArtifactStore` | P2-S4 实现；P2-S3 只冻结 Artifact boundary 和 opaque `artifact_ref` |
| Parent sibling Source/Evidence registries | S4-D15 已拒绝作为当前 carrier；未来若改变 Result ownership，必须重新进入 contract/version review |
| Hard child-exception partial-state recovery | P2-S4/P2-S6 评估 state-aware boundary/checkpoint recovery；P2-S3 不新增 persistence、attempt lifecycle 或 topology |
| Evidence Store / cross-run Evidence persistence | Future persistence phase；P2-S4 inline Result ledger 是 run-local business output，不是 durable Store |
| Global Evidence identity / cross-run Source dedup | Future persistence phase 必须在 global ID、`(run_id, evidence_id)` 或 provenance-derived identity 之间显式决策 |
| Artifact retention/GC、object-storage migration、transactional persistence | Future durability phase；P2-S4 只保证 run-scoped resolution lifetime |
| RAG / embedding / vector index lifecycle | Future retrieval phase；Vector index 只能是 derived、rebuildable projection，不能成为 authoritative provenance store |

同时显式不在 v1 冻结：完整医学 question/study/source-policy enums、跨 run Evidence identity、完整
Provider Adapter 统一、长期 retention/privacy policy、Plan + Send、Durable Queue 以及具体持久化产品。
这些能力若进入实现范围，必须由后续 contract version、阶段设计或 ADR 明确授权。
