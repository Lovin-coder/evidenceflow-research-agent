# P2-S3 — Clarifications & Implementation Decisions

## 0. Purpose

本文记录 P2-S3 在 repository-grounded planning 与 implementation 准备过程中暴露出的 Contract ambiguity、implementation conflict、migration exception，以及经过人工分析后冻结的实现级决定。

本文不是新的 Source of Truth，也不是完整设计文档，更不是 Codex / ChatGPT 对话记录。

其职责是保存：

- 问题为什么出现；
- 当前源码事实是什么；
- 有哪些真实可行方案；
- 最终选择了什么；
- 为什么这样选择；
- 该决定影响哪些 Contract / State / Runtime / Test；
- 哪些能力明确 deferred 到后续 Step。

当 clarification 改变正式的：

- Domain Contract；
- State semantics；
- Phase scope；
- migration rule；
- Acceptance Criteria；

最终结论必须同步回对应 canonical document。

当前 canonical documents 包括：

- `docs/application_track/EVIDENCEFLOW_IMPROVEMENT_MASTER_PLAN.md`
- `docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md`
- `docs/plans/P2_S3.md`
- `AGENTS.md`

本文保留 decision provenance；canonical documents 保留当前有效设计。

---

## 1. Clarification Status

本文使用以下状态：

### OPEN

问题尚未完成决策，implementation 不应在该问题上自行做架构性假设。

### RESOLVED

问题已经明确，但最终结论不改变正式 Contract / Phase semantics，因此主要保留在 Clarification Log。

### PROMOTED

问题已经明确，而且决定改变或补充正式 Contract、State semantics、migration rule 或 Acceptance Criteria。

对应 canonical document 必须同步更新。

### TEMPORARY

当前 Step 接受的临时 migration exception。

必须明确 removal / follow-up Step。

### SUPERSEDED

历史决定已经被新的正式决定替代。

不得继续作为当前 implementation rule。

---

# 2. Clarification Round 1

## C-01 — `ConductResearch` 如何映射为 `MedicalResearchTask`

**Status**: PROMOTED  
**Raised by**: Codex `/plan`

### Problem

当前 ODR `ConductResearch` 只有 free-form `research_topic`。

P2-S3 需要引入：

`MedicalResearchTask`

但 frozen design 没有唯一决定：

- `task_id` 是否由模型生成；
- Tool Schema 是否直接暴露完整 Domain Model；
- 还是由 Host / Dispatcher 完成 Tool Call → Domain Object 的转换。

### Relevant Baseline

当前 Supervisor 通过 LLM 产生 `ConductResearch` Tool Calls。

`supervisor_tools` 已经承担：

- Tool Call parsing；
- concurrency admission；
- Researcher input construction；
- Researcher Subgraph invocation；
- result aggregation；
- ToolMessage construction。

因此它天然已经是 Parent → Researcher delegation boundary。

### Options

1. Host envelope  
   LLM 只生成 task semantic fields，由 Host / Dispatcher 创建 identity 并构造完整 `MedicalResearchTask`。

2. Direct full task  
   LLM 直接生成完整 `MedicalResearchTask`，包括 `task_id`。

3. Dual old/new schema  
   同时支持旧 `research_topic` 和新的 structured task schema。

### Decision

采用 **Host envelope**。

LLM-facing `ConductResearch` 只负责表达 task semantics。

例如：

- `research_question`
- `evidence requirements`
- `source preferences`
- `priority`

Runtime identity 不由模型产生。

`supervisor_tools` / Dispatcher 根据 Tool Call 创建完整：

`MedicalResearchTask`

### Rationale

Task semantic decision 属于 LLM responsibility。

Task identity 属于 Runtime / Host responsibility。

让模型生成 `task_id`：

- 不增加智能能力；
- 增加 duplicate / malformed identity 风险；
- 将 deterministic runtime responsibility 错误交给模型；
- 不利于后续 tracing、retry 和 persistence 扩展。

同时不采用 Dual Schema，避免长期维持两个 LLM-facing task contracts。

Legacy compatibility 应主要存在于 Host / Adapter boundary，而不是污染新的 canonical Tool Contract。

### Impact

影响：

- `ConductResearch`
- `MedicalResearchTask`
- `supervisor_tools`
- Researcher input adapter
- Tool Contract tests
- runtime tracing

### Canonical Update

需要同步：

- `EVIDENCEFLOW_CONTRACTS_V1.md`
  - `MedicalResearchTask` identity ownership
  - Parent → Researcher Contract
- `P2_S3.md`
  - structured Supervisor delegation semantics

### Deferred

以下内容不在 P2-S3 设计：

- cross-run global task identity；
- retry attempt identity；
- durable task registry。

---

## C-02 — P2-S3 是否让真实 Researcher runtime 返回 `ResearchTaskResult`

**Status**: PROMOTED  
**Raised by**: Codex `/plan`

### Problem

P2-S3 可以有两种实现深度：

1. 只定义 `ResearchTaskResult` schema；
2. 让真实 Researcher runtime 已经穿过新的 structured Result boundary。

P2-S4 才负责完整 Source / Evidence / Finding population，因此需要明确 P2-S3 是否真正接线。

### Options

1. Shadow Result  
   真实 runtime 返回 `ResearchTaskResult`，同时继续保留 `compressed_research` / `raw_notes`。

2. Schema Only  
   P2-S3 只定义 schema 和 State，Researcher runtime 仍只返回 legacy fields。

### Decision

采用 **Shadow Result**。

P2-S3 必须让实际 Researcher runtime 穿过：

`MedicalResearchTask → ResearchTaskResult`

这一业务边界。

同时继续保留：

- `compressed_research`
- `raw_notes`

作为 legacy compatibility path。

### Shadow Result Semantics

P2-S3 中：

- `status` 反映实际 execution outcome；
- `summary` 可以映射当前 `compressed_research`；
- `findings` 可以为空；
- `evidence_ids` 可以为空；
- `source_ids` 可以为空。

上述空 structured collections 表示：

> P2-S3 尚未实现 structured Evidence population。

不能解释为：

> 当前 Researcher 没有实际使用任何来源或证据。

### Rationale

如果 P2-S3 只创建未被 runtime 使用的 schema，则无法真正验证：

- Parent / Researcher boundary；
- State integration；
- reducer semantics；
- legacy compatibility；
- runtime handoff。

Shadow migration 可以先验证 Contract Wiring，而不提前实现 P2-S4 Evidence Pipeline。

### Impact

影响：

- `ResearcherOutputState`
- `ResearchTaskResult`
- Parent `research_results`
- `supervisor_tools`
- `compress_research`
- runtime adapter tests

### Canonical Update

需要同步：

- `EVIDENCEFLOW_CONTRACTS_V1.md`
- `P2_S3.md`
- `CONTRIBUTION_MAP.md`

### Deferred

P2-S4 负责真实：

`Search Result → SourceRecord → EvidenceRecord → ResearchFinding → ResearchTaskResult`

population。

---

## C-03 — Tavily summarization failure 导致 raw content 进入 Graph State

**Status**: TEMPORARY  
**Raised by**: Codex `/plan`

### Problem

Frozen design 原则规定：

> Raw source artifacts 不应进入 Graph State。

但当前 ODR Tavily path 在 summarization timeout / failure 时，可能将较大的 raw webpage content 放入：

`ToolMessage → raw_notes → Graph State`

P2-S3 同时要求保留 legacy path，因此两个要求无法同时严格满足。

### Options

1. Strict Now  
   P2-S3 立即修改 fallback，阻止 raw page content 进入 legacy State。

2. Temporary Exception  
   P2-S3 只禁止新的 structured channels 保存 raw artifact，旧 fallback 暂时保留。

### Decision

采用 **Temporary Exception**。

P2-S3 不重构现有 Tavily summarization / raw-content fallback。

规则调整为：

- 新的 EvidenceFlow structured state channels 不得持久化 raw source artifact；
- 当前 legacy `ToolMessage/raw_notes` fallback 暂时保留；
- 不得将该 exception 扩展到新的 Source / Evidence / Result contracts；
- P2-S4 必须移除该 exception。

### Rationale

P2-S3 尚未实现：

- `ArtifactStore`
- Source normalization
- stable source snapshot
- Evidence-native ingestion

如果现在简单删除 raw fallback，可能为了满足未来 invariant 而破坏 baseline failure behavior。

更合理的是在 P2-S4 建立真正的 replacement：

`raw source → ArtifactStore → artifact_ref → SourceRecord`

### Impact

影响：

- Graph State invariant wording
- P2-S3 Non-goals
- migration rules
- P2-S4 TODO

### Canonical Update

原有绝对规则：

`Raw source artifacts MUST NOT persist in Graph State.`

需要修改为：

> New EvidenceFlow structured state channels MUST NOT persist raw source artifacts. Existing ODR legacy raw-content fallback is a temporary P2-S3 migration exception and must not be extended.

需要同步：

- `EVIDENCEFLOW_CONTRACTS_V1.md`
- `P2_S3.md`

### Follow-up

Removal target：

`P2-S4 — Evidence-native Researcher`

---

# 3. Clarification Round 2

## C-04 — `MedicalResearchTask.task_id` 的 v1 identity strategy

**Status**: PROMOTED  
**Raised by**: Codex `/plan`

### Problem

决定由 Host 负责 identity 后，仍需确定具体 identity strategy。

候选包括：

- namespaced Tool Call ID；
- independent UUID；
- semantic hash。

### Relevant Baseline

当前 `tool_call["id"]` 已贯穿：

`AIMessage.tool_calls → supervisor_tools → ToolMessage`

因此已有一个天然的 delegation request identity。

P2-S3 当前没有：

- retry identity registry；
- global task registry；
- cross-run persistence requirement。

### Decision

采用 **Namespaced Tool ID**。

正常路径：

`task:{encoded_tool_call_id}`

其中 runtime 必须对非空 `tool_call_id` 使用 deterministic、lossless/injective encoding。编码可以保留
常见安全字符的可读形式，但两个不同的原始 `tool_call_id` 不得编码为同一个 domain `task_id`。

如果缺失 `tool_call_id`，使用 deterministic run-local fallback，例如：

`task:iteration:{supervisor_iteration}:call:{ordinal}`

### Identity Semantics

P2-S3 的 `task_id` 定义为：

> run-local stable logical delegation identity。

它不是当前阶段保证 globally unique 的 persistent identity。

### Rationale

Tool Call 与 `MedicalResearchTask` 在当前 runtime 中是一一对应的 delegation event。

复用 Tool Call identity：

- 不需要维护额外 UUID mapping；
- tracing 更自然；
- Debug 时可以从 Task 回溯到 Supervisor Tool Call；
- 避免模型生成 identity；
- 避免 semantic hash 将语义相似但独立的 follow-up research 错误合并。

### Important Boundary

Supervisor observe 后发现全局研究不足，再次生成一个新的 `ConductResearch`：

→ 这是新的 `MedicalResearchTask`

→ 使用新的 `task_id`

即使它与之前 Task 语义接近。

Agentic re-planning creates new Tasks。

### Canonical Update

同步：

- `EVIDENCEFLOW_CONTRACTS_V1.md`
  - task identity semantics
- `P2_S3.md`
  - reducer / identity tests

### Deferred

未来如果需要：

- cross-run persistence；
- durable task lifecycle；
- single-task retry；

应区分：

`task_id = logical task identity`

和：

`attempt_id = execution attempt identity`

P2-S3 不引入 `attempt_id`。

---

## C-05 — `ResearchTaskResult.status` 的 serialization convention

**Status**: PROMOTED  
**Raised by**: Codex `/plan`

### Problem

设计文档中同时出现：

`SUCCESS / PARTIAL / FAILED`

与：

`success / partial / failed`

需要冻结 Python symbol 与 serialized wire value。

### Decision

采用：

Python Enum members：

- `SUCCESS`
- `PARTIAL`
- `FAILED`

Serialized JSON values：

- `"success"`
- `"partial"`
- `"failed"`

### Execution / Termination Semantics

P2-S3 的 status 只表达当前 Researcher invocation 的 execution / termination outcome，不是独立验证过的
Evidence sufficiency、Evidence quality、coverage、grounding 或医学正确性判断：

- `SUCCESS`：Researcher 正常终止（没有继续发起 tool call，或显式调用 `ResearchComplete`），且成功产生
  compression / result output；若同一步同时触达 budget boundary，显式 `ResearchComplete` 优先。
- `PARTIAL`：Researcher 因 tool-call budget 或已识别的 tool failure 被迫终止，但仍成功产生可使用的
  partial result output。
- `FAILED`：task 因 admission、child execution 或 compression failure 未能正常完成 result boundary；
  finalization/failure boundary 已经能够取得且通过 validation 的可用 Source/Evidence/Finding references
  仍必须保留。hard child exception 在 State 返回前的 recovery limitation 由 C-13 进一步收窄。

`SUCCESS` 可以在 P2-S3 shadow Result 的 structured collections 为空时出现，因此不得将它解释为
Evidence-native quality verification 已经通过。

### Example

```python
class ResearchTaskStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
```

### Canonical Update

已同步到：

- `docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md`
- `docs/plans/P2_S3.md`

---

## C-06 — 相同 identity 的 reducer merge 语义

**Status**: PROMOTED

### Decision

- 不同 ID 按到达顺序追加；
- 相同 ID、完全相同 payload 视为 replay 并幂等去重；
- 相同 ID、不同 payload 抛出 contract conflict；
- 不做 field-wise merge；
- P2-S3 不引入 retry/attempt lifecycle。

未来若需要单任务 retry，先区分 logical `task_id` 与 execution `attempt_id`。

---

## C-07 — Materialized Task 的 failure contract

**Status**: PROMOTED

### Decision

每个成功 materialize 的 Task 都产生一个 `ResearchTaskResult`：

- Researcher 完成 → `SUCCESS` 或 `PARTIAL`；
- child subgraph exception → `FAILED`，error 前缀为 `execution_failure`；
- concurrency admission overflow → `FAILED`，error 前缀为 `admission_failure`。

无法通过 `ConductResearch` schema validation 的 call 尚未形成 Task，只产生明确的 legacy
contract-validation ToolMessage。该设计隔离单个 child failure，但不改变并发 topology。

---

## C-08 — Structured contract 到 legacy text 的映射

**Status**: PROMOTED

### Decision

采用单向 deterministic host renderer：

- `MedicalResearchBrief → research_brief Markdown`；
- `MedicalResearchTask → research_topic Markdown`；
- `ResearchTaskResult.summary → legacy ToolMessage/compressed_research`。

不再让第二次 LLM 调用独立生成 legacy prose，也不从 legacy Markdown 反向解析 structured contract。

---

# 4. Clarification Round 3

## C-09 — `ResearchTaskResult` 的 serialized contract version

**Status**: PROMOTED  
**Raised by**: Human core diff review

### Problem

P2-S3 已定义模块级 `CONTRACT_VERSION`，但 cross-graph `ResearchTaskResult` 的序列化结果无法从 envelope
本身发现 contract version，不满足 v1 versioning boundary。

### Decision

- `ResearchTaskResult` 是 P2-S3 唯一需要携带 serialized `contract_version` 的 cross-graph result
  contract。
- `contract_version` 的 v1 固定值为 `evidenceflow.contracts.v1`。
- 现有模块级 `CONTRACT_VERSION` 保持为 canonical code constant，Result 默认值和 validation 必须引用该
  常量。
- 不新增 `ResearchTaskResultEnvelope`。
- 不把 `contract_version` 添加到其他每一个 Domain Model。
- 未来 persisted Source/Evidence artifacts 的版本机制延后到引入其 storage boundary 的 phase。

### Rationale

Result 自身携带版本即可让 Parent、序列化 consumer 和 contract tests 在不依赖 Researcher implementation
module 的情况下识别 wire contract，同时避免在尚未进入 persistence scope 的领域对象上提前设计版本层。

### Impact

影响：

- `ResearchTaskResult` schema 与 serialization；
- Researcher → Parent contract tests；
- P2-S3 versioning wording。

### Canonical Update

同步：

- `docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md`
- `docs/plans/P2_S3.md`

---

# 5. Clarification Round 4 — Accepted Review Triage

## C-10 — P2-S3 provenance resolvability 的保证范围

**Status**: PROMOTED

**Raised by**: Post-implementation `/review`

**Accepted by**: Human frozen triage

### Problem

`ResearcherState` 可以保存 `SourceRecord`、`EvidenceRecord` 与 `ResearchFinding`，但当前
`ResearcherOutputState` 只投影 `ResearchTaskResult`、`compressed_research` 与 `raw_notes`。

当 Result 的 `source_ids` / `evidence_ids` 非空时，Researcher-local records 不会自动跨过 subgraph
output boundary；Parent/Supervisor State 也没有 run-scoped Source/Evidence registry。因此 P2-S3 当前
实现无法保证 populated IDs 在 Parent boundary 可解析。

### Relevant Baseline

- P2-S3 正常 runtime 仍是 shadow structured path，尚未真实 population Source/Evidence/Finding；
- P2-S3 不实现 Parent registry、EvidenceStore 或 ArtifactStore；
- 保留当前 Supervisor–Researcher Tool Loop 和 `ResearcherOutputState` projection。

### Options

1. P2-S3 新增 Parent Source/Evidence registries；
2. 将全部 records inline 到 `ResearchTaskResult`；
3. 收窄 P2-S3 guarantee，只保证 Researcher-local provenance consistency，并把 cross-boundary
   resolvability 设为 P2-S4 real population 的 mandatory prerequisite。

### Decision

采用 **Phase-scoped local guarantee**：

- P2-S3 不新增 Parent registry 或 EvidenceStore；
- P2-S3 的 provenance validator 只要求 Result references 能在同一次 Researcher finalization 可见的
  `source_records` / `evidence_records` 中解析；
- P2-S3 不声称 populated Source/Evidence IDs 在 Parent boundary 已经可解析；
- P2-S4 开始真实 structured population 之前，必须先实现 record carry、inline envelope 或 run-scoped
  registry 中的一种，使所有 Parent-visible IDs 可解析；
- P2-S4 不能以 bare dangling IDs 发布真实 structured Result。

### Rationale

P2-S3 的目标是验证 typed Task/Result wiring，而不是提前实现 storage/registry infrastructure。当前
shadow collections 通常为空，因此在本阶段增加 Parent registry 会扩大 phase scope，却不能替代 P2-S4
对真实 population boundary 的完整设计。

这是一项明确的 phase limitation，而不是对 end-state provenance requirement 的放宽。

### Impact

影响：

- `ResearchTaskResult` phase semantics；
- Parent/Researcher boundary wording；
- provenance contract tests 的 P2-S3 interpretation；
- P2-S4 entry criteria。

### Canonical Update

同步：

- `docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md`
- `docs/plans/P2_S3.md`

### Deferred

P2-S4 在真实 population 前选择并实现 Parent-visible record carry / inline / run-scoped registry。
EvidenceStore 仍属于 future reuse/retrieval layer，不是本决定要求的 P2-S4 infrastructure。

---

## C-11 — Provenance validator 必须成为 Researcher publish gate

**Status**: PROMOTED

**Raised by**: Post-implementation `/review`

**Accepted by**: Human frozen triage

### Problem

`validate_provenance_graph()` 已实现 Task/Result/Source/Evidence consistency checks，但当前
`compress_research` 构造 `ResearchTaskResult` 后直接返回。存在 validator 不等于 runtime 已经 enforce
provenance contract。

### Decision

- 在 Researcher publish/finalization boundary 调用现有 `validate_provenance_graph()`；
- normal、partial 和 failed candidate Result 在 emit 前都必须通过 validation；
- invalid Source/Evidence/Finding references 不得跨过 structured Result boundary；
- validation failure 必须中止 invalid candidate Result 的发布；现有 Parent child-failure isolation 可以将
  escaped boundary error 转换为不含 invalid references 的 task-correlated FAILED Result；
- 增加 focused regression tests，分别保护 normal finalization 与 failure finalization boundary。

### Rationale

Contract guarantee 取决于 validator 是否位于对象发布前的强制 boundary，而不是项目中是否存在一个可供
测试手动调用的 helper。

### Impact

影响：

- `compress_research`；
- failed Result construction；
- Researcher runtime tests；
- P2-S3 provenance Acceptance Criteria。

### Canonical Update

同步：

- `docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md`
- `docs/plans/P2_S3.md`

---

## C-12 — Structured Graph State compactness guardrails

**Status**: PROMOTED

**Raised by**: Post-implementation `/review`

**Accepted by**: Human frozen triage

### Problem

Raw-artifact metadata key denylist 可以被 provider aliases/casing 绕过；同时 `EvidenceRecord.excerpt` 只有
non-empty 约束，完整 HTML/PDF text 仍可能伪装成 excerpt 进入 structured Graph State。

### Decision

P2-S3 冻结并实现以下 runtime compactness guardrails：

- `EvidenceRecord.excerpt` 最大 **8000 characters**；
- `SourceRecord.metadata` 的 canonical compact JSON serialized representation 最大
  **8000 characters**；
- metadata serialized length 使用 UTF-8-independent Python character count：
  `json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))` 后取 `len()`；
- metadata key 在比较前忽略 case 和非字母数字 separator，使 `raw_html`、`raw-html`、`rawHtml` 等映射到
  同一 normalized key；
- `content`、`page_content` 与既有 raw/full-payload aliases 继续作为 content-bearing keys 被拒绝；
- key rejection 是 defense-in-depth，不能替代 serialized total bound 与 ArtifactStore boundary。

这些数字只表示 Graph State/runtime compactness guardrails，不表示：

- 医学证据质量；
- 引文充分性；
- excerpt 的临床语义边界；
- provider content 的可信度。

### Rationale

Architecture invariant 必须具有可执行和可测试的 bound。字符上限限制 State/checkpoint payload，normalized
key rejection 负责拦截明显误用，两者职责不同。

### Impact

影响：

- `SourceRecord.metadata` validation；
- `EvidenceRecord.excerpt` schema；
- domain boundary tests；
- Artifact Boundary 文档。

### Canonical Update

同步：

- `docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md`
- `docs/plans/P2_S3.md`

---

## C-13 — Hard child exception 的 partial-state preservation 范围

**Status**: PROMOTED

**Raised by**: Post-implementation `/review`

**Accepted by**: Human frozen triage

### Problem

当 error 在 Researcher finalization/failure boundary 内处理时，该 boundary 可以读取 local
Source/Evidence/Finding 并保留它们。但若后置 child node 抛出 hard exception，
`researcher_subgraph.ainvoke()` 不返回 child State；Parent catch 只有 exception，无法恢复之前
materialize 的 local records。

### Options

1. P2-S3 引入 checkpoint recovery；
2. P2-S3 引入 retry/attempt lifecycle 或新 persistence；
3. P2-S3 保持 topology 与 infrastructure 不变，明确 preservation guarantee 只覆盖 finalization/failure
   boundary 实际可见的 artifacts，并将 state-aware recovery 延后。

### Decision

采用 **Bounded preservation guarantee**：

- P2-S3 不引入 checkpoint recovery、retry/attempt lifecycle、新 persistence 或 topology change；
- P2-S3 保证 finalization/failure boundary 能取得的 valid Source/Evidence/Finding 不因 compression 或已
  处理 failure 被丢弃；
- hard child exception 在 child State 返回前逃逸时，Parent-generated FAILED Result 只保证 task
  correlation 与 error visibility，不保证恢复不可见的 child partial records；
- state-aware child failure handling/recovery 延后到 P2-S4/P2-S6；
- 该 limitation 必须保持显式，不得描述为当前 runtime 已完整满足 hard-exception partial preservation。

### Rationale

在 P2-S3 为恢复尚未真实 population 的 records 引入 checkpoint/persistence 或新 lifecycle，会破坏最小
change discipline，并扩大 architecture scope。明确 failure boundary 可以避免将无法兑现的保证写成实现
事实。

### Impact

影响：

- FAILED status 与 partial-artifact wording；
- Parent/Researcher failure contract；
- P2-S3 Risks / Non-goals；
- P2-S4/P2-S6 reliability inputs。

### Canonical Update

同步：

- `docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md`
- `docs/plans/P2_S3.md`

### Deferred

- P2-S4：在 evidence-native finalization 设计中评估 state-aware child failure boundary；
- P2-S6：结合 retry、observability 与 reliability evidence 决定是否需要 checkpoint recovery。
