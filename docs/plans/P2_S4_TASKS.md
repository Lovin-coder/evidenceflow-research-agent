# P2-S4 — Implementation Tasks

## 1. Execution Policy

每个 Task 必须：

- 只修改 Allowed files；
- 满足对应 SPEC invariants；
- 先完成 deterministic test，再进入 integration；
- 保留现有 Supervisor–Researcher Tool Loop；
- 保持 structured source of truth 与 legacy projection dual-write。

如果 implementation 需要修改 Domain semantics、graph topology、dependencies、lockfile、State ownership 或
Acceptance Criteria，必须停止当前 Task 并回到 Clarification / SPEC review，不得静默处理。

所有 Search ingestion task 都必须遵守：

```text
Provider SearchResult is not automatically an EvidenceFlow Source.

missing / unusable source content
→ no authoritative SourceRecord
→ no EvidenceRecord
→ warning / trace only
```

P2-S4 的五个关键 boundary tasks 为：

```text
T02 — deterministic Candidate boundary
T05 — Evidence authority boundary
T08 — Data Plane / Model Context boundary
T10 — provenance-preserving semantic compression
T11 — cross-agent provenance publication boundary
```

### Allowed-file mapping

| Task | Allowed files |
|---|---|
| T00 | `tests/`、本 PLAN/TASKS 文档 |
| T00A | `src/open_deep_research/domain_models.py`、`tests/test_domain_models.py`、`tests/test_state_contracts.py`、`tests/test_p2_s3_runtime.py`、`docs/application_track/EVIDENCEFLOW_CONTRACTS_V1.md`、P2-S4 phase docs |
| T01–T02 | `src/open_deep_research/evidence_ingestion.py`、`tests/test_evidence_ingestion.py` |
| T03 | `src/open_deep_research/artifact_store.py`、必要的 `src/open_deep_research/configuration.py`、对应 tests |
| T04 | `src/open_deep_research/prompts.py`、`src/open_deep_research/evidence_ingestion.py`、对应 tests |
| T05 | `src/open_deep_research/evidence_ingestion.py`、`src/open_deep_research/artifact_store.py`、对应 tests |
| T06–T07 | `src/open_deep_research/utils.py`、ingestion/store modules、对应 tests |
| T08–T09 | `src/open_deep_research/deep_researcher.py`、renderer 所在既定 module、对应 tests |
| T10 | `src/open_deep_research/deep_researcher.py`、`src/open_deep_research/prompts.py`、对应 tests |
| T11 | `src/open_deep_research/deep_researcher.py`、必要的 `src/open_deep_research/state.py` output typing、对应 tests；不得新增 Parent sibling Source/Evidence registry |
| T12 | T06、T08、T10、T11 已允许的 files 与对应 tests |
| T13 | `tests/`；仅修复 deterministic integration 揭示的 scoped implementation files |
| T14 | 不因 quality gate 扩大 production scope；只修复本阶段已允许 files |
| T15 | smoke evidence / phase documentation；不得为 smoke 修改 graph topology |
| T16 | `P2_S4_CHECKLIST.md`、`P2_S4_RETRO.md`、`CONTRIBUTION_MAP.md` |
| T17 | S4 runtime files、对应 tests 与 closeout docs；仅限 post-review corrective defects |

任何超出该 mapping 的 production file 修改必须先说明必要性，并检查是否触发 Clarification/Contract promotion。

---

## T00 — Baseline Guard & Fixture Preparation

### Goal

冻结当前 Search path baseline，为后续改造建立 regression guard。

### Work

确认：

- `tavily_search` entry；
- summarization call chain；
- `researcher_tools` dispatch path；
- Researcher State channels；
- `compress_research` inputs/outputs。

新增固定 fixtures：

- usable Tavily-like result：`title`、`url`、`content`、`raw_content`；
- missing/unusable `raw_content` result；
- medical raw-content document。

### Allowed

- `tests/`；
- `docs/plans/P2_S4.md`；
- `docs/plans/P2_S4_TASKS.md`。

### Forbidden

- production behavior changes；
- dependencies / lockfile；
- graph topology。

### Done

Fixtures 能分别表达 provider discovery result 与可进入 authoritative Source pipeline 的 accepted result。

---

## T00A — ResearchTaskResult Carrier Contract Promotion

### Depends

T00。

### Goal

落实 promoted `S4-D15`，将 `ResearchTaskResult` 升级为 self-contained task-level provenance aggregate，为后续
population 提供非悬空的 canonical cross-graph carrier。

### Spec

`S4-R01`–`S4-R05`、`S4-I16`–`S4-I17`、`S4-D15`。

### Implement

- add inline `source_records: list[SourceRecord]`；
- add inline `evidence_records: list[EvidenceRecord]`；
- retain `source_ids` / `evidence_ids` as explicit deterministic ordered projections；
- provide empty-list defaults for S3 shadow Result read compatibility；
- update provenance validator for same-Result Source/Evidence/Finding resolution；
- reject non-empty projected IDs without their inline targets；
- freeze `contract_version=evidenceflow.contracts.v1` behavior and atomic producer/consumer upgrade requirement。

### Contract Tests

- S3 shadow payload with empty ledgers remains readable；
- populated Result requires exact `source_ids == source_records IDs`；
- populated Result requires exact `evidence_ids == evidence_records IDs`；
- Evidence Source resolves inside the same Result；
- Finding Evidence resolves inside the same Result；
- duplicate or divergent identities rejected；
- serialized populated Result exposes v1 plus both inline ledgers；
- old strict consumer forward compatibility is not claimed。

### Forbidden

- Parent sibling Source/Evidence registries；
- EvidenceStore or store-backed ID-only Result；
- raw Source artifacts inside Result；
- global/cross-run Evidence identity；
- graph topology change。

### Done

Result schema、canonical Contracts 与 contract tests 对 D15 representation/version behavior 完全一致；后续 Tasks
不再选择 provenance carrier。

---

## T01 — Deterministic Source Text Normalization

### Goal

建立 Evidence locator 的 canonical text space。

### Implement

实现 `normalize_source_text()`：

- newline normalization；
- control-character cleanup；
- line trailing-space trim；
- excessive blank-line normalization；
- document trim。

### Files

- `src/open_deep_research/evidence_ingestion.py`；
- `tests/test_evidence_ingestion.py`。

### Spec

`S4-I03`、`S4-I04`、`S4-I05`、`S4-I07`。

### Tests

- same input → same output；
- CRLF handling；
- blank-line handling；
- control-character handling；
- empty/unusable normalized content rejected by ingestion gate。

### Done

Normalization 不调用 LLM，不依赖 network，并能明确判断 normalized content 是否 usable。

---

## T02 — Deterministic Candidate Chunker

### Depends

T01。

### Goal

实现：

```text
normalized_source_text
→ CandidateChunk[]
```

### Strategy

```text
paragraph-first
→ oversized paragraph sentence split
→ whitespace fallback
→ hard-boundary fallback
→ adjacent block packing
→ short-tail merge
```

初始 tuning range：

- target `≈ 1000–1200 chars`；
- max `≈ 1600–1800 chars`；
- min tail `≈ 250–300 chars`；
- `overlap = 0`。

实现常量必须满足 `MAX_CANDIDATE_CHARS <= MAX_EVIDENCE_EXCERPT_CHARS`。

### Candidate

内部 representation 包含：

- `chunk_id`；
- `start`；
- `end`；
- `text`。

### Tests

- determinism；
- all chunks contiguous；
- `text == source[start:end]`；
- order preserved；
- no max overflow；
- long paragraph；
- single huge sentence；
- small trailing chunk；
- empty input；
- short document。

### Done

同一 normalized text 与 config 多次运行产生 identical candidates。

---

## T03 — Minimal ArtifactStore

### Depends

T01。

### Goal

把 provenance 使用的 normalized source text 移出 Graph State。

### Implement

- `ArtifactStore` Protocol；
- `LocalFileArtifactStore`；
- `put_text`；
- `get_text`；
- run-scoped namespace/factory，使所有 Researcher calls 与 publication gate 共享 resolution lifetime。

### Tests

使用 `tmp_path` 验证：

- write/read exact equality；
- deterministic retrieval；
- missing artifact explicit failure；
- returned ref cannot escape configured root；
- artifact remains resolvable after originating Researcher call returns；
- two Researcher calls in one Run resolve through the same run-scoped namespace；
- different Runs do not implicitly share run-local artifact identity。

### Forbidden

- database；
- cloud storage；
- new dependency；
- retention lifecycle platform。

### Done

chunk locator 能从 artifact 重新取得 exact normalized text，Graph State 不持有 raw artifact。

---

## T04 — WebpageSelection Structured Contract

### Depends

T02。

### Goal

让现有 summarization model 只负责 semantic selection。

### Implement

internal schema：

```text
summary
selected_chunk_ids[]
```

Prompt 强调：

- select relevance；
- avoid redundancy；
- prefer factual / recommendation / limitation content；
- include relevant conflicting content；
- respect max selected count；
- no useful Evidence 时返回 `[]`。

Host validator 检查：

- known IDs only；
- no duplicates；
- within max selection limit。

### Files

- `src/open_deep_research/prompts.py`；
- `src/open_deep_research/evidence_ingestion.py`；
- `tests/test_evidence_ingestion.py`。

### Forbidden

- LLM-generated locator；
- LLM-generated authoritative excerpt；
- LLM-generated `evidence_id`。

### Done

Structured output 只表达 semantic selection，不拥有 Domain identity 或 Evidence content。

---

## T05 — Host Source & Evidence Materialization

### Depends

T00A、T02、T03、T04。

### Goal

实现：

```text
accepted Tavily result with usable normalized content
→ Researcher-local compact SourceRecord ledger

selected CandidateChunk
→ Researcher-local compact EvidenceRecord ledger
```

### Implement

概念 helpers：

- `build_source_record()`；
- `materialize_evidence()`；
- `validate_evidence_provenance()`。

`build_source_record()` MUST 位于 usable content gate 之后；无 usable normalized content 时不得调用它创建
authoritative Source。

Evidence 必须：

- exactly one Source；
- contiguous locator；
- `excerpt == artifact[start:end]`；
- Host-generated `evidence_id`；
- verified `content_hash`。

### Tests

- stable Source ID；
- stable Evidence ID；
- valid / invalid locator；
- excerpt mutation rejected；
- wrong Source rejected；
- same Evidence replay idempotent；
- missing/unusable content cannot create Source/Evidence。

### Done

每个 Evidence 都可由 Evidence ID 解析到 Source、artifact、locator 与 exact excerpt。

T05 只建立 authoritative Researcher-local compact ledgers，不 assembly 或 publish `ResearchTaskResult`；
cross-agent publication 由 T11 独占。

---

## T06 — Structured Tavily Execution

### Depends

T03、T04、T05。

### Goal

将当前 `tavily_search` internal pipeline 改造成：

```text
Tavily
→ content gate
→ structured SearchExecutionResult
```

### Add

`SearchExecutionResult` internal transport：

- `model_content`；
- `sources`；
- `evidences`；
- `warnings`。

### Implement

概念入口 `execute_tavily_search_structured(...)`。每个 provider result：

1. 验证 usable `raw_content`；
2. unusable 时仅追加 warning/trace，不创建 Source/Evidence；
3. usable 时 normalize 并 persist Artifact；
4. build Source；
5. chunk；
6. summarization/selection；
7. validate；
8. materialize Evidence；
9. render bounded model content。

### Preserve

- existing Tavily query semantics；
- existing search concurrency；
- existing Tool schema。

单 result 失败必须转换为 warning，同时保留成功 siblings。

### Done

固定 Tavily fixture 产生完整 `SearchExecutionResult`；无 usable content fixture 只产生 warning/trace。

---

## T07 — Preserve Agent-visible tavily_search

### Depends

T06。

### Goal

最小侵入地保持现有 Tool contract。

### Implement

现有 `tavily_search` wrapper：

```text
structured executor
↓
return model_content
```

Agent 不需要知道 `SourceRecord`、`EvidenceRecord` 或 `ArtifactStore` 的存在。

### Regression

- Tool name unchanged；
- Tool arguments unchanged；
- Researcher 能发出相同 Tool Call。

### Done

不修改 Researcher Tool-selection behavior。

---

## T08 — researcher_tools Dual-channel Integration

### Depends

T06、T07。

### Goal

让 Search execution 同时写入 Model Context 与 Data Plane。

### Tavily branch

```text
SearchExecutionResult.model_content
→ ToolMessage

sources
→ Researcher source state

evidences
→ Researcher evidence state
```

其他 Tools 继续走 `execute_tool_safely()`，不得重写 generic Tool runtime。

### Concurrency

保持 `asyncio.gather(...)`，并保持 Tool Call 输入顺序与 Observation 输出顺序对应。

### Tests

- 0 search calls；
- 1 search call；
- multiple search calls；
- search + non-search Tools；
- one result partial failure；
- complete search failure；
- unusable provider result produces no Source/Evidence。

### Done

同一次 Researcher Tool node output 同时具备 ToolMessages、SourceRecords 和 EvidenceRecords。

---

## T09 — Evidence-aware Researcher Rendering

### Depends

T08。

### Goal

让 Researcher observe Evidence，而不是 arbitrary provider text。

### Renderer

```text
Source metadata

Derived Summary (non-evidence)

Selected Evidence
[E...]
...
```

### Requirements

- bounded；
- explicit Evidence IDs；
- summary 标为 derived/non-evidence；
- no raw webpage dump；
- warnings 不伪装成 Evidence。

### Tests

- Evidence ID visible；
- excerpt visible；
- raw artifact absent；
- summary clearly separated；
- rejected SearchResult represented only as warning/trace。

### Done

Researcher 能基于 Evidence 判断 research gap 与是否继续 Search。

---

## T10 — Structured compress_research

### Depends

T08、T09。

### Goal

实现 provenance-preserving compression：

```text
EvidenceRecord[]
→ ResearchFinding[]
```

T10 只负责 semantic compression 与 structured Finding generation；它不 assembly/publish
`ResearchTaskResult`，也不决定 provenance carrier。

### Prompt

向模型提供 Evidence ID 与 authoritative excerpt，要求输出 Findings、summary、limitations。

### Host validation

每个 `finding.evidence_ids` 必须存在于 authoritative Evidence collection。

### Forbidden

Compression 不得：

- create Evidence；
- change Evidence excerpt；
- create Source；
- rebind Source/Evidence。

### Legacy

同一次 compression 同时产生 structured Findings 与 legacy `compressed_research`。

### Done

Researcher-local structured Findings 已生成，所有 Finding Evidence IDs 均对 authoritative local Evidence ledger
通过 Host validation，unknown Evidence IDs 被拒绝；Result publication 留给 T11。

---

## T11 — Cross-Agent Provenance Publication & Supervisor Projection

### Depends

T00A、T05、T08、T09、T10。

### Goal

建立 S4 cross-agent provenance publication boundary：

```text
Researcher local ledgers
→ validated Findings
→ assemble self-contained ResearchTaskResult
→ Publication Gate
→ ResearcherOutputState
→ Supervisor structured Data Plane
→ bounded model projection
```

### Spec

`S4-R01`–`S4-R09`、`S4-I11`、`S4-I13`、`S4-I16`–`S4-I18`、`S4-D15`、SPEC §24.9–§24.14。

### Result Assembly

- inline all valid compact `source_records` / `evidence_records` visible at the selected boundary；
- inline validated `findings`；
- derive `source_ids` / `evidence_ids` deterministically from inline record ordering；
- carry status、summary、limitations、conflicts、error；
- preserve valid records in `PARTIAL` / `FAILED` Results；
- do not carry Researcher messages、Candidates、provider payloads or raw Source artifacts。

### Publication Gate

Before every populated Result crosses `ResearcherOutputState`, validate：

- unique record IDs；
- exact Source/Evidence ID projections；
- every Evidence Source resolves within Result；
- every Finding Evidence resolves within Result；
- each published Source has a non-empty run-scoped `artifact_ref`；
- each `artifact_ref` remains resolvable after child return；
- locator parses and `artifact[start:end] == excerpt`；
- recomputed excerpt hash equals `EvidenceRecord.hash`；
- raw Source artifact absent from Result；
- per-record and total Result provenance payload bounds pass。

Invalid Results MUST NOT publish。Valid records that can form a `PARTIAL` / `FAILED` Result MUST NOT be erased by a
handled selector/compression/finalization failure。

### Supervisor model-facing projection

只 render：

- status；
- Findings；
- summary；
- limitations；
- conflicts。

完整 Source/Evidence 保留在 Data Plane。

Parent/Supervisor MUST consume the self-contained Result；T11 MUST NOT add Parent sibling Source/Evidence registries。

### Tests

- `ResearchTaskResult` retains/resolves Evidence；
- `source_ids` exactly match `source_records`；
- `evidence_ids` exactly match `evidence_records`；
- every Finding Evidence ID resolves；
- every Evidence Source ID resolves；
- artifact ref resolves after compiled Researcher return；
- artifact round-trip reproduces exact Evidence excerpt/hash；
- total provenance payload bound enforced；
- `PARTIAL` / `FAILED` Result retains valid inline records；
- Supervisor `ToolMessage` does not dump raw Source artifacts；
- Supervisor `ToolMessage` does not dump the full inline ledger；
- structured Result 与 bounded context projection 分离。

### Done

实现 `self-contained full structured Result ≠ bounded Supervisor context`，所有 provenance targets 合法跨越
Researcher boundary，且不存在 dangling IDs。

---

## T12 — Search / Evidence Failure Isolation

### Depends

T06、T08、T10、T11。

### Goal

补齐 S4 failure matrix。

### Cases

Tavily request failure：

```text
no Source
no Evidence
explicit error
```

One result malformed：successful siblings preserved。

`raw_content` missing/unusable：

```text
no authoritative SourceRecord
no EvidenceRecord
ingestion warning / trace only
```

Selector failure：accepted Source/Artifact preserved，no fabricated Evidence。

Invalid selected ID / provenance failure：invalid Evidence not materialized，其他 valid Evidence preserved。

Compression failure：Source/Evidence preserved，Finding absent，Task status 按 S3 frozen semantics 映射。

Publication gate failure：invalid Result 不跨边界；能够组成 valid partial Result 的 earlier records 保留并重新通过
同一 gate。

### Done

任何 handled later-stage failure 都不删除已经 valid 的 earlier artifact，provider/process/error content 永不升级为
Evidence。

---

## T13 — Deterministic Integration Suite

### Depends

T00A、T01–T12。

### Goal

形成完整 fixture data-chain regression。

### Flow

```text
fixed Tavily response
→ content gate
→ Source
→ Artifact
→ Chunk
→ selected IDs
→ Evidence
→ ToolMessage
→ ResearchFinding
→ Result assembly
→ Publication Gate
→ ResearchTaskResult
```

### Must assert

- Source ID deterministic；
- Evidence ID deterministic；
- locator valid；
- excerpt exact；
- unknown IDs rejected；
- Evidence never cross-Source merged；
- `AIMessage` never Evidence；
- Tool Error never Evidence；
- unusable provider SearchResult never Source/Evidence；
- Findings resolve；
- Result Source/Evidence ID projections exact；
- Result has no dangling Source/Evidence targets；
- artifact_ref remains resolvable after Researcher boundary；
- Result total provenance payload is bounded；
- full inline ledger is absent from Supervisor model prompt；
- dual-write works；
- topology unchanged。

### No

- network；
- real LLM。

---

## T14 — Quality Gates

### Depends

T13。

### Run

- targeted P2-S4 `pytest`；
- `ruff check ...`；
- scoped `mypy ...`；
- `compileall`；
- `git diff --check`；
- full existing test suite。

使用 repository 当前 frozen environment 与可用命令；若 scoped `mypy` 本身存在 baseline limitation，必须如实记录，
不得扩大配置修改。

### Forbidden

- disable type checking；
- skip failing contract tests；
- weaken validator；
- modify dependency/lockfile to silence quality gate。

---

## T15 — Real Medical Runtime Smoke

### Depends

T14。

### Flow

至少执行一个真实医学 research question：

```text
MedicalResearchTask
↓
Tavily search
↓
Source IDs
↓
Evidence IDs
↓
Evidence excerpts
↓
Finding evidence_ids
↓
ResearchTaskResult
↓
Supervisor observation
```

### Inspect

- Search 后不再只有 formatted string；
- 只有 usable content results 进入 Source collection；
- Evidence excerpt 确实来自 Source artifact；
- Researcher 可以再次 Search；
- Compression 不产生 unknown Evidence ID；
- Supervisor 不被 raw webpages 淹没；
- legacy final-report path 仍可运行。

完成一个通过的 controlled smoke 后停止额外 model experiments。

---

## T16 — P2-S4 Closeout

### Depends

T15。

### Update

- `docs/plans/P2_S4_CHECKLIST.md`；
- `docs/plans/P2_S4_RETRO.md`；
- `CONTRIBUTION_MAP.md`。

### Record

- Implemented；
- Deviation；
- Deferred；
- Runtime evidence；
- Tests；
- Smoke result。

不得把 Temporal Source Versioning、Evidence diversity、Groundedness、Claim/Citation 写成 P2-S4 已实现。

---

## T17 — Post-review Corrective Conformance

### Depends

T00A、T02、T03、T08、T10、T11、T12。

### Goal

Correct four verified implementation defects without changing the frozen Domain contract,
graph topology, or persistence scope.

### Allowed files

- `artifact_store.py`、`configuration.py`、`state.py`、`domain_models.py`；
- `evidence_ingestion.py`、`utils.py`、`deep_researcher.py`；
- corresponding deterministic tests and P2-S4 closeout documents.

### Implement

- replace node-local config mutation with one internal State-carried owning-run Artifact
  identity; no default `thread_id` reuse;
- distinguish Finding materialization failure from true Publication Gate failure and keep
  newly generated Finding batches atomic;
- preserve bounded structured execution issues in Researcher-local State and remove
  `ToolMessage` substring status inference;
- enforce `max_result_provenance_chars` during deterministic State admission using the same
  canonical measurement as the Domain validator and Publication Gate.

### Required regressions

- no explicit `artifact_run_id`: multiple graph nodes and later Researcher invocation share
  one namespace; independent runs do not;
- invented compression Evidence ID produces a gated FAILED Result retaining valid
  Source/Evidence rather than escaping the child boundary;
- a task-degrading issue still produces PARTIAL when its warning is absent from bounded
  model context;
- a deliberately small valid serialized provenance bound produces a deterministic accepted
  subset, a structured admission issue, aligned ToolMessage content, and a publishable Result;
- T02 directly covers empty input, a short single block, small-tail merge, and exact Evidence
  slicing after contract validation.

### Forbidden

- new Domain contracts or Parent sibling registries;
- storing `SearchExecutionResult` in Graph State;
- Publication Gate subset repair;
- dependency/lockfile or topology changes.

### Done

All corrective regressions and the existing deterministic suite pass, closeout claims are
updated to match the corrected evidence, and runtime smoke remains separately classified.

### Completion evidence

- project suite: `72 passed`;
- no-explicit-ID multi-iteration Supervisor namespace regression passed, including
  independent-run isolation and explicit sharing;
- recoverable Finding batch, structured issue/context separation, configured provenance
  admission, T02 edge cases, and Publication Gate regressions passed;
- targeted Ruff, scoped mypy, compileall, and `git diff --check` passed;
- clean proxy-sanitized runtime checks reached the model endpoint, Tavily, and structured
  Tavily executor; the single Researcher exceeded its 60-second bound, so full graph smoke
  was not attempted and remains explicitly blocked.
