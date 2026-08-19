# P2-S4 — Architecture Clarification Resolution

## 0. Document Status

| Field | Value |
|---|---|
| Phase | P2-S4 — Evidence-native Researcher |
| Status | **RESOLVED FOR SPEC FREEZE** |
| Resolution authority | Human Architecture Resolution, 2026-08-17；S4-D15 Human Resolution, 2026-08-18 |
| Previous state | Specification-bootstrap decision buffer with `S4-D00`–`S4-D14` OPEN |
| Canonical promotion | Completed in frozen `P2_S4_SPEC.md` |
| Production implementation | Not authorized by this document alone |

P2-S4 Architecture Clarification 已完成。本轮不继续扩展新的 first-class Domain Model 或横向基础设施
能力。后续工作进入：

```text
Clarification Resolution
→ SPEC Freeze
→ PLAN
→ TASKS
→ CHECKLIST
→ Runtime Implementation
```

本文件是 Human Resolution 与历史 architecture questions 的 decision record。它冻结业务责任、边界与
禁止事项；具体算法、数值和 repository mapping 仍由 PLAN 在不改变这些语义的前提下补齐。

P2-S4 的核心目标冻结为：

> 将当前 ODR Researcher 从 text-centric search/compression pipeline 改造为 Evidence-native
> Researcher，使真实外部 Source、source-derived Evidence 和 model-generated ResearchFinding 成为具有
> 明确语义边界的结构化数据，并在 Researcher → Supervisor 的 compression 过程中保持 provenance。

当前 baseline 的核心结构性缺口是：`raw_notes` 混合 Tool Output、AIMessage、网页 Summary、搜索片段和
错误信息，并缺少稳定 Source/Evidence provenance。

---

## 1. Core Architectural Thesis

P2-S4 不以“增加更多模型调用”为目标。核心设计原则是：

> **Probabilistic semantics belong to the LLM; deterministic identity, materialization and provenance belong to
> the Host runtime.**

### 1.1 LLM responsibility

LLM 负责概率性的语义任务：

- semantic relevance；
- information selection；
- evidence interpretation；
- finding synthesis；
- research gap reasoning。

### 1.2 Host runtime responsibility

Host runtime 负责确定性的系统任务：

- identity；
- canonicalization；
- chunk boundary；
- locator；
- excerpt materialization；
- content hash；
- schema validation；
- ID resolution；
- provenance validation；
- failure preservation。

因此，EvidenceFlow 的质量提升不是简单增加 computation budget，而是：

- 缩小单个模型节点的职责范围；
- 减少模型同时处理 identity、storage、reasoning 和 synthesis 的负担；
- 保持不同阶段之间的信息语义；
- 防止 compression 丢失 Evidence provenance；
- 防止 model-generated content 被重新当作 external Evidence；
- 让错误可以定位到 Retrieval、Evidence Selection、Compression 或 Final Synthesis 的具体阶段。

---

## 2. Frozen Domain Chain

P2-S4 保持既有的一等 Domain 主链：

```text
MedicalResearchTask
        ↓
SourceRecord
        ↓
EvidenceRecord
        ↓
ResearchFinding
        ↓
ResearchTaskResult
```

P2-S5 以后继续扩展：

```text
ResearchFinding
        ↓
Claim
        ↓
Groundedness / Citation
        ↓
Final Report
```

P2-S4 不引入以下 first-class Domain Model：

- `QueryRecord`；
- `RetrievalObservation`；
- `ArtifactSnapshot`；
- `Claim`；
- `Citation`；
- `EvidenceSet`。

内部可以使用 implementation-level value object、typed envelope 或 helper representation，但不得把它们
升级成新的跨边界 Domain Contract，除非重新进入 Clarification/Contract promotion。

---

## 3. Source Semantics

`SourceRecord` 表示一个已经通过 Host ingestion gate、具有 usable normalized source content、可检查并有资格进入
provenance-bearing Evidence construction 的外部研究资源，例如：

- web page；
- paper；
- guideline；
- systematic review；
- official document；
- database record。

其核心问题是：

> **What external resource was retrieved?**

Provider `SearchResult` 只表示 discovery observation，不会自动成为 `SourceRecord`。冻结关系为：

```text
SearchResult ≠ SourceRecord
```

只有成功取得 usable source content，并能将 chunking 使用的 exact normalized text 持久化到 ArtifactStore 的
accepted result，才 materialize 为 authoritative `SourceRecord`。

### 3.1 Source identity ownership

- `source_id` MUST 由 Host runtime 生成；
- LLM MUST NOT 生成、修改或重新绑定 `source_id`；
- 同一个 canonical external resource 在同一 identity rule 下 MUST 映射为稳定 `source_id`；
- identity algorithm 必须 deterministic、versioned/testable，并能在并发 Researcher merge 时避免意外
  collision。

以下属于 PLAN / implementation-level decision，不在 SPEC 中提前冻结：

- hash algorithm；
- URL normalization details；
- tracking parameter handling；
- exact Source ID string format。

### 3.2 Query provenance

Search query 属于：

```text
Process / Trace Metadata
```

而不是：

```text
Evidence Domain Artifact
```

因此 P2-S4 不引入 `QueryRecord` 或 `RetrievalObservation`。一个 Source 被多个 Query 找到不会改变 Source
identity。Query → Source retrieval history 可以从 Tool Calls、runtime trace 或 LangSmith trajectory 观察，
P2-S4 不要求将其复制进 `SourceRecord`。

这项决定有一个明确边界：Trace 必须足够支持 Debug/Eval，但 Trace 不成为 Evidence provenance 的替代品。

### 3.3 Temporal source versioning

已知存在：

```text
same URL
↓
webpage changes later
↓
different observed content
```

但 **Temporal Source Versioning explicitly DEFERRED beyond P2-S4**。

P2-S4 不实现：

- historical webpage versioning；
- snapshot lifecycle/version graph；
- freshness policy；
- conditional refetch；
- cross-run cache invalidation；
- content diff。

Raw source persistence 的目标不是把 ArtifactStore 变成永久 Search Cache。其主要用途是：

- Artifact offloading；
- Debugging；
- provenance audit；
- frozen regression support。

网页未来发生变化不影响 P2-S4 当前 Run 内 Evidence pipeline 的正确性边界。Artifact fidelity 必须准确
描述为本次 Tavily retrieval 提供的 raw source content，不能夸大为永久、权威的网页版本系统。

---

## 4. Evidence Semantics

`EvidenceRecord` 表示从 exactly one Source 原始内容中直接取得的一段 bounded、contiguous、
source-derived passage。

冻结核心规则：

```text
One EvidenceRecord
=
one contiguous source-derived passage
from exactly one SourceRecord
```

关系为：

```text
SourceRecord 1 ─── N EvidenceRecord

EvidenceRecord → exactly one SourceRecord
```

P2-S4 不允许：

```text
one EvidenceRecord → multiple Sources
```

跨 Source 合并会破坏 provenance，并丢失 independent source support。

### 4.1 `excerpt` semantics

现有 `EvidenceRecord.excerpt: str` 是 Evidence 的 canonical bounded content。P2-S4 不新增重复的 text
字段。

`excerpt` 不表示：

- LLM summary；
- paraphrase；
- generated evidence；
- quality judgment。

它表示 Host 从 Source raw content 中确定性 materialize 的原文片段。`EvidenceRecord.excerpt` MUST 保持
source-derived content，不得由模型改写。

### 4.2 Evidence Selection is not Evidence Materialization

Evidence construction 分成两个职责不同的阶段：

```text
Evidence Selection
≠
Evidence Materialization
```

#### Evidence Selection

问题是：

> 当前 Source 中哪些候选片段与当前 Research Task 有关？

这是 semantic relevance problem，可由 LLM 完成。

#### Evidence Materialization

负责：

- `source_id`；
- `evidence_id`；
- `locator`；
- `excerpt`；
- `hash`。

这是 deterministic runtime problem，只能由 Host 完成。

冻结原则：

> **LLM may select Evidence candidates, but LLM MUST NOT author Evidence content.**

更准确地说：

```text
LLM references Evidence candidates
↓
Host materializes Evidence
```

---

## 5. Candidate Chunk Boundary

Raw source content 在进入 LLM selection 之前，由 Host 做 deterministic chunking：

```text
raw_content
    ↓
normalize
    ↓
deterministic chunking
    ↓
CandidateChunk[]
```

每个内部 Candidate 至少具有：

- Host-owned `candidate_chunk_id`；
- Source association；
- start/end locator；
- exact chunk content。

`CandidateChunk` 是 implementation-level intermediate representation，不升级为一等 Domain Model。

### 5.1 Frozen Candidate properties

#### Determinism

相同：

```text
normalized source content
+
chunking configuration/version
```

必须产生相同 chunk boundary。

#### Contiguity

每个 Candidate 必须对应 normalized source 中一个连续范围。

#### Resolvability

Host 必须能够从 locator 确定性重新取得 Candidate content。

#### Boundedness

Candidate 长度必须有明确上限，防止单一 chunk 占据过多 model context。

#### Host-owned identity

Candidate ID 和 locator 均由 Host runtime 生成。LLM 不生成 offset、locator 或 authoritative chunk
identity。

### 5.2 Not frozen in SPEC

以下具体规则进入 PLAN，并由 Tavily fixtures 与真实医学网页观察支撑：

- paragraph-first splitting；
- sentence-boundary fallback；
- `MAX_CHUNK_CHARS`；
- `MIN_CHUNK_CHARS`；
- overlap；
- paragraph grouping；
- whitespace normalization；
- heading retention。

SPEC Freeze 不提前冻结这些数字或算法。

---

## 6. Structured Summarization / Evidence Selection

`tavily_search` 是 P2-S4 的核心改造入口。冻结目标流程：

```text
Tavily Search
      ↓
structured Tavily results
      ↓
usable source-content gate
      │
      ├── rejected → warning / trace only
      │
      └── accepted
              ↓
      Source construction
              ↓
      ArtifactStore
              ↓
deterministic candidate chunking
              ↓
summarization / selection model
              ↓
structured selection result
              ↓
        Host validation
              ↓
    Evidence materialization
```

### 6.1 Tavily result handling

Tavily 返回的数据属于 External Tool Result。Host 必须先执行 usable source-content gate，不要求 LLM 重写 Source
schema：

```text
missing / unusable raw_content
→ no authoritative SourceRecord
→ no EvidenceRecord
→ retrieval/ingestion warning or trace only
```

只有具有 usable normalized source content 的 accepted result 才能由 Host 构造 `SourceRecord`。

Provider raw content 进入 ArtifactStore boundary；Graph State 只保留 compact metadata、bounded Evidence
excerpt 和 artifact reference。

### 6.2 Summarization model structured output

LLM structured output 应保持很小。概念结构可以是：

```text
WebpageSelection
    summary
    selected_chunk_ids[]
    selection_limitations[]  # optional debug/process field
```

该结构是 internal application result，不成为新的一等 Evidence Domain Model。`summary` 和
`selection_limitations` 不是 Evidence source of truth。

### 6.3 LLM MUST NOT return authoritative Domain fields

不得要求 summarization/selection model authoritative 地返回完整 `SourceRecord` 或 `EvidenceRecord`。以下
字段不能交给模型决定：

- `source_id`；
- `evidence_id`；
- `locator`；
- `excerpt`；
- content hash；
- artifact URI/ref。

Structured output 只提高 parse reliability，不自动提供 truth/provenance reliability。因此必须保持：

```text
LLM structured output
↓
Host validation
↓
Domain materialization
```

---

## 7. Evidence Selection Protocol

概念协议如下：

```text
Research Task / current topic

[C01]
exact candidate content

[C02]
exact candidate content

[C03]
exact candidate content
```

模型返回：

```text
selected_chunk_ids = ["C02", "C03"]
```

Host 验证：

- `C02` exists；
- `C03` exists；
- no unknown candidate ID；
- selection count is within policy。

随后：

```text
C02 → Host lookup → EvidenceRecord E01
C03 → Host lookup → EvidenceRecord E02
```

不采用：

```text
LLM returns excerpt
↓
another LLM validates excerpt
```

采用：

```text
Host chunks
↓
LLM selects IDs
↓
Host materializes exact text
```

---

## 8. Provenance, Relevance, and Groundedness

P2-S4 明确区分三个问题。

### 8.1 Provenance Validation

问题：

> 这个 Evidence 是否真实来自这个 Source？

由 deterministic code 完成：

```text
locator
↓
stored source artifact
↓
resolved content
↓
compare excerpt/hash
```

不需要 LLM Judge。

### 8.2 Relevance Selection

问题：

> 这个原文片段对当前 Research Task 是否有用？

这是 semantic task，由 summarization/selection model 判断。

### 8.3 Groundedness / Entailment

问题：

> Evidence 是否真正支持 Finding 或 Claim？

属于后续 Grounding protocol，主要在 P2-S5/P2-S6 处理。

因此：

```text
Provenance
≠
Relevance
≠
Groundedness
```

三者不得合并到一个 Judge 或一个模糊的“verified evidence”字段中。

---

## 9. Evidence Deduplication

P2-S4 不做 semantic Evidence merge。

Host 可以确定性处理：

- exact duplicate；
- identical normalized-content hash；
- obvious overlapping candidate interval。

不同位置、语义相似的两个原文片段不强制合并。跨 Source Evidence 严禁合并：

```text
E1 from guideline
E2 from systematic review
E3 from randomized controlled trial
```

即使内容高度一致，也保留为三个独立 Evidence，因为 independent source support 本身是后续 Evidence
Quality/Grounding 的重要信息。

### 9.1 Future Evidence-set quality

以下指标有价值：

- `unique_source_count`；
- source-type diversity；
- support distribution；
- conflict distribution；
- independent source support。

但它们描述的是 Finding ↔ Evidence Set，而不是单个 EvidenceRecord。P2-S4 不增加这些字段，相关设计
延后到 Grounding/Evaluation phase。

---

## 10. Search → Evidence Runtime

P2-S4 的核心 Researcher Tool path 冻结为：

```text
Researcher AIMessage
        ↓
web search Tool Call
        ↓
researcher_tools
        ↓
tavily_search
        ↓
Tavily raw structured result
        ↓
for each provider SearchResult
        ↓
usable source-content gate
        │
        ├── No
        │     → warning / trace only
        │     → no SourceRecord / EvidenceRecord
        │
        └── Yes
               ↓
        normalize source content
               ↓
           ArtifactStore
               ↓
           SourceRecord
               ↓
        deterministic chunking
               ↓
        CandidateChunk[]
               ↓
        summarization/selection model
               ↓
    summary + selected_chunk_ids
               ↓
          Host validation
               ↓
        EvidenceRecord[]
               ↓
        SearchExecutionResult
               ↓
        ├── structured State update
        └── bounded model-facing ToolMessage
```

`SearchExecutionResult` 是 internal transport/value object，不是一等 Domain Model。它必须同时支持 data
plane 更新与 model-context projection，但不得把 legacy formatted string 解析回 authoritative records。

---

## 11. Internal Service Boundary

Evidence processing 不暴露为 Agent-visible Tool。以下属于 internal application logic：

- `normalize_source(...)`；
- `build_source_record(...)`；
- `chunk_source_content(...)`；
- `validate_chunk_selection(...)`；
- `materialize_evidence(...)`；
- `validate_evidence_provenance(...)`；
- `render_researcher_observation(...)`。

模型不决定是否调用这些函数；runtime 在 search execution 后自动执行它们。

### 11.1 Agent Tool is not internal tooling

Agent-visible Tools，例如：

- `web_search`；
- `think_tool`；
- MCP tool。

由模型决定何时调用。

Internal Application Services，例如：

- chunking；
- canonicalization；
- Source construction；
- Evidence materialization；
- ID validation；
- Artifact persistence。

由 runtime 自动执行。Evidence ingestion 含有多个内部步骤，不代表每一步都应包装成 `@tool`。

---

## 12. Researcher Model Context

Evidence ingestion 后，Researcher 不直接 observe arbitrary provider string。Host 将 Source/Evidence 构造成
bounded model-facing view：

```text
[S01] Source title ...

[E01]
source-derived excerpt ...

[E02]
source-derived excerpt ...
```

Researcher 由此执行：

```text
Search
↓
Observe Evidence
↓
Assess evidence gap
↓
Search again if needed
```

这构成 Evidence-native Researcher loop。

### 12.1 Data Plane is not Model Context

Data Plane 在 Graph/runtime structured State 中保存：

- `SourceRecord[]`；
- `EvidenceRecord[]`；
- `ResearchFinding[]`；
- `ResearchTaskResult`；
- artifact references。

Model Context 只包含 renderer 组装进 System/Human/AI/Tool Message 的内容。

因此：

> Node/State 持有某个 field，不等于 LLM observe 了这个 field。只有 render 到 message 后，model 才能
> observe it。

---

## 13. Compression Boundary

Researcher 完成 Search loop 后进入现有 `compress_research` responsibility boundary。P2-S4 冻结其新职责
为：

```text
Evidence
+
research context
↓
structured ResearchFinding generation
```

而不是：

```text
Raw Source
↓
Evidence + Finding generation
```

Evidence 在 compression 之前已经由 Host materialize。

### 13.1 Provenance-preserving Compression

Compression context 向模型提供：

```text
[E01] exact evidence excerpt
[E02] exact evidence excerpt
...
```

模型生成 task-local `ResearchFinding`，包括 `text`、已有 `evidence_ids[]`、limitations/conflicts。模型只能
引用已经存在的 Evidence IDs。

Host validator 必须验证 every Finding Evidence ID exists。Compression 不允许：

- create `source_id`；
- create `evidence_id`；
- rewrite Evidence excerpt；
- rebind Evidence to another Source。

冻结原则：

> **Compression reduces context size, not provenance.**

Webpage selection → Evidence → ResearchFinding → compressed Researcher output → Final Report 之间不得丢失或
重新绑定 Source/Evidence IDs。

---

## 14. ResearchTaskResult and Supervisor Boundary

`ResearchTaskResult` 是完整 structured result。逻辑上包含：

- status；
- Sources；
- Evidences；
- Findings；
- summary；
- limitations；
- conflicts；
- failure information。

S4-D15 已冻结并提升具体 carrier：`ResearchTaskResult` inline compact Source/Evidence records，并保留
deterministic `source_ids` / `evidence_ids` projections。Parent 不增加 sibling Source/Evidence registries；大体积
Source artifact 继续由 run-scoped ArtifactStore 外置。

Supervisor LLM 不需要把所有 Source/Evidence 塞进 context。Host 为 Supervisor 构造 bounded projection：

```text
Research task
Status

Findings
F01 ...
F02 ...

Summary
...

Limitations
...

Conflicts
...
```

因此：

```text
ResearchTaskResult
≠
Supervisor model context
```

前者属于 Data Plane；后者属于 Context Projection。

---

## 15. Why Hierarchical Compression Exists

Researcher → Supervisor compression 不只是减少 Token。它同时提供：

- local Evidence isolation；
- semantic abstraction；
- context-size control；
- cross-topic interference reduction；
- parallel Researcher independence；
- adaptive Supervisor planning。

职责层次：

```text
Researcher
→ local raw Evidence + task-local Findings

Supervisor
→ global research Findings / gaps / delegation

Final Synthesis (later phases)
→ global Claims and report
```

这是 hierarchical information abstraction，不要求每个上层模型读取所有原始网页。

---

## 16. Conflict Semantics

P2-S4 保留当前 `ResearchFinding.conflicts` 能力，但不新增：

- `conflicting_evidence_ids`；
- `supporting_evidence_ids`；
- `contradicting_evidence_ids`；
- formal support labels。

这些字段会与后续 `SUPPORTED / PARTIAL / CONTRADICTED / UNVERIFIABLE` Grounding semantics 耦合，因此
延后到 P2-S5/P2-S6。

---

## 17. ArtifactStore Boundary

Raw source content 不进入新的 structured Graph State。Graph State 只保存：

- IDs；
- compact metadata；
- bounded Evidence excerpt；
- artifact reference；
- structured Findings/Result。

大体积 raw source 存放在 ArtifactStore，目的包括：

- State/checkpoint compactness；
- trace usability；
- Debugging；
- provenance audit；
- frozen regression。

ArtifactStore 不是跨 Run 的永久 Search Cache，不引入 Evidence Store、Vector DB 或 RAG。

以下 Store mechanics 进入 PLAN：

- protocol sync/async shape；
- local root/configuration；
- `artifact_ref` encoding；
- atomic write and collision rules；
- safe size/type bounds；
- test isolation；
- run-scoped resolution lifetime 与 post-run non-guarantee。

PLAN 中的选择不得改变“raw Artifact 不进入 Graph State、Run 内可审计、非永久 Search Cache”的冻结语义。

---

## 18. Failure Semantics

P2-S4 延续 S3 已冻结的 `SUCCESS / PARTIAL / FAILED` execution/termination semantics，不重新把 status 定义为
Evidence quality score。

### 18.1 Search request failure

```text
Tavily request failed
→ no SourceRecord from failed request
→ no EvidenceRecord
→ explicit Tool/retrieval failure
```

Tool Error 永远不能成为 Evidence。

### 18.2 Search result has no usable raw content

如果某条 provider `SearchResult` 缺少或无法提供 usable source content：

```text
no authoritative SourceRecord
no EvidenceRecord
retrieval/ingestion warning or trace only
```

该 result 不进入 authoritative structured Source/Evidence collections。P2-S4 不把 provider snippet、Tool Error、
model summary、formatted content 或 arbitrary provider text 当作 raw-content fallback，也不自动升级为 external
Evidence。

这冻结了两个连续的接纳边界：

```text
SearchResult
→ usable content gate
→ SourceRecord

CandidateChunk
→ semantic selection + Host validation
→ EvidenceRecord
```

### 18.3 Evidence selection failure

如果：

```text
Source ✔
Raw Artifact ✔
Candidate chunks ✔
LLM selection ✘
```

已经建立的 Source/Artifact 不因下游 failure 被擦除；该 Source 可以没有 Evidence，并保留 explicit
limitation。

### 18.4 Partial search ingestion

多个 Tavily result 中单条 malformed/failed 不要求整个 search invocation 原子失败。成功 records 可以
保留：

```text
R1 success → S1/E...
R2 success → S2/E...
R3 malformed → warning
R4 success → S4/E...
```

### 18.5 Compression failure

如果：

```text
Source ✔
Evidence ✔
Finding generation ✘
```

Result status 按 S3 frozen semantics 映射，但 SourceRecords/EvidenceRecords 必须在 selected
finalization/failure boundary 中保留用于 Trace/Debug/audit。

### 18.6 Partial ResearchTaskResult

如果 Research Task 只有部分 retrieval/evidence paths 成功但存在可用结构化产物，使用 S3 已冻结的
execution/termination mapping，并显式保留 warnings/limitations。

### 18.7 Hard child exception boundary

P2-S4 不因本次 Resolution 隐式引入 checkpoint recovery、durable persistence、attempt lifecycle 或新
topology。所有由 S4 pipeline 自己识别的 per-result/per-phase failure 必须在 child boundary 内转化并保留
已 materialize artifacts；在 State 返回前逃逸的 process-level hard exception 继续作为 known limitation，
由 P2-S6 reliability work 决定是否引入 checkpoint/state-aware recovery。

这一区分保证“failure preservation”不被描述成 runtime 当前无法兑现的无限保证。

---

## 19. Structured Source of Truth and Dual-write

迁移期间继续：

```text
Structured Path
+
Legacy Path
```

Search 层：

```text
Structured Source/Evidence
+
bounded legacy model-facing ToolMessage
```

Researcher 层：

```text
Structured ResearchFinding/ResearchTaskResult
+
legacy compressed_research
```

Supervisor 继续通过 bounded ToolMessage observation 做 runtime-adaptive planning。

新的 structured artifacts 是 system source of truth；legacy string 是 model-facing/compatibility projection。
二者必须来自同一次 Researcher execution，不能通过解析 legacy string 重建 authoritative records。

---

## 20. Decisions Explicitly Deferred

以下全部 **NOT BLOCKING P2-S4**：

- Temporal Source Versioning；
- RetrievalObservation Domain；
- QueryRecord Domain；
- cross-run search-cache freshness；
- semantic Evidence merge；
- embedding retrieval；
- reranker；
- Vector DB / RAG；
- production database persistence；
- S3/MinIO/distributed ArtifactStore；
- all Search Provider adapters；
- MCP Evidence implementation；
- `conflicting_evidence_ids` formal semantics；
- Evidence quality score；
- `unique_source_count` policy；
- source-type diversity policy；
- support/conflict distribution；
- medical evidence hierarchy scoring；
- Claim；
- Citation protocol；
- Groundedness Judge；
- Contradiction Judge；
- final-report generation protocol redesign。

知道这些问题存在，不代表必须在 P2-S4 解决。

---

## 21. Removed / Rejected Complexity

### 21.1 RetrievalObservation as first-class Domain

**Rejected for P2-S4.** 当前目标是 Evidence provenance，不是完整 Retrieval provenance platform。Query
attribution 可从 Trace 观察。

### 21.2 ArtifactSnapshot / Temporal versioning

**Deferred.** 该问题会把 S4 扩展为网页版本管理系统，不是当前医学 Research MVP 的最高价值边界。

### 21.3 LLM-generated EvidenceRecord

**Rejected.** Structured output 只能保证结构，不能保证 Evidence content 来自真实 Source。

### 21.4 LLM-generated locator

**Rejected.** Locator 属于 deterministic provenance，由 Host 生成。

### 21.5 LLM-generated excerpt plus semantic verification

**Rejected.** 不采用冗余链路：

```text
LLM generates excerpt
↓
LLM/code tries to verify excerpt
```

采用：

```text
Host chunks
↓
LLM selects ID
↓
Host materializes exact text
```

### 21.6 Host lexical retriever / BM25 / embedding as mandatory S4 scope

**Rejected as mandatory scope.** 当前复用 existing semantic model call 做 Candidate selection。只有未来出现
latency、cost、context 或 selection-quality 证据后，再评估 Retriever。

### 21.7 Every internal step as `@tool`

**Rejected.** Internal deterministic services 不暴露给 Agent，也不由模型决定是否调用。

---

## 22. Resolution of Previous Decision Register

下表将 Specification Bootstrap 与后续 canonical promotion 中的 `S4-D00`–`S4-D15` 映射到 Human Resolution。`PLAN delegated`
表示具体算法/数值仍待 PLAN，而不是架构语义仍 OPEN。

| ID | Resolution for SPEC freeze | Remaining PLAN responsibility |
|---|---|---|
| `S4-D00` | **RESOLVED FOR SPEC PROGRESSION**：Human Resolution 授权进入 SPEC Freeze → PLAN workflow；S3 stale status text 作为 documentation consistency item，不再阻止 S4 SPEC | 在 Checklist 记录 S3 status reconciliation，不得伪造不存在的 review evidence |
| `S4-D01` | **RESOLVED**：Tavily 保留 Agent-visible Tool；structured ingestion 由 internal runtime pipeline 完成，通过 internal `SearchExecutionResult` 同时输出 State update 与 bounded ToolMessage projection | 确定与 frozen LangChain Tool execution 的最小 adapter/API mapping |
| `S4-D02` | **RESOLVED / PROMOTED BY S4-D15**：ResearchTaskResult boundary logically owns complete resolvable Sources/Evidences/Findings；Parent-visible IDs 禁止 dangling；carrier 为 inline compact records | 实现 Result assembly/publication gate，并进行 serialized consumer/version tests |
| `S4-D03` | **RESOLVED / PROMOTED BY S4-D15**：不新增 first-class Domain Model；保持既有主链；inline ledgers 作为 Contracts v1 staged migration 的 additive completion | 实现 empty-ledger shadow read compatibility、atomic producer/consumer upgrade 与 v1 serialization tests |
| `S4-D04` | **RESOLVED**：本次 Tavily retrieval 返回的 usable raw source content 是 S4 auditable Artifact input；缺少 usable content 的 provider SearchResult 不 materialize Source/Evidence；不实现 original-web historical version system | 准确记录 provider fidelity、normalization input、content gate 与 malformed/missing content warning/trace behavior |
| `S4-D05` | **RESOLVED AT BOUNDARY**：使用 minimal run-scoped LocalArtifactStore 做 raw offloading/debug/audit/regression；Graph State 只存 opaque ref | protocol/ref/atomicity/size/path-safety/test-root/run-namespace mechanics |
| `S4-D06` | **RESOLVED AT SCOPE**：ArtifactStore 不是永久 Search Cache；只保证 Run 内跨 Researcher boundary 的 resolution lifetime；Temporal lifecycle/retention/GC system deferred | 冻结 Run 内 lifetime 与 explicit post-run non-guarantee，记录 privacy/copyright limitations |
| `S4-D07` | **RESOLVED**：Source identity Host-owned；Query 是 Trace metadata；不新增 QueryRecord，也不复制 query history进 SourceRecord；Temporal versioning deferred | URL canonicalization、tracking handling、ID/hash format与 fixtures |
| `S4-D08` | **RESOLVED**：Host deterministic chunks；LLM selects Candidate IDs；Host materializes exact contiguous excerpt/locator/hash；Provenance deterministic | normalization、chunk bounds、overlap、locator encoding、hash algorithm |
| `S4-D09` | **RESOLVED**：Evidence 在 Search ingestion 时 materialize；现有 compression responsibility 生成 structured ResearchFinding 并只引用已有 Evidence IDs | structured-output schema、helper/module mapping、prompt与 failure mechanics；不默认新增 Graph node |
| `S4-D10` | **RESOLVED**：structured artifacts 是 source of truth；legacy string 是 bounded context/compatibility projection；Supervisor 接收 Findings/summary/limitations/conflicts projection | renderer format、context budgets、legacy regression details |
| `S4-D11` | **RESOLVED**：per-result partial ingestion；无 usable content 的 SearchResult 只记录 warning/trace；handled downstream failure保留已 materialized Source/Evidence；沿用 S3 status；不把 Tool Error变 Evidence | phase→status→preserved-artifacts matrix；hard process escape仍是明确 limitation |
| `S4-D12` | **RESOLVED AT PRINCIPLE**：Candidate、Evidence、State与 model projection全部 bounded；不在 SPEC 冻结具体数字 | 基于 Tavily/medical fixtures确定 chunk/count/context limits |
| `S4-D13` | **RESOLVED**：S4 evidence-native实现范围为 Tavily；all-provider/MCP Evidence deferred；其他 Tool output保持 Process Artifact | 配置/运行时如何显式暴露 partial structured coverage |
| `S4-D14` | **RESOLVED AT EVIDENCE CLASS**：需要 frozen fixtures、Artifact round-trip、locator/hash audit、compiled boundary、failure与 controlled integration evidence | 在 PLAN/CHECKLIST 冻结命令、fixture version、smoke stop point与 pass criteria |
| `S4-D15` | **RESOLVED / PROMOTED**：`ResearchTaskResult` 是 self-contained task-level provenance aggregate，inline compact `SourceRecord[]` / `EvidenceRecord[]`，并保留 deterministic `source_ids` / `evidence_ids` projection；大体积 normalized Source artifact 继续由 run-scoped `ArtifactStore` 外置 | Result assembly、publication gate、payload bounds、run-scoped ArtifactStore lifetime 与 consumer compatibility tests |

本轮没有保留 blocking Architecture OPEN decision。PLAN 只能补充表中 implementation-level mechanics；若某
项 mechanics 会改变 Domain Contract、State ownership、Graph topology、migration rule 或 Acceptance
Criteria，必须重新打开 Clarification 并完成 canonical promotion。

---

## 23. S4-D15 — ResearchTaskResult Provenance Carrier

### 23.1 Problem

S3 `ResearchTaskResult` 携带 `source_ids` / `evidence_ids`，但对应 records 仍停留在 Researcher-local
`source_records` / `evidence_records`。

当前 `ResearcherOutputState` 在 child boundary 只投影 Result 与 legacy outputs；如果 P2-S4 直接 population
IDs 而不携带 resolution targets，则：

```text
ResearchTaskResult.evidence_ids
→ Parent 无 EvidenceRecord target
→ dangling provenance reference
```

这违反 P2-S4 Parent-visible provenance resolvability、failure preservation 与 downstream audit requirements。

### 23.2 Decision

P2-S4 SHALL promote `ResearchTaskResult` into a self-contained task-level provenance aggregate.

`ResearchTaskResult` SHALL inline compact `SourceRecord` and `EvidenceRecord` collections while retaining
`source_ids` and `evidence_ids` as explicit deterministic reference projections.

Large normalized Source artifacts SHALL remain externalized through the run-scoped `ArtifactStore` and SHALL NOT be
inlined into `ResearchTaskResult`.

`ResearchFinding` SHALL continue to reference Evidence through `evidence_ids`. `ResearchFinding` SHALL NOT inline,
copy, or rewrite authoritative Evidence excerpts.

Supervisor model context SHALL remain a bounded projection and SHALL NOT automatically receive the complete inline
Evidence ledger. Inline records belong to the structured Data Plane, not implicitly to model context.

P2-S4 SHALL NOT add Parent sibling Source/Evidence registries. The stable cross-graph business output remains one
self-contained `ResearchTaskResult`; complete Researcher-local process State still MUST NOT cross the boundary.

### 23.3 Resolution Chain

```text
ResearchFinding.evidence_ids[]
→ ResearchTaskResult.evidence_records
→ EvidenceRecord.source_id
→ ResearchTaskResult.source_records
→ SourceRecord.artifact_ref
→ run-scoped ArtifactStore
→ EvidenceRecord.locator
→ exact source-derived passage
```

### 23.4 Version and Compatibility Resolution

`evidenceflow.contracts.v1` remains the canonical contract version for P2-S4. The inline `source_records` and
`evidence_records` fields complete the Parent-visible end-state already reserved by Contracts v1; they do not change
Source, Evidence, Finding, status, identity, or provenance semantics.

For S3 shadow-result read compatibility, both inline collections SHALL deserialize with empty-list defaults. Empty
IDs plus empty records remain a valid S3 shadow payload. A populated P2-S4 Result MUST pass the stronger publication
gate and MUST NOT use the empty defaults to publish dangling IDs.

Because the current strict S3 model rejects unknown fields, an un-upgraded S3 consumer is not forward-compatible with
a populated S4 payload. Producer and consumer code therefore MUST be upgraded atomically; P2-S4 does not claim mixed
runtime-version wire compatibility. Any future removal, rename, requiredness change, or identity-scope change still
requires a new contract version or explicit migration.

### 23.5 Why

- **Minimal runtime change**：现有 Parent/Supervisor 已持有 `research_results`，无需新增跨层 registry channels
  或 reducers。
- **Self-contained cross-graph aggregate**：Task Result 可独立序列化、验证、调试和交付给后续 system stage。
- **Failure artifacts survive boundary**：在 finalization/failure boundary 可见的 valid Source/Evidence records
  可随 `SUCCESS` / `PARTIAL` / `FAILED` Result 一起发布。
- **No Parent registries**：避免 Result 与 sibling registries 的原子一致性、生命周期和并发 merge 复杂度。
- **No premature EvidenceStore**：S4 只完成 run-local provenance carry，不引入 durable persistence 或 retrieval
  platform。
- **Straightforward future adapter**：未来可以按 stable IDs 从 Result ledger 写入独立 EvidenceStore，而无需
  从 legacy strings 或 raw artifacts 重建 Evidence。

### 23.6 Rejected Alternatives

#### Parent sibling registries — REJECTED FOR P2-S4

该方案要求同时扩展 `ResearcherOutputState`、`SupervisorState`、`AgentState`、reducers 和 cross-subgraph
aggregation，并引入 Result/registry 同步问题。它对当前 task-local publication boundary 没有必要，且容易被
误解为 run-scoped EvidenceStore。

#### Store-backed ID-only Result — DEFERRED

该方案要求 durable EvidenceStore、store availability contract、transaction/partial-write semantics、cross-run
identity 与 migration policy。P2-S4 的 minimal ArtifactStore 只保存 normalized Source artifact，不是
authoritative Evidence database。Store-backed ID-only Result 延后到明确的 persistence/retrieval phase。

### 23.7 P2-S4 Non-goals

P2-S4 does NOT define:

- durable EvidenceStore；
- cross-run Evidence persistence；
- global Evidence identity；
- cross-run Source deduplication；
- vector retrieval；
- embedding lifecycle；
- index synchronization；
- object-storage migration；
- artifact retention / garbage collection；
- transactional persistence；
- Temporal Source Versioning。

### 23.8 Deferred Persistence / Retrieval Evolution

未来 Persistence / RAG phase MAY promote the following deferred decisions into its own SPEC:

- durable EvidenceStore and Source persistence；
- cross-run Source/Evidence identity and deduplication；
- durable ArtifactStore and artifact-ref migration；
- EvidenceStore ingestion adapter；
- embedding generation/version lifecycle；
- vector index synchronization and rebuild policy；
- retrieval policy and RAG context projection。

Roadmap-level summary SHOULD remain limited to：introduce durable Evidence persistence and derived retrieval indexes；
do not use a Vector Store as authoritative provenance storage。P2-S4 不创建单独的 future RAG canonical design
document。

#### Future Note 1 — Evidence ID scope

P2-S4 的 `evidence_id` 仍是 run-local identity。未来 persistence phase MUST NOT 假定它 globally unique，并且
必须明确选择：

- global Evidence identity；
- `(run_id, evidence_id)` composite identity；或
- content/provenance-derived identity。

#### Future Note 2 — Vector index is derived state

未来持久化架构必须保持：

```text
EvidenceStore
→ authoritative structured provenance

Vector index
→ derived, rebuildable retrieval projection
```

Vector DB MUST NOT become the provenance source of truth。

---

## 24. Architecture Value for EvidenceFlow

P2-S4 的核心差异不是单独某个 Schema，而是一组协同边界：

```text
External Source
        ↓
deterministic Host ingestion
        ↓
Source / Candidate Chunks
        ↓
LLM relevance selection
        ↓
Host-materialized Evidence
        ↓
LLM Finding synthesis
        ↓
deterministic provenance validation
        ↓
ResearchTaskResult
        ↓
bounded Supervisor observation
```

它解决三个核心 Agent 工程问题。

### 24.1 Trust boundary

LLM 可以做 semantic reasoning，但不能成为自己的 external evidence provider。

### 24.2 Information boundary

Raw Evidence、local Findings、global synthesis 分层处理，避免所有模型读取所有原始网页。

### 24.3 Evaluation boundary

最终报告失败时，可以定位：

- retrieval failure；
- Evidence selection failure；
- compression/Finding failure；
- provenance failure；
- final synthesis failure。

而不是只得到一个缺乏归因能力的 final report score。

这也是 EvidenceFlow 相比 baseline text-centric Deep Research 更核心的工程价值。

---

## 25. Promotion Checklist

- [x] Human Architecture Resolution 已记录。
- [x] Previous OPEN register 已逐项 disposition。
- [x] Domain chain 与不新增 first-class models 的范围已冻结。
- [x] LLM/Host responsibility boundary 已冻结。
- [x] Source/Evidence/excerpt semantics 已冻结。
- [x] Candidate chunk、selection、materialization、provenance职责已冻结。
- [x] Search → Evidence → Compression → Supervisor responsibility flow 已冻结。
- [x] Failure、dual-write、deferred/rejected complexity 已冻结。
- [x] 将本 Resolution 同步到 `P2_S4_SPEC.md`，移除已解决的 blocking OPEN 表述。
- [x] Human Resolution 已明确指定 `P2_S4_SPEC.md` 状态为 `FROZEN`。
- [x] `S4-D15` 已决定 self-contained inline provenance carrier，并同步到 canonical Contracts/SPEC。
- [x] `P2_S4.md` 已同步 Result assembly、publication gate 与 run-scoped ArtifactStore lifetime。
- [x] `P2_S4_TASKS.md` / `P2_S4_CHECKLIST.md` 已同步 cross-agent provenance publication boundary。

本 Resolution 只授权按照 frozen SPEC/PLAN/TASKS 实现；它不授权扩大到 deferred persistence、EvidenceStore 或
RAG scope。
