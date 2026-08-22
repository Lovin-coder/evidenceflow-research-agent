# P2-S4 — Evidence-native Researcher Specification

## 1. 状态

| 字段 | 值 |
|---|---|
| Phase | P2-S4 |
| Status | **FROZEN** |
| Architecture Clarification | Completed |
| Frozen upstream baseline | `20aaa0d422bd290c83f93574810ef1244e8d5955` |
| Governing resolution | `docs/plans/P2_S4_CLARIFICATIONS.md` |

任何未解决的架构问题都不得静默改变下文冻结的语义。

如果 implementation 发现本 SPEC 与真实 runtime 存在冲突，MUST 按以下流程处理：

```text
stop affected implementation
→ record conflict
→ update Clarification Decision
→ update SPEC
→ update PLAN/TASKS
→ resume coding
```

---

## 2. 目标

P2-S4 SHALL 将当前 Researcher search path 从 text-centric pipeline 改造成 Evidence-native pipeline。

目标链路：

```text
MedicalResearchTask
        ↓
Researcher
        ↓
Tavily Search
        ↓
SourceRecord
        ↓
EvidenceRecord
        ↓
ResearchFinding
        ↓
ResearchTaskResult
        ↓
Supervisor
```

P2-S4 SHALL 保留现有 ODR：

```text
Supervisor
↔
Researcher Tool Loop
```

P2-S4 不包含 `Planner`、`Send`、`RAG` 或其他 graph-topology migration。

---

## 3. 主要交付结果

P2-S4 MUST 交付：

- Tavily structured ingestion；
- Source construction；
- Artifact offloading；
- deterministic Candidate chunking；
- LLM Candidate selection；
- Host Evidence materialization；
- Evidence-aware Researcher observation；
- provenance-preserving compression；
- structured ResearchFinding；
- ResearchTaskResult population；
- self-contained ResearchTaskResult provenance ledger；
- cross-agent publication gate；
- failure preservation；
- legacy dual-write。

---

## 4. Domain 边界

### 4.1 `SourceRecord`

`SourceRecord` 表示一个已经通过 Host ingestion gate、具有 usable normalized source content、可检查并可用于
provenance-bearing Evidence construction 的 canonical external research resource。

Provider-level `SearchResult` 只表示 discovery observation，不会自动成为 `SourceRecord`。

- `source_id` MUST 由 Host runtime 生成；
- LLM MUST NOT 创建或修改 Source identity；
- 相同 canonical external resource 在相同 identity rule 下 MUST 映射为稳定 `source_id`。

### 4.2 `EvidenceRecord`

`EvidenceRecord` 表示来自 exactly one `SourceRecord` 的一段 bounded、contiguous、source-derived
passage。

```text
One EvidenceRecord
=
one contiguous passage
+
exactly one Source
```

`EvidenceRecord.excerpt` SHALL 是 canonical bounded Evidence content。P2-S4 SHALL NOT 引入重复的
Evidence text 字段。

### 4.3 `ResearchFinding`

`ResearchFinding` 表示 Researcher 基于一个或多个既有 Evidence IDs 生成的 interpretation 或 research
finding。

`Finding` 由 model 生成；`Evidence` 必须来自 Source。

两者 MUST NOT 混同。

---

## 5. Evidence Candidate Pipeline

`tavily_search` SHALL 在 legacy string rendering 之前保留 structured Tavily result。

每个 provider result 按以下职责链处理：

```text
Tavily SearchResult
        ↓
usable source-content gate
        │
        ├── No
        │     → warning / trace only
        │     → no SourceRecord
        │     → no EvidenceRecord
        │
        └── Yes
              ↓
      normalize source content
              ↓
          ArtifactStore
              ↓
          SourceRecord
              ↓
  deterministic CandidateChunk[]
              ↓
    semantic chunk selection
              ↓
    Host Evidence materialization
```

`CandidateChunk` 是 internal runtime representation，不是 first-class Domain Model。

因此：

```text
SearchResult ≠ SourceRecord
CandidateChunk ≠ EvidenceRecord
```

---

## 6. Deterministic Chunking 要求

Chunking MUST 满足：

- deterministic；
- bounded；
- contiguous；
- Host-generated locator；
- Host-generated Candidate identity；
- resolvable to normalized raw content。

相同：

```text
normalized content
+
chunking configuration/version
```

MUST 产生相同 Candidate boundaries。

具体 chunk size、overlap 和 splitting algorithm SHALL 在 PLAN 中定义，并通过 fixtures 验证。

---

## 7. LLM Selection Contract

summarization/selection model MAY 执行 semantic relevance selection。

其 structured output SHOULD 在概念上保持为：

```text
summary
selected_chunk_ids[]
```

模型 MUST NOT authoritative 地生成：

- `source_id`；
- `evidence_id`；
- `locator`；
- `excerpt`；
- `content_hash`；
- `artifact_uri`。

模型返回的 unknown Candidate ID MUST 使对应 selection 发生 deterministic validation failure，并且 MUST
NOT materialize `EvidenceRecord`。

---

## 8. Evidence Materialization

只有 Host runtime MAY 创建 `EvidenceRecord`。

Materialization SHALL 完成：

```text
selected Candidate ID
→ Candidate
→ Source
→ locator
→ exact excerpt
→ Evidence ID/hash
```

LLM MUST NOT rewrite Evidence excerpt。

---

## 9. Provenance Invariant

每个 `EvidenceRecord` MUST 满足：

```text
Evidence
→ exactly one Source
→ valid locator
→ stored Source Artifact
→ exact source-derived excerpt
```

Provenance validation MUST 由 deterministic code 完成。

Semantic relevance SHALL NOT 替代 provenance validation。

---

## 10. Evidence Immutability

`EvidenceRecord` 在一个 Run 内 materialize 后，其表达的 semantic content MUST NOT 被下游 LLM stage
rewrite。

下游 stage MAY：

- reference Evidence ID；
- select Evidence；
- group Evidence；
- reason over Evidence。

下游 stage MUST NOT redefine Evidence。

---

## 11. Process / Evidence Isolation

以下内容 MUST NOT 成为 External Evidence：

- `AIMessage`；
- `ResearchFinding`；
- model Summary；
- Tool Error；
- model-generated paraphrase。

只有满足 Evidence materialization contract 的 source-derived material 才能进入 structured Evidence
collection。

该边界直接处理 baseline `raw_notes` 中 AI-generated content 可能进入 grounding context 的问题。

---

## 12. Evidence Deduplication

不同 Sources 的 EvidenceRecords 即使语义相似，也 MUST 保持独立。

P2-S4 MAY 对同一 Source 执行 deterministic deduplication：

- exact duplicate；
- identical normalized content；
- obvious interval overlap。

P2-S4 MUST NOT 引入 semantic Evidence merge。

---

## 13. Artifact Boundary

MUST NOT 将 Raw Source content 新增持久化到 structured Graph State。

P2-S4 SHALL 使用 minimal `ArtifactStore` boundary，将 raw source artifact 存储在 structured State 之外。

Graph State MAY 保留：

- artifact reference；
- Source metadata；
- Evidence IDs；
- bounded Evidence excerpts；
- Findings。

P2-S4 的 Artifact persistence 用于：

- offloading；
- audit；
- debugging；
- reproducibility。

它不用于 production-grade cross-run search caching。

ArtifactStore SHALL be run-scoped rather than Researcher-call-scoped。一个 Run 内所有 Researcher invocation 与
downstream publication/provenance validation boundary MUST 能解析该 Run 已发布的 `artifact_ref`。P2-S4 不冻结
Run 结束后的 retention、garbage collection 或 durable migration policy。

---

## 14. Researcher Observation

Search execution SHALL 产生两个逻辑输出：

```text
Host-facing structured data
+
model-facing bounded content
```

Host-facing output：

- `SourceRecord[]`；
- `EvidenceRecord[]`；
- artifact references；
- warnings。

Model-facing output：

- bounded Source/Evidence rendering。

只有 model-facing rendering 进入 `ToolMessage.content`。

---

## 15. Data Plane 与 Model Context

Structured State 是 Data Plane；Messages 是 Model Context。

State 持有 Source/Evidence 不表示 LLM 自动观察全部 Source/Evidence。只有 explicit renderer 将 structured
data 投影到 model-facing Messages 后，LLM 才能观察这些内容。

---

## 16. Compression Contract

`compress_research` SHALL 消费 Researcher 已积累的 Evidence context，并生成：

- `ResearchFinding[]`；
- summary；
- limitations；
- 或 S3 已冻结的等价 `ResearchTaskResult` output。

每个 Finding MUST 只引用既有 Evidence IDs。

Compression MUST NOT：

- create Source IDs；
- create Evidence IDs；
- modify Evidence excerpts；
- rebind Evidence to another Source。

Compression 的职责是缩小 context，而不是重新定义 provenance。

---

## 17. `ResearchTaskResult`

`ResearchTaskResult` SHALL 保留足以支持下游 groundedness、citation、final synthesis、debugging 和
evaluation 的 structured Researcher output。

逻辑上包含 S3 frozen schema 已有或关联的：

- `SourceRecord`；
- `EvidenceRecord`；
- `ResearchFinding`；
- status；
- summary；
- limitations；
- conflicts；
- failure information。

`ResearchTaskResult` SHALL inline compact `SourceRecord[]` 与 `EvidenceRecord[]`，并保留 `source_ids` 与
`evidence_ids` 作为 deterministic reference projections。P2-S4 SHALL NOT 新增 Parent sibling Source/Evidence
registries，也不得发布 bare populated IDs。

大体积 normalized Source artifact SHALL 继续通过 run-scoped `ArtifactStore` 外置；不得 inline 到
`ResearchTaskResult`。完整 Researcher process State 仍不得跨越 Parent boundary。

Supervisor model context MAY 只使用该 Result 的 bounded projection。完整 structured Result 仍属于 Data
Plane。

### 17.1 Publication Requirements

#### `S4-R01` — Complete compact targets

`ResearchTaskResult` MUST contain all compact `SourceRecord` and `EvidenceRecord` targets required to resolve its
published `source_ids` and `evidence_ids`.

#### `S4-R02` — Source projection

`source_ids` MUST be the deterministic projection of `source_records`.

#### `S4-R03` — Evidence projection

`evidence_ids` MUST be the deterministic projection of `evidence_records`.

#### `S4-R04` — Evidence-to-Source resolution

Every `EvidenceRecord.source_id` MUST resolve within the same `ResearchTaskResult`.

#### `S4-R05` — Finding-to-Evidence resolution

Every identity in `ResearchFinding.evidence_ids` MUST resolve within the same `ResearchTaskResult`.

#### `S4-R06` — Artifact resolution lifetime

Every published `SourceRecord.artifact_ref` MUST remain resolvable through the run-scoped `ArtifactStore` after the
Researcher boundary.

#### `S4-R07` — No raw artifact inline

Large Source artifacts MUST NOT be inlined into `ResearchTaskResult`.

#### `S4-R08` — Result boundedness

`ResearchTaskResult` MUST remain bounded independently of Researcher search iteration count.

#### `S4-R09` — Context independence

Supervisor model rendering MUST remain independent from the full structured `ResearchTaskResult` payload.

---

## 18. Supervisor Observation

Supervisor SHALL 主要观察：

- Findings；
- bounded summary；
- limitations；
- conflicts；
- status。

Supervisor 不需要在 model context 中观察全部 raw Evidence content。

这是 context policy，不是 data-retention policy。完整 structured `ResearchTaskResult` 仍然提供给下游
system stage。

---

## 19. Failure Semantics

### 19.1 Search failure

失败的 Tool/Search invocation MUST NOT 从 error content 创建 Source/Evidence。

### 19.2 Result-level ingestion failure

一个 Tavily result 处理失败 MUST NOT 自动丢弃已经成功处理的 sibling results。

如果单条 provider `SearchResult` 缺少 usable source content，则该 result MUST NOT materialize 为 authoritative
`SourceRecord` 或 `EvidenceRecord`；它只能进入 retrieval/ingestion warning 或 trace。Provider snippet、Tool Error、
formatted content 或 model summary MUST NOT 作为 raw-content fallback 越过该 gate。

### 19.3 Evidence-selection failure

已经有效的 Source/Artifact data MUST 保留。invalid 或 unknown model-selected Candidate IDs MUST NOT
materialize Evidence。

### 19.4 Compression failure

Finding generation 失败时，已经有效且在 finalization/failure boundary 可见的 Source/Evidence artifacts
MUST 以 compact inline records 保留在 `PARTIAL` / `FAILED` `ResearchTaskResult` 中。Result 发布失败不得通过只保留
IDs 而丢弃对应 records 来伪装 failure preservation。

Task status MUST 继续遵循 S3 frozen `SUCCESS / PARTIAL / FAILED` semantics。

在 child State 返回前逃逸的 process-level hard exception 继续遵循 S3 known limitation；P2-S4 不隐式引入
checkpoint recovery、attempt lifecycle、durable persistence 或 topology change。

---

## 20. Dual-write

P2-S4 SHALL 在 migration 期间保持 compatibility。

Search：

```text
Structured Source/Evidence
+
legacy ToolMessage rendering
```

Researcher：

```text
Structured ResearchFinding
+
legacy compressed_research
```

Structured artifacts 是新的 authoritative data path。Legacy strings 是 compatibility/model-facing
projections。

两条 path MUST 来自同一次 Researcher execution；不得通过解析 legacy string 重建 authoritative
structured records。

---

## 21. Required Invariants

### `S4-I01` — Host-owned Source identity

`Source identity` MUST 由 Host deterministic 地生成。

### `S4-I02` — One Evidence, One Source

每个 Evidence MUST 属于 exactly one Source。

### `S4-I03` — Contiguous Evidence

每个 Evidence MUST 表示一段 contiguous source-derived passage。

### `S4-I04` — Evidence content authority

`excerpt` MUST 来自 stored Source content，不得来自 LLM generation。

### `S4-I05` — Host-owned locator

Locator 与 Candidate boundary MUST 由 Host code deterministic 地生成。

### `S4-I06` — LLM selection only

LLM MAY 选择 Candidate IDs，但 MUST NOT materialize Evidence。

### `S4-I07` — Deterministic provenance

Evidence locator MUST 能解析到 Evidence excerpt/hash 所表示的 content。

### `S4-I08` — Process/Evidence isolation

Model/process/error content MUST NOT 静默成为 External Evidence。

### `S4-I09` — Compression provenance

Compression MAY 引用 Source/Evidence identity，但 MUST NOT 创建或修改它们。

### `S4-I10` — Finding resolution

每个 Finding Evidence ID MUST 能在 authoritative Evidence collection 中解析。

### `S4-I11` — Failure preservation

在 selected finalization/failure boundary 可见的有效 Source/Evidence artifacts MUST NOT 被后续 handled
failure 擦除。

### `S4-I12` — Independent Source preservation

不同 Sources 的 Evidence MUST NOT 被 semantic merge 成一个 `EvidenceRecord`。

### `S4-I13` — Data-plane/context separation

Structured State 与 model-visible context MUST 显式分离。

### `S4-I14` — Temporal versioning deferred

Source temporal version management 不属于 P2-S4。

### `S4-I15` — SearchResult/Source separation

Provider `SearchResult` MUST NOT 自动成为 `SourceRecord`。只有具有 usable normalized source content、可持久化并可
审计的 accepted result 才能 materialize 为 authoritative Source；否则只能记录 warning/trace。

### `S4-I16` — Self-contained provenance publication

Parent-visible `ResearchTaskResult` MUST inline the compact Source/Evidence targets needed to resolve all published
provenance references。

### `S4-I17` — Deterministic Result projections

`source_ids` / `evidence_ids` MUST exactly and deterministically project the corresponding inline record identities；
不得成为独立且可能漂移的第二份事实。

### `S4-I18` — Run-scoped Artifact resolution

Published `artifact_ref` MUST remain resolvable for the Run after the originating Researcher invocation returns。

---

## 22. Non-goals

P2-S4 MUST NOT 要求：

- `QueryRecord`；
- `RetrievalObservation`；
- `ArtifactSnapshot`；
- Temporal Source Versioning；
- cross-run freshness cache；
- Vector DB；
- RAG；
- embedding retriever；
- reranker；
- semantic Evidence merge；
- production database；
- distributed object storage；
- all-provider Evidence adapters；
- Parent sibling Source/Evidence registries；
- durable EvidenceStore；
- cross-run Evidence persistence；
- global Evidence identity；
- cross-run Source deduplication；
- embedding lifecycle；
- vector index synchronization；
- object-storage migration；
- artifact retention / garbage collection；
- transactional persistence；
- Claim；
- Citation；
- Groundedness Judge redesign；
- Contradiction Judge；
- Evidence diversity scoring；
- medical authority scoring；
- final-report architecture redesign。

---

## 23. Deferred Improvements

后续 phases MAY 研究：

- Temporal Source Versioning；
- Evidence Set quality：
  - `unique_source_count`；
  - `source_type_diversity`；
  - independent source support；
  - support/conflict distribution；
- `conflicting_evidence_ids`；
- semantic Evidence selection optimization：
  - embeddings；
  - reranker；
  - hybrid retrieval；
- production Artifact persistence；
- medical Source Quality policy。

这些能力 MUST NOT 阻止 P2-S4 implementation。

---

## 24. Acceptance Criteria

P2-S4 只有在以下条件全部满足后才能完成。

### 24.1 Search ingestion

具有 usable raw content 的 fixed Tavily-like fixture MUST 能 deterministic 地生成 `SourceRecord[]`。

缺少或无法提供 usable source content 的 fixture MUST 只产生 warning/trace，不得生成 `SourceRecord` 或
`EvidenceRecord`。

### 24.2 Chunking

对相同 raw content 与 chunk configuration，以下结果 MUST deterministic：

- CandidateChunk boundaries；
- Candidate IDs；
- locators。

### 24.3 Evidence selection

structured model fixture 选择 `C02`、`C05` 时，只能 materialize Host-owned `C02`、`C05` exact content。

### 24.4 Invalid selection

Unknown Candidate ID MUST NOT 生成 `EvidenceRecord`。

### 24.5 Evidence provenance

每个 Evidence MUST deterministic 地解析到：

```text
Source
+
locator
+
source-derived excerpt
```

### 24.6 Evidence isolation

`AIMessage`、model Summary 与 Tool Error MUST NOT 进入 structured Evidence collection。

### 24.7 Multiple Source independence

来自不同 Sources 的 equivalent statements MUST 保持为独立 EvidenceRecords。

### 24.8 Compression

`ResearchFinding` MAY 只引用 existing Evidence IDs；unknown IDs MUST 被拒绝。

### 24.9 Failure preservation

Compression failure MUST 保留已经成功 materialize 且 boundary 可见的 Source/Evidence artifacts。

### 24.10 Supervisor context

Supervisor MUST 获得 bounded、Finding-oriented model-facing projection，并且 message context 不依赖 raw
Source content。

### 24.11 Artifact boundary

新的 structured Graph State MUST NOT 持久化 full raw webpage content。

### 24.12 Migration

Legacy ODR Researcher/Supervisor behavior MUST 通过 dual-write compatibility 保持可运行。

### 24.13 Topology

P2-S4 MUST NOT 引入新的 `Planner`、`Send`、`RAG`、vector retrieval 或 graph-topology migration。

### 24.14 Cross-agent provenance publication

Published `ResearchTaskResult` fixtures MUST prove：

- no dangling `source_ids` / `evidence_ids`；
- `source_ids` exactly match inline `source_records` identities；
- `evidence_ids` exactly match inline `evidence_records` identities；
- every Evidence Source resolves within the same Result；
- every Finding Evidence resolves within the same Result；
- every published `artifact_ref` survives the Researcher boundary and round-trips to the exact Evidence excerpt；
- raw Source artifacts are absent from the Result；
- the total provenance payload respects configured bounds；
- Supervisor model context does not automatically include the full inline ledger；
- `PARTIAL` / `FAILED` Results retain valid records visible at the selected failure boundary。

---

## 25. Validation Strategy

Deterministic tests SHALL 至少覆盖：

- Source ID determinism；
- usable source-content gate；
- unusable provider result cannot become Source/Evidence；
- Candidate chunk determinism；
- locator correctness；
- Evidence excerpt materialization；
- Evidence hash / Source resolution；
- invalid selected Candidate ID；
- cross-Source Evidence independence；
- process content cannot become Evidence；
- compression unknown Evidence ID；
- later-stage failure preservation；
- Result source/evidence projection equality；
- compiled Researcher boundary artifact resolution；
- Result total provenance payload bound；
- full inline Result exclusion from Supervisor prompt；
- structured/legacy dual-write；
- graph topology unchanged。

Fixture integration tests SHALL 使用：

- fixed Tavily-like response；
- fixed raw webpage content；
- stubbed structured selection model。

Deterministic contract tests 不需要 network 或 external LLM。

当前 architecture 已经将 fixed Tavily-like response、fixed webpage content、Evidence ledger 和
ResearchFinding 冻结为适合 fixture integration 的数据链测试边界。

---

## 26. SPEC Freeze Exit

本 SPEC Freeze 后进入：

```text
P2_S4_SPEC.md
        ↓
P2_S4.md
        ↓
P2_S4_TASKS.md
        ↓
P2_S4_CHECKLIST.md
        ↓
implementation
```

PLAN MAY 决定：

- exact chunking algorithm；
- internal helper/class layout；
- `ArtifactStore` interface shape；
- structured selector schema implementation；
- concurrency implementation details；
- renderer formatting；
- file locations；
- test helper organization。

任何 PLAN decision MUST NOT 违反本 SPEC 的 frozen invariants。

如果 PLAN 发现必须修改 Domain Contract、State ownership、Graph topology、migration rule 或 Acceptance
Criteria，MUST 返回 `P2_S4_CLARIFICATIONS.md`，完成新的 Human Resolution 与 canonical update 后才能继续。
