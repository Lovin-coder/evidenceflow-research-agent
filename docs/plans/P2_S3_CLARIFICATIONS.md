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
  已经 materialize 的可用 Source/Evidence/Finding references 仍必须保留。

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
