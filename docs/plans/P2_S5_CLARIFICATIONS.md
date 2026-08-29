# P2-S5 — Clarifications and Decision Log

## 0. 文档目的与状态

`P2_S5_CLARIFICATIONS.md` is the authoritative decision-provenance log for P2-S5. It records alternatives, Human
Resolution, rationale, supersession, and promotion history, but does not independently define normative runtime
semantics.

本文不是第二份 SPEC；normative S5 requirements 已提升到 `EVIDENCEFLOW_CONTRACTS_V1.md` 与
`P2_S5_SPEC.md`。本轮 B01 canonical promotion、S5-D19 Research Run lifecycle、S5-D20 lifecycle conflict atomicity
与 CB01–CB06 contract surface audit
均已完成对应 promotion；这些记录解释语义如何形成，不在 promotion 之外独立定义 runtime behavior。

Decision lifecycle：

```text
question
→ alternatives
→ Human Resolution
→ RESOLVED
→ canonical promotion
→ PROMOTED
```

当前状态：

```text
P2-S5
CONTRACT_BOUNDARY_DECISIONS_RESOLVED
D00_D20_AND_CB01_CB06_PROMOTED
D14_LATEST_RENDERER_RESOLUTION_PROMOTED
PLAN_AUDITED_DRAFT_READY_FOR_FREEZE_REVIEW
```

### 0.1 Document Responsibility Model

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

Authoritative decision provenance 与 normative semantic authority 是不同职责。Historical wording remains decision
provenance only；current runtime semantics 以 Contracts 与 SPEC 中已提升的内容为准。

若后续实现发现新的 contract、topology、State、failure、migration 或 acceptance ambiguity，必须新增或重新打开
相应 decision，完成 Human Resolution 与 canonical promotion 后才能继续受影响的任务。

### 0.2 Decision Index

| Decision | Topic | Final status |
|---|---|---|
| S5-D00 | Global Reference Scope | **RESOLVED / PROMOTED** |
| S5-D01 | Claim-first vs Report-first | **RESOLVED / PROMOTED** |
| S5-D02 | Claim Contract / Identity / Lineage | **CORRECTED / RESOLVED / PROMOTED** |
| S5-D03 | Claim-centered Grounding Semantics | **REOPENED TWICE / CORRECTED / RESOLVED / PROMOTED** |
| S5-D04 | Citation Semantics | **REOPENED / CORRECTED / RESOLVED / PROMOTED** |
| S5-D05 | Global Synthesis Runtime Placement | **RESOLVED / PROMOTED** |
| S5-D06 | Grounding Status and Metrics | **REOPENED / CORRECTED / RESOLVED / PROMOTED** |
| S5-D07 | V1/V2 Shadow Output Boundary | **RESOLVED / PROMOTED** |
| S5-D08 | Claim Revision and Report Eligibility | **CORRECTED / RESOLVED / PROMOTED** |
| S5-D09 | Historical Relation Granularity | **MERGED / SUPERSEDED / PROMOTED** |
| S5-D10 | Global Synthesis Input Projection | **REOPENED / CORRECTED / RESOLVED / PROMOTED** |
| S5-D11 | Global Publication Gate | **RESOLVED / PROMOTED** |
| S5-D12 | Failure, Status and Shadow Fallback | **EXTENDED / RESOLVED / PROMOTED** |
| S5-D13 | Dedup Semantics | **EXTENDED / RESOLVED / PROMOTED** |
| S5-D14 | Renderer Faithfulness Boundary | **REOPENED / CORRECTED / RESOLVED / PROMOTED** |
| S5-D15 | Model Role and Retry Semantics | **RESOLVED / PROMOTED** |
| S5-D16 | Bounds and Admission | **EXTENDED / RESOLVED / PROMOTED** |
| S5-D17 | Deterministic Ordering and Display | **REOPENED / CORRECTED / RESOLVED / PROMOTED** |
| S5-D18 | Manifest Envelope, State and Versioning | **RESOLVED / PROMOTED** |
| S5-D19 | Research Run State Lifecycle and Provenance Isolation | **RESOLVED / PROMOTED** |
| S5-D20 | Lifecycle Conflict Atomicity Under LangGraph Input Admission | **RESOLVED / PROMOTED** |

Contract Boundary decisions：

| Decision | Topic | Final status |
|---|---|---|
| CB01 | `GlobalSynthesisIssue.stage` and diagnostic taxonomy authority | **RESOLVED / PROMOTED** |
| CB02 | Cross-task reader-facing grouping behavior authority | **RESOLVED / PROMOTED** |
| CB03 | `SourceDisplayKey` representation authority | **RESOLVED / PROMOTED** |
| CB04 | Display label ordering authority | **RESOLVED / PROMOTED** |
| CB05 | Bibliography presence vs formatting-style authority | **RESOLVED / PROMOTED** |
| CB06 | `artifact_ref` semantic identity vs encoding boundary | **RESOLVED / PROMOTED** |

---

## S5-D00 — Global Reference Scope

### Status

**RESOLVED / PROMOTED**

### Baseline

P2-S4 将 `ResearchTaskResult` 冻结为 self-contained task-level provenance aggregate。Source、Evidence 与
Finding 的 authoritative resolution scope 是单个 Result；系统没有 Parent-level Source/Evidence registry，
也不保证 bare IDs 在不同 Tasks 或 Runs 中全局唯一。

### Alternatives

1. 将 S4 bare IDs 升级为 global identity；
2. 新增 Parent sibling registry；
3. 保持 S4 identity semantics，使用 task-qualified composite address。

### Human Resolution

选择方案 3：

```python
class EvidenceRef:
    task_id: str
    evidence_id: str


class FindingRef:
    task_id: str
    finding_id: str
```

Resolver MUST 先用 `task_id` 找到唯一 `ResearchTaskResult`，再在该 Result 内解析 bare ID。Unknown、dangling、
ambiguous 或 out-of-allowlist refs MUST 被拒绝；不得扫描 sibling Results 猜测目标。

### Rationale and Impact

- 保持 S4 identity generation/canonicalization 不变；
- 不引入 global registry 或 cross-run persistence；
- 相同 bare ID 在不同 Tasks 中仍是不同地址；
- Citation 与 Grounding 始终保存完整 `EvidenceRef`。

### Deferred

- global Evidence identity；
- `(run_id, evidence_id)` durable address；
- cross-run registry/dedup。

### Canonical Promotion

Promoted to `EVIDENCEFLOW_CONTRACTS_V1.md` and `P2_S5_SPEC.md` S5-R03。

---

## S5-D01 — Claim-first vs Report-first

### Status

**RESOLVED / PROMOTED**

### Alternatives

#### Report-first

```text
Research results
→ free-form report
→ extract Claims
→ attach Evidence/Citation
```

风险是 post-hoc Claim drift、Citation drift 与 report text accidental authority。

#### Claim-first

```text
ResearchTaskResult[]
→ Claim synthesis
→ Claim-level Grounding
→ Citation
→ constrained rendering
```

### Human Resolution

采用 Claim-first。V2 report 是 validated Claims 的 derived artifact，Renderer 不得成为第二个 Claim
Generator。

### Canonical Promotion

Promoted to S5-R02。

---

## S5-D02 — Claim Contract / Identity / Lineage

### Status

**REOPENED / CORRECTED / RESOLVED / PROMOTED**

### Alternatives

1. Model 输出可直接成为 authoritative Claim；
2. `ClaimDraft != ClaimRecord`，Host validation 后物化 Claim；
3. 延迟到 Grounding 完成后一次性创建 Grounded Claim。

### Previous Human Resolution

选择方案 2。

Internal structured output：

```python
class ClaimDraft:
    text: str
    materiality: ClaimMateriality
    finding_refs: list[FindingRef]
    scope: str | None
    qualifiers: list[str]
```

Stable Domain record：

```python
class ClaimRecord:
    claim_id: str
    text: str
    materiality: ClaimMateriality
    finding_refs: list[FindingRef]
    scope: str | None
    qualifiers: list[str]
```

`ClaimDraft` SHALL NOT 包含 `candidate_evidence_refs` 或 Evidence Groups。Host 在 Model A 后验证 schema、
bounds、FindingRefs 与 visible allowlist，分配 Manifest-local `claim_id` 并立即物化 `ClaimRecord`。

### Latest Human Resolution — Complete Claim Proposition

此前文档容易把 `ClaimRecord.text` 单独理解为完整 Claim。本轮 Human Resolution 明确修正为：

```text
authoritative Claim proposition
= ClaimRecord.text
  + ClaimRecord.scope
  + ClaimRecord.qualifiers
```

`text + scope + qualifiers` jointly define the complete Claim proposition。`scope` 与 `qualifiers` 不是
presentation-only hints，而是 authoritative Claim semantics 的组成部分。Grounding Judge 必须评估完整
proposition；Renderer faithfulness evaluation 必须同时检查 text semantic meaning、scope preservation 与 qualifier
preservation。

Renderer MAY 在 derived Shadow Report 中 paraphrase complete Claim semantics，但不得 mutate/replace
`ClaimRecord`。Paraphrase 没有 Domain authority，并受 external faithfulness evaluation 约束。

### Identity

`claim_id`：

- Host-owned；
- owning Manifest 内唯一；
- run-local；
- 不解释为 cross-run global identity；
- exact canonical payload/encoding 进入 PLAN，但不得改变上述 scope。

### Lineage

`finding_refs` 表示 Claim semantic derivation lineage，不是 external Evidence authority：

```text
ClaimRecord → FindingRef → ResearchFinding
```

Grounding provenance 由 `ClaimGroundingRecord` 单独表达。

`finding_refs` MUST non-empty。正式 Claim authorization 只来自：

```text
ClaimRecord
→ FindingRef
→ ResearchFinding
```

`ResearchTaskResult.summary`、Result-level `limitations` 与 Result-level `conflicts` 只提供 contextual hints。Model A
MAY 看见并使用这些内容理解上下文，但 Host MUST NOT 将它们当作 Claim-authorizing records，也不得接受
`finding_refs=[]`。

FindingRef Host validation 只证明 declared lineage 在结构上可解析、属于 allowlist；它不能确定性证明 Claim
在语义上一定由该 Finding 推导。S5 不新增 Claim↔Finding semantic Judge。最终 reportability 仍由完整 Claim
proposition 与从 retained Findings 派生的 Evidence universe 交给 Grounding Judge 判断。

### Scope / Qualifiers / Materiality

```python
class ClaimMateriality(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

- `scope`：population、condition、applicability boundary；
- `qualifiers`：报告表达必须保留的比较条件、时间、效应变化与限制；
- `materiality`：Claim 对用户核心问题的重要程度，仅允许 `HIGH/MEDIUM/LOW`。

Materiality SHALL NOT 表示 Evidence quality、Grounding confidence、Citation count、correctness 或 probability。

### Prohibited Duplication

`ClaimRecord` SHALL NOT 保存 Evidence refs、Grounding status、Citation IDs、`report_eligible` 或
`revision_required`。

### Claim ID Stability and Exact Replay

Exact `claim_id` encoding 仍属于 PLAN，但必须满足：reject/omit 一个 sibling ClaimDraft 不得改变另一个 otherwise
identical admitted ClaimDraft 的 deterministic identity。推荐 PLAN 使用 original Generator ordinal + canonical
semantic payload hash；不得只使用 survivor ordinal。

“exact duplicate ClaimDraft”只表示 canonical serialization identical replay；至少比较 `text`、`scope`、
`qualifiers`、`finding_refs` 与 `materiality`。任一字段不同都不是 exact duplicate。String similarity、embedding
similarity 或 semantic fuzzy matching 不得成为 Host Claim dedup authority。

### Canonical Promotion

Promoted to S5-R04, S5-R08, S5-R15 and S5-R16。

---

## S5-D03 — Claim-centered Grounding Semantics

### Status

**REOPENED TWICE / CORRECTED / RESOLVED / PROMOTED**

### Decision History

#### Historical stage 1 — Relation-centric design

```text
EvidenceGroupDraft
→ ClaimEvidenceRelation
→ GroundingAssessment
```

Human review 发现 group identity、relation identity、ordering、retry、bounds 与 Citation binding 的主要下游
需求由该架构自身产生。当前 S5 consumer 不需要保存多个独立 proof sets，因此该方案被重新打开并替换。

#### Historical stage 2 — Claim-centered record with binary sufficiency

第一次简化保留 `ClaimGroundingRecord`，并让 Judge 输出 `SupportSufficiency`：`SUFFICIENT/INSUFFICIENT`；Host
再根据 contradiction set 是否为空机械映射五态。

该方案再次被 Human Resolution supersede。`CONTRADICTED` 是强 semantic verdict；存在一条 material
contradicting Evidence 不能确定性推出 overall contradiction。Judge 已看到完整 admitted Evidence universe，
overall verdict 应属于 Judge semantic role，Host 不应以 set presence/count heuristic 代替语义判断。

#### Latest stage 3 — Claim-centered record with overall semantic verdict

最终设计保留 Claim-centered `ClaimGroundingRecord`，将 binary sufficiency 替换为
`ClaimEvidenceVerdict + material supporting/contradicting subsets`。

### Alternatives

1. 保留 authoritative Evidence Groups / Relations；
2. 使用 Claim-level Grounding record；
3. 将 Grounding fields 合并进 ClaimRecord。

### Latest Human Resolution

选择方案 2，删除 authoritative Evidence Group、Relation、`relation_id` 与独立 Assessment 层。

Internal Judge output：

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

Stable Domain record：

```python
class ClaimGroundingRecord:
    claim_id: str
    evaluated_evidence_refs: list[EvidenceRef]
    supporting_evidence_refs: list[EvidenceRef]
    contradicting_evidence_refs: list[EvidenceRef]
    status: GroundingStatus
    reason: str | None
```

`ClaimGroundingRecord` 与 Claim 一对一，以 `claim_id` 作为 binding，不增加 `grounding_id`。

### Evidence Universe

Host 从 validated `ClaimRecord.finding_refs` 解析各 `ResearchFinding.evidence_ids`，task-qualify 后执行 ordered
union 与 exact same-ref first-occurrence dedup。Model A 不拥有 Candidate Evidence selection。

`evaluated_evidence_refs` 是一次 valid Judge assessment 的 exact Host-owned admitted input list，不由模型回显
决定。Model B universe 必须从 retained `ClaimRecord.finding_refs → ResearchFinding.evidence_ids` 重新派生，并
应用独立 Judge admission budget；它与 Model A visible Evidence context 不是同一个 authority。

### Judge Semantics

Judge 面对完整 authoritative Claim proposition（`text + scope + qualifiers`）与整个 admitted Evidence universe，
返回：

- overall `ClaimEvidenceVerdict`；
- material supporting Evidence subset；
- material contradicting Evidence subset；
- bounded explanation。

`supporting_evidence_refs` 表示对 Claim 提供 material positive support，并 materially participates in the Judge's
overall grounding assessment 的 Evidence。单条 Evidence 不需要独立建立 sufficient support；以下结果合法：

```text
verdict = INSUFFICIENT
supporting_evidence_refs = [E1, E2]
```

它表示 E1/E2 提供 material positive support，但总体 Evidence 仍不足以得到 `SUPPORTED` verdict。

`contradicting_evidence_refs` 表示对 Claim 提供 material negative evidence，并且足以参与 overall assessment 或
必须作为 meaningful conflict 披露的 Evidence。它既不要求每条 Evidence 单独推翻 Claim，也不接纳任何轻微、
不影响判断的反对内容。

Supporting 与 contradicting lists MUST：

- 都是 evaluated set 的 subsets；
- 内部 unique；
- 彼此 disjoint；
- 保持 Host canonical order。

额外 structural invariants：

- `SUPPORTED` verdict → supporting list MUST non-empty；
- `CONTRADICTED` verdict → contradicting list MUST non-empty；
- `INSUFFICIENT` verdict → 两个 lists 均 MAY empty 或 non-empty。

Evaluated 但未进入两个 material sets 的 Evidence 由集合差集表达，不新增 neutral/insufficient fields。

### Authority Boundary

Model B owns overall semantic verdict。Host owns reference/set validation 与 deterministic final status
materialization。Host MUST NOT 使用 Evidence count、Source count、presence/absence heuristic 或 string matching
替代整体 semantic judgment。

`ClaimGroundingRecord.reason` 是 bounded、sanitized Judge semantic explanation，只服务 audit/debug/evaluation。
它不是 Evidence、Claim 或 Renderer factual authority；Citation 不为 reason 生成 provenance，Renderer 不消费
reason。Publication Gate 只检查 reason requiredness、type、bounds 与 sanitization，不验证其 semantic truth。

### Evidence Quality Boundary

Judge SHALL 在 optional validated Source context 可见时定性考虑 Source authority、directness、methodological
limitations、applicability、recency 与 consistency。`supporting_evidence_refs` / `contradicting_evidence_refs` 只保存
足以 materially participate in overall assessment or conflict disclosure 的 Evidence。

S5 SHALL NOT 新增 calibrated Evidence/Source quality score、硬编码 Evidence hierarchy 或 source classifier。
无法可靠判断 Source quality 时，Judge 不得假设高质量，并 MAY 返回 `INSUFFICIENT`。

### Lost Information

方案明确接受丢失多个独立 sufficient proof groups 的信息。该信息当前不改变 report eligibility、Citation、
Source resolution 或 Grounding coverage；未来出现 argument-mining/meta-analysis consumer 时再演进 Contract。

### Canonical Promotion

Promoted to S5-R05–S5-R07, S5-R11, S5-R12 and S5-R15。

---

## S5-D04 — Citation Semantics

### Status

**REOPENED / CORRECTED / RESOLVED / PROMOTED**

### Human Resolution

Citation 是 reader-facing provenance mapping，不是 semantic Grounding relation。

```python
class Citation:
    citation_id: str
    claim_id: str
    evidence_ref: EvidenceRef
```

### Identity and Authority

- `citation_id` 由 Host 根据 `(claim_id, EvidenceRef)` 确定性生成；
- 每个 Claim/Evidence pair 只有一个 Citation record；
- URL、title、Source metadata 与 display label 不进入 Citation authority；
- Citation 通过 EvidenceRef 确定性解析到 Evidence → Source → Artifact；
- `display_label` 由 Host 派生，不存为 canonical identity。

### Required Citation Set

```text
SUPPORTED
→ supporting_evidence_refs

SUPPORTED_WITH_CONFLICT
→ supporting_evidence_refs ∪ contradicting_evidence_refs

INSUFFICIENT / CONTRADICTED / UNASSESSED
→ empty; Claim is not report-eligible
```

每个 report-eligible Claim 的 actual Citation EvidenceRefs MUST 与 required set 严格相等。Missing、duplicate 或
extra Citation 均使 Manifest Gate 失败。

### Reader-facing Display Decision History

上一轮 Resolution 只允许同一 canonical `(task_id, source_id)` 内的 EvidenceRefs 共享 display label，并将
cross-task same-URL/source display grouping 保留为 follow-up。该 presentation decision 现已由最新 Human
Resolution 重新打开并替换；canonical identity 禁止合并的规则从未改变。

> **CB02–CB05 authority-placement note:** 本节保留 D04 的 historical design provenance。当前 observable grouping
> behavior 已提升到 S5-R09；`SourceDisplayKey` representation、exact label algorithm 与 bibliography style 已由
> CB03–CB05 下沉到 PLAN。下文 historical wording 中的 “validated canonical URL” 在 current behavior 中只表示
> resolved `SourceRecord.metadata["url"]` 的 validated stored value，并采用 exact stored string equality；S5 不新增
> 或调用自己的 URL canonicalizer。

### Historical Human Resolution — Reader-facing Display

**Authority placement superseded by CB02–CB05；grouping behavior retained in S5-R09。**

Canonical provenance identity 与 reader-facing display grouping MUST 保持分离。Canonical Citation 仍是
`Claim × EvidenceRef(task_id, evidence_id)`；任何 display grouping 都不得合并跨 Task 的 canonical Source、Evidence
或 Citation identity。

#### Same canonical Source

多个 Citations 若解析到同一 canonical SourceRecord `(task_id, source_id)` 中不同的 EvidenceRefs，SHOULD 共享一个
reader-facing Source label。Canonical Citations 仍逐 `(claim_id, EvidenceRef)` 保留。

#### Cross-task display-only Source grouping

跨 Task canonical identity MUST NOT merge。但在同一个 EvidenceFlow Run 内，若多个 resolved Sources 同时满足：

1. validated canonical URL 相同；
2. owning run-scoped Artifact namespace 中的 `artifact_ref` 相同；

则 reader-facing display MAY 将其分组为一个 Source entry。Conceptual presentation key：

```text
SourceDisplayKey
=
(canonical_url, artifact_ref)

scope = one EvidenceFlow Run
```

完整可解析 Artifact address 仍是 `(artifact_run_id, artifact_ref)`。`artifact_ref` 不是 filesystem/storage path，而是
由 persisted normalized Artifact text 派生的 content-addressed reference。当前语义等价于：

```text
artifact_ref
=
"artifact:sha256:"
+
sha256(persisted_normalized_source_text)
```

实际 storage implementation/path 不进入 P2-S5 Domain semantics。

“Same persisted Artifact content”严格表示同一 owning `artifact_run_id` 中 `artifact_ref` 相同，即 existing Artifact
normalization/content-addressing semantics 下 persisted normalized content byte-equivalent。它不得表述为 original
provider/webpage bytes globally identical，因为 identity 在 configured truncation 与 normalization 等既有 content
preparation 后计算。

Frozen grouping cases：

- same canonical URL + same `artifact_ref` within one Run → MAY group；
- same canonical URL + different `artifact_ref` → MUST NOT group；
- different canonical URL + same `artifact_ref` → MUST NOT group；
- canonical URL unavailable → MUST NOT cross-task group；
- same `artifact_ref` string across different Runs → MUST NOT infer shared Artifact identity。

该 grouping strictly 是 derived presentation view，MUST NOT 修改或合并 Citation、EvidenceRef、SourceRecord、
`source_id`、`evidence_id`、`artifact_ref`、`task_id`、ResearchTaskResult 或任何 provenance identity，也不得引入 global
Source/Evidence identity、persistent Source registry 或 cross-run dedup。

一个 reader-facing label MAY 回查多个 canonical Citations、EvidenceRefs 与 task-qualified SourceRecords。Click-through
/ audit view MAY 展示为该 grouped Source entry 提供内容的全部 EvidenceRefs。

#### Display labels and bibliography

`display_label` 仍是 derived presentation field，不存为 Citation authority。Host SHALL 从 ordered
`SourceDisplayKey` projection 派生 labels；同一 canonical Source 没有 canonical URL 时仍按其 exact
`(task_id, source_id)` display entry 处理。

V2 bibliography SHOULD 使用 best-effort GB/T 7714-style rendering，但只可使用 validated available metadata；不得
推断缺失 author/year/publisher，metadata 不完整时 graceful degradation。Bibliography formatting 是 presentation/
PLAN-level policy，不是 Citation identity、Source identity 或 Grounding authority。

### Canonical Promotion

Promoted to S5-R09。

---

## S5-D05 — Global Synthesis Runtime Placement

### Status

**RESOLVED / PROMOTED**

### Alternatives

1. 将 S5 全部逻辑嵌入 legacy `final_report_generation`；
2. 在 Parent graph 增加一个 `global_synthesis` stage；
3. 为 Generator/Judge/Citation 分别增加 orchestration Agents。

### Human Resolution

选择方案 2：

```text
research_supervisor
→ global_synthesis
→ final_report_generation     # legacy V1 continues
→ END
```

Generator、Judge、Host materialization、Gate 与 Shadow Renderer 是 `global_synthesis` 内部 stages/helpers，不
拆成新的 graph Agents，不修改 Supervisor–Researcher Tool Loop。

Source audit 已确认 Parent `AgentState` 持有 structured `research_results`，当前 graph 存在
`research_supervisor → final_report_generation` edge，因此插入单一 Parent node 可行。

### Latest Human Resolution — Shadow Isolation

上述顺序继续冻结。P2-S5 shadow 保证 output isolation 与 failure isolation，但不保证 latency isolation。Model
A/B/C 会顺序增加 legacy V1 的 end-to-end latency；这是 S5 accepted tradeoff，不是 runtime defect。不得为 latency
isolation 引入 fan-out、parallel V1/V2 branch、Send、queue 或 background job。

### Canonical Promotion

Promoted to S5-R13 and S5-R18。

---

## S5-D06 — Grounding Status and Metrics

### Status

**REOPENED / CORRECTED / RESOLVED / PROMOTED**

### GroundingStatus

```python
class GroundingStatus(str, Enum):
    SUPPORTED = "supported"
    SUPPORTED_WITH_CONFLICT = "supported_with_conflict"
    INSUFFICIENT = "insufficient"
    CONTRADICTED = "contradicted"
    UNASSESSED = "unassessed"
```

### Host Mapping

此前 `INSUFFICIENT + contradiction → CONTRADICTED` 的 presence heuristic 已被 supersede。最新 frozen mapping：

| Valid Judge verdict | Contradicting set | Host-derived status |
|---|---:|---|
| `SUPPORTED` | empty | `SUPPORTED` |
| `SUPPORTED` | non-empty | `SUPPORTED_WITH_CONFLICT` |
| `INSUFFICIENT` | any valid set shape | `INSUFFICIENT` |
| `CONTRADICTED` | non-empty required | `CONTRADICTED` |
| unavailable | N/A | `UNASSESSED` |

Model B owns overall `ClaimEvidenceVerdict`；Host owns deterministic final status materialization。Host 不得根据
supporting/contradicting list presence、Evidence count、Source count 或 string matching 改写 verdict。

`SUPPORTED` verdict requires non-empty supporting set；`CONTRADICTED` verdict requires non-empty contradicting set；
`INSUFFICIENT` 允许两个 material sets 为空或非空。即使 `INSUFFICIENT` draft 同时包含 material supporting 与
contradicting Evidence，final status 仍为 `INSUFFICIENT`。

### UNASSESSED Record

`UNASSESSED` record 使用 empty Evidence lists 与 `reason=None`。Attempted Evidence、provider error、invalid output
等进入 process issues，不伪装成 valid evaluated universe。

### Metrics

Required shadow metrics：

```text
supported_claim_count
supported_with_conflict_claim_count
insufficient_claim_count
contradicted_claim_count
unassessed_claim_count
assessed_claim_coverage
report_eligible_claim_coverage
material_report_eligible_claim_coverage
```

```text
assessed_claim_coverage
= count(status != UNASSESSED) / count(all Claims)

report_eligible_claim_coverage
= count(SUPPORTED + SUPPORTED_WITH_CONFLICT) / count(all Claims)

material_report_eligible_claim_coverage
= count(report-eligible AND materiality=HIGH)
  / count(materiality=HIGH)
```

任一 coverage denominator 为零时 value 必须为 `None`，不是 0、1 或 NaN。Metrics 全部 Host-derived、recomputable、
non-authoritative，不进入 `GroundingManifest`，S5 不设置 production threshold。

此前 citation coverage metrics 已删除：Publication Gate 已强制 actual Citation set exact equal required set，因此
valid Manifest 上该指标只会退化为 1.0 或 None，不提供 evaluation information。Citation completeness Gate invariant
继续保留。

### Canonical Promotion

Promoted to S5-R07 and S5-R17。

---

## S5-D07 — V1/V2 Shadow Output Boundary

### Status

**RESOLVED / PROMOTED**

### Human Resolution

```text
V1 Report
= legacy official/compatibility output

GroundingManifest
= authoritative V2 structured shadow output

V2 Shadow Report
= derived evaluation artifact
```

S5 不以 V2 替换 V1。Manifest 与 Shadow Report 使用独立 Parent channels；Renderer failure 不擦除 Manifest，
V2 failure 不阻止 legacy V1 path。

若 published Manifest 中没有 report-eligible Claims，Host 不调用 Model C，而是生成 deterministic
no-grounded-claim shadow output，不创建 fake Claim/Citation。若所有 Claims 都经过 valid semantic assessment、
结果均不 eligible 且没有 degradation，Global Synthesis MAY 为 `SUCCESS`；因 Judge failure 全部 `UNASSESSED`
则必须为 `PARTIAL`。

### Canonical Promotion

Promoted to S5-R13, S5-R15 and S5-R18。

---

## S5-D08 — Claim Revision and Report Eligibility

### Status

**CORRECTED / RESOLVED / PROMOTED**

### Human Resolution

S5 不实现 iterative Claim repair。Canonical Claim proposition（`text + scope + qualifiers`）在 Grounding 后保持
不变；Renderer 可以在 non-authoritative report 中 paraphrase，但不能修改 Domain record。

| Status | `revision_required` | `report_eligible` |
|---|---:|---:|
| `SUPPORTED` | `False` | `True` |
| `SUPPORTED_WITH_CONFLICT` | `True` | `True` |
| `INSUFFICIENT` | `True` | `False` |
| `CONTRADICTED` | `True` | `False` |
| `UNASSESSED` | `True` | `False` |

上述 fields 均由 status 派生，不存入 Claim/Grounding canonical records。

`SUPPORTED_WITH_CONFLICT` 必须进入报告。Primary occurrence 只承担以下 runtime hard requirements：

- 明确披露存在 material contradictory Evidence；
- 包含覆盖 material supporting Evidence 的 display citations；
- 包含覆盖 material contradicting Evidence 的 display citations。

Runtime 不要求 Model C 精确表达哪一侧权重更大，也不把 nuanced uncertainty narrative 作为 hard invariant；这些
属于 report quality、external faithfulness evaluation 与 later calibration。

### Canonical Promotion

Promoted to S5-R08 and S5-R15。

---

## S5-D09 — Historical Relation Granularity

### Status

**MERGED / SUPERSEDED / PROMOTED**

早期 D09 已合并到 D03；D03 后续又被 Claim-centered decision 替换。S5 不存在独立 relation-granularity
implementation path。多个独立 proof sets 明确 deferred。

---

## S5-D10 — Global Synthesis Input Projection

### Status

**REOPENED / CORRECTED / RESOLVED / PROMOTED**

### Authoritative Input

```text
MedicalResearchBrief
+ ResearchTaskResult[]
```

Authoritative Data Plane 与 model-facing bounded projection 必须分离。

### Model A — Claim Generator Projection

Generator 接收：

- MedicalResearchBrief；
- task identity/status；
- bounded task summary；
- Findings（text、FindingRef、limitations、conflicts）；
- Findings 引用的 bounded exact Evidence excerpts；
- available 时有助于 interpretation 的 optional compact Source metadata。

Generator 不接收 raw notes、ToolMessages、provider snippets、model reasoning、full Artifact 或 unbounded Result
serialization。

Evidence 对 Model A 只有 semantic-context 角色：帮助判断 Finding 是否值得综合、避免 overgeneralization、形成
scope/qualifiers、理解 Findings 的限制与冲突。它不是 output reference authority。Model A 只输出 Claim text、
scope、qualifiers、materiality 与 FindingRefs；`ClaimDraft` 不得包含 candidate Evidence refs、Evidence Groups、
supporting refs 或 contradicting refs。

Result-level summary/limitations/conflicts 同样只提供 contextual hints，不 authorizes Claim。Model A 不能生成没有
至少一个 valid FindingRef 的 Claim。

`ResearchTaskResult.status` 不单独决定 records admission。`PARTIAL/FAILED` Result 中已经发布且可解析的 valid
records MAY 使用，但 projection 必须同时暴露 status、limitations、conflicts 与 bounded error context；不得把
execution status 伪装为 Evidence quality。

### Model B — Grounding Evidence View

Internal projection：

```python
class GroundingEvidenceView:
    evidence_ref: EvidenceRef
    excerpt: str
    source_title: str | None
    source_url: str | None
    retrieval_provider: str | None
    publisher: str | None
    authors: str | None
    published_at: str | None
    document_type: str | None
```

该 shape 是 internal model projection，不是 stable Domain record；PLAN MAY 使用更精简的 serialization。Model B
semantic required input 只有 `EvidenceRef + exact excerpt`。Locator 与 `source_id` 继续存在于 authoritative Host
provenance path，但不要求进入 Model B context；Host resolver 语义不变。

所有 Source context fields 都是 optional、best-effort、never inferred，只能来自 validated、whitelisted
`SourceRecord.metadata`。缺失 metadata 不得阻止 otherwise valid Evidence 进入 Judge。`artifact_ref`、full Artifact
与 raw provider payload 不进入 Judge Context。

当前 S4 source audit：title 通常存在但可能只是 `Untitled source` fallback；URL optional；provider 当前通常为
`tavily` 但不是 S4 required contract；canonical writer 当前不提供 publisher、authors、published_at 或
document_type。S5 不得假设这些 keys 稳定存在，也不增加 required `source_type` classifier。

S5 MAY 对 Source materialization 时 provider 已提供的 fields 做 backward-compatible best-effort metadata enrichment，
但 correctness 不得依赖 enrichment。Enrichment 不得修改 Source/Evidence identity、Artifact semantics、mandatory
upstream schema，也不得 fabricate missing metadata。本轮只记录后续 implementation requirement，不修改 S4 code。

### Renderer Projection

该段记录 D10 resolution 时的 Renderer projection；D14 Latest Human Resolution 已扩展其 current authority。当前 Model C
只接收 MedicalResearchBrief 与 bounded report-eligible Claim packages：Claim text、scope、qualifiers、presentation 所需
materiality、GroundingStatus、已经 materialize 的 bounded material supporting / contradicting Evidence projection、
optional validated Source metadata，以及 Host-derived `conflict_present` 或等价 deterministic flag。Citation identity、
required Citation set、display labels 与 numbering 继续由 Host 拥有。

`ClaimGroundingRecord.reason` MUST NOT 进入 Model C input；它不是 Renderer factual authority。

### Admission

- Host 建立每个 model role 的 exact visible allowlist；
- model output refs 必须同时可解析且属于该 allowlist；
- Findings/Evidence 以完整 units 接纳，不切片 exact excerpts；
- capacity omission 生成 bounded degrading issue，不解释为 semantic insufficiency；
- upstream structured Data Plane 不因 model-context admission 被删除。

Generator projection 按 Parent `research_results` ledger order 遍历 Tasks，应用 per-task Finding cap 后按 Result
Finding order 接纳；每个 Finding 只投影其 own `evidence_ids` 指向的 Evidence，并按 Finding Evidence order
接纳。Non-authoritative summary MAY bounded truncate 并标记，Finding/Evidence authoritative units 不切片；
Generator Context admission 不使用尚未生成的 Claim materiality。

Model A visible Evidence context 与 Model B admitted Evidence universe 不是同一个 authority。Per-Claim Judge
universe 必须从 surviving `ClaimRecord.finding_refs → ResearchFinding.evidence_ids` 重新确定性派生，再应用独立
Judge budget。Judge admission 以 derived Evidence canonical order 接纳完整 Evidence views；达到 bound 后保留 legal
prefix，省略 refs 写 `EVIDENCE_ADMISSION` degrading issue。`evaluated_evidence_refs` 只记录实际 admitted input，
不得把 omitted Evidence 伪装成 evaluated。S5 采用 generous configurable budget 以尽量避免该 shadow-mode
degradation，不增加 reranking 或 quality-score admission。

### Canonical Promotion

Promoted to S5-R05, S5-R10, S5-R14 and S5-R15。

---

## S5-D11 — Global Publication Gate

### Status

**RESOLVED / PROMOTED**

### Human Resolution

建立一个 Host-controlled、atomic、validate-not-repair Gate。Gate 只验证 structural integrity，不判断医学
semantic correctness。

### Required Invariants

#### Claim

- IDs unique；
- FindingRefs resolve、unique、in allowlist；
- fields 与 bounds 合法；
- canonical order 合法。

#### Grounding

- 每个 Claim 恰好一个 GroundingRecord；
- `claim_id` resolves；
- evaluated/supporting/contradicting refs resolve；
- subset、unique、disjoint invariants 成立；
- assessed states 的 evaluated set non-empty；
- `SUPPORTED`-derived result 的 supporting list non-empty；
- `CONTRADICTED`-derived result 的 contradicting list non-empty；
- final status 与 validated `ClaimEvidenceVerdict` mapping 一致，不从 set presence 猜测 verdict；
- reason requiredness/type/bounds/sanitization 正确；Gate 不验证 reason factual truth。

#### Citation

- IDs unique/deterministic；
- Claim/EvidenceRefs resolve；
- 每个 required pair 恰好一个 Citation；
- missing、duplicate、extra Citations 被拒绝；
- order 合法。

#### Manifest

- contract version 正确；
- no dangling/ambiguous refs；
- collections/order/payload bounds 合法；
- no duplicated canonical IDs。

Gate failure SHALL 发布 no Manifest。Gate 不删除坏 record 后继续发布，也不通过猜测修复 refs。

### Renderer Boundary

Renderer 位于 Manifest Gate 后，使用独立 structural validator。Renderer failure 不回滚 valid Manifest。

### Canonical Promotion

Promoted to S5-R12。

---

## S5-D12 — Failure, Status and Shadow Fallback

### Status

**EXTENDED / RESOLVED / PROMOTED**

### Global Status

```python
class GlobalSynthesisStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
```

- `SUCCESS`：Manifest 发布、Renderer 或 zero-eligible Host output 成功，且 monotonic degradation accumulator 为
  `False`；
- `PARTIAL`：Manifest 发布，但 monotonic degradation accumulator 为 `True`，或 Renderer failure 等事件已观察到
  degradation；
- `FAILED`：没有 Manifest 发布。

Empty Manifest structurally legal；只有在 degradation accumulator 为 `False` 且 pipeline 正常完成时才可为
`SUCCESS`。

### Issue Contract

> **CB01 authority-placement note:** 下列 `GlobalSynthesisStage` enum 是 D12 当时采用的 historical runtime
> taxonomy，已被 CB01 supersede，不再是 stable Contracts closed vocabulary。Current stable
> `GlobalSynthesisIssue.stage` 是 open、non-empty、machine-readable、sanitized、runtime-bounded string；exact enum
> 只约束当前 Host-produced values。

```python
class GlobalSynthesisIssue:
    issue_id: str
    stage: GlobalSynthesisStage
    code: str
    severity: GlobalSynthesisSeverity
    message: str
    claim_id: str | None
    task_id: str | None
    evidence_ref: EvidenceRef | None
    attempt: int | None
    degrades_global_status: bool
```

Historical runtime classification（exact vocabulary superseded by CB01）：

```python
class GlobalSynthesisStage(str, Enum):
    INPUT_PROJECTION = "input_projection"
    CLAIM_GENERATION = "claim_generation"
    CLAIM_MATERIALIZATION = "claim_materialization"
    EVIDENCE_ADMISSION = "evidence_admission"
    GROUNDING_JUDGE = "grounding_judge"
    GROUNDING_MATERIALIZATION = "grounding_materialization"
    CITATION_MATERIALIZATION = "citation_materialization"
    PUBLICATION_GATE = "publication_gate"
    SHADOW_RENDERING = "shadow_rendering"
    RENDERER_VALIDATION = "renderer_validation"


class GlobalSynthesisSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"
```

Issues MUST bounded、Host-owned、deterministically identified，并且不得保存 raw prompt、raw model output、
hidden reasoning 或 external Evidence。Per-issue `degrades_global_status` 表示该 event 是否触发 degradation，不得仅凭
severity 文本推导；真正 sticky 的是单独的 monotonic accumulator。Faithfulness evaluator 位于 external Eval，因此
没有 runtime `FAITHFULNESS_EVALUATION` stage。

### Monotonic Degradation Fact

Bounded issue ledger 可能因容量限制不再保留早期 issue，因此 Global status MUST NOT 通过扫描 retained issues
反向重建。Host 必须维护 monotonic degradation accumulator：

```text
global_synthesis_degradation_observed: bool

False OR False → False
False OR True  → True
True  OR False → True
True  OR True  → True
```

一旦为 True 不可恢复为 False。由于所有 S5 stages 位于单一 `global_synthesis` node，SPEC 不强制该 accumulator
成为 Parent State channel；PLAN MAY 使用 node-local execution context sticky flag 或 internal State carrier。最终
Parent `global_synthesis_status` 必须依据该 monotonic fact，而不是 issue strings/records。

### Partial Salvage vs Atomic Publish

Stage-level valid siblings MAY survive：invalid ClaimDraft 可被拒绝；Judge failure 的 valid Claim materializes an
`UNASSESSED` GroundingRecord。最终 candidate Manifest 中每个 retained Claim 必须拥有完整 record set。

```text
stage-level sibling salvage
!= Gate-level partial publication
```

Gate 通过时一次性发布完整 candidate；Gate 失败时发布 none。Exception 必须在 `global_synthesis` node boundary
捕获，写 status/issues，并继续 V1 path。

### Failure Isolation

- V2 failure 不修改 S4 Results；
- invalid refs 不猜测；
- Judge failure 不伪造 support；
- Renderer failure 只使 Shadow Report absent / status PARTIAL；
- internal drafts MAY 留在 process-local trace，但不得成为 authoritative State。

Zero report-eligible Claims 不构成 Renderer failure：Host 跳过 Model C，生成 deterministic no-grounded-claim
shadow output。Valid `INSUFFICIENT/CONTRADICTED` semantic outcomes 不设置 degradation；若没有其他 degrading
event，Global status MAY 为 `SUCCESS`。`UNASSESSED` 仍设置 degradation，并使已发布 Manifest 的 outcome 至少为
`PARTIAL`。

### Canonical Promotion

Promoted to S5-R13, S5-R15 and S5-R18。

---

## S5-D13 — Dedup Semantics

### Status

**EXTENDED / RESOLVED / PROMOTED**

### Human Resolution

S5 不实现 cross-task derived Evidence dedup：

- 不按 URL、hash 或 excerpt 合并不同 EvidenceRefs；
- 不修改 canonical `(task_id, evidence_id)`；
- 同一 Claim universe 内只对 exact EvidenceRef first-occurrence dedup；
- Host MAY 拒绝 exact duplicate ClaimDraft；
- 不使用 string similarity 做 semantic Claim dedup；
- Generator prompt SHOULD 要求 non-redundant Claims。

Historical D04/D17 display policy 使用 `(canonical_url, artifact_ref)` conceptual condition 表达 cross-task
reader-facing Source grouping；该 grouping 从未构成 canonical dedup。CB02–CB05 后，current observable behavior 由
S5-R09 定义，internal key representation、ordering 与 style 由 PLAN 定义。所有 Citation、EvidenceRef、
SourceRecord 与 task-qualified provenance identities 继续原样保留。

Exact duplicate ClaimDraft 的 recommended PLAN interpretation 是 canonical serialization identical replay，至少比较
`text/scope/qualifiers/finding_refs/materiality`；任一不同即不是 exact duplicate。Host 不得使用 string similarity、
embedding similarity 或 semantic fuzzy matching 做 Claim dedup。

### Rationale

Derived cross-task Evidence/Grounding dedup 需要将合并 view 的 Judge output 映射回多个 canonical refs，重新增加
mapping complexity；当前 bounded MVP 没有该 consumer/blocker。Reader-facing Source grouping 仅发生在 Grounding 与
canonical Citation materialization 后，不改变 Judge universe 或 Manifest identity，因此不违反该 decision。

### Canonical Promotion

Promoted to S5-R03, S5-R05, S5-R09 and S5-R14。

---

## S5-D14 — Renderer Faithfulness Boundary

### Status

**REOPENED / CORRECTED / RESOLVED / PROMOTED**

### Alternatives

1. deterministic template renderer；
2. constrained LLM renderer + Host bindings；
3. free-form LLM renderer；
4. runtime semantic verifier/repair loop。

### Previous Human Resolution — Host-fixed Section Catalog

采用方案 2。Renderer 是第三个 runtime model role，但只生成 derived V2 Shadow Report，不参与 Manifest
authority。

`ClaimRecord` 保存 immutable authoritative Claim semantics；Renderer MAY paraphrase complete validated Claim
proposition 以提高可读性，但 paraphrase 没有 Domain authority，不能 mutate/replace ClaimRecord、创建
authoritative Claim/Citation identity 或修改 Manifest，并受 external faithfulness evaluation。

Internal output：

```python
class ReportParagraphDraft:
    text: str
    claim_ids: list[str]


class ReportSectionDraft:
    section_id: str
    paragraphs: list[ReportParagraphDraft]


class ShadowReportDraft:
    sections: list[ReportSectionDraft]
```

`section_id` 必须来自 Host-prepared bounded section allowlist。Unbound title、section heading 与固定 boilerplate 只能
由 Host deterministic 生成；Model C 不输出 unbound free-form body content。

该 section catalog 约束已被下面的 Latest Human Resolution supersede。它继续保留在 Decision Log 中仅用于说明设计
演进，不再定义当前 Renderer structure authority。

### Latest Human Resolution — Model-owned Report Organization with Bounded Evidence Context

继续采用 constrained LLM renderer，但修正 Renderer 与 Host 的职责边界：

- Model C 决定 section count、section title、section order、paragraph organization 与 paragraph prose；
- Model C 使用 structured output 返回 section title、paragraph text 与 paragraph `claim_ids`；
- 每个 model-generated body paragraph 仍必须绑定至少一个 valid report-eligible Claim；section title 不是 body
  paragraph，不要求 Claim binding；
- Model C MAY 读取每个 report-eligible Claim 对应的 bounded material supporting / contradicting Evidence
  projection，以形成连贯、平衡且能自然解释冲突的报告；
- Model C 只可读取已经由 `ClaimGroundingRecord` materialize 为 supporting / contradicting 的 Evidence，不得重新搜索、
  扩大 Evidence universe、修改 Evidence role 或引入 evaluated-but-non-material Evidence；
- Host 继续拥有 Claim eligibility、Evidence projection admission、Citation identity、required Citation set、display labels、
  bibliography、bounds、structural validation 与最低限度 conflict disclosure；
- Model C 不获得 Citation numbering authority，也不得创建或修改 Claim、Grounding、Citation 或 Manifest。

Model C 的 material Evidence visibility 与 Citation completeness 是两条不同边界。Renderer context MAY 因 bounded
admission 省略部分 Evidence，但 authoritative required Citation set 必须完整保留，且由 Host 在渲染后确定性注入。

Latest structured-output concept：

```python
class ReportParagraphDraft:
    text: str
    claim_ids: list[str]


class ReportSectionDraft:
    title: str
    paragraphs: list[ReportParagraphDraft]


class ShadowReportDraft:
    sections: list[ReportSectionDraft]
```

这是 internal DTO concept，不是 stable Domain Contract；exact field bounds 与 serialization 由 PLAN 定义。

### Host Validation and Citation Injection

- 每个 model-generated body paragraph 的 `claim_ids` MUST non-empty；Host 不尝试判断 factual/non-factual；
- paragraph Claim IDs 必须存在、unique、bounded、report-eligible；
- Renderer 不输出 URL、Citation identity 或 numbering；
- Host 根据 paragraph `claim_ids` 注入 required display labels；
- 每个 surviving report-eligible Claim MUST 至少出现一次；
- 一个 Claim MAY bounded 地出现在多个 body paragraphs；
- first canonical occurrence 是 derived primary occurrence，不增加 Domain field；
- 每个 occurrence 注入同一组 required labels；
- repeated occurrence 不创建新 Claim/Citation identity；
- Host 保留 Model C 输出的 section / paragraph order，并验证 section title non-empty、sanitized、bounded；
- `SUPPORTED_WITH_CONFLICT` 的 first canonical paragraph occurrence 由 Host deterministic 插入最小 conflict marker，
  明确 material contradictory Evidence exists，并同时包含 supporting 与 contradicting material Evidence 的 display
  citations。

Model C input MUST NOT 包含 `ClaimGroundingRecord.reason`。Conflict rendering 使用完整 Claim proposition、
GroundingStatus、bounded material Evidence projection、Host-derived `conflict_present` 或等价 flag，以及 optional
validated Source metadata。Runtime 不要求准确叙述相对 Evidence weight 或 detailed uncertainty narrative；这些属于
report quality / external faithfulness evaluation。

### Coverage and Admission

Host 尽可能接纳全部 validated Claims。容量 overflow 时按 `HIGH → MEDIUM → LOW` 选择 surviving set，同一
materiality 内按 Generator order，选择后将 survivors 投影回 Generator canonical order。Renderer 不得自行
省略 surviving eligible Claim。Claim survivor selection 只发生一次：Model A output → Host validation → capacity
admission → surviving ClaimRecords → Grounding → Manifest。Renderer 不得执行第二次 Claim selection。

Published Manifest 中每个 report-eligible Claim MUST 至少渲染一次；若 Renderer budget/context 无法覆盖全部，
属于 runtime sizing / Renderer failure，不得 silent admission。若 eligible set 为空，Host 跳过 Model C 并生成
deterministic no-grounded-claim output。

Renderer Evidence context 使用 deterministic whole-unit admission，不截断 authoritative Evidence excerpt。PLAN 负责在
bounded context 内优先避免 Claim starvation；任何 Renderer-visible Evidence omission 不得改变 GroundingStatus、required
Citation set 或 Manifest。

### Multi-Claim Paragraph Residual Risk

一个 paragraph MAY 绑定多个 Claim IDs。Model C 可能在这些 Claims 之间生成新的 causal、comparison、synthesis
或 transition proposition；Host structural validator 不能证明不存在新 semantic proposition。S5 runtime 只保证
structural Claim binding，不保证 semantic no-new-proposition，也不新增 runtime semantic verifier/repair loop。

### Faithfulness Evaluation

S5 实现 external evaluation-only semantic faithfulness evaluator。它位于 graph/runtime State 之外，输入 V2
Shadow Report + Manifest projection，测量 unsupported proposition、scope expansion、qualifier loss、conflict
omission 与 Claim misrepresentation。Evaluator 必须将 `text + scope + qualifiers` 视为完整 Claim proposition，
同时检查 text semantic meaning、scope preservation 与 qualifier preservation。

Evaluator 不进入 Parent State、不影响 Global status、不作为 Manifest/Renderer Gate、不触发 automatic repair。
Evaluator execution/schema failure MAY retry；valid FAIL verdict 不得 retry 到 PASS。

### Canonical Promotion

Original faithfulness boundary promoted to S5-R15 and S5-R16。Latest Renderer structure authority与bounded material
Evidence visibility已resync到S5-R15及`EVIDENCEFLOW_CONTRACTS_V1.md` §3.14；external evaluator boundary保持不变。

---

## S5-D15 — Model Role and Retry Semantics

### Status

**RESOLVED / PROMOTED**

### Logical Roles

```text
Model A: Claim Generator
Model B: Grounding Judge
Model C: Shadow Report Renderer
```

Physical provider/model MAY 相同；SPEC 不冻结具体 selection。Faithfulness evaluator 是 external Eval role。

### Retry Semantics

- retry 仅用于 transient provider、timeout、structured schema/reference validation failure；
- valid negative semantic result 不是 execution failure；
- Generator retry 不预先发布 ClaimRecord；
- Judge retry 不修改 Claim identity；
- Renderer retry 使用同一 published Manifest projection；
- retry exhaustion 生成 issue，并按 D12 处理；
- exact attempts、timeout、backoff 与 concurrency 属于 PLAN/config。

### Sibling Preservation

Host validation MAY salvage valid siblings。Generator batch 中 invalid drafts 被拒绝；单 Claim Judge exhaustion
produces `UNASSESSED`，不擦除 other valid Claims。

### Canonical Promotion

Promoted to S5-R11 and S5-R13。

---

## S5-D16 — Bounds and Admission

### Status

**EXTENDED / RESOLVED / PROMOTED**

### Bound Dimensions

Contract MUST 对以下维度保持 hard/configured bounds：

- Claim count、text、scope、qualifiers、FindingRefs；
- evaluated/supporting/contradicting EvidenceRefs per Claim；
- Grounding reason；
- Citation count；
- Manifest serialized size；
- issue count/message/payload；
- Generator/Judge/Renderer input/output Context；
- report sections/paragraphs/text/Claim occurrences。

### Admission Rules

- proactive deterministic admission precedes model call/Gate；
- 完整 Finding/Evidence/Claim units，不切片 authoritative Evidence excerpt；
- upstream Data Plane 不因 Context omission 被删除；
- Host 先尝试接纳所有 validated Claims；只有 capacity overflow 时才使用 `HIGH → MEDIUM → LOW` selection，
  canonical order 恢复为 Generator order；
- Generator input 使用 Parent Result ledger order、per-task Finding cap、Result Finding order；
- per-Claim Judge Evidence overflow 保留 derived canonical prefix，不 rerank、不截断 excerpt；
- normal overflow 保留 legal subset 并生成 issue；
- Publication Gate 是 defense-in-depth，不是 normal truncation engine。

ClaimMateriality 虽由 Model A proposal 且未经 calibration，MAY 只影响 post-generation Claim capacity admission。
它 MUST NOT 影响 upstream Generator Finding/Evidence context admission，因为 Model A 执行前 materiality 不存在；
也不得变成 Grounding confidence、Evidence quality 或 numeric calibrated score。

Claim survivor selection 只执行一次并位于 Grounding 前。Renderer 不得进行第二次 Claim selection；Renderer
capacity 必须在同一 selection boundary 预留。无法覆盖 published Manifest 中全部 eligible Claims 时是 Renderer
failure，不是 silent capacity admission。

### Capacity

每个 model role 使用独立 budget，并为 prompt/schema/output/provider overhead 保留 safety reserve。Exact token
budgets、numeric defaults、tokenizer、timeout 与 concurrency 属于 PLAN/config，不冻结到 SPEC。

### Canonical Promotion

Promoted to S5-R14 and S5-R15。

---

## S5-D17 — Deterministic Ordering and Display

### Status

**REOPENED / CORRECTED / RESOLVED / PROMOTED**

### Human Resolution

```text
ClaimRecord[]
→ validated Generator order after survivor selection

ClaimGroundingRecord[]
→ exact Claim order

evaluated_evidence_refs
→ FindingRef order, then Finding evidence_ids order, first occurrence

supporting_evidence_refs
→ evaluated order filtered by Judge selection

contradicting_evidence_refs
→ evaluated order filtered by Judge selection

Citation[]
→ Claim order, then supporting refs, then contradicting refs
```

Async completion、dict/set/hash iteration 或 model callback timing 不得成为 ordering authority。

### Historical Citation Display Implementation Policy

**Representation、label algorithm与style authority placement superseded by CB02–CB05。**

上一轮 ordering decision 将 cross-task display-only grouping 保持为 deferred；最新 Human Resolution 已重新打开并
冻结该 presentation policy，但未改变 canonical ordering 或 identity。

> **CB02–CB05 authority-placement note:** 下列 key representation、first-occurrence label algorithm 与 GB/T style
> 保留为 D17 historical decision provenance；current canonical Contracts 不再定义这些 presentation mechanics。
> Grouping eligibility、determinism、provenance non-mutation 与 bibliography behavior 由 S5-R09 约束，具体实现由
> PLAN 约束。

Host SHALL 从 canonical Citation traversal 构建 ordered Source display projection：

1. 同一 canonical `(task_id, source_id)` 的多个 EvidenceRefs 聚合为一个 display Source entry，保留 first Citation
   occurrence order；
2. 在同一 EvidenceFlow Run 内，对同时具有相同 canonical URL 与相同 `artifact_ref` 的跨 Task entries，MAY 按
   `SourceDisplayKey=(canonical_url, artifact_ref)` 进一步做 display-only grouping；
3. 缺少 canonical URL、URL 不同、`artifact_ref` 不同或不属于同一 owning `artifact_run_id` 时，MUST 保持独立
   display entries；
4. ordered projection 中每个 display entry 的 first canonical Citation occurrence 决定 label order；
5. support/contradiction 不使用特殊编号，角色由 Grounding/prose 表达；
6. repeated Claim occurrences 复用同一 labels。

Display grouping 不改变 canonical Citation traversal，也不得将 `SourceDisplayKey` 提升为 Source identity。一个 label
MAY 映射多个 canonical Citations、EvidenceRefs 与 task-qualified SourceRecords，audit view MAY 展示全部 contributing
EvidenceRefs。

Bibliography SHOULD best-effort 使用 GB/T 7714-style rendering，只使用 validated available metadata，缺失 author/
year/publisher 时不得推断并应 graceful degradation。Formatting 不定义 Citation identity 或 Grounding authority。

### Canonical Promotion

Promoted to S5-R09, S5-R14 and S5-R15。

---

## S5-D18 — Manifest Envelope, State and Versioning

### Status

**RESOLVED / PROMOTED**

### Manifest Contract

```python
class GroundingManifest:
    contract_version: str
    claims: list[ClaimRecord]
    groundings: list[ClaimGroundingRecord]
    citations: list[Citation]
```

Manifest 不包含 Relations、Metrics、process issues、drafts、raw Evidence、Shadow Report 或 copied Source
metadata。

### Parent State

```python
grounding_manifest: GroundingManifest | None
global_synthesis_status: GlobalSynthesisStatus | None
global_synthesis_issues: list[GlobalSynthesisIssue]
v2_shadow_report: str | None
```

Faithfulness assessments 属于 external Eval，不进入 Parent State。

Monotonic `global_synthesis_degradation_observed` 是 Freeze-level execution invariant，但因 S5 stages 位于同一 node，
不强制新增 Parent channel。PLAN 可选择 node-local sticky flag 或 internal carrier；最终 status 不得从 bounded
`global_synthesis_issues` ledger 反向重建。

### Version

Manifest 使用 canonical `evidenceflow.contracts.v1`。S5 扩展 v1 roadmap 中明确 deferred 的 Claim/Citation
contract，不修改 S4 wire semantics，因此不创建第二个 version namespace。

### Update Semantics

- Manifest 只有 Gate 通过后 atomic one-shot publish；
- `None → Manifest` 是合法 publication；
- identical replay 幂等；
- divergent replay 报 contract conflict；
- empty Manifest structurally legal；
- issues bounded append/dedup；
- status/report 使用 Host-owned override；
- Renderer failure 不修改 Manifest；
- zero report-eligible Claims 时 Host deterministic shadow output 可写入 `v2_shadow_report`，无需调用 Model C；
- 不增加 manifest ID、durable persistence 或 cross-run registry。

### Canonical Promotion

Promoted to S5-R10, S5-R12, S5-R13 and S5-R18。

---

## S5-D19 — Research Run State Lifecycle and Provenance Isolation

### Status

**RESOLVED / PROMOTED**

### Problem and Source Baseline

Final Freeze Audit 发现：当前 Parent `AgentState.research_results` 在 active State 内按 `task_id` append/merge，
`ResearchTaskResult` 本身不携带 `artifact_run_id`；与此同时，Parent entry 已明确需要防止 checkpointed conversation
沿用已完成 execution 的旧 Artifact namespace。若新 execution 只替换 `artifact_run_id` 而保留旧 Results，旧
`SourceRecord.artifact_ref` 将可能被放到新的 run-scoped `ArtifactStore` namespace 中解析。

当前源码还没有实现 S5 State channels，也没有冻结 conversation lifetime 与 Research Run lifetime 的关系。因此该
问题不能留给 PLAN 通过 reducer 或 entry-node 写法隐式决定。

### Alternatives

1. 在 active `AgentState` 内持续累积多个 Research Runs 的 structured history；
2. 一次 checkpointed conversation 只允许一个 active authoritative Research Run，新 Run bootstrap reset 所有
   run-scoped State；
3. 把 previous-run Results 自动复用到新 Run，并新增 run-qualified provenance address。

### Human Resolution — One Active Authoritative Research Run

选择方案 2。

`Research Run` 表示一个 research request 的一次逻辑 top-level Deep Research execution lifecycle，从 Research Run
bootstrap 持续到 finalization。它不是单个 Supervisor iteration、`ConductResearch` Task、Researcher invocation、
search call、arbitrary graph node execution，也不必等于每条 user message 或每次 `graph.invoke()`。

一个 Research Run MAY 跨越 multiple Supervisor iterations、ResearchTasks、Researchers、Tool/Model retries，以及
继续同一逻辑 execution 的 clarification、interrupt 与 resume。上述阶段 MUST 共用同一个 `artifact_run_id`。

Frozen lifetime model：

```text
Conversation / checkpoint lifetime
        >
Research Run lifetime
        >
ResearchTask lifetime
```

Checkpointed conversation MAY 先后承载 Run A 与 Run B，但 active Parent State 同一时间最多只拥有一个 authoritative
Research Run。P2-S5 不在 active `AgentState` 保存 multi-run structured research history。

### User Message and Resume Boundary

不得把“每条 user message”或“每次 graph invocation”定义为新 Research Run。Clarification 后的 user answer、interrupt
resume 或其他继续同一 logical execution 的输入 MUST 保持原 `artifact_run_id`。只有当前 Run 已 finalization，且新
request 启动新的 top-level Deep Research execution 时，才 bootstrap 新 Run 与 fresh `artifact_run_id`。

SPEC 冻结上述 logical lifecycle；PLAN/runtime mapping 负责根据当前 LangGraph entry、checkpoint、interrupt/resume
API 确定性识别 bootstrap、resume 与 finalization，不得改变 lifecycle semantics。

### State Ownership and New-run Reset

`messages` 属于 conversation-scoped context，MAY 按 checkpoint policy 跨 Runs 保留，以帮助 clarification、brief
generation 或 follow-up interpretation。但 conversation context 不是 structured provenance reuse。

以下 Parent fields 属于 active Research Run：

| State field | New Research Run behavior |
|---|---|
| `supervisor_messages` | reset，为新 Run 创建 fresh Supervisor context |
| `artifact_run_id` | replace 为 fresh Run namespace |
| `medical_research_brief` | clear，随后由新 Run replace |
| `research_brief` | clear，随后派生新 legacy brief |
| `research_results` | reset 为 empty fresh ledger |
| `raw_notes` | reset 为 empty legacy process ledger |
| `notes` | reset 为 empty V1 writer input |
| `final_report` | reset 为 no prior report (`None`/empty 的具体 representation 属于 PLAN/schema) |
| `grounding_manifest` | reset 为 `None` |
| `global_synthesis_status` | reset 为 `None` |
| `global_synthesis_issues` | reset 为 `[]` |
| `v2_shadow_report` | reset 为 `None` |
| run-local degradation accumulator | reset 为 `False` |
| any future S5 derived/eval runtime artifact stored in State | reset；不得自动成为新 Run authority |

Supervisor-local `research_iterations`、Supervisor messages/Results projection，以及所有 Researcher-local Task、messages、
Source/Evidence/Finding ledgers、issues、status、compression 与 Result fields，均必须在新 Run/Task invocation 中 fresh
initialize；它们不形成 cross-run history。

该表冻结 conceptual reset，不冻结 LangGraph reducer mechanics。PLAN MAY 使用 bootstrap helper、entry node、reducer
command、State replacement 或其他 deterministic mechanism，但 MUST 使 reset 可表达、可验证，并在任何新 Run
Source/Evidence/Result admission 之前完成。

### Artifact Namespace and Physical Lifetime

一个 Research Run 对应一个 `artifact_run_id` namespace。Run 内所有 Supervisor iterations、ResearchTasks 与
SubResearchers MUST 传播同一值。新 Run 的 fresh `artifact_run_id` MUST NOT 与旧 authoritative
`ResearchTaskResult[]` 在 active Data Plane 中共存。

State reset 不要求删除 physical ArtifactStore data。旧 run directories MAY 继续存在；P2-S5 只停止把旧 Run
Artifact/Result 当作 active authority，不新增 retention、GC 或 destructive cleanup。

### Replay and Same-run Updates

Manifest replay semantics 只在同一 active Research Run 内适用：

- `None → Manifest` 合法；
- identical replay idempotent；
- divergent replay 是 contract conflict；
- Run B bootstrap 先把 `grounding_manifest` reset 为 `None`，因此 Run B Manifest 不构成 Run A 的 divergent replay。

同一 active Run 内：`global_synthesis_status` 与 `v2_shadow_report` 是 Host-owned replace/override；
`global_synthesis_issues` bounded append/dedup；degradation accumulator monotonic OR。新 Run bootstrap reset 这些
run-local semantics。

### Cross-run Provenance and Display Boundary

Prior-run `ResearchTaskResult`、Source、Evidence、Finding、Claim、Grounding、Citation 或 Manifest MUST NOT 自动进入
新 Run authoritative Data Plane。P2-S5 不实现 multi-run Result ledger、ResearchRun registry、run-qualified
`EvidenceRef`、cross-run Evidence/Citation reuse、Source dedup、Artifact provenance merge 或 historical Manifest
registry。未来如需复用 previous-run Evidence，必须建立新的 explicit contract/phase。

S5-R09 governing 的 reader-facing cross-task grouping eligibility 只适用于同一 owning Research Run / artifact
namespace，并比较 resolved Source 中 validated stored URL 的 exact string value 与 `artifact_ref`。Canonical Source
address 仍是 `(task_id, source_id)`；Artifact address 仍是 `(artifact_run_id, artifact_ref)`；bare `artifact_ref` 不用于
推断 cross-run equality。Internal display-key representation 由 PLAN 定义，S5 不自行 canonicalize URL。

### Canonical Promotion

Promoted to `P2_S5_SPEC.md` S5-R19 and `EVIDENCEFLOW_CONTRACTS_V1.md` Research Run/State/update invariants。

---

## S5-D20 — Lifecycle Conflict Atomicity Under LangGraph Input Admission

### Status

**RESOLVED / PROMOTED**

### Problem

Pre-implementation Review 的真实 runtime probe 证明：LangGraph input processing / `add_messages` 在 EvidenceFlow
entry node 运行前，已经可能把 incoming `HumanMessage` 写入 conversation-level `messages` channel 与 checkpoint。
因此 entry node 无法同时抛出 lifecycle conflict 并保证整个 checkpoint byte-for-byte unchanged。

Observed behavior：

```text
before messages:
[("m-seed", "seed")]

after framework admission + lifecycle conflict:
[("m-seed", "seed"), ("m-conflict", "conflict")]
```

### Human Resolution

Conflict atomicity applies after framework-level `HumanMessage` admission and covers EvidenceFlow-owned Research Run
lifecycle and structured provenance. Framework-admitted incoming `HumanMessage` MAY remain in `messages`。

The `HumanMessage` is not considered consumed by the current or a new Research Run unless
`research_run_input_cursor` advances according to the frozen P01 state machine。

### Required Conflict Behavior

On lifecycle conflict：

- `messages` MAY already contain the incoming `HumanMessage`；
- `research_run_input_cursor` MUST remain unchanged；
- `research_run_status` MUST remain unchanged；
- `artifact_run_id` MUST remain unchanged；
- no run-scoped reset；
- no brief、`ResearchTaskResult`、notes/raw notes、report 或 Shadow Report mutation；
- no Manifest mutation/publication；
- no global synthesis issue/status write；
- no sticky degradation mutation；
- no Claim、Grounding 或 Citation materialization；
- no implicit `ACTIVE` Run abandonment；
- no message rollback or deletion attempt。

### Explicitly Not Required

- checkpoint byte-for-byte immutability；
- rollback of the framework-admitted message；
- `RemoveMessage` compensation；
- pre-graph admission wrapper；
- transport admission gateway；
- rejected-message ledger；
- active-run abandonment API。

### Rationale

Conversation admission 与 Research Run admission 是两层不同 authority：

```text
messages
→ conversation-level occurrence ledger

research_run_input_cursor
→ Research Run consumed-input position
```

因此，framework-admitted but cursor-unconsumed `HumanMessage` 是合法且可观察的 rejected/unsupported mid-run
occurrence，不是 current Run 已消费输入。`message exists in messages` 不等于 `message has been consumed by a
Research Run`。

### Scope Impact and Promotion

- Contracts unchanged；
- SPEC unchanged；
- P02–P10 unchanged；
- topology unchanged；
- no new subsystem；
- implementation mapping only。

Promoted to the P01 mapping and verification boundaries in `P2_S5_PLAN.md`、`P2_S5_TASKS.md` and
`P2_S5_CHECKLIST.md`。

---

## Contract Boundary Clarifications — CB01–CB06

### Status

**RESOLVED / PROMOTED**

### Audit Question

本轮只审计 canonical contract surface：一个语义是否必须被跨 phase、跨 module 或 serialized consumer 稳定依赖？
若不是，则不得仅因当前 S5 implementation 需要而进入 `EVIDENCEFLOW_CONTRACTS_V1.md`。

| ID | Item | Previous authority | Final authority | Judgment |
|---|---|---|---|---|
| CB01 | exact `GlobalSynthesisStage` vocabulary | Contracts | PLAN / process-internal | diagnostics taxonomy 不是 closed wire vocabulary |
| CB02 | cross-task Source display grouping eligibility | Contracts | SPEC | reader-visible observable behavior |
| CB03 | tagged `SourceDisplayKey` representation | Contracts | PLAN | Host-internal presentation value |
| CB04 | first-occurrence label algorithm | Contracts | PLAN | deterministic rendering policy |
| CB05 | GB/T 7714-style bibliography formatting | Contracts | PLAN | presentation style；bibliography behavior仍在SPEC |
| CB06 | `artifact_ref` content identity、run-scoped address与wire encoding | Contracts | Contracts | stable provenance semantics |

### CB01 — Open Issue Stage Contract

`GlobalSynthesisIssue`、`GlobalSynthesisStatus` 与 `GlobalSynthesisSeverity.WARNING/ERROR` 继续属于 stable serialized
process contract。`GlobalSynthesisIssue.stage` 的 stable contract 改为 required `str`，且必须 non-empty、
machine-readable、sanitized 与 runtime-bounded；它表达 issue 被观察到的 logical S5 processing stage。

Stable deserialization MUST 保持 open：consumer MUST 接受任何满足上述通用约束的未知 stage string，不得使用
`GlobalSynthesisStage` 对 wire payload 做 closed enum validation。PLAN MAY 定义 exact `GlobalSynthesisStage` enum
约束当前 Host-produced values；新增或细分 Host stage name 在 stable Issue shape 不变时不自动构成 Contracts v1
migration。

Numeric bounds（例如 stage/code/issue ID 的当前字符上限）属于 Host issue factory/admission guardrail，不成为
`evidenceflow.contracts.v1` 的永久 numeric compatibility guarantee。D12 的 exact stage enum 保留为 historical
taxonomy，但其 authority placement 被 CB01 supersede。

### CB02–CB05 — Display Behavior vs Presentation Mechanics

Contracts 只保留 `Citation identity != display identity` 与 presentation grouping 不得改变 canonical provenance。

SPEC 约束 observable behavior：同一 canonical Source 下的 cited Evidence SHOULD 共享一个 reader-facing Source
entry；cross-task grouping 只 MAY 在 same Research Run、same validated stored URL value 与 same `artifact_ref` 时
发生。URL 缺失或不同、Artifact 不同、Run 不同均不得 cross-task group；labels 必须 deterministic；任何 grouping
不得 merge Citation、EvidenceRef、SourceRecord 或其 canonical identity。

URL comparison authority 是 resolved `SourceRecord.metadata["url"]` 的 validated stored value，并使用 exact stored
string equality。当前 S4 writer 在 source materialization 前调用 shared upstream `canonicalize_source_url()` 并存储其
结果；S5 只消费 stored value，不重新 canonicalize、normalize、清理或推断 URL。若 record 没有 upstream
canonicalized value，但包含合法 stored URL，S5 仍只进行 exact stored equality；缺失或 invalid value 禁止
cross-task grouping。

PLAN 负责 tagged internal representation、exact label assignment/format、metadata merge/fallback 与 bibliography
formatter。`SourceDisplayKey` 不成为 stable Contract type。V2 渲染 source display entries 时 SHOULD 提供由
validated available metadata 确定性派生的 bibliography；缺失 metadata 不得推断或伪造。当前 best-effort GB/T
7714-style 只是 PLAN presentation policy，未来替换 style 不改变 Citation/Source/Grounding authority。

D04/D17 的 grouping design history 保留，但其 key representation、label algorithm 与 style authority placement 被
CB02–CB05 supersede。

### CB06 — Artifact Semantic and Encoding Boundary

Contracts 继续冻结：`artifact_ref` 在 owning `artifact_run_id` namespace 内标识传给
`ArtifactStore.put_text()` 的最终 logical text content。Exact current wire encoding 是：

```python
artifact_ref = (
    "artifact:sha256:"
    + sha256(final_text.encode("utf-8")).hexdigest()
)
```

`final_text` 是 upstream preparation/normalization 完成后交给 `put_text()` 的最终 logical text value。相同
`final_text` MUST 产生相同 `artifact_ref`；完整可解析 address 仍为 `(artifact_run_id, artifact_ref)`。

Contracts 不定义 `final_text` 如何产生、filesystem bytes 的重新读取、storage path/layout 或 backend。该 identity
不证明 original provider/webpage bytes globally identical，也不是 Source identity。Exact wire encoding保持不变，
因此 contract version继续是 `evidenceflow.contracts.v1`。

### Version and Migration Classification

本轮是 pre-implementation canonical surface refinement。当前尚无 P2-S5 producer、checkpointed Issue payload 或
serialized `SourceDisplayKey` consumer；`stage enum → open string` 是当前时间点上的 accepted validation widening，
不能推广为“已部署 enum 永远可以无版本删除”的通用规则。

### Canonical Promotion

- CB01、CB06 promoted to `EVIDENCEFLOW_CONTRACTS_V1.md`；
- CB02 与 CB05 的 observable behavior promoted/resynced to S5-R09；
- CB03、CB04 与 CB05 formatting policy promoted/resynced to `P2_S5_PLAN.md`；
- authority resync本身不关闭P01–P10；这些PLAN-level事项已在后续`P2_S5_PLAN.md` final revision中独立关闭。

---

## Deferred Documentation / Contract Surface Debt

### Status

**NON-BLOCKING / NON-NORMATIVE / DEFERRED**

This note identifies documentation-surface debt only. It does not alter current Contracts v1 authority or reopen P2-S5
semantics.

当前 `EVIDENCEFLOW_CONTRACTS_V1.md` 仍包含一部分长期可能更适合 SPEC、PLAN 或 Eval documentation 的内容：

- internal `ClaimDraft` shape 与 Model A behavior；
- internal `ClaimGroundingDraft` / `ClaimEvidenceVerdict` representation；
- `GroundingManifest` section 中的 admission、ordering 与 Publication Gate algorithm summary；
- V2 Renderer 与 external evaluator 的 phase behavior；
- derived metrics definitions，以及由PLAN P09确定的exposure boundary。

这些内容目前与 frozen SPEC 一致，不产生 implementation ambiguity，也不阻断PLAN freeze review、TASKS/CHECKLIST
final revision或P2-S5 implementation planning。本轮不迁移、删除或重新解释这些内容；在 P2-S5 closeout 后或 P2-S6 前执行独立的
`Contracts v1 structural compact audit`，届时再判断其 long-term authority placement 与 version impact。

---

## 20. Decision Closure

P2-S5 architecture-sensitive decisions D00–D20 与 canonical surface decisions CB01–CB06 已完成 Human Resolution
和相应 promotion。Exact model/provider、token budgets、numeric bounds、retry counts、concurrency、Research Run
lifecycle 的 LangGraph bootstrap/resume mapping 与 file-level implementation mapping 明确保留给 PLAN，不得改变
已冻结 semantics。

下一阶段：

```text
P2_S5_SPEC.md FROZEN / RENDERER RESYNCED
→ P2_S5_PLAN.md AUDITED DRAFT / READY_FOR_FREEZE REVIEW
→ P2_S5_TASKS.md FINAL REVISION
→ P2_S5_CHECKLIST.md FINAL REVISION
→ implementation
```
