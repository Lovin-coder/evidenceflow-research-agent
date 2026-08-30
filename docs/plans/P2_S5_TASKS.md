# P2-S5 — Global Claim, Citation and Grounding TASKS

## 0. 状态与文档职责

| Field | Value |
|---|---|
| Phase | `P2-S5` |
| Document | `P2_S5_TASKS.md` |
| Status | **FINAL FROZEN** |
| SPEC status | **FINAL FROZEN / RENDERER RESYNCED** |
| PLAN status | **FINAL FROZEN** |
| Contracts status | **CONSISTENT / `evidenceflow.contracts.v1`** |
| Decision gate | **CLOSED — P01–P10 RESOLVED** |
| Coding gate | **CLOSED UNTIL CHECKLIST IS REVIEWED AND FROZEN + PRE-IMPLEMENTATION REVIEW COMPLETE** |
| Target branch | `p2-s5-claim-citation-grounding` |

本文将 frozen `P2_S5_PLAN.md` 拆解为可执行 implementation tasks。

文档职责：

```text
Semantic authority
EVIDENCEFLOW_CONTRACTS_V1.md
        ↓
P2_S5_SPEC.md

Decision provenance
P2_S5_CLARIFICATIONS.md

Implementation-quality governance
AGENTS.md
+
EVIDENCEFLOW_ENGINEERING_GUIDELINES.md

Implementation mapping
P2_S5_PLAN.md
        ↓
P2_S5_TASKS.md
        ↓
P2_S5_CHECKLIST.md
        ↓
implementation
```

Contracts / SPEC 决定系统必须保证什么；Clarifications 是 authoritative decision-provenance log，但不独立
定义 normative runtime semantics；PLAN 定义当前 ODR runtime 如何实现已冻结语义；TASKS 只拆解 exact
implementation units，包括 files、helpers、call sites、tests 与 dependency order。CHECKLIST 记录验证与
acceptance evidence。

TASKS 不得重新决定：

- Claim / Grounding / Citation semantics；
- Research Run boundary；
- message identity policy；
- retry authority；
- Source display grouping；
- Renderer authority；
- Manifest publication semantics；
- failure / replay semantics；
- metrics exposure；
- V1/V2 migration topology。

如果 implementation source inspection 暴露新的 Domain、State、identity、topology、failure 或 acceptance ambiguity，
停止受影响 Task 并回到 Clarifications / PLAN，不得由 Coding Agent 自行选择新语义。

---

## 1. Execution Rules

### 1.1 Task status

每个 Task 使用：

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
DONE
```

`DONE` 必须同时满足：

```text
implementation complete
+ focused tests complete
+ no known frozen-invariant violation
+ no unrecorded scope expansion
```

仅“代码已写”不等于 `DONE`。

### 1.2 Dependency rule

只有 dependency 已完成的 Task 才进入实现。`T00` 完成后，在无依赖冲突时允许并行：

```text
T01 / T02 / T04 / T05
```

后续按本文 dependency graph 收敛。

### 1.3 Change boundary

实现必须遵循：

- 不修改 frozen Contract semantics；
- 不新增 unrelated architecture；
- 不进行大规模 upstream refactor；
- 不为 convenience 创建第二套 identity/provenance representation；
- 不增加新的 Agentic Loop；
- 不引入 `Send`、queue、background worker；
- 不增加 generalized metadata framework；
- 不增加 generalized evaluation platform；
- 不通过降低 validators、跳过 tests 或 blanket ignore 完成 Task。

### 1.4 Tests belong to Tasks

TASKS 决定 concrete test coverage；CHECKLIST 负责最终验证这些 coverage 已存在并通过。

推荐 test ownership：

```text
tests/test_p2_s5_contracts.py
tests/test_p2_s5_state.py
tests/test_p2_s5_run_lifecycle.py
tests/test_p2_s5_types.py
tests/test_p2_s5_source_metadata.py
tests/test_p2_s5_projection.py
tests/test_p2_s5_claims.py
tests/test_p2_s5_grounding.py
tests/test_p2_s5_publication.py
tests/test_p2_s5_status.py
tests/test_p2_s5_display.py
tests/test_p2_s5_renderer.py
tests/test_p2_s5_pipeline.py
tests/test_p2_s5_integration.py
tests/test_p2_s5_faithfulness_eval.py
```

如果 repository existing convention 已经存在更合适的相邻测试文件，MAY 扩展现有文件而不是机械创建
新文件，但不得降低本 TASKS 定义的 coverage。

### 1.5 Unified Host retry and timeout policy

T07 Model A、T09 Model B、T16 Model C 与 T20 External Faithfulness Evaluator 共用一套 Host retry
policy。`max_structured_output_retries = R` 唯一解释为：

```text
maximum actual model/provider requests = 1 + R
```

Backoff sleep 不计为 request attempt。无论 failure classification 或 backoff 如何，actual requests 均不得突破
`1 + R`。

#### Validation failure

以下 Host/structured validation failure 立即 retry，不 sleep：

- schema validation failure；
- structured parse failure；
- reference validation failure；
- allowlist validation failure；
- aggregate payload validation failure；
- Host structural validation failure。

等待不会改变 deterministic Host validation problem，因此该类 failure 不使用 backoff。

#### Transient infrastructure failure

Provider、transport/network、timeout 或等价 transient infrastructure failure 使用 deterministic bounded
exponential backoff：

```text
retry #1 → 0.5 seconds
retry #2 → 1.0 seconds
retry #3 → 2.0 seconds
subsequent retries → 2.0 seconds
```

定义：

```text
delay = min(0.5 * 2 ** (retry_index - 1), 2.0)
```

`retry_index` 从 1 开始表示首次 retry。禁止 jitter、random sleep、provider-specific retry tree 或
secondary retry wrapper。Cancellation/system-level control flow 不得被 retry driver 捕获为普通 transient failure。

#### Single-attempt and retry-driver boundary

S5 实现 reusable private single-attempt primitive，例如 `invoke_structured_once(...)`；每次调用 exactly one
actual provider/model request。Host retry driver 只负责 failure classification、optional deterministic backoff 与调用
下一个 single attempt，不拥有 Model A/B/C/Evaluator 的 semantic validation authority。

T04 在 `global_synthesis/types.py` 或 T00 确认的现有 S5 shared internal location 提供该 reusable boundary。
不要为它创建 retry subpackage，helper 不得依赖 `pipeline.py`。Exact private helper name 可按 repository
命名惯例确定，但 semantic ownership 不得改变。

S5 Model A/B/C/Evaluator request path 不得依赖会额外发送 logical request 的 nested `.with_retry(...)` 或
provider/client automatic retry。若现有 wrapper/client 支持 `max_retries=0` 或等价机制，必须关闭或绕过。
不修改与 S5 request construction 无直接关系的 S1–S4 retry path。

#### Role timeouts

Timeout 是 per actual request 的 transient infrastructure failure，使用上述 backoff：

| Role | Effective timeout |
|---|---|
| Model A | `min(existing stricter provider/wrapper timeout, 90 seconds)` |
| Model B | `min(existing stricter provider/wrapper timeout, 60 seconds)` per Claim / per request |
| Model C | `min(existing stricter provider/wrapper timeout, 90 seconds)` |
| External evaluator | `min(existing stricter eval/provider timeout, 90 seconds)` |

如果当前 path 没有更严格 timeout，Host 必须 enforce 表中上限。Timeout 不得触发 valid semantic result
retry-to-pass，也不得突破 request-count invariant。

---

## 2. Dependency Overview

```text
T00
├─ T01
├─ T02 → T03
├─ T04
└─ T05

T01 + T04 + T05 → T06 → T07 → T08 → T09 → T10 → T11

T02 + T07 + T10 + T11 → T12
T02 + T04             → T13
T05 + T11             → T14
T10 + T14             → T15
T04 + T15             → T16
T14 + T16             → T17

T07 + T09 + T10 + T12 + T13 + T14 + T15 + T16 + T17
→ T18

T03 + T18       → T19
T12 + T14 + T17 → T20
T19 + T20       → T21 → T22 → T23
```

每个 Task 的 `Depends on` 是 exact dependency authority；上述概览与它们保持同一组 edges。

---

## 3. Implementation Tasks

### T00 — Implementation Preflight and Source Mapping

**Status:** `DONE`

**Depends on:** none

#### Goal

在任何 P2-S5 source modification 前确认当前 branch、runtime call sites 和已有 infrastructure 与 frozen PLAN 一致。

该 Task 是 read-only source audit，不重新选择 architecture。

#### Inspect

至少确认：

- `domain_models.py` 当前 stable contract base class / validation convention；
- `state.py` 当前 `AgentState`、reducers、`MessagesState` inheritance；
- `deep_researcher.py` entry / clarification / finalization / graph edge；
- Model construction 与 structured output wrappers；
- automatic model/provider retry 是否可关闭；
- current S4 `SourceRecord` materialization 的唯一 active writer/call site；
- `prompts.py` 当前 prompt organization；
- existing evaluation harness；
- current tests conventions；
- `langgraph.types.Overwrite` actual import/use path。

#### Required result

形成实现所需的 exact source map，但不新建 architecture document。

如果发现：

```text
multiple active SourceRecord writers
lower-level model retries cannot be disabled
current graph entry cannot express frozen lifecycle behavior
current code contradicts frozen Contract boundary
```

停止相关 Task 并报告 exact source evidence，不自行改变 PLAN。

#### Done when

- 所有 T01–T22 的 active call sites 均已定位；
- 没有新的 architecture-sensitive blocker；
- baseline tests 当前状态已记录。

### T01 — Implement P2-S5 Stable Domain Contracts

**Status:** `DONE`

**Depends on:** `T00`

#### Files

```text
src/open_deep_research/domain_models.py
tests/test_p2_s5_contracts.py
```

#### Implement

按 Contracts v1 增加或补齐：

```text
EvidenceRef
FindingRef
ClaimMateriality
ClaimRecord
GroundingStatus
ClaimGroundingRecord
Citation
GroundingManifest
```

继续复用当前项目 stable `ContractModel` / strict serialization convention。

#### Requirements

必须保证：

- required / optional fields 与 Contracts v1 一致；
- enum serialized values 一致；
- extra fields rejected；
- `FindingRef` / `EvidenceRef` non-empty identifiers；
- `ClaimRecord.finding_refs` non-empty；
- stable manifest `contract_version`；
- stable Domain models 不包含 drafts、metrics、issues、display metadata、report；
- `ClaimGroundingRecord.UNASSESSED` semantic consistency 由后续 Host validator 严格执行。

不要在 `domain_models.py` 增加：

```text
ClaimDraft
ClaimGroundingDraft
ReportDraft
SourceDisplayKey
GlobalSynthesisOutcome
receipts
evaluation models
```

#### Tests

至少覆盖：

- valid serialization round-trip；
- invalid enum；
- missing required field；
- extra field rejection；
- empty required IDs；
- empty Claim FindingRefs；
- Contract version；
- task-qualified refs with same bare ID remain distinct。

#### Done when

Stable contract code 与 Contracts v1 逐项一致且 focused tests 通过。

### T02 — Parent Process State and Reducer Semantics

**Status:** `DONE`

**Depends on:** `T00`

#### Files

```text
src/open_deep_research/state.py
tests/test_p2_s5_state.py
```

#### Implement

增加：

```text
GlobalSynthesisStatus
GlobalSynthesisSeverity
GlobalSynthesisIssue
ResearchRunStatus
```

Parent State 增加：

```text
grounding_manifest
global_synthesis_status
global_synthesis_issues
v2_shadow_report
research_run_status
research_run_input_cursor
```

#### Stable/open-stage boundary

`GlobalSynthesisIssue.stage` 的 stable type 是 `str`。不得在 stable State model 中使用 phase-local enum 做
closed deserialization。

#### Reducer semantics

实现或补齐：

```text
grounding_manifest
→ same-run one-shot publish
→ identical replay idempotent
→ divergent payload conflict

global_synthesis_status
→ Host replace

v2_shadow_report
→ Host replace

global_synthesis_issues
→ bounded append / dedup
→ defensive first-write-wins
```

P05 semantic payload reconciliation 不由 reducer 完成，留给 T13。

#### New-run reset support

确保所有 reducer-backed run-scoped channels 可以由 `Overwrite` 完整替换。

#### Tests

覆盖：

- unknown valid `stage` accepted；
- severity closed enum；
- identical Manifest replay；
- divergent Manifest replay；
- issue same-ID identical dedup；
- `Overwrite([])` truly clears merge/append channels；
- ordinary `[]` 与 `Overwrite([])` 行为区别；
- State serialization。

#### Done when

State contract 能够支持 P01、P05、P10，而没有扩大 Domain module 职责。

### T03 — Research Run Lifecycle and Entry Identity

**Status:** `DONE`

**Depends on:** `T02`

#### Files

```text
src/open_deep_research/deep_researcher.py
tests/test_p2_s5_run_lifecycle.py
```

必要时只做最小 `state.py` integration。

#### Implement

定义 private lifecycle conflict：

```text
_ResearchRunLifecycleConflict
```

实现 entry helper，例如：

```text
_bootstrap_or_resume_research_run(...)
```

#### Human occurrence calculation

计算 `current_human_count`。Initialized lifecycle 使用：

```text
fresh_delta =
current_human_count - research_run_input_cursor
```

实现 frozen mapping：

```text
fresh_delta < 0
→ lifecycle integrity conflict

fresh_delta == 0
→ no fresh input

fresh_delta == 1
→ status dispatch

fresh_delta > 1
→ lifecycle conflict
```

#### State machine

严格实现：

```text
no lifecycle + exactly one HumanMessage
→ first Run bootstrap

no lifecycle + zero/multiple
→ lifecycle conflict

ACTIVE + delta=0
→ same Run continuation/recovery

ACTIVE + delta>=1
→ lifecycle conflict

AWAITING_CLARIFICATION + delta=0
→ no-op / remain awaiting

AWAITING_CLARIFICATION + delta=1
→ resume same Run
→ ACTIVE
→ advance cursor

AWAITING_CLARIFICATION + delta>1
→ conflict

FINALIZED + delta=0
→ completed-run replay

FINALIZED + delta=1
→ new Run bootstrap
→ fresh artifact_run_id
→ advance cursor

FINALIZED + delta>1
→ conflict
```

#### Conflict requirements

Framework-level incoming `HumanMessage` admission MAY already have occurred。After that admission，every lifecycle
conflict MUST guarantee：

- `research_run_input_cursor` unchanged；
- `research_run_status` unchanged；
- `artifact_run_id` unchanged；
- no run-scoped reset；
- brief、Results、notes/raw notes、reports 与 Manifest unchanged；
- no global synthesis issue/status mutation；
- no sticky degradation mutation；
- no Claim、Grounding 或 Citation materialization；
- no implicit `ACTIVE` Run abandonment。

`messages` MAY contain the newly admitted `HumanMessage`。The conflicting occurrence MUST remain unconsumed by the
Research Run because the cursor is not advanced。Do not implement message rollback or deletion。

#### Conflict checkpoint tests

Given an existing active Run plus a framework-admitted conflicting `HumanMessage`，verify：

```text
messages
→ old messages + newly admitted conflict occurrence

research_run_input_cursor / research_run_status / artifact_run_id
→ unchanged

brief / Results / notes / raw_notes / final_report / v2_shadow_report
→ unchanged

grounding_manifest / global_synthesis_issues / sticky degradation
→ unchanged

new Claim / Grounding / Citation provenance
→ none
```

The node MUST raise `_ResearchRunLifecycleConflict`。The test MUST also verify no `RemoveMessage`、no compensating
rollback and no current/new Run consumption；it MUST NOT require `messages_after == messages_before`。

#### Message identity tests

验证：

```text
same message.id + same logical payload
→ no new occurrence

same text + no/replaced ID
→ new occurrence
```

same ID + divergent payload 仅作为 caller contract violation fixture/documentation，不实现 fingerprint 检测。

#### No mid-run steering

不得实现：

```text
ACTIVE + new message
→ modify brief/task/research
```

#### Done when

P01 state machine 在 checkpoint-backed tests 中具有 deterministic 行为。

### T04 — Internal DTOs, Receipts, Limits and Execution Types

**Status:** `DONE`

**Depends on:** `T00`

#### Files

```text
src/open_deep_research/global_synthesis/__init__.py
src/open_deep_research/global_synthesis/types.py
tests/test_p2_s5_types.py
```

如果 repository 希望减少 test files，可合并进 `test_p2_s5_contracts.py`，但 stable/internal tests 必须分区清楚。

#### Implement internal structured models

至少包括：

```text
ClaimDraft
ClaimDraftBatch
ClaimEvidenceVerdict
ClaimGroundingDraft

GroundingEvidenceView
RendererEvidenceView
ReportClaimView

ReportParagraphDraft
ReportSectionDraft
ShadowReportDraft

ClaimMaterializationReceipt
AssessedGroundingReceipt
UnassessedGroundingReceipt

GlobalSynthesisStage
GlobalSynthesisLimits
GlobalSynthesisExecutionContext
GroundingMetrics
GlobalSynthesisOutcome
```

推荐 aggregate：

```text
ClaimDraftBatch
└─ claims: list[ClaimDraft]

ShadowReportDraft
└─ sections: list[ReportSectionDraft]
```

#### Receipts

使用 frozen dataclass 或等价 immutable internal representation。必须保持：

```text
Assessed receipt
→ verdict + actual evaluated refs + expected status

Unassessed receipt
→ no fake evaluated universe
```

#### Host-produced stage vocabulary

至少覆盖：

```text
input_projection
claim_generation
claim_materialization
evidence_admission
grounding_judge
grounding_materialization
citation_materialization
publication_gate
shadow_rendering
renderer_validation
```

该 enum 仅约束 Host producer。

#### Shared retry execution boundary

按 §1.5 实现 Model A/B/C/Evaluator 共用的 private single-attempt/retry-driver boundary。该 boundary 只管理实际
request count、failure classification、deterministic wait 与 timeout；role-specific schema/reference/semantic validation
仍由各 owning Task 负责。不新建 retry micro-module/subpackage，也不依赖 `pipeline.py`。

#### GlobalSynthesisLimits

固定 PLAN 已定义的 limits：

```text
max_findings_total = 40
max_findings_per_task = 8
max_generator_evidence_chars = 96_000
max_task_summary_chars = 2_000
max_task_error_context_chars = 1_000
max_generator_context_chars = 128_000
max_claim_drafts_returned = 64
max_claim_batch_serialized_chars = 128_000

max_claims = 20
max_claim_text_chars = 1_500
max_claim_scope_chars = 500
max_qualifiers_per_claim = 8
max_qualifier_chars = 300
max_finding_refs_per_claim = 8

max_evidence_refs_per_claim = 24
max_judge_evidence_chars = 64_000
max_judge_context_chars = 80_000
max_grounding_reason_chars = 2_000
max_grounding_draft_serialized_chars = 16_000

max_citations = 512
max_manifest_serialized_chars = 1_000_000

max_global_synthesis_issues = 64
max_issue_message_chars = 1_000
max_issue_ledger_chars = 128_000

max_renderer_context_chars = 128_000
max_sections = 8
max_section_title_chars = 300
max_paragraphs_total = 24
max_paragraph_chars = 2_000
max_claim_ids_per_paragraph = 6
max_claim_occurrences_per_claim = 3
max_shadow_report_chars = 30_000
max_renderer_draft_serialized_chars = 128_000
```

保持：

```text
max_citations >= max_claims × max_evidence_refs_per_claim
```

#### Tests

覆盖 boundary value：

```text
limit-1
limit
limit+1
```

重点测试：

- structured aggregate serialized payload；
- `max_section_title_chars=300`；
- Renderer paragraph/section bounds；
- immutable receipts；
- stage `.value` 与 stable issue string 兼容；
- validation failure 不 sleep；
- transient retry delays 严格为 `0.5 / 1.0 / 2.0 / 2.0...`；
- no jitter 与 `1 + R` request-count bound；
- single-attempt primitive 每次只发送一个 actual request。

### T05 — Compact Search-provider Metadata Enrichment

**Status:** `DONE`

**Depends on:** `T00`

#### Scope

这是 **required small best-effort implementation task**。“Required”指 adapter implementation 必须完成；单个 provider
没有 optional metadata 时允许正常 omission。只扩充现有 S4 `SourceRecord` materialization，不创建 provider
abstraction framework。

#### Files

修改 T00 确认的 **现有唯一 active S4 SourceRecord materialization file/call site**。

测试优先放入 existing S4 Source materialization tests；若没有合适文件，再创建：

```text
tests/test_p2_s5_source_metadata.py
```

#### Canonical metadata scope

保留已有：

```text
url
title
provider
```

实现 Contracts v1 已列的 best-effort enrichment：

```text
retrieved_at
published_at
publisher
authors
document_type
```

`retrieved_at` 使用 Host-owned retrieval timestamp 与 repository 现有 UTC serialization convention，不引入第二套
time representation。其他字段只在 provider result 真实存在、type 合法且 adapter 可靠映射时写入。

P2-S5 不引入：

```text
retrieval_score
```

#### Tavily mapping

对当前 Tavily path，T00 先确认 actual provider keys；T05 仅对真实存在且通过验证的值执行：

```text
result.url
→ metadata["url"]

result.title
→ metadata["title"]

provider identity
→ metadata["provider"]

Host retrieval timestamp
→ metadata["retrieved_at"]

result.published_date
→ metadata["published_at"]
```

`published_date` 不存在或不合法时 omit，不得 fabricate。

#### Native/provider path

OpenAI / Anthropic/native search 只有在当前 response 确实提供可靠等价字段时才映射。

不得通过：

- URL pattern；
- title parsing；
- content；
- model inference；

补造 `publisher`、`authors`、`published_at` 或 `document_type`。

#### Explicit exclusions

不得加入 metadata：

```text
content
raw_content
page_content
full response payload
images
favicon
retrieval_score
```

继续满足 Source metadata compact payload bound 与 content-bearing key rejection。

#### Tests

覆盖：

- Tavily 已验证字段正常映射；
- Host retrieval timestamp 写入；
- missing optional fields；
- malformed provider date/metadata 不 fabricated；
- raw content 不进入 metadata；
- metadata 仍满足 serialized bound；
- enrichment 不改变 `source_id` / `artifact_ref`；
- S5 未引入 `retrieval_score` 或 quality heuristic。

#### Done when

Required adapter 已实现并经 focused tests 验证；optional provider fields 缺失时仍能正常 materialize Source，
且 S5 diff 仍是 small adapter change。

### T06 — Task-qualified Resolver and Bounded Projection Foundation

**Status:** `DONE`

**Depends on:** `T01`, `T04`, `T05`

#### Files

```text
src/open_deep_research/global_synthesis/projection.py
tests/test_p2_s5_projection.py
```

#### Implement resolver

建立 task-qualified resolution：

```text
task_id
→ unique ResearchTaskResult

FindingRef
→ owning Result.findings

EvidenceRef
→ owning Result.evidence_records
→ same Result SourceRecord
→ current-run Artifact when required
```

禁止 sibling scan。Duplicate/ambiguous `task_id` 必须拒绝。

#### Source metadata adapter

建立只读 normalized adapter，Model projection 只读 whitelist fields：

```text
url
title
provider
publisher
authors
published_at
document_type
```

`retrieved_at` 保留 retrieval provenance，默认不进入 Grounding/Renderer semantic context。

#### Generator projection

实现：

```text
MedicalResearchBrief
+ bounded ResearchTaskResult projection
```

顺序：

```text
Parent Result ledger order
→ per-task Finding cap
→ Finding order
→ Finding Evidence order
```

输出：

- task/status；
- bounded summary；
- limitations/conflicts；
- bounded error；
- FindingRef；
- Finding text；
- exact referenced Evidence excerpts；
- optional validated metadata。

建立 `generator_visible_finding_refs`。

#### Admission

Finding/Evidence authoritative units 使用 whole-unit admission。不得截断 Evidence excerpt。

非 authoritative summary/error 允许 bounded truncation，并应可观察地标记 truncation。

#### Zero-visible

没有 visible FindingRef：

```text
skip Model A
→ legal empty Claim candidate
```

如果 zero-visible 由 overflow/invalid upstream 导致，记录 degradation。

#### Tests

覆盖：

- same bare ID across tasks；
- unknown task/ref；
- sibling scan prohibited；
- Result ordering；
- whole-unit admission；
- no Evidence excerpt slicing；
- optional metadata missing；
- no raw Artifact；
- total role-context limit；
- deterministic replay。

### T07 — Model A Claim Generation and Materialization

**Status:** `DONE`

**Depends on:** `T01`, `T04`, `T06`

#### Files

```text
src/open_deep_research/global_synthesis/claims.py
src/open_deep_research/prompts.py
tests/test_p2_s5_claims.py
```

必要 model call orchestration 由后续 `pipeline.py` 组合，但 Claim-specific validation 保持在 `claims.py`。

#### Prompt

新增 `CLAIM_GENERATION_PROMPT`，明确：

- complete Claim proposition；
- scope/qualifiers；
- only allowed FindingRefs；
- Evidence 只是 context，不是 output reference；
- no `claim_id`；
- no EvidenceRef；
- no Grounding；
- no Citation；
- no hidden reasoning。

#### Structured invocation

实现一次 physical request primitive 或现有等价 mechanism。必须遵守：

```text
Host retry authority
maximum request count = 1 + R
```

lower-level automatic request retry 关闭/绕过。

Model A 必须使用 §1.5 的共享 Host retry driver。Schema/parse/reference/allowlist/aggregate/Host structural
validation failure 立即 retry且不 sleep；provider/transport/timeout 使用 deterministic capped backoff。

#### Timeout

Model A 每个 actual request 的 effective timeout：

```text
min(existing stricter provider/wrapper timeout, 90 seconds)
```

当前 path 没有更严格 timeout 时，Host enforce 90 seconds。Timeout retry 不得突破 `1 + R`。

#### Aggregate validation

验证：

```text
ClaimDraftBatch item count
serialized payload
schema
field bounds
```

Aggregate invalidity 可 retry。

#### Sibling validation

每个 Claim：

- FindingRefs non-empty；
- unique；
- resolve；
- visible allowlist；
- field bounds。

Individual invalid sibling：

```text
drop
→ degradation
→ valid siblings continue
→ do not retry whole batch just to repair sibling
```

#### Identity

实现 canonical Claim payload serialization 及 deterministic Claim ID。Identity 包含：

```text
original Generator ordinal
+ validated semantic payload
```

不得包含 survivor ordinal。

#### Exact duplicate

只 canonical exact duplicate。不得 fuzzy / embedding dedup。

#### Capacity

只有 validated count 超过 `max_claims` 才：

```text
HIGH
→ MEDIUM
→ LOW
```

同 tier 保持 Generator order，最后 survivors 恢复原 Generator canonical order。

#### Receipt

每个 materialized Claim 生成 `ClaimMaterializationReceipt`。

#### Tests

覆盖：

- Model A seen/unseen FindingRef；
- EvidenceRef output rejected；
- sibling invalid salvage；
- exact duplicate；
- near duplicate not dedup；
- Claim ID stability under sibling rejection；
- capacity；
- aggregate overflow retry；
- all siblings invalid；
- valid empty batch；
- validation failure immediate retry / no sleep；
- provider/timeout retry delays `0.5 / 1.0 / 2.0` 并 cap at `2.0`；
- 90-second Host timeout policy；
- actual requests `<= 1 + R`；
- nested provider/client retry disabled。

### T08 — Finding-derived Evidence Universe and Judge Projection

**Status:** `DONE`

**Depends on:** `T06`, `T07`

#### Files

```text
src/open_deep_research/global_synthesis/projection.py
src/open_deep_research/global_synthesis/grounding.py
tests/test_p2_s5_grounding.py
```

#### Evidence universe

对每个 surviving Claim：

```text
Claim.finding_refs order
→ resolved Findings
→ finding.evidence_ids order
→ EvidenceRef
→ exact first-occurrence dedup
```

Model A 不得影响该 universe。

#### GroundingEvidenceView

至少：

```text
EvidenceRef
exact excerpt
```

Optional：

```text
title
stored_url
provider
publisher
authors
published_at
document_type
```

不得包含：

```text
artifact_ref
full Artifact
raw provider payload
unvalidated metadata
```

#### Admission

应用：

```text
max_evidence_refs_per_claim
max_judge_evidence_chars
max_judge_context_chars
```

规则：

```text
canonical order
legal prefix
whole Evidence view
no rerank
no excerpt slicing
```

Omission 触发 degradation。

#### Empty admitted universe

```text
skip Model B
→ UnassessedGroundingReceipt
→ strict UNASSESSED path
```

#### Tests

覆盖：

- FindingRef order；
- first-occurrence EvidenceRef dedup；
- cross-task same bare Evidence ID；
- bounds；
- exact excerpt preserved；
- metadata optional；
- omission issue/degradation；
- empty universe。

### T09 — Model B Execution, Retry, Concurrency and Sibling Isolation

**Status:** `DONE`

**Depends on:** `T04`, `T08`

#### Files

```text
src/open_deep_research/global_synthesis/grounding.py
src/open_deep_research/prompts.py
src/open_deep_research/configuration.py
tests/test_p2_s5_grounding.py
```

#### Configuration

加入：

```text
max_concurrent_grounding_judgments: int = 4
```

#### Prompt

新增 `GROUNDING_JUDGE_PROMPT`，要求 Model B：

- judge complete Claim proposition；
- judge only admitted Evidence；
- return overall verdict；
- material supporting refs；
- material contradicting refs；
- bounded reason；
- no final GroundingStatus；
- no new Evidence；
- no hidden reasoning。

#### Per-Claim safe worker

实现 `_judge_claim_safe(...)` 或语义等价 helper。Ordinary Claim-local exception：

```text
affected Claim only
→ UNASSESSED path
→ issue
→ degradation
```

不得 catch system cancellation / `BaseException` semantics。

#### Concurrency

```text
Semaphore(max_concurrent_grounding_judgments)
+ asyncio.gather
```

最终 records 按 Claim canonical order，不按 completion order。

#### Retry

每 Claim 最多 `1 + max_structured_output_retries` requests。只 retry：

- provider/transport；
- timeout；
- schema；
- invalid refs；
- structural validation；
- output payload overflow。

Valid `INSUFFICIENT`、`CONTRADICTED`、`SUPPORTED` 均不得 retry-to-pass。

T09 使用 §1.5 的共享 Host retry driver：validation failure 立即 retry且不 sleep，provider/transport/timeout 使用
deterministic capped backoff。Model B effective timeout：

```text
min(existing stricter provider/wrapper timeout, 60 seconds)
```

该 timeout 按每 Claim、每 actual request 独立执行。一个 Claim 的 timeout/retry 不得改变 sibling execution
isolation 或 canonical output ordering。Lower-level nested request retry 必须关闭/绕过。

#### Tests

覆盖：

- concurrency bound；
- completion reorder；
- sibling ordinary exception；
- cancellation propagation；
- max actual request count；
- provider/schema failure；
- valid negative no retry；
- draft payload overflow；
- validation failure immediate retry / no sleep；
- provider/timeout retry delays `0.5 / 1.0 / 2.0` 并 cap at `2.0`；
- 60-second per-request/per-Claim timeout；
- one Claim retry 不影响 siblings 或最终 ordering；
- actual requests `<= 1 + R`；
- nested provider/client retry disabled。

### T10 — Grounding Validation, Five-state Materialization and Receipts

**Status:** `DONE`

**Depends on:** `T09`

#### Files

```text
src/open_deep_research/global_synthesis/grounding.py
tests/test_p2_s5_grounding.py
```

#### Validate Model B output

要求：

- supporting refs within evaluated；
- contradicting refs within evaluated；
- unique；
- disjoint；
- canonical filtered order；
- verdict-specific non-empty constraints；
- bounded/sanitized reason。

#### Materialize exact mapping

```text
SUPPORTED + no contradiction
→ SUPPORTED

SUPPORTED + contradiction
→ SUPPORTED_WITH_CONFLICT

INSUFFICIENT
→ INSUFFICIENT

CONTRADICTED + contradiction
→ CONTRADICTED

no valid semantic assessment
→ UNASSESSED
```

不得 heuristic override Model verdict。

#### Assessed records

```text
evaluated_evidence_refs
= exact actual successful Judge input
```

Reason present。生成 `AssessedGroundingReceipt`。

#### Strict UNASSESSED

必须：

```text
evaluated=[]
supporting=[]
contradicting=[]
reason=None
```

生成 `UnassessedGroundingReceipt`。Attempted Evidence 仅进入 issues。

#### Tests

覆盖所有 frozen legal/illegal combinations，特别是：

```text
INSUFFICIENT
+ supporting non-empty
+ contradicting non-empty
→ still INSUFFICIENT
```

### T11 — Citation Materialization and Deterministic Identity

**Status:** `DONE`

**Depends on:** `T10`

#### Files

```text
src/open_deep_research/global_synthesis/publication.py
tests/test_p2_s5_publication.py
```

#### Required Evidence refs

实现：

```text
SUPPORTED
→ supporting

SUPPORTED_WITH_CONFLICT
→ supporting + contradicting

INSUFFICIENT
CONTRADICTED
UNASSESSED
→ []
```

#### Citation identity

Citation ID 只使用：

```text
claim_id
+ EvidenceRef.task_id
+ EvidenceRef.evidence_id
```

不得包含 display/source metadata。

#### Ordering

```text
Claim canonical order
→ supporting canonical order
→ contradicting canonical order
```

#### Validation

Citation EvidenceRef 必须可解析。任何 required Citation materialization failure 使 candidate publication fail。

#### Tests

- deterministic ID；
- repeated replay；
- missing/extra/duplicate；
- conflict both roles；
- non-reportable no Citation；
- order independent of dict/set/async。

### T12 — Manifest Publication Gate, Replay and Derived Metrics

**Status:** `DONE`

**Depends on:** `T02`, `T07`, `T10`, `T11`

#### Files

```text
src/open_deep_research/global_synthesis/publication.py
tests/test_p2_s5_publication.py
```

#### Candidate Manifest

在 process-local memory 构造，不提前写 Parent State。

#### Publication Gate

Claim：

- unique；
- receipt-backed ID；
- FindingRefs resolve；
- generator allowlist；
- order/bounds。

Grounding：

- exactly one per Claim；
- no foreign/orphan；
- refs resolve；
- subset/disjoint/order；
- assessed/unassessed representation；
- receipt verdict/status match。

Citation：

- deterministic ID；
- refs resolve；
- exact required pair set；
- no missing/extra/duplicate；
- canonical order。

Manifest：

- `contract_version`；
- collection binding；
- payload bounds；
- deterministic order。

#### Gate rule

```text
validate
NOT repair
```

Failure 不发布 Manifest，不得在 candidate creation 后 sibling salvage。

#### Replay helper

实现：

```text
no Manifest
→ synthesis required

Manifest + report
→ full short-circuit

Manifest + report=None + PARTIAL
→ preserve
→ no automatic Model C retry
```

#### Metrics

实现 pure `derive_grounding_metrics(manifest)`，返回 Contracts 定义 metrics，zero denominator = `None`。

#### Tests

包括 Gate mutation tests：

- Claim ID；
- receipt；
- Grounding status；
- missing Citation；
- extra Citation；
- order；
- version；
- payload；
- identical replay；
- divergent replay；
- Renderer-failure replay；
- metrics all statuses / zero denominator。

### T13 — Issue Factory, Conflict Reconciliation and Global Status

**Status:** `DONE`

**Depends on:** `T02`, `T04`

#### Files

```text
src/open_deep_research/global_synthesis/types.py
src/open_deep_research/global_synthesis/pipeline.py
tests/test_p2_s5_status.py
```

可以先实现 helper，T18 再接入完整 pipeline。

#### Issue factory

ID coordinates：

```text
stage
code
claim_id
task_id
evidence_ref
attempt
bounded occurrence_key
```

Message 不参与 ID。实施：

- sanitized message；
- count bound；
- ledger payload bound；
- stable stage 写 `.value` string。

#### P05 reconciliation

Same ID + same semantic payload + message wording different：

```text
retain first
no conflict escalation
```

Same ID + semantic fields divergent：

```text
retain first
degradation_observed=True
emit ISSUE_PAYLOAD_CONFLICT
```

不得仅因此 invalidate Manifest。

#### Sticky degradation

`GlobalSynthesisExecutionContext.degradation_observed` 只允许 `False → True`，不能从 bounded ledger 反推。

#### Final status helper

```text
Manifest absent
→ FAILED

Manifest present + degradation
→ PARTIAL

Manifest present + Renderer failure
→ PARTIAL

Manifest present + output success + no degradation
→ SUCCESS
```

Valid `INSUFFICIENT/CONTRADICTED` 不自动 degradation。

#### Tests

覆盖：

- message-only divergence；
- semantic divergence；
- issue conflict issue 自身 deterministic；
- ledger full 后 late degradation；
- severity 不等于 degradation；
- empty Manifest success path；
- all valid negative claims still success。

### T14 — Reader-facing Source Display Projection

**Status:** `DONE`

**Depends on:** `T05`, `T11`

#### Files

```text
src/open_deep_research/global_synthesis/renderer.py
tests/test_p2_s5_display.py
```

#### Tagged keys

实现：

```text
TaskSourceDisplayKey
UrlArtifactDisplayKey
SourceDisplayKey
```

#### Key selection

```text
current Run
+ valid exact stored URL
+ resolvable artifact_ref
→ UrlArtifactDisplayKey

otherwise
→ TaskSourceDisplayKey
```

S5 不得 recanonicalize URL。

#### Grouping rules

允许：

- same canonical task Source；
- cross-task same Run + exact URL + same Artifact。

禁止：

- missing URL cross-task；
- different URL；
- different Artifact；
- different Run；
- bare Artifact hash 推断 cross-run equality。

#### SourceDisplayEntry

记录：

- key；
- contributing canonical Source refs；
- EvidenceRefs；
- selected metadata；
- label；
- bibliography text。

不得删除任何 canonical Source/Citation identity。

#### P06 metadata merge

Identity fields 来自 key。Display metadata：

```text
title
publisher
authors
published_at
document_type
provider
```

逐字段：

```text
canonical Citation traversal
→ first validated non-empty wins
```

后续不同值不覆盖；所有 contributing canonical Source refs 仍保留。

#### Labels

Canonical Citation traversal 中 first key occurrence 依次分配 `[1]`, `[2]`, ...。

#### Bibliography

使用 deterministic best-effort GB/T 7714-style；缺失字段 graceful omit；不得 fabricate。

#### Tests

覆盖所有 grouping/non-grouping cases、metadata conflicts、label stability 与 ordering。

### T15 — Renderer Claim/Evidence Projection and Context Admission

**Status:** `DONE`

**Depends on:** `T10`, `T14`

#### Files

```text
src/open_deep_research/global_synthesis/projection.py
src/open_deep_research/global_synthesis/renderer.py
tests/test_p2_s5_renderer.py
```

#### Report eligibility

只包括：

```text
SUPPORTED
SUPPORTED_WITH_CONFLICT
```

#### ReportClaimView

必须包含完整：

```text
claim_id
text
scope
qualifiers
materiality
grounding_status
```

#### RendererEvidenceView

只来自 `supporting_evidence_refs` / `contradicting_evidence_refs`，字段：

```text
EvidenceRef
role
exact excerpt
optional validated Source metadata
```

禁止：

```text
Grounding reason
evaluated-but-non-material Evidence
Artifact
full Result
notes
raw provider data
```

#### Context admission

先保留全部 Claim propositions。Evidence whole-unit 两阶段：

Phase 1：

- 每个 eligible Claim 尝试提供一个 supporting Evidence；
- 每个 `SUPPORTED_WITH_CONFLICT` 再尝试提供一个 contradicting Evidence。

Phase 2：

```text
remaining budget
→ canonical Claim/Citation order
→ remaining material Evidence
```

#### Omission

Context 无法容纳 Evidence 时：

- Claim 保留；
- Grounding 不变；
- Citation 不变；
- `degradation=True`；
- no excerpt slicing。

#### Tests

覆盖：

- all eligible Claim retained；
- conflict role minimum；
- non-material exclusion；
- reason exclusion；
- deterministic context overflow；
- complete Citation authority unaffected。

### T16 — Model C Structured Renderer and Aggregate Validation

**Status:** `DONE`

**Depends on:** `T04`, `T15`

#### Files

```text
src/open_deep_research/global_synthesis/renderer.py
src/open_deep_research/prompts.py
tests/test_p2_s5_renderer.py
```

#### Prompt

新增 `SHADOW_RENDERER_PROMPT`，告知 Model C：

- 自由决定 section count/title/order；
- 自由组织 paragraph；
- every body paragraph must bind Claim IDs；
- preserve complete Claim scope/qualifiers；
- use admitted supporting/conflicting Evidence；
- explicitly discuss meaningful conflict；
- do not output Citation identity/number；
- do not invent unavailable sources；
- do not modify Grounding role。

#### Structured output

使用 frozen DTO：

```text
ShadowReportDraft
└─ sections[]
   ├─ title
   └─ paragraphs[]
      ├─ text
      └─ claim_ids[]
```

#### Validation

验证：

- section count；
- title non-empty；
- title <= 300 chars；
- paragraph count；
- paragraph chars；
- Claim IDs non-empty；
- IDs exist；
- report-eligible；
- unique per paragraph；
- occurrence bounds；
- every eligible Claim covered；
- serialized aggregate bound。

Model output order 保留。禁止 unbound body paragraph。

#### Retry

Aggregate invalid 时 retry whole Renderer，最多 `1 + R` model requests。Valid 但语言一般时不 retry。

T16 与 T17 共用同一个 Model C `1 + R` attempt budget，T17 final-size validation failure 不得启动第二个
retry loop。Model C 使用 §1.5 共享 Host retry driver：aggregate/schema/reference/coverage/Host validation
failure 立即 retry且不 sleep；provider/transport/timeout 使用 deterministic capped backoff。

Model C 每个 actual request 的 effective timeout：

```text
min(existing stricter provider/wrapper timeout, 90 seconds)
```

当前 path 没有更严格 timeout 时，Host enforce 90 seconds。Lower-level nested request retry 必须关闭/绕过。

Exhaustion：

```text
Manifest preserved
report=None
PARTIAL
```

#### Zero eligible

不调用 Model C；实际 Host zero-output 由 T17 完成。

#### Tests

覆盖：

- structured shape、section/title/paragraph/binding/coverage/aggregate bounds；
- aggregate validation immediate retry / no sleep；
- provider/timeout retry delays `0.5 / 1.0 / 2.0` 并 cap at `2.0`；
- 90-second Host timeout policy；
- merely ugly but structurally valid prose 不 retry；
- T16/T17 共用一个 attempt budget；
- actual requests `<= 1 + R`；
- nested provider/client retry disabled；
- exhaustion semantics。

### T17 — Deterministic Report Finalization, Conflict Marker and Citation Injection

**Status:** `DONE`

**Depends on:** `T14`, `T16`

#### Files

```text
src/open_deep_research/global_synthesis/renderer.py
tests/test_p2_s5_renderer.py
```

#### Primary occurrence

根据 Model output canonical section/paragraph order 找到每个 Claim first occurrence。

#### Conflict disclosure

每个 `SUPPORTED_WITH_CONFLICT` 的 first occurrence：

- deterministic 插入 localized minimum conflict marker；
- supporting labels 可见；
- contradicting labels 可见。

Host 不 semantic classify Model prose 是否已“说得够好”。

#### Citation injection

```text
paragraph.claim_ids
→ canonical Claims
→ required Citations
→ SourceDisplayKeys
→ ordered union labels
→ final paragraph
```

重复 Claim 不生成新 Citation。Multi-Claim paragraph 按 canonical Claim/Citation traversal 做 ordered union。

#### Bibliography

只输出实际 Source display entries。

#### Final report bound

完成 Host post-processing 后再次验证 `max_shadow_report_chars`。Final serialized shadow report 超过该上限是
renderer Host validation failure。

如果 T16/T17 共享的 Model C retry budget 仍有剩余：

```text
same authoritative Manifest / Claim / Evidence projection
→ immediate retry Model C
→ no sleep
```

该 retry 不改变 Claim、Grounding、Citation 或 display authority。Retry exhaustion：

```text
preserve published Manifest
→ v2_shadow_report = None
→ GlobalSynthesisStatus = PARTIAL
→ bounded issue
→ V1 continues
```

禁止 silent truncate final report、truncate Claim-linked body paragraph、drop section 后伪装 valid、mutate
Manifest、regenerate Claims、re-ground 或 reduce Citation set to fit output。

#### Zero eligible path

生成 deterministic no-grounded-claim output：

- skip Model C；
- no fake Claim；
- no fake Citation；
- no fabricated bibliography。

#### Tests

- conflict marker exactly once at primary occurrence；
- both support/conflict labels visible；
- repeated Claim；
- multi-Claim union；
- bibliography stable；
- zero eligible；
- final size overflow 触发 immediate Renderer validation retry；
- retry exhaustion 保留 Manifest、`report=None`、`PARTIAL` 与 bounded issue；
- no silent truncation / section drop / Citation reduction；
- final size bound。

### T18 — Global Synthesis Pipeline Orchestration

**Status:** `DONE`

**Depends on:** `T07`, `T09`, `T10`, `T12`, `T13`, `T14`, `T15`, `T16`, `T17`

#### Files

```text
src/open_deep_research/global_synthesis/pipeline.py
src/open_deep_research/global_synthesis/__init__.py
tests/test_p2_s5_pipeline.py
```

#### Public facade

`__init__.py` 只暴露最小：

```text
global synthesis pipeline entry
GlobalSynthesisOutcome
```

不得 re-export internal implementation zoo。

#### Pipeline order

严格：

```text
1. replay check
2. execution context
3. Generator projection
4. Model A
5. Claim validation / identity / admission
6. per-Claim Evidence universe / Model B / Grounding
7. Citation materialization
8. candidate Manifest / Gate
9. metrics / display projection
10. zero eligible OR Model C / Host rendering
11. final status/outcome
```

#### No early Parent State write

Pipeline 内部只返回 `GlobalSynthesisOutcome`。Gate 前无 authoritative Manifest State write。

#### Failure containment semantics

Pre-Gate ordinary failure：

```text
manifest=None
status=FAILED
```

Post-Gate Renderer failure：

```text
manifest=valid
report=None
status=PARTIAL
```

#### Replay

Existing Manifest + report 时 skip A/B/C。Existing Manifest + missing report + `PARTIAL` 时不 retry C。

#### Metrics

Gate 通过后计算。

#### Tests

覆盖完整 happy path、empty path、partial path、failed path、replay path。

### T19 — Parent Graph Integration, V1 Fallback and Run Finalization

**Status:** `DONE`

**Depends on:** `T03`, `T18`

#### Files

```text
src/open_deep_research/deep_researcher.py
src/open_deep_research/state.py
tests/test_p2_s5_integration.py
tests/test_p2_s5_run_lifecycle.py
```

#### Graph

修改：

```text
research_supervisor
→ global_synthesis
→ final_report_generation
```

不修改 Supervisor/Researcher loop。

#### Parent node

`global_synthesis` wrapper：

- 读取 frozen input；
- 调用 pipeline；
- 一次返回 bounded Parent State update；
- 不包含 subsystem logic。

#### Failure containment

Ordinary S5 exception：

```text
bounded FAILED/PARTIAL State
→ continue final_report_generation
```

System cancellation 传播。

#### V1 isolation

V2 failure 不得：

- erase `research_results`；
- erase `notes/raw_notes`；
- block V1 writer。

#### New-run isolation

确认 new Run reset 后的 old Result、old Manifest、old V1 report、old V2 report 与 old issues 均不进入 new Run。

#### Terminal finalization

受控 `final_report_generation` terminal path 写 `research_run_status=FINALIZED`，包括 bounded V1 fallback。

#### Checkpoint tests

使用实际 LangGraph checkpointer 测试：

- same Run；
- replay；
- clarification；
- finalized + new message；
- fresh Artifact namespace；
- lifecycle conflict may retain the framework-admitted message，while cursor、Run status、Artifact namespace and
  structured provenance remain unchanged。

### T20 — Minimal External LLM-as-a-Judge Faithfulness Evaluator

**Status:** `DONE`

**Depends on:** `T12`, `T14`, `T17`

#### Scope

实现 **最小可运行 Eval slice**，不得变成 generalized evaluation framework。

#### Location

优先复用 T00 确认的现有 evaluation infrastructure 和相邻 tests。如果没有可复用的合适模块，只创建
P2-S5-specific evaluation-only module 与：

```text
tests/test_p2_s5_faithfulness_eval.py
```

不得放入 compiled graph、AgentState、global synthesis runtime package public API、Manifest 或 Publication Gate。

#### Components

必须提供：

```text
1. graph-external evaluator entry
2. bounded evaluator input projection
3. structured evaluation output
4. six-dimension frozen rubric
5. deterministic PASS/FAIL fixtures
6. live-model smoke entry / callable path ready for T22
```

T20 不要求实际成功完成 real-provider/live-model execution；所有 environment-dependent execution 由 T22 统一
负责。

#### Six dimensions

固定：

```text
unsupported factual proposition
scope expansion
qualifier loss
conflict omission
Claim misrepresentation
Citation/Claim placement mismatch
```

#### Eval-only DTO

可实现：

```text
FaithfulnessDimensionResult
├─ dimension
├─ passed
└─ bounded reason

FaithfulnessEvaluation
├─ passed
└─ dimensions[]
```

Overall PASS 要求 six dimensions 全部 PASS。该 shape 仅 Eval-internal，不成为 Contracts v1。

#### Input

只给 evaluator：

```text
V2 Shadow Report
+ bounded authoritative Claim/Manifest projection
+ required Citation/display context
```

不得提供 hidden reasoning。

#### Retry

只有 provider、transport、timeout、schema/structured-output 或 Host validation failure 允许 Host retry。

- schema/reference/Host validation failure：immediate retry，no sleep；
- provider/transport/timeout：按 §1.5 使用 deterministic `0.5 / 1.0 / 2.0` capped backoff；
- actual requests：`<= 1 + R`；
- lower-level nested request retry：disabled/bypassed。

Evaluator 每个 actual request 的 effective timeout：

```text
min(existing stricter eval/provider timeout, 90 seconds)
```

当前 path 没有更严格 timeout 时，Host enforce 90 seconds。

Valid LLM-as-a-Judge semantic FAIL，包括任一 dimension 返回 violation，是 terminal valid evaluator result：直接
返回 FAIL，不得 retry-to-pass。

#### Fixtures

至少构造：

PASS：

- faithful paraphrase；
- scope/qualifiers preserved；
- conflict explicit；
- correct citation placement。

FAIL：

- invented fact；
- scope expansion；
- qualifier dropped；
- contradiction hidden；
- Claim changed；
- citation misplaced。

#### No runtime effect

Eval 结果：

- 不进 State；
- 不改 GlobalSynthesisStatus；
- 不修 report；
- 不重跑 Claim；
- 不 re-ground。

#### Tests

覆盖：

- deterministic PASS/FAIL fixtures 与 six dimensions；
- valid semantic FAIL no retry；
- schema/reference/Host validation failure immediate retry / no sleep；
- provider/timeout retry delays `0.5 / 1.0 / 2.0` 并 cap at `2.0`；
- 90-second evaluator timeout policy；
- actual requests `<= 1 + R`；
- nested provider/client retry disabled；
- live smoke entry callable 但 deterministic tests 不发送真实 provider request。

#### Done when

- evaluator implementation complete；
- deterministic fake/stub tests PASS；
- live smoke entry 可由 T22 调用；
- evaluator 未进入 runtime State、Gate 或 compiled graph；
- environment unavailable 不阻塞 T20 implementation completion。

### T21 — Deterministic Integration, Regression and Failure Injection

**Status:** `DONE`

**Depends on:** `T19`, `T20`

#### Files

```text
tests/test_p2_s5_integration.py
```

以及前述 focused tests。

#### Goal

使用 fake/stub structured models 完成不依赖真实 provider 的 end-to-end 验证。

#### Must cover

Lifecycle：

- bootstrap；
- clarification resume；
- replay；
- new Run；
- multiple fresh conflict；
- ACTIVE steering conflict；
- Artifact namespace isolation。

Generator：

- success；
- empty；
- sibling invalid；
- overflow；
- aggregate exhaustion。

Judge：

- all five-state mappings；
- sibling exception；
- concurrency reorder；
- UNASSESSED；
- valid negative semantic result。

Publication：

- exact Citations；
- Gate mutation；
- no partial publish；
- replay。

Renderer：

- free section structure；
- Claim coverage；
- Evidence admission；
- conflict marker；
- Citation labels；
- Renderer exhaustion；
- zero eligible。

Issues/status：

- sticky degradation；
- payload conflict；
- ledger bound。

V1：每种 V2 failure 下 V1 edge 仍可执行。

#### Regression

现有 P2-S1–S4 tests 不得因 S5 无关改动回归。

#### Done when

S5 deterministic correctness 不依赖真实 network/model provider。

### T22 — Controlled Real-provider Smoke

**Status:** `DONE`

**Smoke Outcome:** `PASS`

**Depends on:** `T21`

**Smoke Outcome:** 在 T22 执行时记录；terminal values 仅允许 `PASS`、`FAIL`、
`SKIPPED_DUE_TO_ENVIRONMENT`

#### Scope

仅做受控真实 provider smoke，不作为新的实现调参 phase。

#### Scenario

使用：

```text
valid MedicalResearchBrief
+ small persisted/fixture ResearchTaskResult[]
```

执行 Model A、Model B、Publication Gate 和 Model C。T20 evaluator path/config 可用时，T22 同时调用 external
LLM-as-a-Judge live smoke entry；T20 本身不执行真实 provider smoke。

#### Record

至少记录：

```text
Claim count
Grounding status counts
Citation count
Manifest Gate result
Renderer result
GlobalSynthesisStatus
bounded issues
Model A/B/C physical mapping
role latency
request/retry count
external evaluator execution status / semantic verdict when available
```

#### Task Status vs Smoke Outcome

Task Status 继续只使用全局 `NOT_STARTED / IN_PROGRESS / BLOCKED / DONE`，表示 T22 implementation/execution
task lifecycle。Smoke Outcome 单独表示真实 provider smoke 结果，不得混入 Task status enum。

Required runtime smoke 是 Model A/B/Publication Gate/Model C 路径。External evaluator live smoke 由 T22 统一执行，但只在
evaluator path/config/environment 可用时要求调用并单独记录。Evaluator 返回 valid semantic FAIL 是合法
evaluation result，不 retry-to-pass，也不因其 graph-external/non-gating 性质单独将 required runtime smoke
改写为 execution failure。Evaluator provider/schema/timeout 等 operational failure 必须单独如实记录。

#### Environment-conditional gate

Environment available：

- credentials / model endpoint / network 均可用时 smoke MUST execute；
- required runtime smoke 全部成功时 `Smoke Outcome = PASS` 且 T22 Task Status 可为 `DONE`；
- 任一 required runtime step 真实执行但失败时 `Smoke Outcome = FAIL`，T22 不得 `DONE`；
- `FAIL` 不得改写为 `SKIPPED_DUE_TO_ENVIRONMENT`。

Environment unavailable：

- 客观上无法执行 required runtime smoke 时允许 `Smoke Outcome = SKIPPED_DUE_TO_ENVIRONMENT`；
- 必须记录客观原因，例如 credentials、endpoint 或 network unavailable；
- 按 environment-conditional policy 完成记录后，T22 Task Status 可为 `DONE`；
- 此时可记录 `Implementation Verification = PASS`与
  `Real-provider Smoke = SKIPPED_DUE_TO_ENVIRONMENT`；
- `SKIPPED_DUE_TO_ENVIRONMENT` 不等于 PASS，summary 不得将它计为 provider smoke success；
- 如果 required runtime smoke 已成功且仅 evaluator config/environment 不可用，保留总体 `PASS` 并单独记录
  evaluator smoke unavailable，不把已完成的 required runtime smoke 改写为 SKIP。

#### Failure policy

- implementation bug：fix code 并回归；
- prompt quality issue：在 frozen authority 内调整；
- provider-specific issue：记录；
- architecture-sensitive ambiguity：停止并 reopen design。

不得为了 smoke “跑过”而修改 frozen semantic rules。

#### Validation / record obligations

- Task Status 与 Smoke Outcome 分离；
- environment skip reason 如实记录；
- `FAIL` 不得转换为 `SKIPPED_DUE_TO_ENVIRONMENT`；
- `SKIPPED_DUE_TO_ENVIRONMENT` 不得报告为 PASS；
- evaluator execution/semantic verdict/environment limitation 与 required runtime smoke 结果分别记录。

### T23 — Implementation Documentation and Phase Closeout

**Status:** `DONE`

**Depends on:** `T22` Task Status = `DONE`（`T22` 已依赖 `T21`），且 T22 Smoke Outcome 必须属于：

```text
PASS
SKIPPED_DUE_TO_ENVIRONMENT
```

`Smoke Outcome = FAIL` 时，T22 不得 `DONE`，T23 不得进入 closeout。

#### Files

至少更新：

```text
docs/plans/P2_S5_TASKS.md
docs/plans/P2_S5_CHECKLIST.md
```

以及 repository 已有 phase closeout / implementation record convention 中的对应文档；不得为本 Task 新建
不必要的文档体系。

#### Closeout record

记录：

- completed Task IDs；
- implementation footprint；
- tests summary；
- regression result；
- real-provider smoke Task Status + Smoke Outcome；
- external evaluator status；
- known non-blocking limitations；
- no Contract/SPEC drift statement。

#### Required final checks

确认：

```text
no TODO/TBD/OPEN architecture choice
no stale Host-fixed Renderer section catalog
no second Citation authority
no nested model retry
no mid-run steering
no raw Artifact in new structured State
no cross-run provenance reuse
no new mypy errors from EvidenceFlow S5 code
```

#### Coding closeout status

只有 CHECKLIST 全部 required items 通过后，P2-S5 coding 才可进入 phase closeout。

---

## 4. Test Ownership Matrix

| Test area | Primary tasks |
|---|---|
| Stable Domain contracts | T01 |
| Parent State / reducers | T02 |
| Research Run lifecycle | T03, T19 |
| Internal DTO / limits | T04 |
| Source metadata enrichment | T05 |
| Resolver / projection | T06 |
| Claims / identity / admission | T07 |
| Evidence admission | T08 |
| Judge execution / concurrency | T09 |
| Grounding mapping / receipts | T10 |
| Citation | T11 |
| Manifest Gate / replay / metrics | T12 |
| Issues / status | T13 |
| Source display | T14 |
| Renderer projection | T15 |
| Renderer structured output | T16 |
| Citation injection / conflict marker | T17 |
| Pipeline | T18 |
| Parent integration / V1 fallback | T19 |
| External faithfulness evaluator | T20 |
| Failure injection / full regression | T21 |
| Real-provider smoke | T22 |

---

## 5. SPEC Requirement Traceability

| Requirement | Primary implementation Tasks |
|---|---|
| `S5-R01` Preserve P2-S4 Boundary | T05, T06, T18, T19 |
| `S5-R02` Claim-first Synthesis | T07, T10, T11, T12, T16–T18 |
| `S5-R03` Task-qualified Resolution | T06, T08, T12 |
| `S5-R04` Claim Generation/Materialization | T07 |
| `S5-R05` Evidence Universe / Projection | T06, T08 |
| `S5-R06` Grounding Judge | T09, T10 |
| `S5-R07` Five-state Grounding | T10 |
| `S5-R08` Eligibility / Conflict | T10, T15–T17 |
| `S5-R09` Citation / Display | T11, T14, T17 |
| `S5-R10` Manifest / State | T02, T12, T19 |
| `S5-R11` Model/Host + Retry | T07, T09, T16, T20 |
| `S5-R12` Publication Gate | T12 |
| `S5-R13` Failure / Status / Issues | T13, T18, T19 |
| `S5-R14` Bounds / Admission / Ordering | T04, T06–T12, T15–T17 |
| `S5-R15` Shadow Renderer | T15, T16, T17 |
| `S5-R16` Faithfulness Evaluation | T20 |
| `S5-R17` Derived Metrics | T12 |
| `S5-R18` Parent Placement / V1/V2 | T18, T19 |
| `S5-R19` Research Run Lifecycle | T02, T03, T19 |

所有 `S5-R01–R19` 必须至少有一个 concrete implementation Task 和一个 validation path。

---

## 6. Task-level Non-goals

TASKS/coding 不得自行增加：

```text
Agentic Global Synthesis loop
Claim repair loop
Grounding repair loop
Renderer evaluator repair loop
mid-run user steering
active Run abandonment
message fingerprint subsystem
request-id registry
cross-run Evidence reuse
global Source registry
Evidence Store
RAG / Vector DB
semantic Claim dedup
Source quality scoring
numeric Groundedness score
Host-fixed Renderer section catalog
Model-owned Citation IDs
parallel V1/V2 graph branch
Send
background worker
queue
deployment redesign
generalized Search Provider framework
generalized Evaluation platform
retrieval_score metadata/quality semantics
```

---

## 7. TASKS Freeze Gate

`P2_S5_TASKS.md` 只有满足以下条件才可标记 `FINAL FROZEN`：

1. T00–T23 均具有唯一目标和 scope；
2. 每个 Task 都有明确 dependency；
3. 每个 Task 都映射到 frozen PLAN；
4. `S5-R01–R19` 全部有 implementation Task；
5. 不存在 Task 要求 Coding Agent 重新选择 architecture；
6. P01 lifecycle 不留下 mid-run steering/batching 解释空间；framework input admission 后的 conflict 不推进 cursor，
   且 EvidenceFlow-owned Research Run lifecycle 与 structured provenance 保持不变；
7. Model A/B/C/Evaluator 共用唯一 Host retry authority，validation failure immediate/no-sleep，transient failure
   使用 deterministic `0.5 / 1.0 / 2.0` capped backoff，no jitter；
8. Model A/B/C/Evaluator timeout responsibility 与 `1 + R` request bound 唯一，nested logical retry disabled；
9. `max_section_title_chars=300` 与 T17 final report overflow failure mapping 固定；
10. Source metadata enrichment 是 required small best-effort adapter，不引入 raw provider payload、`retrieval_score` 或
    Source quality semantics；
11. Model C structured section authority 唯一，T16/T17 不得形成两套 Renderer retry budget；
12. T20 只负责 minimal external evaluator implementation 与 live-smoke entry，真实 provider/evaluator execution 统一归 T22；
13. T22 Task Status 与 Smoke Outcome 分离，`FAIL` 不得改写为 SKIP，SKIP 不得报告为 PASS；
14. S5-R11 / S5-R14 与其余 requirement traceability、test ownership 完整；
15. Coding 仍未因 TASKS Freeze 自动授权。

最终状态：

```text
P2-S5 SPEC
→ FINAL FROZEN

P2-S5 PLAN
→ FINAL FROZEN

P2-S5 TASKS
→ FINAL FROZEN

P2-S5 CHECKLIST
→ AUTHORIZED TO DRAFT / REVIEW / FREEZE

Coding
→ STILL BLOCKED UNTIL CHECKLIST + PRE-IMPLEMENTATION REVIEW COMPLETE
```

---

## 8. Implementation Execution Evidence

Execution completed on 2026-08-29 from verification base
`dc43cd83b4f2c6716c82cd791d0ad28fe9e0d51a` on branch
`p2-s5-claim-citation-grounding`. T00–T23 are `DONE`; S5-R01–R19 are
`19/19 PASS`.

Implementation footprint:

- stable contracts, Parent State/reducers, lifecycle admission, metadata adapter,
  configuration, prompts, graph integration, and V1 fallback were updated in the
  existing project-owned modules;
- the semantic subsystem was added under
  `src/open_deep_research/global_synthesis/`;
- deterministic contract, lifecycle, Claim, Grounding, publication, display,
  renderer, pipeline, graph-integration, and evaluator tests were added under
  `tests/`;
- an opt-in, environment-gated real-provider smoke entry was added at
  `tests/test_p2_s5_provider_smoke.py`.

Verification evidence:

```text
P2-S5 focused and directly affected tests:
150 passed, 1 skipped, 26 warnings

Full deterministic regression:
190 passed, 1 skipped, 1 deselected, 48 warnings

Ruff canonical target:
12 pre-existing violations in untouched evaluation scripts

Ruff new/touched S5 target:
PASS — no violations

Mypy full/scoped target:
9 pre-existing errors, all in src/open_deep_research/utils.py
PASS — no new errors in the other 14 touched/new production modules

git diff --check:
PASS
```

Controlled provider smoke:

```text
Task Status = DONE
Smoke Outcome = PASS
Model A requests/retries = 1 / 0
Model B requests/retries = 2 / 0
Model C requests/retries = 1 / 0
Claim count = 2
Grounding = SUPPORTED: 2; all other statuses: 0
Citation count = 2
Manifest Gate = PASS
Renderer = MODEL_C_PASS
GlobalSynthesisStatus = SUCCESS
Issues = none
External evaluator = OPERATIONAL_FAILURE: NotFoundError
Reason = the configured endpoint does not expose the frozen default gpt-4.1 model
```

The first sandboxed smoke attempt stopped before any provider request because the
injected SOCKS proxy required an unavailable optional `socksio` package. The same
frozen smoke was then executed through the allowed unrestricted network path with
proxy variables removed and passed. This environmental pre-request failure is not
the recorded runtime smoke outcome.

Contract drift: none. SPEC drift: none. Architecture drift: none. No dependencies or
lockfiles were changed, and no commit was created by implementation execution.
