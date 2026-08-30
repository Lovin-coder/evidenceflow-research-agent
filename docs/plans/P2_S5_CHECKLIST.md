# P2-S5 — Global Claim, Citation and Grounding CHECKLIST

## 0. 状态与文档职责

| Field | Value |
|---|---|
| Phase | `P2-S5` |
| Document | `P2_S5_CHECKLIST.md` |
| Status | **FINAL FROZEN** |
| SPEC status | **FINAL FROZEN / RENDERER RESYNCED** |
| PLAN status | **FINAL FROZEN** |
| TASKS status | **FINAL FROZEN** |
| Contracts status | **CONSISTENT / `evidenceflow.contracts.v1`** |
| Coding gate | **CLOSED UNTIL PRE-IMPLEMENTATION REVIEW COMPLETE** |
| Target branch | `p2-s5-claim-citation-grounding` |

本文只负责验证 frozen `P2_S5_TASKS.md` 是否被完整、正确实现，不重新定义实现语义。

Document responsibility model：

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

其中 Contracts / SPEC 定义 normative runtime semantics，Clarifications 保存 decision provenance，PLAN / TASKS
定义当前实现映射；CHECKLIST 只保存可复现 verification 与 closeout evidence。

CHECKLIST 不重新决定：

- Domain / State contracts；
- Research Run boundary；
- message identity policy；
- Claim / Grounding / Citation semantics；
- retry authority / backoff / timeout；
- Source metadata enrichment scope；
- Source display grouping；
- Renderer authority；
- Manifest publication semantics；
- replay / failure semantics；
- evaluator runtime boundary；
- smoke acceptance policy。

若实现阶段出现无法由 frozen Contracts / SPEC / PLAN / TASKS 唯一回答的问题：

```text
STOP
→ mark affected Task BLOCKED
→ record exact source evidence
→ reopen appropriate upstream document
```

不得通过 CHECKLIST 或 code 执行 Silent Spec Mutation。

---

## 1. Checklist Result Vocabulary

每个检查项使用：

```text
[ ] NOT_VERIFIED
[x] PASS
[!] BLOCKED
[-] NOT_APPLICABLE
```

`NOT_APPLICABLE` 只允许用于：

- repository 中明确不存在的 optional provider path；
- frozen TASKS 明确允许 conditional execution 的 evaluator/provider subpath；
- 其他明确标记 optional 的非 required 项。

T22 required runtime smoke 不使用 `NOT_APPLICABLE`；它必须记录独立的 `Smoke Outcome`：

```text
PASS
FAIL
SKIPPED_DUE_TO_ENVIRONMENT
```

不得用 `NOT_APPLICABLE` 或 `SKIPPED_DUE_TO_ENVIRONMENT` 跳过 required Contract、SPEC、Task 或 deterministic
test。

### 1.1 Evidence requirement

每个重要 PASS 至少指向一种 evidence：

```text
source diff
test name
test output
static-analysis output
controlled smoke record
checkpoint/state inspection
```

仅口头判断不能作为 PASS。

### 1.2 Failure rule

如果任何 required item FAIL：

```text
do not weaken validator
do not delete failing test
do not expand ignore
do not change frozen semantics merely to make test pass
```

应回到 owning Task 修复。

### 1.3 Focused test command convention

本文中的 focused pytest commands 是 preferred commands，不是 mandatory test-file-layout authority。

如果 frozen Task 合法地将 P2-S5 tests 放入 existing adjacent test module：

- 执行实际 owning test module 或 exact pytest node IDs；
- 在 closeout evidence 中记录 exact command 与 test names；
- required behavioral coverage 必须保持不变；
- 推荐文件名不存在本身不是 failure。

Coding Agent 不得借此减少 required coverage。

---

## 2. Pre-implementation Review Gate

在开始 Coding 前必须完成本节。

### 2.1 Repository state

- [ ] 当前分支为 `p2-s5-claim-citation-grounding` 或明确的 P2-S5 implementation branch。
- [ ] 工作区中的 pre-existing changes 已识别，P2-S5 实现不会覆盖或混入 unrelated changes。
- [ ] 已确认 `main` / 当前 baseline commit。
- [ ] 已记录当前 baseline test status。
- [ ] 已记录当前 baseline mypy status。
- [ ] 已确认当前 Python / `uv` environment 可运行。
- [ ] 已确认 lockfile 当前解析为 `langgraph==1.2.9` 或 frozen equivalent。
- [ ] 已确认 `langgraph.types.Overwrite` 实际 API 可用。

Recommended commands：

```bash
git status --short --branch
git log -1 --oneline
uv --version
uv run --frozen python --version
```

如需要准备 repository environment：

```bash
uv sync --frozen --extra dev
```

不得更新 lockfile，不得为本阶段建立第二套 environment-management path。

### 2.2 Frozen documents

- [ ] `EVIDENCEFLOW_CONTRACTS_V1.md` 为当前 canonical Contracts v1。
- [ ] `P2_S5_SPEC.md` 为 `FINAL FROZEN`。
- [ ] `P2_S5_PLAN.md` 为 `FINAL FROZEN`。
- [ ] `P2_S5_TASKS.md` 为 `FINAL FROZEN`。
- [ ] `P2_S5_CLARIFICATIONS.md` 中 D00–D20 / CB01–CB06 已 resolved/promoted。
- [ ] Renderer latest D14 resolution 与 Contracts §3.14 / SPEC S5-R15 一致。
- [ ] 当前 authority 不再使用 Host-fixed Renderer section catalog。
- [ ] 当前 authority 不再使用 `FINALIZED → every invoke starts new Run` semantics。

### 2.3 Implementation scope

- [ ] T00–T23 均有唯一 owning scope。
- [ ] Coding Agent 不需要再选择 architecture。
- [ ] Source metadata enrichment 仅为 small best-effort canonical-field adapter。
- [ ] `retrieval_score` 不属于 P2-S5 metadata surface 或 quality semantics。
- [ ] External evaluator 仅为 minimal graph-external LLM-as-a-Judge slice。
- [ ] Global Synthesis 不新增 Agentic Loop。
- [ ] P2-S5 不新增 `Send`、queue、background worker、parallel V1/V2 branch。
- [ ] ACTIVE Research Run 不支持 mid-run user steering。

### 2.4 Pre-implementation decision

只有以下全部成立才能开放 coding：

```text
SPEC      = FINAL FROZEN
PLAN      = FINAL FROZEN
TASKS     = FINAL FROZEN
CHECKLIST = FINAL FROZEN
Pre-implementation Review = PASS
```

Pre-implementation Review status：

```text
[ ] PASS
[ ] BLOCKED
```

---

## 3. T00 — Implementation Preflight and Source Mapping

- [ ] 当前 stable `ContractModel` / Domain validation convention 已定位。
- [ ] `AgentState` / `MessagesState` / reducers 已定位。
- [ ] Parent entry / clarification / finalization call sites 已定位。
- [ ] `global_synthesis` graph insertion point 已定位。
- [ ] Model A/B/C construction path 已定位。
- [ ] structured-output wrapper 实际行为已验证。
- [ ] provider/client automatic retry 是否可关闭已验证。
- [ ] S4 `SourceRecord` 唯一 active writer 已定位。
- [ ] 当前 prompt organization 已定位。
- [ ] existing evaluation harness 已定位。
- [ ] current test conventions 已定位。
- [ ] `Overwrite` actual runtime behavior 已验证。
- [ ] 未发现 multiple active Source writers。
- [ ] 未发现 frozen lifecycle 无法映射到当前 graph API。
- [ ] 未发现 lower-level retry 无法关闭且会突破 `1 + R`。
- [ ] 未发现需要重新设计 Contracts / State / topology 的 blocker。

T00 status：

```text
[ ] DONE
[ ] BLOCKED
```

---

## 4. T01 — Stable Domain Contracts

Target：

```text
src/open_deep_research/domain_models.py
```

### 4.1 Types

- [ ] `EvidenceRef` implemented。
- [ ] `FindingRef` implemented。
- [ ] `ClaimMateriality` implemented。
- [ ] `ClaimRecord` implemented。
- [ ] `GroundingStatus` implemented。
- [ ] `ClaimGroundingRecord` implemented。
- [ ] `Citation` implemented。
- [ ] `GroundingManifest` implemented。

### 4.2 Contract invariants

- [ ] required/optional fields 与 Contracts v1 逐项一致。
- [ ] enum serialized values 一致。
- [ ] extra fields rejected。
- [ ] required identifiers non-empty。
- [ ] `ClaimRecord.finding_refs` non-empty。
- [ ] `GroundingManifest.contract_version == "evidenceflow.contracts.v1"`。
- [ ] same bare Evidence/Finding ID 在不同 Tasks 下仍是不同 qualified address。
- [ ] stable models 不包含 drafts、metrics、issues、display metadata 或 V2 report。

### 4.3 Tests

- [ ] valid serialization round-trip。
- [ ] invalid enum rejected。
- [ ] missing required field rejected。
- [ ] extra field rejected。
- [ ] empty required ID rejected。
- [ ] empty Claim FindingRefs rejected。
- [ ] version serialization tested。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_contracts.py -q
```

---

## 5. T02 — Parent State and Reducers

Target：

```text
src/open_deep_research/state.py
```

### 5.1 State contracts

- [ ] `GlobalSynthesisStatus`。
- [ ] `GlobalSynthesisSeverity`。
- [ ] `GlobalSynthesisIssue`。
- [ ] `ResearchRunStatus`。
- [ ] `grounding_manifest`。
- [ ] `global_synthesis_status`。
- [ ] `global_synthesis_issues`。
- [ ] `v2_shadow_report`。
- [ ] `research_run_status`。
- [ ] `research_run_input_cursor`。

### 5.2 Issue stage

- [ ] stable `GlobalSynthesisIssue.stage` 使用 open `str`。
- [ ] unknown legal stage string 可反序列化。
- [ ] phase-local `GlobalSynthesisStage` 未成为 stable closed validator。
- [ ] severity 仍为 `WARNING | ERROR` closed enum。

### 5.3 Reducer semantics

- [ ] Manifest `None → valid Manifest`。
- [ ] identical same-run Manifest replay idempotent。
- [ ] divergent same-run Manifest replay 明确 conflict。
- [ ] status 使用 Host replace。
- [ ] shadow report 使用 Host replace。
- [ ] issue ledger bounded append/dedup。
- [ ] issue reducer defensive first-write-wins。
- [ ] P05 semantic reconciliation 不塞入 reducer。
- [ ] `Overwrite([])` 可真正清空 merge/append channels。
- [ ] ordinary `[]` 未被误认为 reset。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_state.py -q
```

---

## 6. T03 — Research Run Lifecycle

### 6.1 Lifecycle state machine

- [ ] no lifecycle + exactly one HumanMessage → first Run。
- [ ] no lifecycle + zero HumanMessages → conflict。
- [ ] no lifecycle + multiple HumanMessages → conflict。
- [ ] ACTIVE + `delta=0` → same-run continuation。
- [ ] ACTIVE + `delta>=1` → lifecycle conflict。
- [ ] AWAITING_CLARIFICATION + `delta=0` → remain awaiting/no-op。
- [ ] AWAITING_CLARIFICATION + `delta=1` → same-run resume。
- [ ] AWAITING_CLARIFICATION + `delta>1` → conflict。
- [ ] FINALIZED + `delta=0` → completed-run replay。
- [ ] FINALIZED + `delta=1` → new Run。
- [ ] FINALIZED + `delta>1` → conflict。
- [ ] `fresh_delta<0` → lifecycle integrity conflict。

### 6.2 Conflict atomicity

对所有 lifecycle conflict：

- [ ] framework-admitted conflicting `HumanMessage` MAY remain in `messages`。
- [ ] newly admitted conflicting occurrence is visible at conversation level。
- [ ] `research_run_input_cursor` remains unchanged。
- [ ] conflicting `HumanMessage` is not consumed by the current or a new Research Run。
- [ ] `research_run_status` unchanged。
- [ ] `artifact_run_id` unchanged。
- [ ] no run-scoped reset。
- [ ] Medical Research Brief / legacy brief unchanged。
- [ ] `ResearchTaskResult[]` unchanged。
- [ ] notes/raw notes unchanged。
- [ ] `final_report` / `v2_shadow_report` unchanged。
- [ ] `GroundingManifest` unchanged。
- [ ] global synthesis issues/status unchanged。
- [ ] sticky degradation fact unchanged。
- [ ] no new Claim/Grounding/Citation provenance。
- [ ] no implicit `ACTIVE` abandonment。
- [ ] no message rollback/deletion attempted。

Checkpoint probe evidence SHOULD demonstrate：

```text
before messages:
[("m-seed", "seed")]

after framework admission + lifecycle conflict:
[("m-seed", "seed"), ("m-conflict", "conflict")]
```

`messages` changing only through framework admission is not a failure；the cursor、Run status、Artifact namespace and
structured Run state MUST remain unchanged。

### 6.3 Message identity

- [ ] same stable `message.id` retry 不增加 occurrence。
- [ ] same text + different ID 形成新 occurrence。
- [ ] same text + no stable ID retransmission 形成新 occurrence。
- [ ] same ID + divergent payload 只记录为 caller contract violation，不实施 fingerprint repair。
- [ ] 没有 fingerprint/content-hash retry inference。

### 6.4 New Run reset

确认通过 `Overwrite`/replace 清空：

- [ ] `supervisor_messages`。
- [ ] `medical_research_brief`。
- [ ] `research_brief`。
- [ ] `research_results`。
- [ ] `raw_notes`。
- [ ] `notes`。
- [ ] `final_report`。
- [ ] `grounding_manifest`。
- [ ] `global_synthesis_status`。
- [ ] `global_synthesis_issues`。
- [ ] `v2_shadow_report`。
- [ ] run-local degradation fact。

同时：

- [ ] `messages` preserved。
- [ ] cursor 正确推进到 accepted occurrence。
- [ ] fresh `artifact_run_id`。
- [ ] old physical Artifacts 无需删除。
- [ ] old structured provenance 不再 active。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_run_lifecycle.py -q
```

---

## 7. T04 — Internal DTOs, Limits and Retry Boundary

### 7.1 Internal types

- [ ] `ClaimDraft`。
- [ ] `ClaimDraftBatch`。
- [ ] `ClaimEvidenceVerdict`。
- [ ] `ClaimGroundingDraft`。
- [ ] `GroundingEvidenceView`。
- [ ] `RendererEvidenceView`。
- [ ] `ReportClaimView`。
- [ ] `ReportParagraphDraft`。
- [ ] `ReportSectionDraft`。
- [ ] `ShadowReportDraft`。
- [ ] `ClaimMaterializationReceipt`。
- [ ] `AssessedGroundingReceipt`。
- [ ] `UnassessedGroundingReceipt`。
- [ ] `GlobalSynthesisStage`。
- [ ] `GlobalSynthesisLimits`。
- [ ] `GlobalSynthesisExecutionContext`。
- [ ] `GroundingMetrics`。
- [ ] `GlobalSynthesisOutcome`。

### 7.2 Limits

确认 exact initial values：

- [ ] `max_findings_total = 40`
- [ ] `max_findings_per_task = 8`
- [ ] `max_generator_evidence_chars = 96_000`
- [ ] `max_task_summary_chars = 2_000`
- [ ] `max_task_error_context_chars = 1_000`
- [ ] `max_generator_context_chars = 128_000`
- [ ] `max_claim_drafts_returned = 64`
- [ ] `max_claim_batch_serialized_chars = 128_000`
- [ ] `max_claims = 20`
- [ ] `max_claim_text_chars = 1_500`
- [ ] `max_claim_scope_chars = 500`
- [ ] `max_qualifiers_per_claim = 8`
- [ ] `max_qualifier_chars = 300`
- [ ] `max_finding_refs_per_claim = 8`
- [ ] `max_evidence_refs_per_claim = 24`
- [ ] `max_judge_evidence_chars = 64_000`
- [ ] `max_judge_context_chars = 80_000`
- [ ] `max_grounding_reason_chars = 2_000`
- [ ] `max_grounding_draft_serialized_chars = 16_000`
- [ ] `max_citations = 512`
- [ ] `max_manifest_serialized_chars = 1_000_000`
- [ ] `max_global_synthesis_issues = 64`
- [ ] `max_issue_message_chars = 1_000`
- [ ] `max_issue_ledger_chars = 128_000`
- [ ] `max_renderer_context_chars = 128_000`
- [ ] `max_sections = 8`
- [ ] `max_section_title_chars = 300`
- [ ] `max_paragraphs_total = 24`
- [ ] `max_paragraph_chars = 2_000`
- [ ] `max_claim_ids_per_paragraph = 6`
- [ ] `max_claim_occurrences_per_claim = 3`
- [ ] `max_shadow_report_chars = 30_000`
- [ ] `max_renderer_draft_serialized_chars = 128_000`

Capacity invariant：

```text
max_citations >= max_claims * max_evidence_refs_per_claim
```

- [ ] capacity invariant tested。
- [ ] numeric boundaries cover `limit-1`, `limit`, and `limit+1` where applicable。

### 7.3 Unified retry

- [ ] `max_structured_output_retries = R` has the single meaning `maximum actual requests = 1 + R`。
- [ ] reusable single-attempt primitive 每次只发一个 provider/model request。
- [ ] Host retry driver 是唯一 logical retry authority。
- [ ] schema validation failure immediate/no sleep。
- [ ] parse failure immediate/no sleep。
- [ ] reference failure immediate/no sleep。
- [ ] allowlist failure immediate/no sleep。
- [ ] aggregate payload failure immediate/no sleep。
- [ ] Host structural failure immediate/no sleep。
- [ ] transient retry #1 = `0.5s`。
- [ ] transient retry #2 = `1.0s`。
- [ ] transient retry #3 = `2.0s`。
- [ ] further retries cap at `2.0s`。
- [ ] no jitter。
- [ ] no random sleep。
- [ ] no provider-specific retry tree。
- [ ] request count never exceeds `1 + R`。
- [ ] cancellation/system control flow not swallowed。

### 7.4 Nested retries

- [ ] S5 request path 未使用 extra logical `.with_retry(...)`。
- [ ] provider/client automatic retry 已关闭或绕过。
- [ ] S1–S4 unrelated retry path 未被无关修改。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_types.py -q
```

---

## 8. T05 — Source Metadata Enrichment

### 8.1 Required small adapter

- [ ] existing `url` preserved。
- [ ] existing `title` preserved。
- [ ] existing `provider` preserved。
- [ ] Host-owned `retrieved_at` implemented。
- [ ] reliable `published_at` preserved when available。
- [ ] reliable `publisher` preserved when available。
- [ ] reliable `authors` preserved when available。
- [ ] reliable `document_type` preserved when available。

### 8.2 No fabrication

- [ ] missing publisher not inferred from URL。
- [ ] missing authors not inferred from content。
- [ ] missing published date not guessed。
- [ ] document type not LLM-inferred。
- [ ] malformed provider values omitted/rejected safely。

### 8.3 Explicit exclusions

确认 metadata 不新增：

- [ ] `content`
- [ ] `raw_content`
- [ ] `page_content`
- [ ] full provider response
- [ ] images
- [ ] favicon
- [ ] `retrieval_score`

### 8.4 Provenance safety

- [ ] enrichment 不改变 `source_id`。
- [ ] enrichment 不改变 `artifact_ref`。
- [ ] enrichment 不改变 Evidence identity。
- [ ] metadata compact serialization 仍满足 existing bound。
- [ ] content-bearing denylist 仍生效。
- [ ] S5 correctness 不依赖 optional enrichment。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_source_metadata.py -q
```

如果实际复用 existing S4 test file，则执行对应文件并在 closeout 记录实际路径。

---

## 9. T06 — Resolver and Projection

### 9.1 Resolution

- [ ] `task_id` resolves unique owning Result。
- [ ] duplicate/ambiguous task IDs rejected。
- [ ] FindingRef 只在 owning Result 解析。
- [ ] EvidenceRef 只在 owning Result 解析。
- [ ] Evidence source 只在 same Result 解析。
- [ ] Host 不扫描 sibling Results 猜 reference。
- [ ] same bare IDs across tasks remain distinct。

### 9.2 Projection

- [ ] Generator input only comes from Brief + structured Results。
- [ ] `generator_visible_finding_refs` explicitly materialized。
- [ ] Result order preserved。
- [ ] per-task Finding order preserved。
- [ ] Finding Evidence order preserved。
- [ ] summary bounded。
- [ ] limitations/conflicts retained。
- [ ] error context bounded。
- [ ] exact Evidence excerpt preserved。
- [ ] optional metadata validated。
- [ ] raw Artifact absent。
- [ ] Messages absent。
- [ ] raw notes absent。
- [ ] provider payload absent。

### 9.3 Admission

- [ ] Finding/Evidence authoritative units whole-unit。
- [ ] Evidence excerpt never sliced。
- [ ] normal overflow uses deterministic admission。
- [ ] omission produces degradation。
- [ ] no visible FindingRef skips Model A。
- [ ] zero-visible caused by degradation is distinguishable from valid empty input。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_projection.py -q
```

---

## 10. T07 — Model A / Claim Materialization

### 10.1 Prompt authority

- [ ] Model A sees only allowed FindingRefs。
- [ ] Model A cannot output `claim_id`。
- [ ] Model A cannot output Evidence refs as authority。
- [ ] Model A cannot output Grounding status。
- [ ] Model A cannot output Citation identity。
- [ ] scope/qualifiers explicitly represented。

### 10.2 Aggregate validation

- [ ] draft count bound。
- [ ] aggregate serialized payload bound。
- [ ] schema validation。
- [ ] field bounds。

### 10.3 Sibling handling

- [ ] invalid sibling dropped。
- [ ] valid sibling survives。
- [ ] sibling invalidity sets degradation。
- [ ] invalid sibling does not trigger retry-to-repair whole valid batch。

### 10.4 Claim identity

- [ ] Claim ID Host-owned。
- [ ] identity includes original Generator ordinal。
- [ ] identity includes canonical semantic payload。
- [ ] identity excludes survivor ordinal。
- [ ] sibling rejection does not alter sibling Claim ID。
- [ ] capacity omission does not alter retained sibling IDs。
- [ ] timestamps/provider metadata/messages absent from Claim ID。

### 10.5 Dedup/capacity

- [ ] exact canonical duplicate dedup。
- [ ] near-duplicate text not fuzzy deduped。
- [ ] no embeddings。
- [ ] overflow uses `HIGH → MEDIUM → LOW`。
- [ ] same-tier Generator order preserved。
- [ ] survivors restored to original Generator order。

### 10.6 Retry/timeout

- [ ] validation errors immediate/no sleep。
- [ ] transient retry follows `0.5 / 1.0 / 2.0` capped policy。
- [ ] effective timeout = `min(existing stricter timeout, 90 seconds)`。
- [ ] when no stricter lower-level timeout exists, Host enforces 90 seconds。
- [ ] actual requests <= `1 + R`。
- [ ] nested retry disabled。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_claims.py -q
```

---

## 11. T08 — Judge Evidence Universe

- [ ] universe derived only after Claim survivor selection。
- [ ] Model A output does not choose Judge universe。
- [ ] traversal = Claim FindingRefs order。
- [ ] then Finding `evidence_ids` order。
- [ ] exact EvidenceRef first-occurrence dedup。
- [ ] cross-task same bare Evidence ID remains distinct。

### 11.1 Judge view

Required：

- [ ] `EvidenceRef`
- [ ] exact excerpt

Optional only：

- [ ] title
- [ ] stored URL
- [ ] provider
- [ ] publisher
- [ ] authors
- [ ] published_at
- [ ] document_type

Forbidden：

- [ ] no `artifact_ref`
- [ ] no full Artifact
- [ ] no raw provider payload
- [ ] no unvalidated metadata

### 11.2 Admission

- [ ] ref cap enforced。
- [ ] Evidence chars cap enforced。
- [ ] context cap enforced。
- [ ] canonical prefix admission。
- [ ] no rerank。
- [ ] no excerpt slicing。
- [ ] omission degrades status。
- [ ] actual admitted refs become only evaluated universe。
- [ ] empty admitted universe skips Model B。
- [ ] empty admitted universe becomes strict UNASSESSED path。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_grounding.py -q
```

---

## 12. T09 — Model B Execution

### 12.1 Concurrency

- [ ] `max_concurrent_grounding_judgments = 4`。
- [ ] Semaphore actually limits active Judge calls。
- [ ] `asyncio.gather` or equivalent used without completion-order authority。
- [ ] final Groundings restored to Claim canonical order。

### 12.2 Sibling isolation

- [ ] one ordinary Claim exception only affects that Claim。
- [ ] affected Claim becomes UNASSESSED path。
- [ ] siblings continue。
- [ ] issue recorded。
- [ ] degradation recorded。
- [ ] cancellation propagates。
- [ ] `BaseException` not broadly swallowed。

### 12.3 Retry

- [ ] per-Claim request count <= `1 + R`。
- [ ] valid SUPPORTED no retry-to-pass。
- [ ] valid INSUFFICIENT no retry。
- [ ] valid CONTRADICTED no retry。
- [ ] schema invalid retry。
- [ ] invalid refs retry。
- [ ] payload overflow retry。
- [ ] validation retry no sleep。
- [ ] transient retry bounded backoff。
- [ ] one Claim retry does not change sibling ordering or retry state。

### 12.4 Timeout

- [ ] effective timeout = `min(existing stricter timeout, 60 seconds)` per actual request/per Claim。
- [ ] when no stricter lower-level timeout exists, Host enforces 60 seconds。
- [ ] timeout on one Claim does not corrupt siblings。
- [ ] timeout retry does not change canonical output order。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_grounding.py -q
```

---

## 13. T10 — Grounding Materialization

### 13.1 Structural invariants

- [ ] supporting refs subset of evaluated。
- [ ] contradicting refs subset of evaluated。
- [ ] each list unique。
- [ ] lists disjoint。
- [ ] canonical filtered order。
- [ ] bounded/sanitized reason。

### 13.2 Five-state mapping

- [ ] `SUPPORTED + no contradiction → SUPPORTED`。
- [ ] `SUPPORTED + contradiction → SUPPORTED_WITH_CONFLICT`。
- [ ] `INSUFFICIENT + any valid subset shape → INSUFFICIENT`。
- [ ] `CONTRADICTED + contradiction → CONTRADICTED`。
- [ ] no valid assessment → `UNASSESSED`。
- [ ] Host does not use Evidence count heuristic。
- [ ] Host does not use contradiction-presence heuristic to override `INSUFFICIENT`。

### 13.3 Assessed receipt

- [ ] evaluated refs exactly equal actual successful Judge input。
- [ ] reason present。
- [ ] expected status matches verdict。

### 13.4 Strict UNASSESSED

- [ ] evaluated refs = `[]`。
- [ ] supporting refs = `[]`。
- [ ] contradicting refs = `[]`。
- [ ] reason = `None`。
- [ ] attempted refs/errors only in issues。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_grounding.py -q
```

---

## 14. T11 — Citation Materialization

- [ ] SUPPORTED required set = supporting refs。
- [ ] SUPPORTED_WITH_CONFLICT required set = supporting + contradicting。
- [ ] INSUFFICIENT required set empty。
- [ ] CONTRADICTED required set empty。
- [ ] UNASSESSED required set empty。

### 14.1 Identity

- [ ] Citation Host-owned。
- [ ] canonical identity derives from `(claim_id, EvidenceRef)`。
- [ ] no URL in Citation identity。
- [ ] no display label in Citation identity。
- [ ] no metadata in Citation identity。

### 14.2 Order

- [ ] Claim canonical order。
- [ ] supporting canonical order。
- [ ] contradicting canonical order。
- [ ] async completion does not affect Citation order。
- [ ] dict/set ordering does not affect Citation order。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_publication.py -q
```

---

## 15. T12 — Manifest Publication Gate / Replay / Metrics

### 15.1 Gate Claim checks

- [ ] Claim IDs unique。
- [ ] Claim IDs receipt-backed。
- [ ] FindingRefs resolve。
- [ ] generator allowlist preserved。
- [ ] canonical order。
- [ ] bounds valid。

### 15.2 Gate Grounding checks

- [ ] exactly one Grounding per Claim。
- [ ] no orphan Grounding。
- [ ] no foreign Claim binding。
- [ ] EvidenceRefs resolve。
- [ ] assessed receipt valid。
- [ ] unassessed receipt valid。
- [ ] verdict/status exact mapping valid。

### 15.3 Gate Citation checks

- [ ] deterministic IDs。
- [ ] all refs resolve。
- [ ] actual set == required set。
- [ ] no missing Citation。
- [ ] no extra Citation。
- [ ] no duplicate Citation。
- [ ] canonical ordering。

### 15.4 Aggregate checks

- [ ] contract version。
- [ ] payload bound。
- [ ] collection binding。
- [ ] canonical order。
- [ ] Gate validates; does not repair。
- [ ] invalid candidate publishes no Manifest。
- [ ] Gate does not drop invalid sibling then publish remainder。
- [ ] no early Parent State Manifest write。

### 15.5 Replay

- [ ] Manifest absent → normal synthesis。
- [ ] Manifest + report → skip A/B/C。
- [ ] Manifest + report missing + PARTIAL → preserve/no automatic C rerun。
- [ ] identical same-run replay idempotent。
- [ ] divergent same-run replay conflict。
- [ ] new Run reset prevents cross-run divergent replay confusion。

### 15.6 Metrics

- [ ] supported count。
- [ ] supported-with-conflict count。
- [ ] insufficient count。
- [ ] contradicted count。
- [ ] unassessed count。
- [ ] assessed coverage。
- [ ] report eligible coverage。
- [ ] material report eligible coverage。
- [ ] zero denominator = `None`。
- [ ] metrics do not enter Manifest。
- [ ] metrics do not enter Parent State。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_publication.py -q
```

---

## 16. T13 — Issues, Degradation and Global Status

### 16.1 Issue identity

- [ ] ID uses stable coordinates。
- [ ] message excluded from identity。
- [ ] message sanitized。
- [ ] issue count bounded。
- [ ] ledger payload bounded。

### 16.2 P05 divergence

Same identity + same semantics + different wording：

- [ ] first Issue retained。
- [ ] no escalation。

Same identity + divergent semantic payload：

- [ ] first Issue retained。
- [ ] degradation becomes true。
- [ ] deterministic `ISSUE_PAYLOAD_CONFLICT` emitted。
- [ ] Manifest not invalidated solely for this reason。
- [ ] V1 not blocked。

### 16.3 Sticky degradation

- [ ] `False → True` only。
- [ ] issue eviction cannot restore false。
- [ ] final status not reconstructed from issue messages。
- [ ] severity does not determine degradation automatically。

### 16.4 Status

- [ ] no Manifest → FAILED。
- [ ] Manifest + degradation → PARTIAL。
- [ ] Manifest + Renderer failure → PARTIAL。
- [ ] Manifest + successful output + no degradation → SUCCESS。
- [ ] valid INSUFFICIENT alone does not degrade。
- [ ] valid CONTRADICTED alone does not degrade。
- [ ] all valid negative Claims can still produce SUCCESS。
- [ ] valid empty Manifest can produce SUCCESS when no degradation。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_status.py -q
```

---

## 17. T14 — Reader-facing Source Display

### 17.1 Tagged key

- [ ] `TaskSourceDisplayKey` implemented。
- [ ] `UrlArtifactDisplayKey` implemented。
- [ ] display identity separate from canonical Source identity。

### 17.2 Grouping

- [ ] same task Source may group its Evidence。
- [ ] same Run + exact stored URL + same Artifact may cross-task group。
- [ ] missing URL prohibits cross-task group。
- [ ] invalid URL prohibits cross-task group。
- [ ] different stored URL prohibits cross-task group。
- [ ] different Artifact prohibits grouping。
- [ ] different Run prohibits grouping。
- [ ] bare artifact hash does not imply cross-run equality。
- [ ] S5 does not recanonicalize stored URL。

### 17.3 Metadata merge

对 `title`、`publisher`、`authors`、`published_at`、`document_type`、`provider` 分别验证：

- [ ] canonical Citation traversal is authority。
- [ ] first validated non-empty wins。
- [ ] later conflicting value does not overwrite。
- [ ] all contributing canonical Source refs retained。
- [ ] no fuzzy “best metadata” selection。
- [ ] no model selection。
- [ ] no async-order dependence。

### 17.4 Labels / bibliography

- [ ] labels assigned `[1]`, `[2]`, ... deterministically。
- [ ] first display-key occurrence determines label。
- [ ] bibliography deterministic。
- [ ] bibliography best-effort GB/T 7714-style。
- [ ] missing fields omitted gracefully。
- [ ] no fabricated metadata。
- [ ] `retrieval_score` absent from display authority。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_display.py -q
```

---

## 18. T15 — Renderer Projection and Admission

### 18.1 Eligibility

- [ ] SUPPORTED eligible。
- [ ] SUPPORTED_WITH_CONFLICT eligible。
- [ ] INSUFFICIENT not eligible。
- [ ] CONTRADICTED not eligible。
- [ ] UNASSESSED not eligible。

### 18.2 Claim projection

Every eligible Claim includes：

- [ ] claim_id
- [ ] text
- [ ] scope
- [ ] qualifiers
- [ ] materiality
- [ ] GroundingStatus

### 18.3 Evidence projection

Only material refs：

- [ ] supporting。
- [ ] contradicting。

Forbidden：

- [ ] no Grounding reason。
- [ ] no evaluated-but-non-material Evidence。
- [ ] no Artifact。
- [ ] no full Result。
- [ ] no notes。
- [ ] no raw provider data。

### 18.4 Admission

- [ ] all eligible Claim propositions admitted first。
- [ ] each eligible Claim attempts at least one supporting Evidence。
- [ ] each conflict Claim attempts at least one contradicting Evidence。
- [ ] remaining Evidence follows canonical Claim/Citation order。
- [ ] Evidence whole-unit only。
- [ ] no excerpt slicing。
- [ ] Evidence omission degrades。
- [ ] Evidence omission does not alter Grounding。
- [ ] Evidence omission does not alter required Citation set。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_renderer.py -q
```

---

## 19. T16 — Model C Structured Renderer

### 19.1 Authority

- [ ] Model C chooses section count。
- [ ] Model C chooses section title。
- [ ] Model C chooses section order。
- [ ] Model C chooses paragraph organization。
- [ ] Model C chooses prose。
- [ ] Host does not use fixed section catalog。
- [ ] Model C does not own Citation identity。
- [ ] Model C does not modify Grounding role。

### 19.2 Schema

- [ ] `ShadowReportDraft.sections`。
- [ ] section title non-empty。
- [ ] section title <= 300 chars。
- [ ] body paragraph text bounded。
- [ ] paragraph `claim_ids` non-empty。
- [ ] Claim IDs exist。
- [ ] Claim IDs are eligible。
- [ ] IDs unique within paragraph。
- [ ] per-Claim occurrences bounded。
- [ ] every eligible Claim covered at least once。
- [ ] aggregate serialized bound。
- [ ] Model output order preserved。
- [ ] unbound model body paragraph rejected。

### 19.3 Retry

- [ ] invalid aggregate uses same Model C retry budget。
- [ ] T16/T17 do not create separate retry loops。
- [ ] validation failure immediate/no sleep。
- [ ] transient failure uses bounded backoff。
- [ ] effective timeout = `min(existing stricter timeout, 90 seconds)`。
- [ ] when no stricter lower-level timeout exists, Host enforces 90 seconds。
- [ ] actual requests <= `1 + R`。
- [ ] ugly but structurally valid prose is not retried。
- [ ] exhaustion → Manifest preserved/report `None`/PARTIAL。

---

## 20. T17 — Report Finalization

### 20.1 Conflict disclosure

For every `SUPPORTED_WITH_CONFLICT`：

- [ ] first canonical occurrence identified。
- [ ] deterministic minimum conflict marker inserted。
- [ ] supporting label visible。
- [ ] contradicting label visible。
- [ ] marker not repeatedly inserted on every occurrence。
- [ ] Host does not semantic-classify whether Model prose was “good enough”。

### 20.2 Citation injection

- [ ] paragraph Claim IDs resolve to canonical Claims。
- [ ] Claims resolve to required Citations。
- [ ] Citations resolve to display keys。
- [ ] labels ordered deterministically。
- [ ] multi-Claim paragraph ordered union。
- [ ] repeated Claim reuses same Citation set。
- [ ] no new Citation generated for repeated occurrence。

### 20.3 Final output bound

- [ ] final Host-serialized report <= `max_shadow_report_chars`。
- [ ] overflow treated as Renderer Host validation failure。
- [ ] retry uses remaining shared Model C budget。
- [ ] retry uses same authoritative Manifest/Claim/Evidence projection。
- [ ] retry immediate/no sleep。
- [ ] exhaustion preserves Manifest。
- [ ] exhaustion sets report `None`。
- [ ] exhaustion produces PARTIAL。
- [ ] bounded issue emitted。
- [ ] V1 continues。
- [ ] no silent truncation。
- [ ] no dropping section to fake validity。
- [ ] no Citation-set reduction。
- [ ] no re-ground。
- [ ] no Claim regeneration。

### 20.4 Zero eligible

- [ ] Model C skipped。
- [ ] deterministic no-grounded-claim output。
- [ ] no fake Claim。
- [ ] no fake Citation。
- [ ] no fake bibliography。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_renderer.py -q
```

---

## 21. T18 — Global Synthesis Pipeline

Pipeline exact order：

- [ ] replay check。
- [ ] execution context。
- [ ] Generator projection。
- [ ] Model A。
- [ ] Claim validation/materialization。
- [ ] per-Claim Evidence universe。
- [ ] Model B / Grounding。
- [ ] Citation materialization。
- [ ] candidate Manifest。
- [ ] Publication Gate。
- [ ] metrics/display。
- [ ] zero eligible or Renderer。
- [ ] final status/outcome。

### 21.1 State ownership

- [ ] pipeline returns `GlobalSynthesisOutcome`。
- [ ] no Parent State writes before boundary wrapper。
- [ ] no Manifest publication before Gate PASS。
- [ ] process-local receipts do not enter State。

### 21.2 Failure containment

- [ ] pre-Gate ordinary failure → no Manifest / FAILED。
- [ ] post-Gate Renderer failure → valid Manifest / no report / PARTIAL。
- [ ] system cancellation propagates。
- [ ] V1 data preserved。

### 21.3 Replay

- [ ] Manifest+report skips A/B/C。
- [ ] Manifest+no report+PARTIAL does not repair/rerender。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_pipeline.py -q
```

---

## 22. T19 — Parent Graph Integration

### 22.1 Topology

确认：

```text
research_supervisor
        ↓
global_synthesis
        ↓
final_report_generation
```

- [ ] only one new Parent node。
- [ ] Supervisor loop unchanged。
- [ ] Researcher loop unchanged。
- [ ] no `Send`。
- [ ] no background branch。
- [ ] no parallel V1/V2 branch。

### 22.2 Parent wrapper

- [ ] reads frozen structured input。
- [ ] invokes pipeline。
- [ ] returns one bounded Parent update。
- [ ] complex validation not duplicated in `deep_researcher.py`。

### 22.3 V1 preservation

For all tested V2 failures：

- [ ] `research_results` preserved。
- [ ] `notes` preserved。
- [ ] `raw_notes` preserved。
- [ ] V1 writer still executes。
- [ ] V1 output remains official compatibility path。

### 22.4 Finalization

- [ ] terminal final report path sets `FINALIZED`。
- [ ] bounded V1 fallback can still finalize Run。
- [ ] uncaught system failure may leave ACTIVE for recovery。

### 22.5 Checkpoint

- [ ] same Run continuation。
- [ ] clarification resume。
- [ ] replay。
- [ ] new Run。
- [ ] fresh Artifact namespace。
- [ ] conflict retains any framework-admitted message but leaves consumed-input cursor、Run status、Artifact namespace
  and structured provenance unchanged。

Focused command：

```bash
uv run --frozen --extra dev pytest \
  tests/test_p2_s5_run_lifecycle.py \
  tests/test_p2_s5_integration.py \
  -q
```

---

## 23. T20 — External LLM-as-a-Judge Evaluator

### 23.1 Runtime isolation

- [ ] evaluator graph-external。
- [ ] not compiled into runtime graph。
- [ ] not in AgentState。
- [ ] not in Manifest。
- [ ] not in Publication Gate。
- [ ] does not change `GlobalSynthesisStatus`。
- [ ] does not trigger report repair。
- [ ] does not trigger Claim repair。
- [ ] does not trigger re-ground。

### 23.2 Input

- [ ] bounded V2 Shadow Report。
- [ ] bounded authoritative Claim/Manifest projection。
- [ ] required Citation/display context。
- [ ] no hidden reasoning。
- [ ] no raw provider payload。

### 23.3 Six dimensions

- [ ] unsupported factual proposition。
- [ ] scope expansion。
- [ ] qualifier loss。
- [ ] conflict omission。
- [ ] Claim misrepresentation。
- [ ] Citation/Claim placement mismatch。

### 23.4 Output

- [ ] structured evaluation result。
- [ ] each dimension returns pass/fail。
- [ ] bounded reason。
- [ ] overall PASS only if all required dimensions PASS。
- [ ] Eval DTO remains internal。

### 23.5 Retry

- [ ] valid semantic FAIL terminal。
- [ ] valid semantic FAIL not retried to PASS。
- [ ] schema/parse/reference/Host validation immediate retry without sleep。
- [ ] provider/transport/timeout failure uses bounded deterministic backoff。
- [ ] effective timeout = `min(existing stricter eval/provider timeout, 90 seconds)`。
- [ ] when no stricter lower-level timeout exists, Host enforces 90 seconds。
- [ ] request count <= `1 + R`。
- [ ] nested retries disabled。

### 23.6 Deterministic fixtures

PASS fixture covers：

- [ ] faithful paraphrase。
- [ ] scope retained。
- [ ] qualifier retained。
- [ ] conflict retained。
- [ ] Citation placement valid。

FAIL fixtures cover：

- [ ] invented fact。
- [ ] scope expansion。
- [ ] qualifier loss。
- [ ] conflict omission。
- [ ] Claim changed。
- [ ] Citation misplaced。

### 23.7 Live smoke entry

- [ ] callable path exists。
- [ ] deterministic tests do not call real provider。
- [ ] actual environment-dependent execution belongs to T22。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_faithfulness_eval.py -q
```

---

## 24. T21 — Deterministic Integration / Failure Injection

使用 fake/stub models 完成。

### 24.1 Lifecycle scenarios

- [ ] first bootstrap。
- [ ] clarification resume。
- [ ] same-run replay。
- [ ] finalized new Run。
- [ ] multiple fresh conflict。
- [ ] ACTIVE steering conflict。
- [ ] Artifact namespace isolation。

### 24.2 Generator scenarios

- [ ] successful batch。
- [ ] valid empty batch。
- [ ] invalid sibling。
- [ ] capacity overflow。
- [ ] aggregate validation exhaustion。
- [ ] provider exhaustion。

### 24.3 Judge scenarios

- [ ] SUPPORTED。
- [ ] SUPPORTED_WITH_CONFLICT。
- [ ] INSUFFICIENT。
- [ ] CONTRADICTED。
- [ ] UNASSESSED。
- [ ] sibling exception。
- [ ] concurrency reorder。
- [ ] timeout/retry。
- [ ] valid negative no retry。

### 24.4 Publication scenarios

- [ ] correct Citations。
- [ ] missing Citation Gate failure。
- [ ] extra Citation Gate failure。
- [ ] receipt mutation Gate failure。
- [ ] no partial publication。
- [ ] same-run replay。

### 24.5 Renderer scenarios

- [ ] Model-defined section order。
- [ ] Claim coverage。
- [ ] conflict Evidence admission。
- [ ] context omission degradation。
- [ ] conflict marker。
- [ ] labels。
- [ ] Renderer retry exhaustion。
- [ ] final size overflow。
- [ ] zero eligible。

### 24.6 Issues/status

- [ ] sticky degradation。
- [ ] issue semantic conflict。
- [ ] ledger full。
- [ ] PARTIAL derivation。
- [ ] FAILED derivation。
- [ ] SUCCESS with negative but valid semantic Claims。

### 24.7 V1

- [ ] Generator failure → V1 executes。
- [ ] Gate failure → V1 executes。
- [ ] Renderer failure → V1 executes。
- [ ] ordinary S5 node failure → V1 executes。

Focused command：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_integration.py -q
```

---

## 25. Full P2-S5 Test Suite

执行所有 P2-S5 focused tests：

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_*.py -q
```

如果 shell / repository layout 不支持 glob，显式列出对应文件并记录实际命令。

如果任意 P2-S5 tests 合法地放入 pre-existing test modules，focused-suite verification MUST additionally include
those modules or exact pytest node IDs。此时 `tests/test_p2_s5_*.py` glob 不能单独作为完整 P2-S5 test evidence。

Required：

- [ ] all P2-S5 deterministic tests PASS。
- [ ] no skipped required Contract/SPEC tests。
- [ ] environment-dependent tests 有明确 marker/record。
- [ ] no test reaches live provider unless intentionally running T22。

记录：

```text
P2-S5 tests:
passed =
failed =
skipped =
duration =
```

---

## 26. Regression Gate

P2-S5 不得破坏 P2-S1–S4。

### 26.1 Existing tests

Preferred：

```bash
uv run --frozen --extra dev pytest -q
```

如果 full suite 因已知 repository baseline 问题无法全部执行：

- [ ] 已记录 baseline failure。
- [ ] 已证明 S5 没有新增该 failure。
- [ ] 所有与修改路径直接相关的 regression tests PASS。

### 26.2 Required regression properties

- [ ] Supervisor–Researcher loop 未改变。
- [ ] S4 Source/Evidence/Finding publication 仍可运行。
- [ ] ArtifactStore resolution 仍正确。
- [ ] V1 Final Writer 仍可运行。
- [ ] legacy notes/raw_notes semantics 未被 S5 重新定义。
- [ ] S4 Result self-contained provenance 仍成立。
- [ ] Source metadata enrichment 未改变 Source identity。
- [ ] provider metadata 缺失不阻断 S4 publication。

Regression status：

```text
[ ] PASS
[ ] BLOCKED_BY_PREEXISTING_BASELINE
[ ] FAIL
```

---

## 27. Static Quality Gates

### 27.1 Ruff

Preferred：

```bash
uv run --frozen --extra dev ruff check src/open_deep_research tests
```

- [ ] no new Ruff violations from S5 changes。

若 repository 使用 narrower canonical command，则执行该命令并记录 exact targets；不得通过 rule disable、broad
`noqa` 或跳过 touched S5 modules 获得 PASS。

### 27.2 Mypy

Preferred：

```bash
MYPYPATH=src uv run --frozen --extra dev mypy src/open_deep_research
```

要求：

- [ ] 新 EvidenceFlow S5 modules 不新增 mypy errors。
- [ ] modified existing modules 不新增 attributable mypy errors。
- [ ] 不通过 blanket `# type: ignore` 隐藏新问题。
- [ ] 必要 local ignore 有明确 narrow justification。

如果 repository 本身已有 baseline mypy errors，必须记录完整失败，并执行覆盖全部 new/touched EvidenceFlow S5
modules 的 scoped command。T00 确认的 S4 metadata writer 也必须进入 scoped targets。

```text
baseline errors =
post-S5 errors =
new S5-attributable errors = 0
scoped command =
```

### 27.3 Formatting / syntax

- [ ] Python imports clean。
- [ ] no dead experimental module。
- [ ] private helper 使用 `_` 标识 module-internal API。
- [ ] `global_synthesis/__init__.py` facade minimal。
- [ ] subsystem module 不反向 import `pipeline.py`。
- [ ] no unnecessary `limits.py` / `retry.py` / `display.py` micro-package。

---

## 28. Architecture Boundary Audit

### 28.1 Global Synthesis

- [ ] no Agentic Loop。
- [ ] no Claim repair loop。
- [ ] no re-ground loop。
- [ ] no evaluator→report loop。
- [ ] no dynamic action-selection loop。

### 28.2 Authority

- [ ] Model A does not own identity。
- [ ] Model B owns semantic verdict only。
- [ ] Host owns final GroundingStatus。
- [ ] Host owns Citation identity/set。
- [ ] Model C does not own Citation identity。
- [ ] evaluator owns no runtime authority。

### 28.3 Provenance

- [ ] no raw Artifact in new structured State。
- [ ] no Messages as V2 Evidence。
- [ ] no notes as V2 Evidence。
- [ ] no provider snippets as V2 Evidence。
- [ ] no sibling Result reference guessing。
- [ ] no cross-run Evidence reuse。
- [ ] no cross-run Citation reuse。
- [ ] no global Source registry。
- [ ] display grouping does not modify canonical provenance。

### 28.4 Lifecycle

- [ ] one active State carries at most one authoritative Research Run。
- [ ] ACTIVE input stable。
- [ ] no mid-run steering。
- [ ] no batch fresh-input interpretation。
- [ ] clarification is explicit input boundary。
- [ ] new Run resets prior structured authority。

---

## 29. Retry / Cost / Determinism Audit

For Model A/B/C/Evaluator：

- [ ] one Host retry authority。
- [ ] one actual request per single-attempt helper call。
- [ ] no nested automatic logical retry。
- [ ] actual requests <= `1 + R`。
- [ ] validation retry immediate。
- [ ] transient retries deterministic。
- [ ] delays exactly `0.5 / 1.0 / 2.0` capped。
- [ ] no jitter。
- [ ] role timeout enforced according to T07/T09/T16/T20。
- [ ] valid negative semantic outputs not retried。
- [ ] retries do not mutate authoritative identity。
- [ ] async timing does not influence canonical order。

---

## 30. Bounds Audit

Verify Host enforcement for：

### 30.1 Generator

- [ ] Finding total。
- [ ] Findings per task。
- [ ] Evidence chars。
- [ ] task summary chars。
- [ ] error context chars。
- [ ] total context。
- [ ] returned ClaimDraft count。
- [ ] ClaimDraftBatch serialized payload。

### 30.2 Claims

- [ ] Claim count。
- [ ] Claim text。
- [ ] scope。
- [ ] qualifiers count。
- [ ] qualifier chars。
- [ ] FindingRefs count。

### 30.3 Judge

- [ ] EvidenceRef count。
- [ ] Evidence chars。
- [ ] total context。
- [ ] reason chars。
- [ ] draft serialized payload。

### 30.4 Manifest

- [ ] Citation count。
- [ ] serialized Manifest chars。
- [ ] capacity invariant。

### 30.5 Issues

- [ ] issue count。
- [ ] issue message chars。
- [ ] ledger payload。

### 30.6 Renderer

- [ ] total context。
- [ ] section count。
- [ ] title <= 300。
- [ ] paragraph count。
- [ ] paragraph chars。
- [ ] Claim IDs per paragraph。
- [ ] Claim occurrences。
- [ ] draft serialized payload。
- [ ] final shadow report chars。

### 30.7 General

- [ ] provider `max_tokens` is not treated as substitute for Host bounds。
- [ ] authoritative Evidence excerpt never silently sliced。
- [ ] structured output never silently truncated into authoritative object。

---

## 31. SPEC Acceptance Gate — S5-R01–R19

### S5-R01

- [x] Global Synthesis authority comes only from Brief + structured Results。
- [x] V2 failure does not alter valid S4 Results。

### S5-R02

- [x] Claim-first authority chain。
- [x] no report-first authoritative extraction。

### S5-R03

- [x] all global references task-qualified。
- [x] no sibling scan。

### S5-R04

- [x] Host materializes Claims。
- [x] FindingRefs non-empty。
- [x] sibling-stable identity。
- [x] exact-only dedup。

### S5-R05

- [x] Judge universe derived from retained Findings。
- [x] Model A/B allowlists separate。
- [x] Model B cannot enlarge universe。

### S5-R06

- [x] Judge verdict + material subsets follow frozen semantics。
- [x] reason non-authoritative。

### S5-R07

- [x] one Grounding per Claim。
- [x] five-state mapping。
- [x] strict UNASSESSED。

### S5-R08

- [x] eligibility derived from status。
- [x] conflict Claim reportable。
- [x] no automatic Claim repair。

### S5-R09

- [x] exact Citation set。
- [x] display grouping does not modify canonical identity。

### S5-R10

- [x] Manifest aggregate valid。
- [x] atomic publication。
- [x] no partial merge。

### S5-R11

- [x] Model/Host authority boundaries intact。
- [x] Model A/B/C valid semantic negatives no retry-to-pass。
- [x] evaluator valid semantic FAIL no retry-to-pass。

### S5-R12

- [x] Gate validate-not-repair。
- [x] invalid aggregate not published。

### S5-R13

- [x] SUCCESS/PARTIAL/FAILED semantics exact。
- [x] status uses sticky degradation fact。

### S5-R14

- [x] all model inputs/outputs bounded。
- [x] Claim, Evidence, Citation, Manifest and final report bounds enforced by their owning Tasks。
- [x] whole-unit deterministic admission。
- [x] canonical order independent of async/unordered containers。

### S5-R15

- [x] Model C owns bounded section structure。
- [x] body paragraphs Claim-bound。
- [x] all eligible Claims covered。
- [x] material Evidence only。
- [x] conflict marker/Citations visible。
- [x] zero eligible skips Model C。

### S5-R16

- [x] graph-external faithfulness evaluator exists。
- [x] six dimensions covered。
- [x] runtime unaffected。

### S5-R17

- [x] required metrics recomputable。
- [x] zero denominator `None`。
- [x] metrics non-authoritative。

### S5-R18

- [x] only `global_synthesis` new Parent orchestration node。
- [x] V1 preserved。
- [x] no forbidden latency-isolation topology。

### S5-R19

- [x] same logical Run preserves namespace。
- [x] new Run resets structured provenance before admission。
- [x] conversation context does not imply provenance reuse。

Requirement gate：

```text
S5-R01–R19 PASS count = 19 / 19
```

- [x] PASS。

---

## 32. Contract Invariant Gate — I1–I24 Relevant Regression

Existing I1–I12 upstream invariants must remain intact。

P2-S5-specific emphasis：

- [x] I13 — Cross-task references are task-qualified and never resolved by sibling scan。
- [x] I14 — Claim identity, proposition and materialization are Host-owned。
- [x] I15 — Claim lineage and Evidence Grounding remain separate。
- [x] I16 — The evaluated Evidence universe is Host-owned and exact for every valid assessment。
- [x] I17 — Supporting and contradicting Evidence are valid material disjoint subsets。
- [x] I18 — Claim-level status preserves the Judge overall semantic verdict。
- [x] I19 — `UNASSESSED` records execution/validation failure, not insufficiency。
- [x] I20 — Citation completeness is exact for every report-eligible Claim。
- [x] I21 — Manifest publication is atomic and validates the whole aggregate。
- [x] I22 — Canonical collection ordering is independent from async completion timing。
- [x] I23 — The V2 renderer cannot become a second factual authority。
- [x] I24 — Active structured provenance is isolated by Research Run。

No Contract invariant has been weakened to make implementation easier：

- [x] PASS。

---

## 33. T22 — Controlled Real-provider Smoke

### 33.1 Preconditions

Record：

```text
credentials available = YES
provider endpoint available = YES
network available = YES through the approved unrestricted path; sandbox SOCKS path unavailable
Model A config available = YES — openai:qwen3.7-plus-2026-05-26
Model B config available = YES — openai:qwen3.7-plus-2026-05-26
Model C config available = YES — openai:qwen3.7-plus-2026-05-26
evaluator config available = YES — frozen default gpt-4.1; endpoint model unavailable
```

### 33.2 Required runtime smoke

If environment available：

- [x] Model A executes。
- [x] materialized Claim set non-empty 时，Model B 对具有 admitted Evidence universe 的 Claims 按 frozen semantics
  执行。
- [ ] empty admitted Evidence universe 的 Claim 按 strict UNASSESSED path 处理。
- [ ] Claim set 合法为空时，legal empty-Claim path 已验证，且未为 smoke 强制调用 Model B。
- [x] smoke 未人工制造 Claim 或 Evidence。
- [x] Publication Gate PASSes。
- [x] report-eligible Claims non-empty 时，Model C MUST execute，且 Host Renderer finalization MUST complete。
- [ ] report-eligible Claims empty 时，Model C MUST NOT execute，且 Host deterministic zero-eligible output MUST
  succeed。
- [x] V2 Shadow Report generated OR deterministic zero-eligible output generated。
- [x] V1 path remains available。

Record：

```text
Claim count = 2
SUPPORTED = 2
SUPPORTED_WITH_CONFLICT = 0
INSUFFICIENT = 0
CONTRADICTED = 0
UNASSESSED = 0
Citation count = 2
Manifest Gate = PASS
Renderer = MODEL_C_PASS
GlobalSynthesisStatus = SUCCESS
Issues = none
Model A latency = 25.881s
Model B latency = 7.306s and 9.632s for two Claim-local requests
Model C latency = 50.499s
Retry/request counts = A 0/1; B 0/2; C 0/1
```

### 33.3 External evaluator smoke

If evaluator path/config/environment available：

- [x] evaluator live entry executes。
- [ ] semantic verdict recorded。
- [x] valid evaluator FAIL not retried to PASS（deterministic coverage; live call had no semantic verdict）。
- [x] evaluator result does not affect runtime status。

If evaluator unavailable but required runtime smoke succeeds：

```text
Runtime Smoke Outcome = PASS
Evaluator Smoke = OPERATIONAL_FAILURE: NotFoundError — endpoint does not expose gpt-4.1
```

不得把 runtime PASS 改为 SKIP；evaluator valid semantic FAIL 也不单独把 graph-external required runtime smoke
改写为 FAIL。

### 33.4 Smoke outcome

Exactly one：

```text
[x] PASS
[ ] FAIL
[ ] SKIPPED_DUE_TO_ENVIRONMENT
```

Rules：

- [x] executed required-runtime failure never converted to SKIP。
- [x] SKIP has concrete environment reason。
- [x] SKIP is not reported as PASS。
- [x] environment skip does not invalidate deterministic implementation verification。
- [x] implementation bug found by smoke returns to owning Task。
- [x] architecture ambiguity found by smoke reopens design rather than silently changing semantics。

T22 Task Status：

```text
[x] DONE
[ ] BLOCKED
```

If `Smoke Outcome = FAIL`：

```text
T22 Task Status MUST NOT be DONE
```

---

## 34. Security / Diagnostics / Data Hygiene

- [x] no raw prompt persisted in issues。
- [x] no raw model response persisted in issues。
- [x] no provider payload persisted in issues。
- [x] no unbounded traceback persisted in issues。
- [x] no hidden reasoning persisted。
- [x] Source metadata contains no raw content aliases。
- [x] Artifact raw text does not enter new structured Graph State。
- [x] logs used for tests/smoke do not expose credentials/API keys。
- [x] test fixtures contain no real secrets。
- [x] errors are bounded/sanitized。

---

## 35. Git / Diff Quality Gate

Determine baseline：

```bash
BASE="$(git merge-base HEAD main)"
```

Inspect committed and tracked working-tree changes：

```bash
git status --short
git diff --name-status "$BASE"
git diff --stat "$BASE"
git diff --check "$BASE"
```

`git diff` 不包含 untracked file 内容。Closeout 前每个 intended untracked file 必须先成为 tracked change，或单独执行：

```bash
git diff --no-index --check /dev/null path/to/untracked-file
```

该命令返回 `1` 可仅表示文件存在差异；判断标准是输出中没有 whitespace error。

Required：

- [x] `git diff --check` PASS。
- [x] intended untracked files 已单独检查或已进入 tracked diff。
- [x] no unrelated file churn。
- [x] no generated/cache files accidentally included。
- [x] no secrets included。
- [x] no dependency change without Task justification。
- [x] no broad formatting-only rewrite mixed into S5 implementation。
- [x] no unexpected upstream refactor。
- [x] package footprint matches PLAN/TASKS。

Search stale/forbidden patterns as applicable：

```bash
rg -n "retrieval_score" src/open_deep_research tests || true
rg -n "section_id" src/open_deep_research/global_synthesis tests || true
rg -n "\.with_retry" src/open_deep_research/global_synthesis tests || true
```

Interpretation：

- `retrieval_score` MUST NOT become S5 metadata semantics。
- `section_id` MUST NOT represent a Host-fixed Renderer section catalog。
- `.with_retry` MUST NOT create nested S5 logical model retries。

---

## 36. Documentation Drift Audit

- [x] implementation does not contradict Contracts v1。
- [x] implementation does not contradict SPEC。
- [x] implementation matches PLAN file ownership。
- [x] implementation matches T00–T23 decomposition。
- [x] no new semantic behavior exists only in code comments。
- [x] no new unresolved design hidden in TODO。
- [x] no stale document says metadata enrichment optional task。
- [x] no stale document introduces `retrieval_score` metadata/quality semantics。
- [x] no stale document says Host owns Renderer section catalog。
- [x] no stale document permits mid-run steering。
- [x] no stale document permits Renderer repair replay。
- [x] no stale document permits nested request retry。

Search for unresolved markers：

```bash
rg -n '\b(TODO|TBD|OPEN|FIXME)\b' \
  src/open_deep_research/global_synthesis \
  docs/plans/P2_S5_*.md \
  || true
```

Any marker affecting frozen behavior：

```text
→ BLOCKED
```

---

## 37. T23 — Implementation Documentation and Completion Ledger

T23 may start only when：

```text
T22 Task Status = DONE
AND
T22 Smoke Outcome ∈ {PASS, SKIPPED_DUE_TO_ENVIRONMENT}
```

- [x] T22 dependency rule satisfied。
- [x] completed Task IDs recorded。
- [x] implementation footprint recorded。
- [x] focused tests summary recorded。
- [x] full regression result recorded。
- [x] real-provider smoke Task Status and Smoke Outcome recorded separately。
- [x] external evaluator implementation and verification status recorded。
- [x] known non-blocking limitations recorded。
- [x] no Contract drift statement recorded。
- [x] no SPEC drift statement recorded。
- [x] required stale-pattern and architecture checks completed。
- [x] no unnecessary closeout-document system introduced。

### 37.1 T00–T23 Completion Ledger

| Task | Status | Primary evidence |
|---|---|---|
| T00 Preflight | [x] DONE | accepted verification base and source map |
| T01 Domain Contracts | [x] DONE | contract tests |
| T02 Parent State | [x] DONE | reducer/state tests |
| T03 Run Lifecycle | [x] DONE | lifecycle/checkpoint tests |
| T04 Internal Types / Retry | [x] DONE | types/retry tests |
| T05 Metadata Enrichment | [x] DONE | ingestion/Tavily tests |
| T06 Resolver / Projection | [x] DONE | projection tests |
| T07 Model A / Claims | [x] DONE | Claim tests |
| T08 Evidence Universe | [x] DONE | Grounding admission tests |
| T09 Model B Execution | [x] DONE | concurrency/isolation tests |
| T10 Grounding Materialization | [x] DONE | five-state Grounding tests |
| T11 Citation | [x] DONE | publication tests |
| T12 Publication / Replay / Metrics | [x] DONE | Gate/replay/metrics tests |
| T13 Issues / Status | [x] DONE | status/reconciliation tests |
| T14 Source Display | [x] DONE | display tests |
| T15 Renderer Projection | [x] DONE | renderer admission tests |
| T16 Model C | [x] DONE | renderer structure tests |
| T17 Report Finalization | [x] DONE | finalization/conflict tests |
| T18 Pipeline | [x] DONE | pipeline tests |
| T19 Parent Integration | [x] DONE | graph/V1 isolation tests |
| T20 Faithfulness Eval | [x] DONE | deterministic evaluator tests |
| T21 Integration / Regression | [x] DONE | 190-test deterministic regression |
| T22 Provider Smoke | [x] DONE | Smoke Outcome PASS |
| T23 Closeout | [x] DONE | execution ledger and retro |

Required before P2-S5 implementation closeout：

```text
T00–T23 = DONE
```

T22 may be DONE with `Smoke Outcome = SKIPPED_DUE_TO_ENVIRONMENT` only when the frozen environment-conditional
policy was followed。`SKIPPED_DUE_TO_ENVIRONMENT` is not PASS。

---

## 38. Final Verification Command Set

在 implementation closeout 前执行并记录。

### 38.1 P2-S5 focused tests

```bash
uv run --frozen --extra dev pytest tests/test_p2_s5_*.py -q
```

### 38.2 Full regression

```bash
uv run --frozen --extra dev pytest -q
```

### 38.3 Ruff

```bash
uv run --frozen --extra dev ruff check src/open_deep_research tests
```

### 38.4 Mypy

```bash
MYPYPATH=src uv run --frozen --extra dev mypy src/open_deep_research
```

如存在 pre-existing full-target baseline limitation，按 §27.2 执行 scoped command，并记录完整 full-target failure
与 exact scoped targets。

### 38.5 Diff

```bash
BASE="$(git merge-base HEAD main)"
git status --short
git diff --check "$BASE"
git diff --stat "$BASE"
git diff --name-status "$BASE"
```

If repository canonical commands differ, use the canonical repository equivalents and record the exact commands
executed；不得省略 required verification surface。

Final result record：

```text
P2-S5 focused pytest:
PASS — 150 passed, 1 provider-smoke test skipped by default, 26 warnings

Full regression:
PASS — 190 passed, 1 provider-smoke test skipped by default,
1 legacy live-provider test deselected, 48 warnings

Ruff:
NO_NEW_S5_VIOLATIONS — touched/new target PASS;
canonical target retains 12 pre-existing violations in untouched evaluation scripts

Mypy:
NO_NEW_S5_ERRORS_WITH_BASELINE_RECORDED — 14 new/touched production modules PASS;
9 pre-existing errors remain in src/open_deep_research/utils.py

git diff --check:
PASS

Real-provider smoke:
PASS
```

---

## 39. Pre-closeout Architecture Audit

Answer all with YES：

```text
[x] YES — No Contract semantics changed during coding.
[x] YES — No SPEC semantics changed during coding.
[x] YES — No architecture decision was silently made in TASKS/code.
[x] YES — Global Synthesis remains deterministic staged orchestration.
[x] YES — No Agentic synthesis loop was introduced.
[x] YES — Research Run input remains stable while ACTIVE.
[x] YES — No second provenance representation was introduced.
[x] YES — No second Citation authority was introduced.
[x] YES — Renderer remains non-authoritative.
[x] YES — Evaluator remains graph-external.
[x] YES — Manifest remains atomic.
[x] YES — Retry remains Host-owned and bounded.
[x] YES — Source metadata enrichment remains compact/best-effort.
[x] YES — V1 remains available during P2-S5.
[x] YES — No new EvidenceFlow S5 mypy errors were introduced.
```

Any `NO`：

```text
→ P2-S5 closeout BLOCKED
```

---

## 40. P2-S5 Implementation Acceptance

Implementation may be marked verified only when：

```text
T00–T23 complete
+
S5-R01–R19 = 19/19 PASS
+
relevant Contract invariants PASS
+
focused deterministic tests PASS
+
regression gate PASS or documented pre-existing baseline only
+
Ruff PASS
+
no new S5 mypy errors
+
git diff --check PASS
+
real-provider smoke = PASS
  OR SKIPPED_DUE_TO_ENVIRONMENT according to frozen policy
+
no authority/document drift
```

Implementation Verification：

```text
[x] PASS
[ ] BLOCKED
```

Real-provider Smoke：

```text
[x] PASS
[ ] SKIPPED_DUE_TO_ENVIRONMENT
[ ] FAIL
```

Known non-blocking limitations：

```text
- external evaluator live entry returned operational `NotFoundError` because the
  configured endpoint does not expose the frozen default `gpt-4.1`; deterministic
  evaluator tests pass
- canonical Ruff retains 12 pre-existing findings in untouched evaluation scripts
- full/scoped mypy retains the accepted 9 pre-existing utils.py errors
```

---

## 41. CHECKLIST Freeze Gate

`P2_S5_CHECKLIST.md` 只有满足以下条件才可改为 `FINAL FROZEN`：

1. CHECKLIST 不包含新的 architecture decision；
2. T00–T23 全部有 verification coverage；
3. S5-R01–R19 全部有 acceptance coverage；
4. Contracts I13–I24 等 P2-S5 关键 invariants 有显式验证；
5. lifecycle/checkpoint verification 完整；
6. retry/backoff/timeout 验证完整；
7. structured input/output bounds 验证完整；
8. metadata enrichment/no-fabrication 验证完整；
9. Publication Gate / atomicity / replay 验证完整；
10. Renderer authority / Claim coverage / conflict disclosure 验证完整；
11. evaluator isolation / six-dimension rubric 验证完整；
12. V1 failure isolation 验证完整；
13. real-provider smoke environment-conditional policy 明确；
14. pytest / Ruff / mypy / git diff quality gates 明确；
15. no-new-mypy-error requirement 明确；
16. document drift / stale behavior scan 明确；
17. CHECKLIST Freeze 本身不自动宣告 implementation PASS。

通过 review 后：

```text
P2-S5 SPEC
→ FINAL FROZEN

P2-S5 PLAN
→ FINAL FROZEN

P2-S5 TASKS
→ FINAL FROZEN

P2-S5 CHECKLIST
→ FINAL FROZEN

Pre-implementation Review
→ AUTHORIZED

Coding
→ STILL BLOCKED UNTIL PRE-IMPLEMENTATION REVIEW PASSES
```

Pre-implementation Review PASS 后：

```text
Coding
→ AUTHORIZED
```

---

## 42. Phase Closeout Record

Implementation 完成后填写：

```text
Phase:
P2-S5

Branch:
p2-s5-claim-citation-grounding

Implementation commit(s):
not created — implementation remains an uncommitted working-tree diff

T00–T23:
DONE

S5-R01–R19:
19/19 PASS

Focused tests:
150 passed, 1 skipped, 26 warnings

Full regression:
190 passed, 1 skipped, 1 deselected, 48 warnings

Ruff:
new/touched S5 target PASS; 12 pre-existing canonical-target findings recorded

Mypy:
NO_NEW_S5_ERRORS; 9 pre-existing utils.py errors recorded

git diff --check:
PASS

Real-provider smoke:
PASS

External evaluator:
IMPLEMENTED / DETERMINISTICALLY VERIFIED / LIVE OPERATIONAL_FAILURE: NotFoundError

Contract drift:
NONE

SPEC drift:
NONE

Known limitations:
evaluator default model unavailable at configured endpoint; accepted Ruff/mypy baselines remain

Final implementation status:
VERIFIED
```

只有：

```text
Final implementation status = VERIFIED
```

才允许进入 P2-S5 phase closeout / commit / review 流程。
