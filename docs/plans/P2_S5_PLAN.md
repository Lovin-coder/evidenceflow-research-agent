# P2-S5 — Global Claim, Citation and Grounding PLAN

## 0. 状态与文档职责

| Field | Value |
|---|---|
| Phase | `P2-S5` |
| Document | `P2_S5_PLAN.md` |
| Status | **FINAL FROZEN** |
| SPEC status | **FINAL FROZEN / RENDERER RESYNCED** |
| Clarification status | **D00–D20 + CB01–CB06 RESOLVED / PROMOTED；D14 LATEST RESOLUTION PROMOTED** |
| Contracts status | **CONSISTENT** |
| Coding gate | **CLOSED UNTIL PLAN / TASKS / CHECKLIST ARE REVIEWED AND FROZEN** |
| Contract version | `evidenceflow.contracts.v1` |
| Target branch | `p2-s5-claim-citation-grounding` |

本文只负责将已经冻结的 P2-S5 semantics 映射到当前 Open Deep Research / LangGraph runtime，不重新定义 Claim、
Grounding、Citation、Source/Evidence identity、Research Run、Manifest 或 failure semantics。

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

Contracts / SPEC 决定系统必须保证什么；Clarifications 是 authoritative decision-provenance log，记录 Human
Resolution、rationale、supersession 与 promotion history，但不独立定义 normative runtime semantics。

PLAN 只回答：

- `WHERE`：组件位于哪些文件；
- `HOW`：frozen semantics 如何映射到当前 runtime；
- `ORDER`：实现依赖顺序；
- `CONFIG`：implementation parameters、bounds 与 concurrency；
- `FAILURE`：如何实现 frozen failure/fallback；
- `VALIDATION`：需要验证哪些 implementation properties。

PLAN 不复制 stable Contract 的完整字段定义，也不维护具体 test 文件、pytest 命令或逐条 CHECKLIST。如果实现映射
发现新的 Domain、State、identity、Grounding、Citation、Research Run、topology 或 failure ambiguity，必须停止受影响
工作并返回 Clarifications，不得 Silent Spec Mutation。

---

## 1. Implementation Goal and Runtime Topology

P2-S5 将：

```text
MedicalResearchBrief
+
ResearchTaskResult[]
```

转换为：

```text
bounded structured projection
        ↓
Model A — Claim Generator
        ↓
Host Claim validation / identity / admission
        ↓
ClaimRecord[]
        ↓
Finding-derived Evidence universe
        ↓
Model B — Grounding Judge
        ↓
Host Grounding materialization
        ↓
Citation materialization
        ↓
GroundingManifest Publication Gate
        ↓
derived metrics / display projection
        ↓
Model C — Shadow Renderer
        ↓
Host structural validation / conflict marker / citation injection / bibliography
        ↓
V2 Shadow Report
```

Parent graph 只新增一个 orchestration node：

```text
research_supervisor
        ↓
global_synthesis
        ↓
final_report_generation
```

Supervisor / Researcher 保持现有 Agentic Loop：

```text
Supervisor: supervisor ↔ supervisor_tools
Researcher: researcher ↔ researcher_tools → compress_research
```

Global Synthesis 输入已经是 structured Results，使用 bounded multi-stage pipeline，不引入 Agentic Loop、Claim repair
loop、Grounding-to-research loop 或 evaluator-to-rewrite loop。

---

## 2. Audited Runtime Baseline

当前 runtime 已确认：

- `AgentState` 基于 `MessagesState`；
- `research_results` 使用 identity merge reducer，普通 `[]` 无法清空；
- `supervisor_messages`、`notes`、`raw_notes` 的当前 reducer 支持显式 override，普通 update 为 append；
- `ResearcherState` 每个 ResearchTask 独立创建；
- `artifact_run_id` 在同一 Research Run 内传播；
- Artifact 完整地址为 `(artifact_run_id, artifact_ref)`；
- pinned `langgraph==1.2.9` 提供 `Overwrite`；
- 当前 graph 没有 active `interrupt()`；
- `HumanMessage.id` 在客户端未提供时默认是 `None`，首次进入 `add_messages` 才生成随机 UUID；
- 客户端 retry 若不复用同一 `message.id`，会产生新的 `HumanMessage` occurrence；
- 当前 SDK / evaluation entry 不提供稳定 message ID guarantee。

S5 不把 process artifacts、Messages、raw notes、provider snippets 或 model reasoning 当作 V2 Evidence authority，也不
重新 ingest Source、重算 Evidence、修改 locator/hash 或增加第二套 Artifact persistence。

---

## 3. Target File and Package Mapping

### 3.1 Stable Domain and Parent process contracts

`src/open_deep_research/domain_models.py` 只实现 Contracts v1 定义的 stable P2-S5 Domain contracts：

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

具体 shape 只以 Contracts v1 为 canonical authority，本 PLAN 不维护副本。

`src/open_deep_research/state.py` 放 Parent process / State contracts：

```text
GlobalSynthesisStatus
GlobalSynthesisIssue
GlobalSynthesisSeverity
ResearchRunStatus
```

新增 Parent fields：

```text
grounding_manifest
global_synthesis_status
global_synthesis_issues
v2_shadow_report
research_run_status
research_run_input_cursor
```

`research_run_input_cursor` 是 conversation/checkpoint-level lifecycle cursor，不是 Domain provenance。

### 3.2 Global Synthesis package

```text
src/open_deep_research/global_synthesis/
├── __init__.py
├── types.py
├── projection.py
├── claims.py
├── grounding.py
├── publication.py
├── renderer.py
└── pipeline.py
```

依赖方向：

```text
stable Domain / State
        ↓
types.py
        ↓
projection / claims / grounding / publication / renderer
        ↓
pipeline.py
        ↓
__init__.py facade
```

Subsystem 不得反向依赖 `pipeline.py`。不再增加 `limits.py`、`receipts.py`、`display.py`、`metrics.py` 等微包。

### 3.3 Integration owners

`deep_researcher.py` 只负责：

- Research Run bootstrap / resume 接入；
- 定义并在entry boundary抛出private `_ResearchRunLifecycleConflict`；
- `global_synthesis` Parent node wrapper；
- graph edge；
- terminal Run finalization；
- node boundary failure containment。

复杂 validation/materialization 不进入该文件。`prompts.py` 新增 Model A/B/C prompts；`configuration.py` 只新增：

```text
max_concurrent_grounding_judgments: int = 4
```

其他 phase limits 保持 immutable `GlobalSynthesisLimits`，位于 `global_synthesis/types.py`。

---

## 4. P01 — Research Run Entry and Message Identity

### 4.1 Lifecycle model

```text
Conversation / checkpoint
        >
Research Run
        >
ResearchTask
```

```text
ResearchRunStatus = ACTIVE | AWAITING_CLARIFICATION | FINALIZED
```

Status 本身不足以区分 new Run 与 replay，因此新增：

```text
research_run_input_cursor: int | None
```

它由服务端维护，表示当前 lifecycle 已消费到的 `HumanMessage` occurrence ordinal；客户端不读写 cursor。服务端从
current `messages` 计算：

```text
current_human_count
```

Lifecycle 已初始化后，Host 定义：

```text
fresh_delta = current_human_count - research_run_input_cursor

fresh_delta < 0  → lifecycle integrity conflict
fresh_delta == 0 → no fresh HumanMessage
fresh_delta == 1 → exactly one new logical HumanMessage
fresh_delta > 1  → lifecycle conflict
```

`fresh_delta < 0` 或 `fresh_delta > 1` 时，Host不消费任何fresh HumanMessage、不推进cursor、不reset current Run、
不修改current Run structured provenance，也不执行Silent Repair。只有`fresh_delta == 1`才结合
`ResearchRunStatus`执行lifecycle dispatch。不得用message content/hash相等推断retry，因为相同文本可能是合法的
两次输入。

P2-S5不支持ACTIVE Research Run执行过程中的普通用户追加指令（mid-run user steering）。Run进入`ACTIVE`后，
当前用户输入视为稳定；新的HumanMessage只有在显式`AWAITING_CLARIFICATION`边界才可被current Run消费。

首次lifecycle initialization同样只接受一个logical input：no lifecycle/cursor且当前恰有一个未消费HumanMessage时
bootstrap first Run；zero或multiple unconsumed HumanMessages均是entry/lifecycle conflict。S5不猜测多个messages是
一个请求的分段输入、多个top-level requests或imported history，也不实现conversation-history import或message batching。

### 4.2 Entry message identity contract

```text
message.id
→ HumanMessage input identity

research_run_input_cursor
→ Run 已消费输入的位置

ResearchRunStatus
→ 当前 Run 生命周期状态
```

Entry identity rules：

- 每个新的逻辑用户输入 SHOULD 使用新的 `message.id`；
- 同一逻辑输入的客户端 retry SHOULD 复用原 `message.id`；
- 同一个 `message.id` MUST 表示同一逻辑 `HumanMessage` 及相同或语义等价 payload；
- same `message.id` + divergent payload 是 caller contract violation；
- S5 不把同 ID divergent payload 解释为合法的新输入或合法内容更新；
- S5 不新增 fingerprint、request ID 或其他子系统检测/修复该 caller violation；
- 因此runtime可能无法发现该违约，且对违约后的lifecycle/content correctness不提供保证；调用方MUST避免该输入；
- 未提供稳定 ID 时，S5 不承诺跨客户端 retry idempotency；
- S5 不通过文本相等、content hash 或 fingerprint 推断 retry；
- 同一稳定 ID 的正常 retry 由 `add_messages` 替换 existing occurrence，不增加 Human count；
- 无 ID 或不同 ID 的重复文本形成新的 occurrence，并按新输入处理；
- 需要 transport-level idempotent retry 的调用方应复用稳定 `message.id`，或继续读取已经创建的 LangGraph Run。

`message.id` 不是 Evidence、Claim、Research Run 或 Artifact provenance identity。

### 4.3 Deterministic entry state machine

#### Framework admission boundary

LangGraph MAY merge an incoming `HumanMessage` into the conversation-level `messages` channel before the EvidenceFlow
entry node executes. This framework-level admission is outside the P01 lifecycle-conflict atomicity guarantee；P01
conflict atomicity begins at the EvidenceFlow Research Run admission boundary。

| Existing State | Input multiplicity | Behavior |
|---|---:|---|
| no lifecycle / cursor | exactly one current HumanMessage | bootstrap first Run；reset run-scoped State；fresh `artifact_run_id`；cursor=`current_human_count` |
| no lifecycle / cursor | zero or multiple unconsumed HumanMessages | lifecycle conflict；do not infer batching/history semantics |
| `AWAITING_CLARIFICATION` | `fresh_delta == 0` | remain awaiting；idempotent no-op；do not rerun research |
| `AWAITING_CLARIFICATION` | `fresh_delta == 1` | resume same Run；preserve namespace；set `ACTIVE`；advance cursor |
| `AWAITING_CLARIFICATION` | `fresh_delta > 1` | lifecycle conflict；consume none |
| `ACTIVE` | `fresh_delta == 0` | same-run replay/recovery；preserve cursor and provenance |
| `ACTIVE` | `fresh_delta >= 1` | typed lifecycle conflict；mid-run steering unsupported |
| `FINALIZED` | `fresh_delta == 0` | application-level replay；preserve current outputs；do not start new Run |
| `FINALIZED` | `fresh_delta == 1` | bootstrap new Run；reset before admission；fresh namespace；advance cursor |
| `FINALIZED` | `fresh_delta > 1` | lifecycle conflict；consume none |
| initialized lifecycle | `fresh_delta < 0` or impossible status/cursor combination | lifecycle integrity conflict；no Silent Repair |

所有 conflict path 在 EvidenceFlow-owned lifecycle / structured provenance mutation 前抛出 typed
`_ResearchRunLifecycleConflict`。Framework-level incoming `HumanMessage` admission MAY 已经发生；该 message 保留在
`messages`，但由于 cursor 不推进，它仍未被 current/new Research Run 消费。

Conflict 后 EvidenceFlow MUST NOT emit any additional lifecycle or structured provenance mutation：

- `research_run_input_cursor`、`research_run_status` 与 `artifact_run_id` 不变；
- no run-scoped reset；
- brief、Results、notes/raw notes、`final_report` 与 `v2_shadow_report` 不变；
- Manifest、global synthesis issues/status 与 sticky degradation fact 不变；
- no Claim、Grounding 或 Citation materialization；
- no implicit `ACTIVE` Run abandonment。

S5 不通过 `RemoveMessage`、compensating message deletion、pre-graph wrapper、new request admission service 或 hidden
checkpoint rollback 恢复“checkpoint unchanged”；未来 phase 如需这些能力必须另行设计。该 conflict 作为 LangGraph
Run/entry error 暴露。`AWAITING_CLARIFICATION`或`FINALIZED`且`fresh_delta == 0`时，entry返回无 EvidenceFlow-owned
State mutation的`Command(goto=END)`。

### 4.4 Reset and finalization

New Run admission 前必须通过 `Overwrite` / replace reset：

```text
supervisor_messages
medical_research_brief
research_brief
research_results
raw_notes
notes
final_report
grounding_manifest
global_synthesis_status
global_synthesis_issues
v2_shadow_report
research_run_status
run-local degradation fact
```

Conversation `messages` 与 `research_run_input_cursor` 保留为 conversation/checkpoint lifecycle context；new Run
bootstrap 将 cursor 设置为当前已接纳 input ordinal。旧 ArtifactStore files 不删除，但旧 Run Result/Manifest 不再是
active authority。

`final_report_generation` 受控 terminal path 完成后写 `FINALIZED`；即使 V1 返回 bounded fallback text，logical Run
仍可结束。未被 containment 捕获的 process/system exception MAY 使 State 保持 `ACTIVE` 供显式 recovery。S5 不新增
active-run abandonment API。

---

## 5. Internal Types, Identity and Receipts

PLAN 只定义 internal/process types，不复制 stable Domain shapes：

```text
ClaimDraft / ClaimDraftBatch
ClaimEvidenceVerdict / ClaimGroundingDraft
GroundingEvidenceView
RendererEvidenceView
ReportClaimView
ReportParagraphDraft / ReportSectionDraft / ShadowReportDraft
GlobalSynthesisLimits / GlobalSynthesisExecutionContext / GlobalSynthesisOutcome
```

### 5.1 Deterministic IDs

Claim ID 使用：

```text
original Generator ordinal
+
validated semantic payload
```

semantic payload 只包含 `text`、`materiality`、`finding_refs`、`scope`、`qualifiers`。不得包含 survivor ordinal、
timestamp、provider metadata 或 message。Sibling reject/overflow不得改变其他 Claim ID。

Citation ID 只由 `claim_id + EvidenceRef` 派生，不包含 URL、display label 或 metadata。

### 5.2 P02 — Tagged materialization receipts

```python
@dataclass(frozen=True)
class ClaimMaterializationReceipt:
    original_generator_ordinal: int
    canonical_claim_payload: bytes
    expected_claim_id: str


@dataclass(frozen=True)
class AssessedGroundingReceipt:
    claim_id: str
    validated_verdict: ClaimEvidenceVerdict
    evaluated_evidence_refs: tuple[EvidenceRef, ...]
    expected_status: GroundingStatus


@dataclass(frozen=True)
class UnassessedGroundingReceipt:
    claim_id: str
```

`AssessedGroundingReceipt` 表示存在合法 semantic Judge verdict 和真实 evaluated universe；Gate验证 verdict/status 与
actual input。`UnassessedGroundingReceipt` 只允许 strict `UNASSESSED`：所有 refs为空且 `reason=None`。Attempted refs 与
errors只进入 issues。

Receipts 只存在于一次 Global Synthesis process-local execution context，不进入 Manifest、Parent State 或 evaluator。

---

## 6. Limits, Context and P04 Retry Authority

### 6.1 Physical model mapping

| Logical role | Initial physical configuration |
|---|---|
| Model A — Claim Generator | `final_report_model` / `final_report_model_max_tokens` |
| Model B — Grounding Judge | `compression_model` / `compression_model_max_tokens` |
| Model C — Shadow Renderer | `final_report_model` / `final_report_model_max_tokens` |
| External Faithfulness Eval | existing evaluation model configuration；not runtime role |

不增加三套role-specific provider configuration。后续Eval如证明quality不足，可调整physical mapping，但不得改变logical
role authority。

### 6.2 Initial limits

使用 immutable `GlobalSynthesisLimits` 集中管理engineering guardrails。初始值：

| Area | Limit | Value |
|---|---|---:|
| Generator | `max_findings_total` | 40 |
| Generator | `max_findings_per_task` | 8 |
| Generator | `max_generator_evidence_chars` | 96,000 |
| Generator | `max_task_summary_chars` | 2,000 |
| Generator | `max_task_error_context_chars` | 1,000 |
| Generator | `max_generator_context_chars` | 128,000 |
| Generator | `max_claim_drafts_returned` | 64 |
| Generator | `max_claim_batch_serialized_chars` | 128,000 |
| Claim | `max_claims` | 20 |
| Claim | `max_claim_text_chars` | 1,500 |
| Claim | `max_claim_scope_chars` | 500 |
| Claim | `max_qualifiers_per_claim` | 8 |
| Claim | `max_qualifier_chars` | 300 |
| Claim | `max_finding_refs_per_claim` | 8 |
| Judge | `max_evidence_refs_per_claim` | 24 |
| Judge | `max_judge_evidence_chars` | 64,000 |
| Judge | `max_judge_context_chars` | 80,000 |
| Judge | `max_grounding_reason_chars` | 2,000 |
| Judge | `max_grounding_draft_serialized_chars` | 16,000 |
| Manifest | `max_citations` | 512 |
| Manifest | `max_manifest_serialized_chars` | 1,000,000 |
| Issues | `max_global_synthesis_issues` | 64 |
| Issues | `max_issue_message_chars` | 1,000 |
| Issues | `max_issue_ledger_chars` | 128,000 |
| Renderer | `max_renderer_context_chars` | 128,000 |
| Renderer | `max_sections` | 8 |
| Renderer | `max_section_title_chars` | 300 |
| Renderer | `max_paragraphs_total` | 24 |
| Renderer | `max_paragraph_chars` | 2,000 |
| Renderer | `max_claim_ids_per_paragraph` | 6 |
| Renderer | `max_claim_occurrences_per_claim` | 3 |
| Renderer | `max_shadow_report_chars` | 30,000 |
| Renderer | `max_renderer_draft_serialized_chars` | 128,000 |

`max_citations=512` replaces the earlier 128 draft guardrail so the required capacity invariant holds：

```text
max_citations >= max_claims × max_evidence_refs_per_claim
```

这些值不是calibrated quality threshold或release gate。调整上游capacity时必须同步验证该不变量和全部role-context
safety reserve；TASKS不得单独修改某个值而破坏capacity relationship。

每个 model role 验证完整 serialized input：prompt + schema + Brief + records/projections + optional metadata。Effective
budget：

```text
min(
  static role cap,
  provider context limit - output reserve - prompt/schema safety reserve
)
```

Authoritative Evidence excerpt 不截断；只允许 whole-unit admission/omission。

Initial timeout guardrails：Model A 90s、每Claim Model B 60s、Model C 90s、external evaluator 90s。若provider wrapper已有
更严格timeout，使用更严格值；timeout不是Contract。

### 6.3 Structured output bounds

Input/context bounds不能替代model-output bounds。每个structured model role都必须执行Host-side aggregate output
validation；provider output-token limit只是资源guardrail，不等于Host对DTO structure、list/field/reference counts与
serialized payload的验证。

- Model A：`ClaimDraftBatch` returned item count受`max_claim_drafts_returned`约束，aggregate serialized payload受
  `max_claim_batch_serialized_chars`约束；
- Model B：supporting/contradicting refs继续受admitted Evidence universe与per-Claim limits约束；`ClaimGroundingDraft`
  aggregate payload受`max_grounding_draft_serialized_chars`约束，`reason`另受`max_grounding_reason_chars`约束；
- Model C：section count、independently bounded section title、paragraph count/length、Claim bindings与aggregate
  `ShadowReportDraft`分别受对应bounds约束；final rendered report再次受`max_shadow_report_chars`约束。

Structured output超过任何aggregate bound时不得silent truncate后materialize authoritative record，必须遵循：

```text
parse → Host validate → retry-if-retryable → frozen stage failure/salvage policy
```

- Model A batch count/payload overflow：aggregate validation failure；P04 retry exhaustion后执行Generator failure policy；
- Model B draft payload overflow：只retry current Claim；exhaustion后该Claim为strict `UNASSESSED`；
- Model C aggregate draft overflow：retry whole Renderer；exhaustion后保留Manifest、`report=None`、status=`PARTIAL`。

这些规则不改变Claim sibling salvage，也不允许valid negative semantic result retry-to-pass。

### 6.4 P04 — Single retry authority

`max_structured_output_retries = R` 的唯一含义：

```text
maximum actual model/provider requests = 1 + R
```

Host 是唯一 logical model-request retry owner。实现 single-attempt `invoke_structured_once()`；其内部不得重新发送 model
request。当前 wrapper/client 的 automatic logical request retry必须关闭或绕过。Host loop：

```text
invoke once → parse → Host validation → success / retryable failure / terminal result
```

Retryable：provider/transport failure、timeout、schema parse failure、aggregate structural/reference validation failure。
Valid `INSUFFICIENT`、`CONTRADICTED`、evaluator FAIL、Claim sibling invalidity和一般 prose质量不得 retry-to-pass。

---

## 7. Model A — Generator Projection and Claim Materialization

Model A 输入：

```text
MedicalResearchBrief
+
bounded ResearchTaskResult projection
```

每个 admitted Result MAY 包含 task/status、bounded summary/limitations/conflicts/error context、Findings、FindingRefs、
referenced exact Evidence excerpts 与 optional validated Source metadata。Result-level text只提供context，不授权Claim。

Admission order：

```text
research_results ledger order
→ per-task Finding cap
→ Finding order
→ Evidence order
```

Host 建立 `generator_visible_finding_refs`。Model A只输出 Claim semantics + allowlisted FindingRefs，不输出 EvidenceRef、
Grounding或Citation。

Claim pipeline：

```text
ClaimDraft[]
→ field/schema validation
→ FindingRef resolution
→ allowlist validation
→ exact duplicate handling
→ sibling-stable ID
→ one-time Claim capacity admission
→ restore Generator order
→ ClaimRecord[]
```

- invalid sibling：drop + degradation；valid siblings继续；
- all invalid：可继续形成 empty candidate Manifest，但 degradation=True；
- exact duplicate只按 canonical serialization；不得 fuzzy/embedding dedup；
- capacity overflow按 `HIGH → MEDIUM → LOW`，同 tier保留Generator order，survivors恢复canonical Generator order；
- Renderer不得执行第二次 Claim selection。

---

## 8. Model B — Evidence Universe and Grounding

每个 surviving Claim 的 candidate Evidence universe：

```text
finding_refs order
→ ResearchFinding
→ finding.evidence_ids order
→ task-qualified EvidenceRef
→ exact first-occurrence dedup
```

Model A 不参与该 universe。`GroundingEvidenceView` 至少包含 `EvidenceRef + exact excerpt`；title、stored URL、provider、
publisher、authors、published_at、document_type均optional、validated、bounded、never inferred。`locator`、`source_id`、
`artifact_ref`保留在Host provenance path。

Judge admission按canonical candidate order应用ref cap、Evidence char cap与total context cap：legal prefix、no rerank、no
excerpt slice。Omission触发degradation；只有actual Model B input refs成为`evaluated_evidence_refs`。Empty admitted universe
不调用Model B，直接strict `UNASSESSED` + degradation。

### 8.1 P03 — Safe sibling isolation

每个 Claim通过 `_judge_claim_safe()` 执行。Ordinary Claim-local exception只影响该Claim：

```text
UNASSESSED + bounded issue + degradation
```

System/task cancellation不得被普通 exception handling吞掉。并发使用Semaphore + `asyncio.gather`；completion timing没有
ordering authority，最终按canonical Claim order materialize。

### 8.2 Validation and materialization

Host验证supporting/contradicting refs是evaluated subset、unique、disjoint、canonical filtered order，并检查verdict-specific
requiredness与reason bounds/sanitization。合法 result按frozen five-state mapping materialize；Judge exhaustion只使当前
Claim `UNASSESSED`。Gate使用tagged receipt验证assessed/unassessed与verdict/status mapping。

---

## 9. Citation, Manifest and Replay

Host从GroundingStatus派生required Citation refs：

```text
SUPPORTED                  → supporting
SUPPORTED_WITH_CONFLICT    → supporting + contradicting
INSUFFICIENT/CONTRADICTED/
UNASSESSED                 → empty
```

每个 `(claim_id, EvidenceRef)` 最多一个 canonical Citation。Citation materialization failure使candidate Manifest无效。
Canonical Citation traversal为：canonical Claim order → supporting refs canonical order → contradicting refs canonical
order。该顺序同时是P06 contributing Source traversal与display-label assignment authority。

Publication Gate位于`publication.py`，输入candidate Manifest、Claim/Grounding receipts、resolver context与configured
bounds。它验证identity、one-to-one binding、reference resolution、Grounding set/receipt invariants、exact Citation
required-vs-actual set、canonical order、contract version与payload bounds。

Gate只validate，不repair；任一失败不发布Manifest。流程必须是：

```text
local candidate → Gate PASS → one-shot State publication
```

Renderer failure不回滚已通过Gate的Manifest。

### 9.1 P10 — Replay, repair and regenerate

```text
Replay != Repair != Regenerate
```

- Manifest absent：normal synthesis；
- Manifest + Shadow Report存在：short-circuit，Model A/B/C均不调用；
- Manifest存在、Shadow Report缺失、status=`PARTIAL`：保留Manifest/PARTIAL/no report，不自动rerun Model C；
- `FINALIZED + fresh HumanMessage`：P01先创建new Run并reset旧Manifest，然后normal synthesis。

这是 application-level idempotency，不等于 LangGraph checkpoint resume，也不承诺 HTTP/token stream reconnect。

---

## 10. Issues, Status and Metrics

`GlobalSynthesisStage` 只存在于 `global_synthesis/types.py`，约束Host-produced values；stable
`GlobalSynthesisIssue.stage`保持open string。

Issue ID只使用stable coordinates：stage、code、claim/task/Evidence coordinates、attempt与occurrence key；message不参与
identity。同ID identical replay幂等。

### 10.1 P05 — Divergent Issue payload

Same issue ID出现divergent payload时：

```text
retain first Issue
→ degradation_observed=True
→ emit deterministic ISSUE_PAYLOAD_CONFLICT
→ do not invalidate Manifest solely for this reason
→ do not block V1
```

`ISSUE_PAYLOAD_CONFLICT` 使用独立deterministic ID。Reconciliation发生在Host issue collection/state-update preparation，
不依赖reducer exception。Reducer只做defensive first-write-wins，不负责跨channel修改status。Ledger满后sticky
degradation仍可从False变True。

### 10.2 Global status

| Status | Result |
|---|---|
| `SUCCESS` | Manifest published；Renderer或zero-eligible Host output成功；no degradation |
| `PARTIAL` | Manifest published；degradation、Renderer failure、UNASSESSED或admission/sibling omission |
| `FAILED` | no Manifest；V1和valid S4 Results保留 |

Valid `INSUFFICIENT` / `CONTRADICTED`不是degradation。

### 10.3 P09 — Metrics exposure

`derive_grounding_metrics(manifest)`位于`publication.py`，pure、deterministic、recomputable，不修改Manifest。`pipeline.py`
返回internal：

```text
GlobalSynthesisOutcome
├─ manifest
├─ shadow_report
├─ status
├─ issues
└─ metrics
```

Metrics不进入Parent State或Manifest，仅服务tests、controlled smoke、evaluation和runtime instrumentation；definitions仍由
Contracts/SPEC定义。

---

## 11. P06/P07 — Reader-facing Source Display

Source层先对单个`SourceRecord`做metadata validation、normalization、whitelist/bounds与no-fabrication。Display层再对多个
canonical Sources做presentation-only deterministic grouping/selection，不修改SourceRecord。

TASKS MUST实现一个required small best-effort Source metadata enrichment adapter。它保留现有URL/title/provider，
并仅处理Contracts v1已列、Host/provider能够可靠验证的`retrieved_at`、publisher、authors、`published_at`与
`document_type`；单个optional value缺失不是Task failure，也不得推断或补造。`retrieval_score`不进入P2-S5 metadata
surface。S5 correctness不得依赖enrichment，enrichment也不得修改Source/Evidence identity、`artifact_ref`或
mandatory upstream schema。

### 11.1 Tagged display key

```python
@dataclass(frozen=True)
class TaskSourceDisplayKey:
    task_id: str
    source_id: str


@dataclass(frozen=True)
class UrlArtifactDisplayKey:
    artifact_run_id: str
    stored_url: str
    artifact_ref: str
```

构造规则：valid stored URL + resolvable current-run `artifact_ref` → `UrlArtifactDisplayKey`；否则 →
`TaskSourceDisplayKey`。Stored URL使用resolved Source中的validated exact stored value；S5不canonicalize、normalize、清理或
推断URL。

因此同一 canonical Source的多个cited Evidences可共享label；cross-task只有same Run + exact stored URL + same
`artifact_ref`才可group；missing/invalid URL禁止cross-task group；bare `artifact_ref`不推断cross-run identity。

### 11.2 P06 — Metadata merge

同一`SourceDisplayEntry`内，identity fields `artifact_run_id/stored_url/artifact_ref`直接来自display key，不merge。

Display metadata：

```text
title
publisher
authors
published_at
document_type
provider
```

按照 canonical Citation traversal 中 contributing Source的first occurrence，对每个字段使用：

```text
first validated non-empty wins
```

后续不同值不覆盖；全部 contributing canonical Source refs保留在entry中供审计。不得依赖async completion、dict update
order、model selection、fuzzy “best metadata”或推断缺失字段。

Label assignment按canonical Citation traversal中的first display-key occurrence分配`[1]`, `[2]`, ...。Bibliography使用
deterministic best-effort GB/T 7714-style formatter，只消费validated available metadata。

---

## 12. P08 — Model C Shadow Renderer

### 12.1 Authority and input

Model C负责section数量/title/order、paragraph organization/prose，以及对supporting/contradicting Evidence的自然叙事。
Host负责eligible Claim allowlist、Evidence projection admission、bounds、paragraph binding validation、Claim coverage、
Citation identity/set、display labels、bibliography、最低conflict disclosure与final serialization。

每个report-eligible Claim形成`ReportClaimView`：完整Claim proposition、materiality、GroundingStatus、bounded supporting /
contradicting Evidence projection与optional validated Source metadata。`RendererEvidenceView`包含`EvidenceRef`、role、exact
excerpt和optional metadata。

只允许来自已materialize的supporting/contradicting refs；Artifact、full Result、raw notes、reason与
evaluated-but-non-material Evidence不进入Model C。Model C不得重新分类role、扩展universe、修改Grounding、创建Citation
identity或输出authoritative numbering。

### 12.2 Evidence context admission

Authoritative required Citation set全部保留；Model C visible Evidence只是bounded semantic aid。Claim proposition优先全部
进入Renderer context，Evidence whole-unit admission分两阶段：

1. 按canonical Claim order，为每个eligible Claim尝试一个supporting Evidence；每个conflict Claim再尝试一个
   contradicting Evidence；
2. 剩余budget按canonical Claim/Citation order接纳其余material Evidence。

若最低role coverage无法完全容纳，Claim仍保留；omitted Evidence不改变Grounding/Citation；记录Renderer context
admission degradation；Host conflict marker仍保证冲突可见。

### 12.3 Structured output and validation

```python
class ReportParagraphDraft(BaseModel):
    text: str
    claim_ids: list[str]


class ReportSectionDraft(BaseModel):
    title: str
    paragraphs: list[ReportParagraphDraft]


class ShadowReportDraft(BaseModel):
    sections: list[ReportSectionDraft]
```

Model C不使用Host-fixed `section_id` catalog。Host保留Model output section/paragraph order，并验证section title non-empty、
sanitized、bounded；每个body paragraph的Claim IDs non-empty、exist、eligible、within-paragraph unique且occurrence bounded；
所有eligible Claims至少出现一次。Model-generated unbound body paragraph禁止，section title不需要Claim binding。

Renderer aggregate schema/reference/coverage failure按P04 Host retry；exhaustion保留Manifest、report=None、status=PARTIAL。

### 12.4 Conflict marker and Citation injection

Model C可读取conflict Evidence并自然解释，但Host不判断prose是否已充分披露。对每个
`SUPPORTED_WITH_CONFLICT` Claim的first canonical paragraph occurrence，Host插入localized deterministic minimum marker，
例如“存在与该结论方向不一致的重要证据。”，并保证supporting与contradicting required display labels均可见。

Paragraph只返回`claim_ids`。Host执行：

```text
claim_ids → required Citations → SourceDisplayKeys → ordered labels → injection
```

Multi-Claim paragraph按canonical Claim/Citation order做ordered union；repeated Claim复用同一Citation set，不生成新
Citation。如果eligible set为空，skip Model C并生成deterministic no-grounded-claim output，不创建fake Claim/Citation。

---

## 13. Pipeline, Failure Containment and V1/V2 Migration

`pipeline.py`顺序：

```text
1. same-run replay check
2. execution context
3. Generator projection / Model A
4. Claim validation / identity / admission
5. per-Claim Evidence universe / safe Model B / Grounding
6. Citation materialization
7. candidate Manifest / Publication Gate
8. metrics / display projection
9. zero eligible Host output OR Model C / validation / marker / labels / bibliography
10. derive GlobalSynthesisStatus
11. return one bounded Parent State update
```

Node boundary捕获ordinary S5 failures并返回bounded State update，使fixed edge继续V1；system cancellation继续传播。
Pre-Gate failure不发布Manifest；post-Gate Renderer failure保留Manifest。V1 final writer继续读取legacy notes。

Graph保持：

```text
research_supervisor → global_synthesis → final_report_generation
```

S5保证output isolation和failure isolation，不保证latency isolation，也不提供HTTP stream reconnect或node-internal durable
stage resume。

### 13.1 Failure mapping

| Event | Result | Status |
|---|---|---|
| Generator request/schema exhaustion | no Manifest/report；preserve S4/V1 inputs | `FAILED` |
| valid empty Generator result | empty valid Manifest + Host zero-eligible output | `SUCCESS` if no degradation |
| invalid Claim sibling / Claim capacity omission | salvage legal siblings | `PARTIAL` if Manifest publishes |
| one Claim Judge exhaustion/ordinary exception | strict `UNASSESSED`；siblings continue | `PARTIAL` if Manifest publishes |
| valid `INSUFFICIENT` / `CONTRADICTED` | normal semantic record | no degradation by itself |
| Citation materialization or Gate failure | no Manifest | `FAILED` |
| Renderer failure after Gate | Manifest preserved；no shadow report | `PARTIAL` |
| unexpected pre-Gate ordinary exception | no Manifest；V1 continues | `FAILED` |
| unexpected post-Gate Renderer exception | Manifest preserved；V1 continues | `PARTIAL` |

### 13.2 External faithfulness evaluator

Evaluator保持compiled graph、Parent State、Manifest、runtime Gate与`GlobalSynthesisStatus`之外。输入V2 Shadow Report +
bounded Manifest/display projection，检查unsupported proposition、scope expansion、qualifier loss、conflict omission、Claim
misrepresentation与Citation/Claim placement mismatch。Provider/timeout/schema failure MAY按Eval harness policy retry；valid
semantic FAIL不得retry-to-pass，也不触发report repair、Claim rewrite或re-ground。

---

## 14. Implementation Workstreams

| Workstream | Deliverable |
|---|---|
| W0 | Run status/cursor、entry identity、Overwrite reset、clarification resume、finalization |
| W1 | stable code models、internal DTOs、tagged receipts、limits/outcome |
| W2 | task-qualified resolver、Generator/Judge/Renderer projections、metadata adapter、whole-unit admission |
| W3 | Model A call、Claim validation、identity、one-time admission |
| W4 | safe per-Claim Model B worker、Host retry、Grounding receipts/materialization |
| W5 | Citation、Manifest Gate、replay、metrics |
| W6 | issues/sticky degradation、display keys、P06 merge、labels/bibliography |
| W7 | Model C free-form sections、Evidence projection、binding validator、marker/injection |
| W8 | Parent node、State update、V1 fallback、Run finalization |
| W9 | graph-external evaluator integration |
| W10 | deterministic suite、checkpoint lifecycle、failure injection、controlled real-provider smoke |

Dependency：`W0/W1 → W2 → W3/W4 → W5/W6 → W7 → W8 → W10`；W9可在后半段独立进行，但必须在S5
acceptance前完成。

---

## 15. Validation Classes

TASKS/CHECKLIST决定具体test文件和命令。实现至少验证：

### 15.1 Lifecycle and identity

- initial bootstrap、clarification resume、same-run continuation；
- initialized lifecycle下`fresh_delta < 0`、`== 0`、`== 1`、`> 1`全部有deterministic结果；
- `ACTIVE + any fresh input`返回conflict且不改变cursor/Run/provenance；
- `AWAITING_CLARIFICATION`只允许exactly one fresh HumanMessage恢复same Run；
- `FINALIZED + fresh_delta == 0` replay；只有`fresh_delta == 1`启动new Run；
- initial bootstrap拒绝zero/multiple ambiguous unconsumed HumanMessages；
- 所有multiplicity/integrity conflict均不推进cursor、不reset、不修改structured provenance；
- `Overwrite` reset、messages preserve、Artifact namespace isolation；
- stable same-ID retry不产生额外occurrence；无ID/不同ID重复文本按新occurrence处理；
- same-ID divergent payload明确属于caller violation，测试不得声称S5自动检测；
- illegal cursor regression/inconsistent status受控失败。

### 15.2 Projection, identity and bounds

- task-qualified resolver、no sibling scan、whole-unit admission；
- sibling Claim rejection不改变其他Claim ID；exact duplicate only；
- optional metadata never inferred；full serialized role context bounded。
- `ClaimDraftBatch` item-count与aggregate serialized-payload bounds；
- provider `max_tokens`不能替代Host-side structure/count/reference/payload validation；
- aggregate output overflow不得silent truncate。

### 15.3 Grounding and retry

- frozen verdict/status mapping；strict assessed/unassessed receipts；
- one Claim ordinary exception不影响siblings；cancellation传播；
- completion timing不改变order；actual model requests不超过`1 + R`。
- `ClaimGroundingDraft` serialized-payload overflow只影响current Claim并按P04 retry/UNASSESSED policy处理。

### 15.4 Publication, issues and replay

- exact Citation required set、receipt mismatch rejection、Gate validate-not-repair、atomic publication；
- replay short-circuit、Renderer failure不触发repair；
- Issue first-write-wins、payload conflict issue、ledger full后degradation sticky。

### 15.5 Display and Renderer

- tagged key全部group/non-group cases、exact stored URL equality、no cross-run grouping；
- P06 per-field first validated non-empty merge与contributing Source audit retention；
- Model C自由section title/order；paragraph Claim binding与eligible coverage；
- section title independent hard bound与`ShadowReportDraft` aggregate serialized-payload bound；
- Evidence projection不含non-material Evidence，role/Citation authority不可被Model C修改；
- conflict marker与supporting/contradicting labels；zero-eligible skip Model C。

External evaluator继续覆盖unsupported proposition、scope expansion、qualifier loss、conflict omission、Claim
misrepresentation与Citation/Claim placement mismatch；valid FAIL不得retry-to-pass。

---

## 16. Explicit Non-goals

继承SPEC全部non-goals，并明确不实现：

- active Run abandonment API；
- `ACTIVE` Run mid-run user steering；
- batched fresh HumanMessage interpretation、conversation-history import semantics或把多个new HumanMessages自动merge进一个Run；
- message fingerprint/request-id subsystem或same-ID divergent payload repair；
- HTTP request/stream durable background execution、token reconnect或stage-level durable checkpoint；
- Claim repair、re-ground或evaluator-to-report repair loop；
- global Source registry、cross-run Source/Evidence reuse/dedup；
- Model C Citation/Grounding authority；
- Host-fixed section catalog；
- `Send`、parallel V1/V2、queue/background worker或deployment redesign。

---

## 17. Freeze Gate

PLAN Freeze确认：

1. P01–P10均只有一套current implementation answer；
2. entry message identity contract、cursor与Run status职责分离；initialized lifecycle每次entry最多消费一个new logical HumanMessage；
3. `ACTIVE` Run input stability与`fresh_delta` multiplicity semantics唯一；
4. 不存在`FINALIZED → every invoke starts new Run`旧映射；
5. structured model-output aggregate bounds完整；provider `max_tokens`不替代Host structural/payload validation；
6. 不存在generic Grounding receipt、nested logical retry或Issue divergent payload reducer throw；
7. P06 metadata merge与tagged display key deterministic；
8. Renderer不再使用Host-fixed section catalog，且bounded Evidence visibility不转移Citation authority；
9. replay / repair / regenerate分离，metrics exposure唯一；
10. stable Contract shape不在PLAN复制，test file/command detail下沉TASKS/CHECKLIST；
11. package dependency不形成god module；
12. D14 / S5-R15 / Contracts §3.14 Renderer semantics一致；
13. `git diff --check`与authority/stale-reference scan通过。

通过后：

```text
P2-S5 PLAN
→ FINAL FROZEN

P2_S5_TASKS.md
→ AUTHORIZED TO DRAFT / REVIEW / FREEZE

P2_S5_CHECKLIST.md
→ AUTHORIZED TO DRAFT / REVIEW / FREEZE

Coding
→ STILL BLOCKED UNTIL TASKS + CHECKLIST + PRE-IMPLEMENTATION REVIEW COMPLETE
```
