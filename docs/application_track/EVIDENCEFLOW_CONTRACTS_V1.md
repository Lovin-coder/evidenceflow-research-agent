# EvidenceFlow Contracts v1

## 1. Purpose

| Field | Value |
|---|---|
| Status | **P2-S5 + CB01–CB06 PROMOTED — v1 evidence / claim-grounding boundary** |
| Scope | EvidenceFlow domain contracts、Graph State boundaries、cross-graph contract 与 update semantics |
| Architecture baseline | ODR Agentic Supervisor–Researcher Tool Loop |
| Governing design | `docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md` |
| Contract version | `evidenceflow.contracts.v1` |

本文是 P2-S3 至 P2-S5 的 implementation-neutral contract specification。它冻结领域对象的职责、最小字段、
State 所有权、Parent 与 Researcher 的输入输出边界、identity/provenance invariants 以及并发更新的业务
语义；它不冻结 Pydantic/TypedDict/dataclass 选择、LangGraph reducer 写法、数据库结构或具体存储产品。

v1 保留现有 Supervisor–Researcher 拓扑，并在 Parent finalization boundary 增加 P2-S5 Global Synthesis：

```text
Medical Question
  → MedicalResearchBrief
  → Agentic Supervisor
  → MedicalResearchTask
  → Researcher Subgraph
  → ResearchTaskResult
  → Supervisor observe / re-evaluate
  → Global Synthesis
  → GroundingManifest
```

v1 当前冻结完整的结构化目标链：

```text
Source → Evidence → Finding → Claim → Claim Grounding → Citation
```

P2-S3/P2-S4 已冻结：

- `MedicalResearchBrief`
- `MedicalResearchTask`
- `SourceRecord`
- `EvidenceRecord`
- `ResearchFinding`
- `ResearchTaskResult`

P2-S5 在同一 v1 contract family 中进一步冻结：

- `EvidenceRef` / `FindingRef`
- `ClaimRecord`
- `ClaimGroundingRecord`
- `Citation`
- `GroundingManifest`

`EvidenceNeed` 是 `MedicalResearchBrief` 和 `MedicalResearchTask` 内的 nested domain object，不是独立
Graph Stage。P2-S5 采用 claim-centered Grounding，不增加 group-level proof graph 或 relation identity。

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

下列字段是 v1 的 conceptual schema。字段存在性和职责在本文件冻结。除后文显式冻结的 wire encoding、exact
enum 与 identity rule（包括 current `artifact_ref` wire encoding）外，精确 Python 类型、JSON Schema、医学 enum、
时间格式以及其他 hash/ID algorithms 由 implementation design 补齐，但不得改变这里的语义。

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
| `artifact_ref` | P2-S3 optional；P2-S4 published Source required | Artifact reference；对 storage location/backend opaque，但 wire syntax 由后文 Artifact contract 定义 |
| `metadata` | Required | 紧凑来源描述与 retrieval provenance；不得承载完整原始 Artifact |

`metadata` v1 MAY best-effort 使用以下 nested keys；它们不增加 SourceRecord 顶层字段，也不构成 P2-S5 Judge
admission 的 required metadata schema。除实际 Source writer/adapter 能验证并写入的值外，缺失字段不得推断：

| Metadata key | Contract meaning |
|---|---|
| `url` | 可用时保存外部定位 URL |
| `title` | Provider 返回或可靠提取的来源标题 |
| `provider` | 产生该检索结果的 provider/source adapter 标识 |
| `retrieved_at` | 本次 retrieval 的时间信息 |
| `publisher` | 可验证时保存发布机构；P2-S5 Judge projection 可选使用 |
| `authors` | 可验证时保存 bounded author display string；P2-S5 不在 v1 引入复杂 author object |
| `published_at` | 可验证时保存来源发布日期；与本次 retrieval time 分离 |
| `document_type` | 来源明确提供或 adapter 可可靠映射时保存 document type；不是 Host 推断的 quality tier |

Contract rules：

- `source_id` 一经发布 MUST NOT 因压缩、排序或跨 State merge 而改变。
- Canonicalization 和 ID 生成算法可以后定，但同一算法在一个 contract version 内必须确定性使用。
- P2-S3 的 `artifact_ref` MAY 为空，且不得被解释为 P2-S3 已实现 Artifact Store。P2-S4 published Source 的
  `artifact_ref` 必须按后文 Artifact contract 在 owning Run 内可解析；“opaque”只表示 consumer 不依赖 physical
  storage location/backend，不表示 wire syntax 或 provenance semantics 未定义。
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

### 3.8 Task-qualified Reference Value Objects

P2-S5 MUST 保持 P2-S4 的 identity scope。`source_id`、`evidence_id` 与 `finding_id` 的 authoritative
resolution scope 仍是一个 `ResearchTaskResult`；它们不会因为进入 Global Synthesis 而被升级为 global ID。

```python
class EvidenceRef:
    task_id: str
    evidence_id: str


class FindingRef:
    task_id: str
    finding_id: str
```

Contract rules：

- `EvidenceRef` 与 `FindingRef` 是 task-qualified address，不是新的 Source/Evidence/Finding identity。
- Host MUST 先以 `task_id` 解析唯一 `ResearchTaskResult`，再只在该 Result 内解析 bare ID。
- `EvidenceRef` 解析链 MUST 为
  `task_id → ResearchTaskResult → evidence_id → EvidenceRecord → source_id → SourceRecord`。
- `FindingRef` 解析链 MUST 为
  `task_id → ResearchTaskResult → finding_id → ResearchFinding`。
- unknown、dangling 或 ambiguous reference MUST 被拒绝；Host MUST NOT 扫描 sibling Results 猜测目标。
- 两个不同 Tasks 中相同的 bare ID MUST 被视为不同 canonical addresses。

### 3.9 ClaimDraft and ClaimRecord

`ClaimDraft` 是 Claim Generator 的 internal structured output，不是 stable Domain Contract：

```python
class ClaimDraft:
    text: str
    materiality: ClaimMateriality
    finding_refs: list[FindingRef]
    scope: str | None
    qualifiers: list[str]
```

`ClaimDraft` MUST NOT 携带 candidate/supporting/contradicting Evidence references、Evidence Groups 或 Grounding
verdict。Model A MAY 查看 bounded Evidence projection 作为 semantic context，以避免 overgeneralization、形成 scope/
qualifiers 并理解 Findings 的限制与冲突，但 Evidence 不是 Model A output reference authority。Host 先验证
`finding_refs`，再于 Claim survivor selection 后从 retained `ClaimRecord.finding_refs → ResearchFinding.evidence_ids`
重新确定性派生 Model B Evidence universe，并应用独立 Judge admission budget；模型不得借 Claim generation 自行扩大
该 universe。

```python
class ClaimMateriality(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

`ClaimRecord` 是 Host materialize 的稳定 Domain Contract：

```python
class ClaimRecord:
    claim_id: str
    text: str
    materiality: ClaimMateriality
    finding_refs: list[FindingRef]
    scope: str | None
    qualifiers: list[str]
```

| Field | Presence | Contract meaning |
|---|---|---|
| `claim_id` | Required | Host-owned、owning `GroundingManifest` 内唯一且稳定的 run-local Claim identity |
| `text` | Required | Global Synthesis 准备送入 V2 report space 的 bounded factual proposition |
| `materiality` | Required | `HIGH/MEDIUM/LOW`；只表达对用户核心问题的重要程度 |
| `finding_refs` | Required, non-empty | Claim 的 task-local semantic derivation lineage |
| `scope` | Optional | population、condition 或 research applicability boundary |
| `qualifiers` | Required, may be empty | 最终表达必须保留的限制条件 |

Contract rules：

- `ClaimRecord` 只在 Parent-level Global Synthesis boundary 产生；Researcher MUST NOT 产生它。
- `claim_id` 由 Host 分配，MUST NOT 由模型决定；它不承诺 cross-run global identity。
- `ClaimRecord.text + scope + qualifiers` jointly define the complete authoritative Claim proposition；`scope` 与
  `qualifiers` 不是 presentation-only hints，Grounding Judge MUST 判断完整 proposition。
- `finding_refs` MUST non-empty，表达 Claim 如何从 Findings 综合而来，不是 external Evidence authority。
- `ResearchTaskResult.summary/limitations/conflicts` 只提供 contextual hints，不是 Claim-authorizing semantic
  records；正式 derivation lineage MUST 是 `ClaimRecord → FindingRef → ResearchFinding`。
- Host 只验证 declared Finding lineage structurally；P2-S5 不新增 Claim↔Finding semantic Judge。Claim reportability
  由完整 proposition 与 Finding-derived Evidence universe 的 Grounding Judge 决定。
- `ClaimRecord` MUST NOT 重复保存 Evidence references、Citation references、Grounding status 或 report
  eligibility。
- `materiality` 不表示 evidence quality、Grounding confidence、Citation count、model probability 或医学正确性。
- `scope` 与 `qualifiers` 是不同语义，不在 v1 扩展为完整 PICO 或医学 ontology。
- 拒绝或省略一个 sibling ClaimDraft SHALL NOT 改变另一个 otherwise identical admitted ClaimDraft 的 deterministic
  identity；exact encoding 属于 PLAN，但不得仅使用 survivor ordinal。
- Exact duplicate ClaimDraft 只表示 `text/scope/qualifiers/finding_refs/materiality` canonical serialization
  identical replay；Host MUST NOT 使用 string similarity、embedding similarity 或 semantic fuzzy matching 做 Claim
  dedup。

### 3.10 ClaimGroundingDraft and ClaimGroundingRecord

Grounding Judge 的 internal structured output 是：

```python
class ClaimEvidenceVerdict(str, Enum):
    SUPPORTED = "supported"
    INSUFFICIENT = "insufficient"
    CONTRADICTED = "contradicted"


class ClaimGroundingDraft:
    verdict: ClaimEvidenceVerdict
    supporting_evidence_refs: list[EvidenceRef]
    contradicting_evidence_refs: list[EvidenceRef]
    reason: str
```

`ClaimEvidenceVerdict` 是 Model B 对完整 authoritative Claim proposition（`text + scope + qualifiers`）与整个
admitted Evidence universe 做出的 overall semantic judgment，不是最终 Domain `GroundingStatus`，也不是单条
Evidence 的 quality grade。Model B owns overall semantic verdict；Host owns structural validation 与 deterministic
status materialization。

Host 验证 Judge draft 后 materialize：

```python
class ClaimGroundingRecord:
    claim_id: str
    evaluated_evidence_refs: list[EvidenceRef]
    supporting_evidence_refs: list[EvidenceRef]
    contradicting_evidence_refs: list[EvidenceRef]
    status: GroundingStatus
    reason: str | None
```

```python
class GroundingStatus(str, Enum):
    SUPPORTED = "supported"
    SUPPORTED_WITH_CONFLICT = "supported_with_conflict"
    INSUFFICIENT = "insufficient"
    CONTRADICTED = "contradicted"
    UNASSESSED = "unassessed"
```

Contract rules：

- 一个 published Claim MUST 恰好对应一个 `ClaimGroundingRecord`。
- 对 valid assessed record，`evaluated_evidence_refs` 是 Host-owned audit universe，MUST exactly equal 获得 valid
  semantic Judge result 的 ordered Evidence inputs；模型不得自行声称未看到的 Evidence 已被评估。
- `supporting_evidence_refs` 表示为 Claim 提供 material positive support、并 materially participate in overall
  Grounding assessment 的 Evidence。单条 Evidence 不必独立建立 sufficient support；因此 `verdict=INSUFFICIENT`
  与 non-empty supporting set 是合法组合。
- `contradicting_evidence_refs` 表示为 Claim 提供 material negative evidence，并足以参与 overall assessment 或
  required meaningful conflict disclosure 的 Evidence。它不要求每条 contradiction 独立推翻 Claim，也不得收录
  weak/incidental disagreement。
- supporting 与 contradicting lists MUST 各自唯一、均为 evaluated universe 的 subset、MUST disjoint，并按
  evaluated canonical order 的 filtered projection 排列。
- `evaluated_evidence_refs - supporting_evidence_refs - contradicting_evidence_refs` 是 derived
  evaluated-but-non-material set；它不新增 neutral/insufficient Evidence canonical field。
- `SUPPORTED` verdict MUST 包含至少一个 supporting EvidenceRef；`CONTRADICTED` verdict MUST 包含至少一个
  contradicting EvidenceRef；`INSUFFICIENT` verdict 的两个 lists 均 MAY empty 或 non-empty。
- Host MUST 依据 validated overall verdict 按下表 materialize status：

| Valid Judge verdict | Material contradiction set | Host-derived `GroundingStatus` |
|---|---:|---|
| `SUPPORTED` | empty | `SUPPORTED` |
| `SUPPORTED` | non-empty | `SUPPORTED_WITH_CONFLICT` |
| `INSUFFICIENT` | any valid shape | `INSUFFICIENT` |
| `CONTRADICTED` | non-empty required | `CONTRADICTED` |
| no valid semantic assessment | N/A | `UNASSESSED` |

- 即使 `INSUFFICIENT` 同时具有 supporting/contradicting refs，final status 仍是 `INSUFFICIENT`。Host MUST NOT 以
  Evidence count、Source count、set presence/absence、contradiction count 或 string matching 代替 overall semantic
  verdict，也不得使用 contradiction-presence heuristic 推导 `CONTRADICTED`。
- `UNASSESSED` 是 execution/validation problem state，不是 Evidence 语义上的 `INSUFFICIENT`。其三个 Evidence
  lists MUST 为空且 `reason` MUST 为 `None`；问题细节进入 bounded `global_synthesis_issues`。
- assessed status 的 `reason` MUST 是 bounded、sanitized semantic explanation，不得包含 hidden chain-of-thought，
  也不得替代 machine-readable status。它只服务 audit/debug/evaluation，不是 Evidence、Claim 或 Renderer factual
  authority；Renderer MUST NOT 消费 reason，Citation 不为 reason 生成 provenance。Gate 只验证 requiredness、type、
  bounds 与 sanitization，不验证 reason factual truth。
- Model B semantic required input 只有 `EvidenceRef + exact Evidence excerpt`。Locator 与 `source_id` 继续用于 Host
  provenance resolution，但不是 required model-visible semantic fields。
- Source title、URL、retrieval provider、publisher、authors、`published_at` 与 `document_type` 全部是 optional、
  best-effort、never inferred context，只能来自 validated/whitelisted `SourceRecord.metadata`。缺少任何 metadata，
  包括 title，MUST NOT 阻止 otherwise valid Evidence 进入 Judge。
- Projection MUST NOT 包含 `artifact_ref`、full Artifact 或未经验证的 metadata key。S5 correctness MUST NOT 依赖
  optional metadata enrichment，也不得 fabricate missing metadata。
- Judge 必须基于上述内容定性考虑 authority、directness、methodology、applicability、recency 与 cross-source
  consistency；S5 不增加 required `source_type`、quality tier 或确定性 Evidence-quality score，也不得虚构缺失
  metadata。
- Per-Claim Evidence admission MUST 按 derived canonical order 保留完整 Evidence views；capacity overflow 保留
  legal prefix、不 rerank、不切片 excerpt，并记录 degrading issue。只有实际 admitted refs 才能进入
  `evaluated_evidence_refs` 与 Judge allowlist。

`revision_required` 与 `report_eligible` 是 status-derived policy，不进入 `ClaimRecord` 或
`ClaimGroundingRecord` canonical fields：

| Status | `revision_required` | `report_eligible` |
|---|---:|---:|
| `SUPPORTED` | `False` | `True` |
| `SUPPORTED_WITH_CONFLICT` | `True` | `True` |
| `INSUFFICIENT` | `True` | `False` |
| `CONTRADICTED` | `True` | `False` |
| `UNASSESSED` | `True` | `False` |

P2-S5 不实现 iterative Claim repair；Grounding 后不得自动 rewrite authoritative Claim 或循环 re-ground。

### 3.11 Citation

`Citation` 是 reader-facing provenance handle，不是 semantic Grounding judgment：

```python
class Citation:
    citation_id: str
    claim_id: str
    evidence_ref: EvidenceRef
```

Contract rules：

- Canonical Citation identity scope 是 `(claim_id, EvidenceRef)`；同一 pair 只能 materialize 一个 Citation。
- `citation_id` 由 Host 确定性分配；display label 是 Host-derived presentation view，不属于 canonical identity。
- Citation MUST 通过 `claim_id + EvidenceRef` 确定性解析到 Claim、EvidenceRecord 与 SourceRecord。
- free-form model URL MUST NOT 成为 Citation authority；URL/title 等显示信息从 resolved SourceRecord 派生。
- `SUPPORTED` Claim 的 required Citation Evidence set exactly equals `supporting_evidence_refs`。
- `SUPPORTED_WITH_CONFLICT` Claim 的 required set exactly equals supporting 与 contradicting references 的并集，
  且最终报告必须显式披露 conflict。
- `INSUFFICIENT`、`CONTRADICTED` 与 `UNASSESSED` Claim 不 report-eligible，required set 为空且 MUST NOT
  materialize Citation。
- Manifest Citation completeness 表示：每个 report-eligible Claim 的 actual cited EvidenceRef set 与上述 required
  set 严格相等；它不证明 LLM renderer 已在每个正文位置正确放置 label。
- Canonical Citation/Source/Evidence identities MUST NOT 因 reader-facing grouping 被合并或修改；全部 canonical
  Citation records 必须保留。
- `citation_id` 与 derived display label 是不同 authority。Display grouping eligibility、label assignment algorithm、
  display-key representation 与 bibliography style 属于 phase behavior/presentation policy，不构成 stable Citation
  wire shape。

### 3.12 GroundingManifest

`GroundingManifest` 是 P2-S5 的 authoritative structured shadow output：

```python
class GroundingManifest:
    contract_version: str
    claims: list[ClaimRecord]
    groundings: list[ClaimGroundingRecord]
    citations: list[Citation]
```

Contract rules：

- `contract_version` MUST 使用 canonical value `evidenceflow.contracts.v1`。
- `claims`、`groundings` 与 `citations` MAY 全部为空；empty Manifest 在结构上合法，不等于 Global Synthesis
  成功或报告有内容。
- Manifest MUST 作为一个 aggregate 通过 Global Synthesis Publication Gate 后 atomic one-shot publish；不得发布
  partial Manifest。
- identical replay 对 `grounding_manifest` 是 idempotent；同一 active Research Run 中不同 payload 的重复 publish 是
  contract conflict。New Research Run bootstrap 先 reset Manifest，因此不构成 previous-run divergent replay。
- Manifest 不增加 `manifest_id`、durable persistence、global registry 或 cross-run identity。
- Manifest 不保存 derivable metrics、display labels、`global_synthesis_status`、issues、V2 report text 或 external
  faithfulness evaluation。
- V2 Shadow Report 是 Manifest 的 derived artifact，不是 authoritative Data Plane。
- Generator upstream Task order 使用 Parent `research_results` ledger order；Context admission 应用 per-task Finding
  cap 后按 Result Finding order 与 Finding `evidence_ids` order 接纳完整 units，不使用 Claim materiality 分配尚未
  生成的 upstream projection。
- `claims` 保持 validated Generator order；capacity overflow 时按 `HIGH → MEDIUM → LOW` 选择、同 tier 保持
  Generator order，survivors 再投影回原 Generator order。Host MUST 先尝试接纳全部 validated Claims，只有
  capacity overflow 才应用 materiality priority。
- `groundings` MUST 与 canonical Claim order 一一对应。每个 Claim 的 derived Evidence universe 按
  `finding_refs` order，再按每个 Finding 的 `evidence_ids` order，以 exact `EvidenceRef` first occurrence 去重；
  supporting/contradicting lists 通过该 evaluated order 过滤得到。
- `citations` 按 Claim canonical order，再按 supporting first occurrence、contradicting first occurrence 排序。
  async completion timing、dict/set iteration 或 provider callback order MUST NOT 成为 ordering authority。
- P2-S5 不跨 Tasks 合并相同 URL、excerpt、hash、Source 或 Evidence identity；同 Claim 内只允许 exact
  `EvidenceRef` first-occurrence dedup。

Global Synthesis Publication Gate MUST Host-controlled、atomic、validate-not-repair。它只验证 structural integrity，
不重新判断 medical entailment：Claim IDs/FindingRefs/bounds/order 合法；每个 Claim 恰好一个 Grounding；Evidence refs
resolve 且 evaluated/supporting/contradicting 满足 exact/subset/unique/disjoint/order/verdict-status/reason invariants；
Citation actual set exactly equals required set 且 IDs/order 合法；Manifest version、bindings 与 payload bounds 合法。
任一失败发布 no Manifest，Gate 不删除 bad records、猜测 refs 或 partial publish。

### 3.13 Derived Grounding Metrics

P2-S5 MUST 能从 valid Manifest 确定性派生以下 shadow metrics；它们不进入 authoritative Manifest：

- `supported_claim_count`
- `supported_with_conflict_claim_count`
- `insufficient_claim_count`
- `contradicted_claim_count`
- `unassessed_claim_count`
- `assessed_claim_coverage`
- `report_eligible_claim_coverage`
- `material_report_eligible_claim_coverage`

Coverage definitions：

- `assessed_claim_coverage = count(status != UNASSESSED) / count(all Claims)`；
- `report_eligible_claim_coverage = count(SUPPORTED + SUPPORTED_WITH_CONFLICT) / count(all Claims)`；
- `material_report_eligible_claim_coverage = count(report-eligible AND materiality=HIGH) /
  count(materiality=HIGH)`。

任一 coverage denominator 为零时 value MUST 为 `None`，不得使用 `0`、`1` 或 `NaN`。Metrics 必须 Host-derived、
recomputable、non-authoritative，且不进入 Manifest。Citation completeness 已由 Publication Gate 的 exact required-vs-
actual Citation set 保证，不再作为退化为 `1.0/None` 的 quality metric；S5 不引入 production threshold 或 release
gate。

### 3.14 V2 Shadow Renderer and External Faithfulness Evaluation

V2 Shadow Report 是 valid `GroundingManifest` 的 non-authoritative derived rendering。Model C MAY paraphrase complete
Claim semantics 以提高可读性，但 MUST NOT mutate/replace `ClaimRecord`、创建 authoritative Claim/Evidence/Citation
identity、改变 `GroundingStatus` 或修改 Manifest。

Renderer contract rules：

- Model C 只消费 report-eligible Claim packages。每个 package 包含完整 Claim proposition、GroundingStatus，并 MAY
  包含该 Claim 已经 materialize 的 bounded material supporting / contradicting Evidence projection，以及 optional
  validated Source metadata。Model C MUST NOT 消费 `ClaimGroundingRecord.reason`、raw notes、ToolMessages、provider
  snippets、unvalidated drafts 或 full Artifact，也不得扩大 Evidence universe、修改 supporting / contradicting role 或
  创建 Citation authority。
- Model C MAY 通过 structured output 决定 section count、section title、section order、paragraph organization 与
  paragraph prose；section title不是body paragraph，不要求Claim binding。Host继续拥有bounds、structural validation、
  Citation identity、required Citation set、display labels、bibliography与final serialization。
- Every model-generated body paragraph MUST bind at least one valid report-eligible `claim_id`。Host 只验证 Claim IDs
  exist、within-paragraph unique、bounded、report-eligible，并确保每个 eligible Claim 至少出现一次；Host MUST NOT
  deterministic classify factual vs non-factual model paragraphs。Model-generated unbound body paragraph不允许；Host
  MAY生成fixed report title或非正文boilerplate。
- Renderer-visible Evidence只可来自该Claim已materialize的supporting / contradicting refs；bounded Renderer context
  omission不得改变GroundingStatus、required Citation set或Manifest。
- `SUPPORTED_WITH_CONFLICT` 是 report-eligible；Host在其first canonical paragraph occurrence deterministic插入最小
  conflict marker，并显示covering supporting与contradicting Evidence references。Model C MAY提供自然冲突叙事；S5
  runtime不要求deterministic relative-weight narrative、numeric confidence或calibrated uncertainty wording。
- 一个 paragraph MAY 绑定多个 Claims；runtime 只保证 structural Claim binding，不保证 no-new-proposition，也不新增
  runtime semantic verifier/repair loop。
- 若 report-eligible Claims 为空，Host MUST 跳过 Model C，生成 deterministic no-grounded-claim shadow output，且
  不创建 fake Claim/Citation。若没有 degradation，Global Synthesis MAY 为 `SUCCESS`；valid `INSUFFICIENT`/
  `CONTRADICTED` 本身不是 execution failure。

P2-S5 SHALL 提供 external evaluation-only faithfulness evaluator，检查 unsupported proposition、scope expansion、
qualifier loss、conflict omission、Claim misrepresentation 与 Citation/Claim placement mismatch。Evaluator 位于 compiled
graph、Parent State、Manifest、runtime Gate 与 `GlobalSynthesisStatus` 之外；它不触发 repair，valid semantic FAIL
不得 retry 到 PASS。Exact evaluator model、dataset、rubric 与 threshold 属于 PLAN/Evaluation。

## 4. State Boundaries

State freeze 同时规定“谁拥有字段”和“哪些内容不进入 State”。以下是逻辑 State schema，不是具体
Python class 定义。

### 4.1 Parent Graph State

Parent Graph 保存跨阶段需要的最小 run state：

| Channel | Role |
|---|---|
| `messages` | conversation/checkpoint context；MAY 跨 Research Runs 保留，但不是 external Evidence 或 structured provenance reuse |
| `supervisor_messages` | 当前 Research Run 的 Supervisor planning/process context |
| `artifact_run_id` | 当前 active Research Run 的 ArtifactStore namespace |
| `medical_research_brief` | 当前有效的 `MedicalResearchBrief` |
| `research_brief` | 当前 Run structured Brief 的 legacy rendering |
| `research_results` | 一个或多个 self-contained `ResearchTaskResult`，按 task identity append/merge；compact Source/Evidence records inline 于各自 Result，不存在 Parent sibling registry |
| `raw_notes` / `notes` | 当前 Run legacy process/V1 writer channels；不是 V2 authority |
| `grounding_manifest` | Optional；P2-S5 atomic published `GroundingManifest`，是 authoritative V2 structured shadow output |
| `global_synthesis_status` | Optional `SUCCESS/PARTIAL/FAILED`；描述 P2-S5 pipeline outcome，不是 Claim GroundingStatus |
| `global_synthesis_issues` | bounded structured issues；用于 stage diagnostics，不保存 raw model payload 或 hidden reasoning |
| `v2_shadow_report` | constrained renderer 派生的 V2 shadow text；可以在 Manifest 有效时为空 |
| `final_report` | 迁移期 legacy V1 official/compatibility report text |

迁移期 Parent MAY 继续携带 `raw_notes` 和 `notes` legacy channels，但它们不是 v1 structured evidence
contract。P2-S5 不新增 Parent-level Source/Evidence registry，也不把 renderer faithfulness evaluation 写入 runtime
State。

v1 evidence-native end-state 中，每个 `ResearchTaskResult` 自己拥有解析其公开 references 所需的 compact
Source/Evidence/Finding records。P2-S3 shadow Result 的 collections 为空；P2-S4 populated Result 使用 inline
record carry，并明确不增加 Parent Source/Evidence registry。

#### 4.1.1 Global Synthesis status and issues

`GlobalSynthesisStatus` 冻结三态 execution semantics：

```python
class GlobalSynthesisStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
```

| Status | Contract meaning |
|---|---|
| `SUCCESS` | Manifest 已通过 Publication Gate，Shadow Renderer 或 zero-eligible deterministic Host output 成功，且没有 observed degradation |
| `PARTIAL` | Manifest 已有效发布，但发生 Claim omission、`UNASSESSED`、admission overflow、renderer failure 或其他明确的 degrading issue |
| `FAILED` | 没有 Manifest 被发布；V1 path 与有效 S4 Results 仍须保留 |

`global_synthesis_status` MUST NOT 由单个 Claim 的 status 直接替代；它描述整个 Global Synthesis execution 与
publication outcome。

每个 `GlobalSynthesisIssue` 的最小语义字段是：

```python
class GlobalSynthesisIssue:
    issue_id: str
    stage: str
    code: str
    severity: GlobalSynthesisSeverity
    message: str
    claim_id: str | None
    task_id: str | None
    evidence_ref: EvidenceRef | None
    attempt: int | None
    degrades_global_status: bool
```

`stage` MUST 是 non-empty、machine-readable、sanitized 且 runtime-bounded string，用于表达观察到 issue 的 logical
S5 processing stage。Stable deserialization MUST 保持 open：consumer MUST 接受任何满足这些通用约束的未知 stage
string，MUST NOT 使用 phase-local `GlobalSynthesisStage` enum 做 closed validation。PLAN MAY 用 exact enum 约束
Host-produced values；新增或细分 Host stage vocabulary 在 stable Issue shape 不变时不自动构成 v1 schema migration。

Exact stage/code/ID/message numeric bounds 属于 Host admission guardrail，不是本 v1 wire contract 的永久 numeric
compatibility guarantee。Stable severity 仍冻结为：

```python
class GlobalSynthesisSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"
```

每个 issue 的 `degrades_global_status` 表示该 event 是否触发 degradation，MUST NOT 仅由 severity 推导。Host MUST
另行维护 monotonic degradation fact：一旦 observation 为 `True`，同一 active Research Run 内不得恢复为 `False`。
Final `GlobalSynthesisStatus` MUST 从该 monotonic fact 派生，MUST NOT 通过扫描 bounded retained issue ledger、issue
message 或 severity 重建。Exact accumulator storage 是 node-local execution context 还是 internal State carrier 属于
PLAN。Faithfulness evaluator 位于 external Eval，不增加 runtime stage。Issues MUST bounded、sanitized、可序列化；
MUST NOT 保存 raw prompt、raw model output、provider payload、stack-sized traceback 或 hidden model reasoning。

#### 4.1.2 Research Run lifecycle and State isolation

`Research Run` 是一个 research request 从 top-level Deep Research bootstrap 到 finalization 的 logical execution
lifecycle。Conversation/checkpoint lifetime MAY 包含多个 sequential Research Runs；一个 Run MAY 包含多个 Supervisor
iterations、ResearchTasks、Researchers、Tool/Model retries，以及继续同一 execution 的 clarification、interrupt 与
resume。单个 user message、`graph.invoke()`、ResearchTask、search call 或 node execution 不自动定义 Run boundary。

```text
Conversation / checkpoint lifetime
        > Research Run lifetime
        > ResearchTask lifetime
```

Active Parent State 同一时间 MUST 最多承载一个 authoritative Research Run。一个 Run MUST 对应一个
`artifact_run_id` namespace，且 Run 内所有 Supervisor/Researcher work MUST 传播同一值。只有 finalized Run 后的新
research request 才 bootstrap fresh Run 与 fresh `artifact_run_id`；clarification/resume 若继续同一 logical execution
MUST 保留现有值。PLAN/runtime mapping 负责确定性识别这些 boundaries。

新 Research Run MUST 在接纳任何新 Source/Evidence/Result 前 reset/replace prior run-scoped State：

- Supervisor messages、structured/legacy brief；
- `research_results`、`raw_notes`、`notes`、`final_report`；
- `grounding_manifest`、`global_synthesis_status`、`global_synthesis_issues`、`v2_shadow_report`；
- run-local degradation accumulator 与任何未来存入 State 的 S5 run-local derived/eval artifact。

Conceptual reset values 是 fresh Supervisor/brief context、empty Result/legacy ledgers、no prior reports、Manifest/status/
shadow report unset、empty issues 与 degradation `False`。Exact representation/reducer mechanism 属于 PLAN，但 reset
MUST 在 new-run provenance admission 前完成。Conversation `messages` MAY 保留；它们不得使 prior-run Result、Source、
Evidence、Finding、Claim、Grounding、Citation 或 Manifest 自动进入新 Run authoritative Data Plane。

Same-run update semantics：`research_results` append/merge、Manifest atomic one-shot/identical replay idempotency/
divergent replay conflict、status/report Host override、issues bounded append/dedup 与 degradation monotonic OR 都只在同一
active Research Run 内成立。New-run bootstrap 将 Manifest reset 为 `None`，因此 new-run publication 不是 prior-run
divergent replay。

State reset 不删除 physical ArtifactStore data；旧 run directories MAY 保留，但不再是 active authority。P2-S5 不
维护 multi-run Result history、ResearchRun registry、run-qualified EvidenceRef、cross-run Evidence/Citation reuse、
cross-run Artifact provenance merge 或 historical Manifest registry。

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
`artifact_ref` 可以为空或仅作为 storage-opaque reference；P2-S4 再实现
`ArtifactStore Protocol → LocalArtifactStore` 并遵守后文 wire encoding。
Artifact Store 与未来 Evidence Store / RAG 不等价：前者保存原始 Artifact，后者是建立在稳定
Source/Evidence contracts 之上的跨 run 复用与检索层。

P2-S4 ArtifactStore scope 是 **run-scoped**，不是 Researcher-call-scoped。一个 Run 中发布到 Result 的每个
`artifact_ref` MUST 在 originating Researcher 返回后继续可解析，至少覆盖 downstream publication validation、
debug/audit 与该 Run 后续 system stages。Store instance 或 raw artifact 不进入 Graph State；State 只保存不暴露
storage location/backend 的 reference。Run 结束后的 retention、garbage collection、object-storage migration 与
transactional durability 不属于
v1/P2-S4 contract。

Current `artifact_ref` 是传给 `ArtifactStore.put_text()` 的最终 logical text value 的 content-addressed reference。
Exact wire encoding 是：

```python
artifact_ref = (
    "artifact:sha256:"
    + sha256(final_text.encode("utf-8")).hexdigest()
)
```

`final_text` 是 upstream preparation/normalization 完成后交给 `put_text()` 的最终 logical text value。相同
`final_text` MUST 产生相同 `artifact_ref`。Contracts 不定义该 value 如何产生、filesystem bytes 的重新读取、storage
path/layout 或 backend；该 identity 不证明 original provider/webpage bytes globally identical，也不是 Source identity。
完整 resolvable address 是 `(artifact_run_id, artifact_ref)`。

P2-S5 中一个 D19 Research Run 对应一个 `artifact_run_id` namespace。State bootstrap 到新 Run 时不删除旧 physical
Artifact data，但 active State MUST 不再携带旧 namespace 的 authoritative Results；bare `artifact_ref` 不得跨 Runs
解析、比较或用于 display grouping。

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

“Stable”在 v1 中表示：ID 在其 owning scope 内唯一，并在对象生命周期、重试、压缩、State merge 和跨图
传递中保持不变。`task_id` 的 scope 是 owning Run；Source/Evidence/Finding bare ID 的 authoritative scope 是
owning `ResearchTaskResult`；`claim_id` 的 scope 是 owning `GroundingManifest`。跨 run global identity、具体 ID
格式和生成算法不在本文件冻结。

| ID | Frozen invariant | Contract-test interpretation |
|---|---|---|
| I1 | Every `MedicalResearchTask` has a stable `task_id`. | Task 创建后 ID 非空、run 内唯一，retry/Result 保持同值 |
| I2 | Every `SourceRecord` has a stable `source_id` within its owning Result. | Source 被接受后 ID 非空、同一 Result 内唯一，dedup/merge/compression 不改 ID |
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
| I13 | Cross-task references are task-qualified and never resolved by sibling scan. | 每个 `EvidenceRef` / `FindingRef` 先解析唯一 Task Result，再在其中解析 bare ID |
| I14 | Claim identity, proposition and materialization are Host-owned. | 模型只产生 `ClaimDraft`；`text+scope+qualifiers` 构成完整 proposition；valid non-empty FindingRefs、bounds 与 admission 通过后才生成 authoritative `claim_id`，且 sibling rejection 不改变其他 Claim identity |
| I15 | Claim lineage and Evidence Grounding remain separate. | `ClaimRecord.finding_refs` 表达 synthesis lineage；Evidence semantics 只进入对应 `ClaimGroundingRecord` |
| I16 | The evaluated Evidence universe is Host-owned and exact for every valid assessment. | assessed record 的 `evaluated_evidence_refs` exactly matches ordered admitted Judge input；`UNASSESSED` 按 I19 使用 empty lists |
| I17 | Supporting and contradicting Evidence are valid material disjoint subsets. | 两个 lists 各自唯一、均可解析、均为 evaluated subset、无 overlap、保持 canonical filtered order；`INSUFFICIENT` 可携带任一 material subset |
| I18 | Claim-level status preserves the Judge overall semantic verdict. | Judge 输出 `ClaimEvidenceVerdict` 与 material Evidence subsets；Host 按冻结 mapping 产生五态 status，不用 count/presence/string heuristic 替代 verdict |
| I19 | `UNASSESSED` records execution/validation failure, not insufficiency. | 无 valid Judge output 时 Evidence lists 为空、reason 为 `None`，诊断进入 issues |
| I20 | Citation completeness is exact for every report-eligible Claim. | actual Citation Evidence set exactly equals status-dependent required set，不多不少 |
| I21 | Manifest publication is atomic and validates the whole aggregate. | 任一 structural invariant 失败均不发布 partial Manifest；合法内部中间产物可保留为 diagnostics |
| I22 | Canonical collection ordering is independent from async completion timing. | Claims、Groundings、Evidence refs 与 Citations 服从冻结的 first-occurrence/order policy |
| I23 | The V2 renderer cannot become a second factual authority. | Renderer 可 paraphrase 但不修改 Claim；每个 model-generated body paragraph 必须绑定 eligible `claim_id`，Host 不做 factual/non-factual semantic classification，Renderer 不消费 Grounding reason |
| I24 | Active structured provenance is isolated by Research Run. | 一个 active State 最多一个 authoritative Run；same-run work 共享 `artifact_run_id`，new-run bootstrap 在 admission 前 reset prior run-scoped State，conversation messages 不自动复用 structured provenance |

P2-S4 对 I2 的 real-population acceptance 补充：`SearchResult ≠ SourceRecord`。只有通过 usable source-content
gate 的 accepted、inspectable result 才能进入 authoritative Source collection；rejected result 仅存在于 warning/trace。

这些 invariants 优先于便利性字段或某种具体框架写法。实现若无法满足，必须修改本 contract 或新增
ADR，不能通过 prompt 约定静默绕过。

## 7. Reducer / Update Semantics

v1 冻结业务更新语义，不冻结这些语义必须由 LangGraph reducer、节点内 merge 还是独立 adapter 实现。

| Channel | Scope | Frozen update semantics |
|---|---|---|
| `supervisor_messages` | Parent / Supervisor | **same-run replace/append by process contract**；new Run reset fresh Supervisor context |
| `artifact_run_id` | Parent / all run stages | **same-run stable propagation**；new Run bootstrap replace 为 fresh namespace |
| `medical_research_brief` | Parent / Supervisor | **same-run replace**：新完整 Brief 替换旧值，不做列表追加；new Run 先 clear |
| `research_brief` | Legacy / Parent | **same-run replace**：从当前 structured Brief 派生；new Run 先 clear |
| `research_results` | Parent / Supervisor | **same-run append/merge**：同一 active Run 内不同 `task_id` 全部保留；相同 ID 的 identical replay 幂等去重，不同 payload 报 contract conflict；new Run reset empty |
| `source_records` | Researcher | **append/dedup**：按 `source_id` 去重，不允许静默覆盖不同内容 |
| `evidence_records` | Researcher | **append/dedup**：按 `evidence_id` 去重，并保持 `source_id` 引用有效 |
| `findings` | Researcher | **append**：保留独立 Findings；重复 ID 的不一致内容视为 contract conflict |
| `tool_call_iterations` | Researcher | **replace/increment**：单调更新当前计数，不使用列表追加 |
| `grounding_manifest` | Parent / Global Synthesis | **same-run atomic publish**：`None` 只可变为一个已通过 Gate 的完整 Manifest；identical replay 幂等，不同 replay 报 contract conflict；new Run reset `None` |
| `global_synthesis_status` | Parent / Global Synthesis | **same-run Host replace/override**：遵守 `SUCCESS/PARTIAL/FAILED` 语义；new Run reset unset |
| `global_synthesis_issues` | Parent / Global Synthesis | **same-run bounded append/dedup**：按 `issue_id` 合并；不一致 payload 报 conflict；new Run reset empty |
| `v2_shadow_report` | Parent / Global Synthesis | **same-run Host replace/override**：只保存当前 valid Manifest 派生的 shadow text；renderer failure 保持为空；new Run reset unset |
| `compressed_research` | Legacy / Researcher | **replace**：每次完成 compression 后保存当前 bounded text result |
| `raw_notes` | Legacy | **same-run append**：保留迁移/debug 输出，不参与 structured dedup；new Run reset empty |
| `notes` | Legacy / Supervisor | **same-run append or explicit clear**：维持现有 Final Writer 消费语义，不作为 Evidence registry；new Run reset empty |
| `final_report` | Legacy / Parent | **same-run replace**：当前 V1 official report；new Run reset 为 no prior report |

Reducer rules：

- 本表 append/merge/replay 语义只在同一 active Research Run 内成立，不授权跨 Runs historical accumulation。
- New Research Run bootstrap MUST 在任何新 provenance admission 前 reset `artifact_run_id` 以外的 prior run-scoped
  payload，并为新 Run 建立 fresh `artifact_run_id`；具体 reducer/entry mechanism 不在 contract 中冻结。
- 并发 R1/R2/R3 的 `research_results` MUST 合并，MUST NOT 发生 whole-channel overwrite。
- Dedup 只合并同一 identity 的同一逻辑对象；相同 ID 对应不一致 immutable content 时必须显式报错或
  记录 conflict，不能采用静默 last-write-wins。
- Result 不执行 field-wise merge。同一 `task_id` 的不同 immutable payload MUST 报 contract conflict；未来若
  引入 retry，必须先区分 logical `task_id` 与 execution `attempt_id`。
- Manifest 不执行 field-wise 或 sibling salvage publication；结构上 invalid 的 aggregate MUST 整体拒绝。Gate
  之前的 valid internal artifacts MAY 保留供 bounded diagnostics，但不得写入 `grounding_manifest`。
- 具体 reducer API、并发锁、排序和序列化实现不属于 contract freeze。

## 8. Legacy Compatibility

P2-S3 至 P2-S5 采用 dual-write / shadow migration，确保现有 ODR V1 report path 可继续运行，同时让
structured Evidence 与 Claim-grounding path 独立验证。

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
8. P2-S5 中 legacy `final_report` 仍是 official/compatibility V1 output；`GroundingManifest` 是 authoritative V2
   structured shadow output，`v2_shadow_report` 只是 derived evaluation artifact。
9. V1 与 V2 SHOULD 消费同一次 run 的上游 research results；P2-S5 MUST NOT 静默用 V2 替换 V1。
10. V2 Generator、Judge、Publication Gate 或 Renderer failure MUST NOT 擦除 valid S4 Results 或阻断可用的 V1
    path；Renderer failure 也不得擦除已发布 Manifest。
11. 上述 preservation 只针对同一 active Research Run；D19 new-run bootstrap 必须 reset prior-run Results、legacy
    notes 与 V1/V2 outputs，conversation messages 的保留不授权 structured provenance reuse。

## 9. Versioning

v1 的逻辑版本标识为 `evidenceflow.contracts.v1`，模块级 contract version constant 是 canonical code
constant。`ResearchTaskResult` 是 P2-S3 cross-graph result contract，MUST 通过自身的
`contract_version` 字段序列化该值；不新增外层 `ResearchTaskResultEnvelope`，也不要求其他每个 Domain
Model 重复保存版本字段。

P2-S5 的 `GroundingManifest` 作为独立 aggregate 同样 MUST 序列化
`contract_version=evidenceflow.contracts.v1`。它不包装或复制 `ResearchTaskResult[]`，而是通过
task-qualified references 解析 owning Parent State 中的 upstream Results。P2-S5 的 additive Domain Models 与
Parent State channels 延续 v1；其 producer/consumer 必须在 S5 implementation slice 中 atomic upgrade。

本轮 B01 promotion 在任何 P2-S5 producer/consumer implementation 之前，将此前 document-only Judge candidate
修正为最终 Human-resolved `ClaimEvidenceVerdict` semantics。由于旧 candidate 从未成为已实现或持久化 wire
payload，本次是 pre-implementation canonical correction，不创建第二个 version namespace；S5 producer/consumer
仍按本文件一次性 atomic upgrade。

CB01–CB06 同样发生在 P2-S5 producer、checkpointed Issue payload 与 serialized display-key consumer 出现之前。
`GlobalSynthesisIssue.stage` 从 document-only closed enum 改为 open string 是当前时间点上的 validation widening；
display representation/ordering/style 下沉到 phase policy 不改变 Citation wire identity；`artifact_ref` encoding 不变。
因此继续使用 `evidenceflow.contracts.v1`。该判断依赖当前尚无 deployed consumer 的事实，不表示已部署 closed enum
未来都可无版本迁移。

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
- 将 same-run append/merge channel 改为 overwrite、将其误用于 cross-run history，或放宽任一 I1–I24 invariant。
- 放宽 self-contained Result、exact ID projection 或 same-Result reference resolution invariant。
- 让 raw artifacts 进入新的 structured Graph State channels，或扩大 P2-S3 legacy migration exception。
- 将 task-qualified references 改为 bare cross-task lookup，或改变 Claim/Grounding/Citation responsibility。
- 改变 `GroundingStatus` 的 frozen semantics、report eligibility 或 exact Citation completeness policy。
- 将 atomic Manifest publication 改为 partial aggregate publication。

以下变化 MAY 在保持 v1 compatibility 的前提下追加：

- `SourceRecord.metadata` 中新增可选 metadata。
- 在不改变既有语义的情况下补充可选 diagnostics。
- 实现层选择或替换等价的 schema/reducer/storage adapter。

新增 enum 值、Requiredness 变化和不同 ID canonicalization 是否兼容，必须通过 consumer contract tests
验证，不能默认视为 non-breaking。Legacy adapter 与 structured schema 应分别标识版本和测试。

## 10. Explicitly Deferred Contracts

| Deferred item | Target / boundary |
|---|---|
| Group-level proof graph / independent support-set identity | 当前没有 report、Citation 或 Gate consumer；未来 scientific argument mining / systematic review phase 如需引入，必须重新进入 contract review |
| Formal `source_type` ontology、Evidence quality tier/score | Future Evaluation/domain-calibration phase；P2-S5 Judge 只定性使用可验证 metadata，不让 Host 以粗粒度类型决定医学可信度 |
| Iterative Claim/Report semantic repair loop | Future evaluated repair phase；P2-S5 valid semantic FAIL 不 retry，runtime 不自动改写 authoritative Claim |
| Renderer faithfulness hard gate | P2-S5 仅在 external Eval harness 评估；达到 calibration threshold 后才可决定是否提升为 runtime contract |
| Production Grounding threshold / V2 rollout gate | Future Evaluation/release phase；P2-S5 只产生 shadow metrics，不替换 V1 official output |
| Cross-task Source/Evidence semantic dedup | S5-D13 明确不实现；同 Claim 内仅对 exact `EvidenceRef` first-occurrence dedup，不改变 canonical address |
| Parent sibling Source/Evidence registries | S4-D15 与 S5-D00 已拒绝作为当前 carrier；未来若改变 Result ownership，必须重新进入 contract/version review |
| Hard child-exception partial-state recovery | Future recovery phase；当前不新增 persistence、attempt lifecycle 或 topology |
| Evidence Store / cross-run Evidence persistence | Future persistence phase；P2-S4 inline Result ledger 是 run-local business output，不是 durable Store |
| Global Evidence identity / cross-run Source dedup | Future persistence phase 必须在 global ID、`(run_id, evidence_id)` 或 provenance-derived identity 之间显式决策 |
| Multi-run active State / ResearchRun registry / previous-run structured provenance reuse | Future explicit lifecycle/persistence phase；P2-S5 active AgentState 只拥有一个 authoritative Run |
| Artifact retention/GC、object-storage migration、transactional persistence | Future durability phase；P2-S4 只保证 run-scoped resolution lifetime |
| RAG / embedding / vector index lifecycle | Future retrieval phase；Vector index 只能是 derived、rebuildable projection，不能成为 authoritative provenance store |

同时显式不在 v1 冻结：完整医学 question/study/source-policy enums、跨 run Evidence identity、完整
Provider Adapter 统一、长期 retention/privacy policy、Plan + Send、Durable Queue、具体模型/provider、exact retry
次数、context budget 数值、并发参数以及具体持久化产品。
这些能力若进入实现范围，必须由后续 contract version、阶段设计或 ADR 明确授权。
