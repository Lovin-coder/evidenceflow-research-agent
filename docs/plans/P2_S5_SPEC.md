# P2-S5 — Global Claim, Citation and Grounding SPEC

## 0. 文档职责、权威与冻结状态

| Field | Value |
|---|---|
| Phase | `P2-S5` |
| Status | **FROZEN** |
| Revision | **SEMANTIC-PRESERVING COMPACT REVISION / RENDERER RESYNCED** |
| Decision gate | **CLOSED — D00–D19 RESOLVED AND PROMOTED** |
| Next workflow stage | **PLAN AUDITED DRAFT / READY_FOR_FREEZE REVIEW** |
| Coding gate | **CLOSED UNTIL PLAN / TASKS / CHECKLIST ARE REVIEWED AND FROZEN** |
| Contract version | `evidenceflow.contracts.v1` |
| Contracts sync | **COMPLETE — P2-S5 CANONICAL SEMANTICS PROMOTED TO CONTRACTS V1** |

本文定义 P2-S5 必须保证的 phase behavior。Stable object shapes、cross-phase field semantics、State/process channel
contracts、identity/provenance semantics 与 Artifact wire semantics 由 `EVIDENCEFLOW_CONTRACTS_V1.md` 定义；本
SPEC 不维护它们的第二份字段级副本。

架构敏感决策的 alternatives、Human Resolution 与 rationale 保存在 `P2_S5_CLARIFICATIONS.md`。Clarifications 是
decision provenance，不是未提升语义的 fallback authority。

文档职责分层如下：

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

Implementation-quality rules 与 semantic authority 同时约束实现，但不得反向修改 Contracts 或本 SPEC。PLAN、TASKS、
CHECKLIST 与 code 也不得以实现细节名义改变 frozen behavior。

本文使用：

- `MUST / SHALL`：强制要求；
- `MUST NOT / SHALL NOT`：禁止行为；
- `SHOULD`：推荐要求，偏离时必须在 PLAN 或 CHECKLIST 说明；
- `MAY`：允许但不是必需。

本次 compact revision 只消除 canonical duplication 与 PLAN/test-level 内容，不改变 requirement IDs、normative force、
externally observable behavior 或 freeze status。SPEC Freeze 不授权立即 coding。

---

## 1. Scope、Inputs and Outputs

### 1.1 Authoritative input

P2-S5 的 authoritative input SHALL 是：

```text
MedicalResearchBrief
+
ResearchTaskResult[]
```

每个 populated `ResearchTaskResult` 继续是 self-contained task-level provenance aggregate。Bare Source、Evidence 与
Finding IDs 只在 owning Result 内 authoritative；raw Source Artifact 继续位于 run-scoped `ArtifactStore`，不得进入
Graph State。

Authoritative Data Plane 与 model-facing bounded projection MUST 保持分离。Legacy notes、Messages、provider text、
prompt 或 process diagnostics 均不得成为 V2 Claim/Grounding provenance。

### 1.2 Outputs

P2-S5 SHALL 产生：

```text
GroundingManifest
    = authoritative V2 structured shadow output

V2 Shadow Report
    = derived, non-authoritative evaluation artifact

V1 Report
    = legacy official/compatibility output during P2-S5
```

Informative pipeline overview：

```text
ResearchTaskResult[]
        ↓
bounded Finding / Evidence projection
        ↓
Model A — Claim Generator
        ↓
Host Claim materialization
        ↓
Finding-derived Evidence universe
        ↓
Model B — Grounding Judge
        ↓
Host ClaimGroundingRecord materialization
        ↓
Host Citation materialization
        ↓
GroundingManifest Publication Gate
        ↓
Model C — constrained V2 Shadow Renderer
```

该图用于说明阶段关系；normative authority 来自 §3 的 `S5-R01–S5-R19`。

### 1.3 In scope

P2-S5 包含：

- Global Claim synthesis、materialization 与 derivation lineage；
- task-qualified Finding/Evidence resolution；
- Claim-level Grounding 与 five-state status；
- Evidence-level Citation completeness；
- atomic `GroundingManifest` publication；
- reader-facing Source display grouping；
- bounded deterministic admission、ordering、status 与 failure semantics；
- constrained V2 Shadow Renderer 与 external faithfulness evaluation；
- V1/V2 shadow migration；
- Research Run lifecycle 与 provenance isolation。

---

## 2. Normative Vocabulary

### 2.1 Stable contracts

P2-S5 consumes or produces the following stable contracts defined by
`EVIDENCEFLOW_CONTRACTS_V1.md`：

- `MedicalResearchBrief`、`ResearchTaskResult`、`SourceRecord`、`EvidenceRecord`、`ResearchFinding`；
- `EvidenceRef`、`FindingRef`；
- `ClaimMateriality`、`ClaimRecord`；
- `GroundingStatus`、`ClaimGroundingRecord`；
- `Citation`、`GroundingManifest`；
- Parent Global Synthesis status、issue 与 State channel contracts。

字段 shape、enum values、requiredness、serialization 与 stable cross-phase semantics 以 Contracts v1 为唯一 canonical
定义。本 SPEC 只规定这些 contracts 在 P2-S5 中如何生成、解析、聚合、发布和消费。

### 2.2 Evidence and Finding

`EvidenceRecord` 表示从 authoritative Source Artifact 通过 deterministic locator 提取的 contiguous exact passage，
是 external provenance authority。P2-S5 不得修改其 excerpt、locator、hash 或 Source binding。

`ResearchFinding` 是单个 `MedicalResearchTask` 内的 semantic synthesis，不是 external Evidence。在 P2-S5 中，它提供：

- Claim derivation lineage；
- Claim 的 candidate Evidence universe derivation input。

### 2.3 Claim

`ClaimRecord` 是 Host 在 Global Synthesis boundary materialize 的 authoritative Claim。其 `text + scope + qualifiers`
共同构成完整 authoritative proposition；`scope` 和 `qualifiers` 不是 presentation hints。

Model A 的 draft 只是 semantic proposal，不是 stable Domain record，也不拥有 Claim identity、Evidence role、Grounding
status 或 Citation identity。

### 2.4 Grounding

Model B 对完整 Claim proposition 与完整 admitted Evidence universe 作出 overall `ClaimEvidenceVerdict`，并识别
material supporting/contradicting Evidence subsets。Host 验证其结构并确定性 materialize `ClaimGroundingRecord` 与
five-state `GroundingStatus`。

### 2.5 Citation and Manifest

`Citation` 是 reader-facing provenance handle，不是 Claim–Evidence semantic judgment。`GroundingManifest` 是 P2-S5
authoritative structured aggregate；Shadow Report、display labels、bibliography、metrics、issues 与 evaluator result 均
不是 Manifest authority。

### 2.6 Research Run

`Research Run` 是一个 research request 从 top-level Deep Research bootstrap 到 finalization 的 logical execution
lifecycle。Conversation/checkpoint 可以包含多个 sequential Runs；一个 Run 可以包含多个 ResearchTasks、Researchers、
Supervisor iterations、retries 与 clarification/resume。

---

## 3. Normative Requirements

### S5-R01 — Preserve the P2-S4 Boundary

P2-S5 MUST：

- 只从 `MedicalResearchBrief + ResearchTaskResult[]` 建立 authoritative Global Synthesis input；
- 保持 Result self-contained provenance、same-Result resolution 与 run-scoped Artifact semantics；
- 保持 Source → Evidence → Finding lifecycle；
- 保持 Researcher output contract 与 Supervisor–Researcher Tool Loop；
- 使 V2/Renderer failure 不修改或擦除 valid S4 Results。

P2-S5 MUST NOT：

- 修改 S4 Source/Evidence/Finding ID canonicalization；
- 将 raw Artifact 写入 Graph State；
- 使用 notes、Messages、provider snippets、prompt、model reasoning 或 process diagnostics 补造 V2 provenance；
- 引入 Parent sibling Source/Evidence registry。

### S5-R02 — Claim-first Synthesis

Canonical authority order SHALL 是：

```text
structured Results
→ Claim generation/materialization
→ Claim-level Grounding
→ Citation
→ Manifest Gate
→ report rendering
```

V2 authority MUST NOT 来自 free-form report 的 post-hoc Claim extraction 或 Citation attachment。Renderer MAY 在
derived report 中 paraphrase complete Claim semantics，但 MUST NOT mutate `ClaimRecord`、创建 authoritative
Claim/Citation identity 或修改 Manifest，也不得成为 Data Plane 中的第二个 Claim Generator。

### S5-R03 — Global Reference Scope and Resolution

Canonical Evidence/Finding addresses SHALL 是 task-qualified refs defined by Contracts v1。给定一个 task-qualified
reference，Host MUST：

1. 以 `task_id` 定位 owning Run 中唯一 `ResearchTaskResult`；
2. 只在该 Result 的对应 record collection 中解析 bare ID；
3. 对 Evidence 继续在同一 Result 内解析 `source_id`；
4. 必要时通过该 Run 的 Artifact address 与 locator 解析 exact excerpt；
5. reject unknown、dangling 或 ambiguous reference；
6. MUST NOT 扫描 sibling Results 猜测目标。

不同 Tasks 中相同 bare ID 是不同 canonical addresses。P2-S5 不得按 URL、hash、excerpt 或 semantic similarity 合并
跨 Task canonical Source/Evidence/Finding identity。

### S5-R04 — Claim Generation and Materialization

Model A MAY propose Claim text、materiality、FindingRefs、scope 与 qualifiers。它 MUST NOT 分配 `claim_id`、选择
candidate Evidence、判断 Evidence role/Grounding、创建 Citation identity，或决定 report eligibility/metrics。

Model A 的 output reference authority 只限 Host-visible FindingRefs；其 draft MUST NOT 携带 candidate Evidence、
Evidence Groups、supporting/contradicting refs 或 Grounding fields。

Host SHALL：

- 验证 draft schema、bounds、FindingRef resolution/uniqueness 与 Model A visible allowlist；
- 拒绝 invalid draft，并按 S5-R13 允许 valid siblings 存活；
- 为 admitted drafts 分配 Host-owned、owning Manifest 内唯一的 run-local `claim_id`；
- 按 S5-R14 materialize deterministic ordered `ClaimRecord[]`。

`ClaimRecord.finding_refs` MUST non-empty。Result-level `summary`、`limitations` 与 `conflicts` 只能提供 contextual
hints，不能 authorize Claim。Formal lineage SHALL 是 `ClaimRecord → FindingRef → ResearchFinding`。

FindingRef Host validation 只证明 declared lineage structurally valid；S5 不增加 Claim↔Finding semantic Judge。
Reportability 由完整 Claim proposition 与 Finding-derived Evidence universe 的 Grounding assessment决定。

Rejecting/omitting 一个 sibling draft SHALL NOT 改变另一个 otherwise identical admitted draft 的 deterministic
identity。Exact duplicate 只允许按 Contracts-defined canonical semantic payload 的 identical replay 判断；Host MUST
NOT 使用 string similarity、embedding 或 semantic fuzzy matching deduplicate Claims。

`ClaimRecord` MUST NOT 复制 Evidence refs、Grounding status、Citation IDs、`report_eligible` 或
`revision_required`。

### S5-R05 — Evidence-universe Derivation and Model Projection

对每个 retained Claim，Host MUST 从 validated `finding_refs` 按 Contracts-defined canonical order 确定性派生 candidate
Evidence universe：

```text
ClaimRecord.finding_refs
→ owning ResearchFinding.evidence_ids
→ task-qualified EvidenceRefs
→ exact first-occurrence dedup
```

Model A visible Evidence context 与 Model B admitted Evidence universe 不是同一 authority。Model B universe MUST 在
Claim survivor selection 后重新从 retained FindingRefs 派生并应用独立 Judge admission；Model B 不得扩大该 universe。

Model A MAY 看见 bounded Evidence-aware context，以避免 overgeneralization 并形成 scope/qualifiers，但只能通过
FindingRefs 表达 Claim lineage。Projection composition、canonical traversal 与 admitted context fields SHALL 遵循
Contracts v1。`ResearchTaskResult.status` 不得单独决定 record admission；`PARTIAL/FAILED` Result 中的 valid
published records MAY 使用，但 projection必须同时保留 Contracts要求的status、limitations、conflicts与bounded
error context，execution status不得被解释为Evidence quality。

Model B semantic minimum input SHALL 是：

```text
EvidenceRef
+ exact admitted Evidence excerpt
```

Validated Source metadata MAY 作为 optional best-effort context；不得推断缺失值，metadata 缺失不得阻断 otherwise
valid Evidence。Locator、`source_id` 与 Artifact address 继续用于 Host provenance resolution，但不必成为 Model B
semantic projection。

S5 MAY 对provider materialization时已经可靠可用的Source metadata做Contracts允许的backward-compatible
best-effort enrichment；correctness不得依赖enrichment，也不得改变identity、Artifact semantics或mandatory upstream
schema。

所有 model-facing projections MUST bounded，并与 authoritative Data Plane 分离；不得包含 raw notes、Messages、raw
provider payload、full Result/Artifact、`artifact_ref` 或 model reasoning。Host MUST 为每个 model role 维护 exact visible
allowlist；任何 model-returned reference 必须既能在 Data Plane 解析，也存在于该 role allowlist。

Admission MUST deterministic、whole-unit 且遵循 Contracts-defined order。Authoritative Finding/Evidence unit 不得被
切片；capacity omission 必须产生 degrading issue，不得伪装为 semantic insufficiency。Claim materiality 在 Model A
执行前尚不存在，因此不得影响 upstream Finding/Evidence context admission。

### S5-R06 — Grounding Judge Semantics

Model B SHALL 对：

```text
complete Claim proposition
+ complete admitted Evidence universe
```

返回 overall `ClaimEvidenceVerdict`、material supporting subset、material contradicting subset 与 bounded reason。

Supporting Evidence 是对 Claim 提供 material positive support 并参与 overall assessment 的 Evidence；单条 Evidence
不必独立达到 sufficient support。Contradicting Evidence 是提供 material negative evidence，并参与 overall assessment
或必须披露为 meaningful conflict 的 Evidence；轻微或未 materially 参与判断的 disagreement 不得被收录。

因此 `INSUFFICIENT` verdict MAY 同时具有 non-empty supporting 和/或 contradicting subsets。Evaluated 但未进入两类
material subsets 的 Evidence 由差集确定，不增加 neutral/insufficient Evidence Domain field。

Judge output MUST 满足 Contracts v1 冻结的 subset、unique、disjoint、canonical filtered order 与 verdict-specific
non-empty invariants。Model B owns overall semantic verdict；Host MUST NOT 以 Evidence/Source count、set presence、简单
source labels 或 string matching 替代其整体判断。

Judge SHALL 在可见信息允许时定性考虑 Source authority、directness、methodological limitations、applicability、recency
与 cross-source consistency，但 P2-S5 不建立 calibrated Source/Evidence score。

Grounding reason 只服务 audit/debug/evaluation；它不是 Evidence、Claim 或 Renderer factual authority。Renderer MUST
NOT 消费 reason，Citation 不为 reason 生成 provenance，Gate 不验证其 factual truth。

Judge MUST NOT 创建/修改 Source、Evidence 或 Claim，不得引用 allowlist 外 Evidence、返回 final
`GroundingStatus`、创建 authoritative identity、输出 raw hidden reasoning，或猜测修复 invalid reference。

### S5-R07 — Claim-level Grounding and Five-state Mapping

Host 只接受满足 S5-R06 与 Contracts v1 structural invariants 的 Judge output，并 SHALL 按下表确定性 materialize final
status，不调用第三个 semantic Judge：

| Valid `ClaimEvidenceVerdict` | Material contradiction set | `GroundingStatus` |
|---|---:|---|
| `SUPPORTED` | empty | `SUPPORTED` |
| `SUPPORTED` | non-empty | `SUPPORTED_WITH_CONFLICT` |
| `INSUFFICIENT` | any valid set shape | `INSUFFICIENT` |
| `CONTRADICTED` | non-empty required | `CONTRADICTED` |
| no valid semantic assessment | N/A | `UNASSESSED` |

即使 `INSUFFICIENT` 同时具有 supporting/contradicting refs，status 仍必须为 `INSUFFICIENT`；Host MUST NOT 使用
contradiction-presence heuristic 将其升级为 `CONTRADICTED`。

对于 assessed status，`evaluated_evidence_refs` MUST exactly equal actual ordered Judge input、non-empty，且 reason
present。`UNASSESSED` 严格表示 operational absence of a valid semantic judgment，不得等同 `INSUFFICIENT`；其
evaluated/supporting/contradicting refs 必须为空、reason 必须为 `None`，attempted refs/errors 进入 process issues。

每个 retained Claim MUST 恰好对应一个 `ClaimGroundingRecord`，通过 `claim_id` 绑定，不增加独立 Grounding identity。

### S5-R08 — Materiality, Revision and Report Eligibility

`ClaimMateriality` 只表示 Claim 对回答核心问题的重要程度；material Claim 等于 `HIGH`。它不是 Evidence quality、
Grounding confidence、probability 或 calibrated numeric score。

`revision_required` 与 `report_eligible` SHALL 从 status 派生，不保存为 canonical fields：

| Status | `revision_required` | `report_eligible` |
|---|---:|---:|
| `SUPPORTED` | `False` | `True` |
| `SUPPORTED_WITH_CONFLICT` | `True` | `True` |
| `INSUFFICIENT` | `True` | `False` |
| `CONTRADICTED` | `True` | `False` |
| `UNASSESSED` | `True` | `False` |

`SUPPORTED_WITH_CONFLICT` MUST 进入 V2 Shadow Report，并显式披露 material contradictory Evidence，同时展示覆盖
material supporting/contradicting Evidence 的 citations。Runtime 不要求 calibrated relative-weight narrative、numeric
confidence 或详细 uncertainty wording。

P2-S5 MUST NOT automatic rewrite Claim、重新 Ground、循环到收敛或覆盖 authoritative Claim text。

### S5-R09 — Citation Identity, Completeness and Display

Canonical Citation identity SHALL 是 Contracts v1 定义的 `(claim_id, EvidenceRef)`。Host MUST 为每个 required pair
确定性生成一个且仅一个 Citation；free-form model URL、title 或 display label 均不是 provenance authority。

Required Citation EvidenceRefs：

```text
SUPPORTED
→ supporting_evidence_refs

SUPPORTED_WITH_CONFLICT
→ supporting_evidence_refs ∪ contradicting_evidence_refs

INSUFFICIENT / CONTRADICTED / UNASSESSED
→ empty
```

每个 Claim 的 actual Citation set MUST exact equal status-derived required set；missing、duplicate 或 extra Citation
均使 candidate Manifest structurally invalid。该 invariant 证明 provenance handles 完整，不证明 Renderer prose 或
label placement 在语义上正确。

Canonical Citation/Source/Evidence identity 与 reader-facing display grouping MUST 分离：

- 同一 canonical SourceRecord 下的多个 cited EvidenceRefs SHOULD 共享一个 reader-facing Source label；
- cross-task display grouping 只 MAY 在同一 Research Run / Artifact namespace、resolved Sources 的 validated stored
  URL value exact相同且 `artifact_ref` 相同时发生；
- S5 MUST 直接使用 resolved `SourceRecord.metadata["url"]` 的 stored value，不得自行 canonicalize、normalize、清理
  或推断 URL；当前 S4 writer 在 materialization 前使用 shared upstream `canonicalize_source_url()` 并存储结果，但
  这不是 S5 的职责；
- stored URL 缺失/invalid、stored value不同、Artifact 不同或 Run 不同时 MUST NOT cross-task group；
- display grouping MUST NOT 合并或修改 Citation、EvidenceRef、SourceRecord、ResearchTaskResult 或 provenance
  identity，也不得引入 global registry/cross-run dedup。

`display_label` SHALL 保持derived presentation value，不得存为Citation authority；`citation_id`与display label不是
同一identity。Display labels MUST 由 Host 确定性派生；exact key representation、label ordering与label format属于
PLAN，不属于 stable Contract wire shape。

当 source display entries 被渲染时，V2 Shadow Report SHOULD 提供由 validated available Source metadata 确定性
派生的 bibliography；缺失 author/year/publisher 等 metadata MUST NOT 被推断或伪造。Exact bibliography style 与
formatter属于PLAN/presentation policy。Artifact content identity、run-scoped address与wire encoding由Contracts v1
定义；本SPEC不复制其hash formula或storage details。

### S5-R10 — GroundingManifest and State Boundary

`GroundingManifest` 的 stable envelope 由 Contracts v1 定义。它 SHALL 是 authoritative V2 structured output，且
MUST NOT 包含 copied Source metadata、raw Evidence/Artifact、drafts、process issues、derived metrics、display labels、
Shadow Report、global status 或 evaluator result。

Empty Manifest structurally legal，但不自动表示 pipeline success。Parent SHALL 使用 Contracts v1 定义的
`grounding_manifest`、`global_synthesis_status`、`global_synthesis_issues` 与 `v2_shadow_report` channels 保持
authoritative aggregate、execution status、bounded diagnostics 与 derived report 的职责分离。

Manifest update semantics 只在同一 active Research Run 内成立：Gate 后 atomic one-shot publish；`None → Manifest`
合法；identical replay idempotent；divergent replay 是 contract conflict；禁止 field-wise merge 或 partial publish。
同一Run内status/report采用Host-owned replace/override，issues采用Contracts-defined bounded append/dedup。New
Research Run必须先按S5-R19 reset run-scoped authority。

### S5-R11 — Model / Host Authority and Retry Boundary

Runtime logical model roles SHALL 是：

```text
Model A — Claim Generator
Model B — Grounding Judge
Model C — Shadow Report Renderer
```

三个 roles MAY 复用同一 physical provider/model；具体 mapping 属于 PLAN。External faithfulness evaluator 不是 runtime
Graph role。

Host exclusively owns identity、reference resolution/allowlists、bounds/admission/order、Evidence-universe derivation、
Judge structural validation、final `GroundingStatus`、Citation/display materialization、Manifest Gate、global status 与
issues。Model B exclusively owns overall semantic Evidence verdict。

Retry 只允许用于 transient provider failure、timeout、structured schema/reference validation failure。Valid negative
semantic output（包括 `INSUFFICIENT`、`CONTRADICTED` 或 evaluator FAIL）不得 retry 到期望结果。

Generator retry 前不得发布 authoritative Claim batch；Judge retry 不改变 Claim identity；Renderer retry 使用同一
published Manifest projection；retry exhaustion 必须进入 S5-R13 status/issues policy。Exact attempts、timeout、
backoff、concurrency 与 physical model 属于 PLAN/config。

### S5-R12 — Global Synthesis Publication Gate

P2-S5 SHALL 建立一个 Host-controlled、atomic、validate-not-repair Publication Gate。Gate 验证 structural integrity，
不重新判断医学 entailment。

Candidate Manifest MUST 整体满足 S5-R03、R04、R06、R07、R09、R10 与 R14。Gate-specific aggregate checks 至少包括：

- contract version 与 envelope 合法；
- Claim/Grounding one-to-one binding，无 foreign/orphan records；
- all references resolve，无 dangling/ambiguous references；
- actual Citation pairs 与 required pairs exact match；
- all configured/hard payload bounds 与 canonical ordering成立。

Gate MUST validate, not repair。任一 Gate failure均发布 no Manifest；不得删除 invalid record 后发布剩余 aggregate，
也不得猜测 reference。Valid siblings MAY 在 Gate 前按 S5-R13 存活，但 candidate 必须整体合法后一次发布。

Renderer 位于 Gate 后并使用独立 structural validator；Renderer failure 不回滚 valid Manifest。

### S5-R13 — Failure, Status, Issues and Shadow Fallback

`GlobalSynthesisStatus` 的 stable values 与 issue process contracts 由 Contracts v1 定义。Status semantics SHALL 是：

| Status | Meaning |
|---|---|
| `SUCCESS` | Manifest 已发布；Renderer 或 zero-eligible Host output 成功；没有 observed degradation |
| `PARTIAL` | Manifest 已发布；存在 omission、`UNASSESSED`、capacity overflow、Renderer failure 或其他 degradation |
| `FAILED` | 没有 Manifest 发布；V1 path 与 valid S4 Results仍保留 |

合法 empty Claim batch MAY 形成 empty Manifest；只有 processing 正常完成且未观察 degradation 时才可为
`SUCCESS`。Generator complete failure 或 Gate failure MUST 为 `FAILED` 并发布 no Manifest。

Global Synthesis issues MUST Host-owned、bounded、sanitized、deterministically identified、same-run append/dedup，并
遵循 Contracts v1 的 process contract。不得保存 raw prompt、raw model output、provider payload、unbounded traceback
或 hidden reasoning。Stable issue `stage` 是 open machine-readable string；consumer不得按phase-local enum做closed
validation。Exact Host-produced stage taxonomy与numeric guardrails属于PLAN/process-internal policy。

`global_synthesis_issues` 是 bounded ledger。Final status MUST 从 monotonic Host degradation fact 派生，不得扫描
retained issue records、message 或 severity 重建。一旦同一 execution 观察到 degrading event，该 fact 不得恢复为
`False`；exact storage mechanism属于 PLAN。

Failure semantics：

- invalid Claim draft MAY 被拒绝，valid siblings MAY 继续；omission degrades status；
- per-Claim Judge exhaustion SHALL 产生 strict `UNASSESSED`，不擦除 sibling assessments；
- Citation materialization或Gate failure SHALL 发布 no Manifest；
- Renderer failure SHALL 保留 Manifest、产生 no shadow report 并使 status 为 `PARTIAL`；
- V2 exception MUST 在 `global_synthesis` boundary 被包含，使 legacy V1 path 继续；
- internal pre-publication artifacts MAY 保留在 bounded process-local diagnostics，但不是 authoritative State。

Valid `INSUFFICIENT`/`CONTRADICTED` 是成功 semantic outcomes，本身不是 degradation。All Claims validly negative且无
其他 degradation时，zero-eligible published Manifest MAY 仍为 `SUCCESS`；由 operational Judge failure 导致的
`UNASSESSED` MUST 至少产生 `PARTIAL`。

### S5-R14 — Bounds, Admission, Dedup and Deterministic Ordering

所有 externally materialized collections、model-facing inputs/outputs 与 aggregate payloads MUST 有 hard/configured
bounds。至少必须覆盖 Claim capacity、per-Claim Evidence capacity、各 model role context 与 Manifest payload；具体
numeric limits、tokenizer、safety reserve、timeout 与 concurrency 属于 PLAN/config。每个model role MUST使用独立
budget，并由PLAN为prompt/schema/output/provider overhead保留safety reserve。

Admission MUST proactive、deterministic、whole-unit，并在 model call/Gate 前处理 normal overflow：

- authoritative Finding/Evidence/Claim units 不得为适配 Context 而截断；
- upstream Data Plane 不因 projection omission 被删除；
- normal overflow 保留 legal subset并产生 degrading issue；
- Publication Gate 是 defense-in-depth，不是 normal truncation engine。

Host SHALL 先验证 Model A proposals，再只在 Claim capacity overflow 时按 `HIGH → MEDIUM → LOW` 选择；同 tier 保持
Generator order，survivors 恢复原 Generator order。Claim selection 只发生一次，位于 Grounding 前；Renderer 不得
再次选择或静默遗漏 surviving eligible Claims。Materiality 不得影响 pre-Model-A projection，也不得变成
Grounding/Evidence quality score。

同 Claim Evidence universe只按 exact EvidenceRef first occurrence dedup。Host MAY reject Contracts-defined exact
duplicate Claim draft，但 MUST NOT 使用 fuzzy/semantic similarity。Cross-task Source/Evidence canonical dedup 不属于
S5；S5-R09 display grouping不得改变 Judge universe、Manifest或provenance。

Model A SHOULD propose non-redundant Claims；该prompt-level guidance不得变成Host fuzzy dedup authority。

All Host-materialized collections SHALL 遵循 Contracts v1 冻结的 canonical order。Async completion、dict/set/hash
iteration 或 provider callback timing MUST NOT 成为 ordering authority。

### S5-R15 — Constrained LLM Shadow Renderer

P2-S5 SHALL 使用 LLM Renderer 生成 V2 Shadow Report。Renderer 只消费 `MedicalResearchBrief` 与 bounded
report-eligible Claim projection。每个 Claim projection MUST 包含完整 Claim proposition 与 Grounding status，并 MAY
包含该 Claim 已经 materialize 的 bounded material supporting / contradicting Evidence projection，以及 optional
validated Source metadata。

Renderer MUST NOT 消费 raw notes、Messages、provider snippets、unvalidated drafts、full Artifacts 或
`ClaimGroundingRecord.reason`，也不得创建/修改 authoritative Claim、Evidence、Grounding、Citation 或 Manifest。
Model C MUST NOT 重新搜索、扩大 Evidence universe、修改 Evidence role，或把 evaluated-but-non-material Evidence 提升为
Renderer factual authority。Model C MAY paraphrase complete Claim semantics并基于 admitted material Evidence形成自然叙事，
但 paraphrase 没有 Domain authority。

Model C SHALL 使用 structured output 决定 section count、section title、section order、paragraph organization 与
paragraph prose，并提供 body paragraph → Claim ID bindings。具体 internal DTO 由 PLAN 定义，但 runtime MUST 保证：

- every model-generated body paragraph 至少绑定一个 valid report-eligible Claim ID；
- section title non-empty、sanitized、bounded；section title 不是 body paragraph，不要求 Claim binding；
- Host 保留 validated Model output 的 section / paragraph order；
- every surviving report-eligible Claim 至少出现一次；
- repeated Claim occurrence bounded，并复用同一 canonical Citation set；
- Model-generated unbound body paragraph 被拒绝；Host MAY 生成 fixed report title 或非正文 boilerplate；
- Host 不尝试 semantic classify factual/non-factual model paragraphs。

Renderer MUST NOT 输出 authoritative URL、Citation identity 或 numbering；Host 按 S5-R09 的 observable display
semantics和PLAN-defined deterministic policy注入labels。一个 paragraph MAY 绑定多个 Claims；runtime只保证
structural binding，不保证 no-new-proposition，也
不增加 runtime semantic verifier/repair loop。

Renderer-visible Evidence context MUST 只来自 `ClaimGroundingRecord.supporting_evidence_refs` 与
`contradicting_evidence_refs`，使用 deterministic bounded whole-unit admission；authoritative Evidence excerpt不得为适配
Renderer context被截断。Renderer context omission不得删除 required Citation、改变 GroundingStatus或修改Manifest。

`SUPPORTED_WITH_CONFLICT` 的 first canonical paragraph occurrence MUST 明确披露 material contradictory Evidence。
Host SHALL 在该 occurrence deterministic 插入最小 conflict marker，并展示 covering supporting / contradicting
references；Model C MAY 提供更自然的冲突叙事。Runtime不要求Host判断该prose是否准确表达relative Evidence weight或
detailed uncertainty。Primary occurrence、Evidence admission、label ordering与repeated occurrence mechanics由PLAN实现，
但必须满足本 requirement 的 observable behavior。

如果没有 report-eligible Claim，Host MUST NOT 调用 Model C，而应生成 deterministic no-grounded-claim shadow output，
不得创建 fake Claim/Citation。若没有 degradation，该路径 MAY 为 `SUCCESS`。

### S5-R16 — External Renderer Faithfulness Evaluation

P2-S5 SHALL 提供 evaluation-only semantic faithfulness evaluator，位于 compiled graph、Parent State、Manifest Gate 与
global status 之外。

Evaluator SHALL 以 `ClaimRecord.text + scope + qualifiers` 的完整 proposition 为基准，并 SHOULD 测量 unsupported
proposition、scope expansion、qualifier loss、conflict omission、Claim misrepresentation 与 Citation/Claim placement
mismatch。

Evaluator result MUST NOT 写入 runtime State/Manifest、改变 global status、成为 S5 runtime hard gate或触发 automatic
report/Claim repair。Valid semantic FAIL 不得 retry 到 PASS；只有 evaluator execution/timeout/schema failure MAY 按
Eval policy retry。Exact model、dataset、rubric 与 threshold 属于 PLAN/Evaluation。

### S5-R17 — Derived Shadow Metrics

P2-S5 MUST 暴露 Contracts v1 定义的 status counts 与 coverage metrics：

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

Metrics MUST 从 valid Manifest 由 Host 确定性派生、可重复计算、non-authoritative，且不得进入 Manifest。Coverage
denominator 为零时 value MUST 为 `None`。Exact formulas 以 Contracts v1 为 canonical authority。

P2-S5 不重新暴露 Citation completeness coverage metrics，不将 metrics 合并为 uncalibrated scalar Groundedness，也
不设置 production threshold。

### S5-R18 — Runtime Placement and V1/V2 Shadow Migration

Parent graph target SHALL 是：

```text
research_supervisor
→ global_synthesis
→ final_report_generation
→ END
```

`global_synthesis` 是唯一新增 Parent orchestration node。Generator、Judge、materializers、Gate 与 Renderer 默认是
internal stages/helpers；P2-S5 不修改 Supervisor–Researcher Tool Loop，不新增 Planner、scheduler、`Send`、queue 或
background topology。

Legacy V1 Report继续是 official/compatibility output；GroundingManifest 是 authoritative V2 structured shadow output；
V2 Shadow Report 是 derived evaluation artifact。V1/V2 SHOULD 使用同一 Run 的 S4 Results；V2 failure不得阻止
legacy final report，Renderer failure不得擦除 Manifest。

Shadow mode保证 output isolation 与 failure isolation，但不保证 latency isolation。Global Synthesis 增加 V1
end-to-end latency是 accepted S5 tradeoff；不得为 latency isolation 引入 fan-out、parallel V1/V2 branch、`Send`、
queue 或 background job。

### S5-R19 — Research Run State Lifecycle and Provenance Isolation

Research Run SHALL 表示一个 research request 从 top-level bootstrap 到 finalization 的 logical Deep Research
execution lifecycle。它不是单个 user message、`graph.invoke()`、Supervisor iteration、ResearchTask、Researcher
invocation、search call 或 arbitrary node。继续同一 execution 的 clarification、interrupt、resume、iterations 与
retries MUST 保持同一 Run。

Lifecycle hierarchy SHALL 是：

```text
Conversation / checkpoint lifetime
        >
Research Run lifetime
        >
ResearchTask lifetime
```

Active Parent State 同一时间 MUST 最多承载一个 authoritative Research Run。Conversation messages MAY 跨 Runs
保留，但 prior-run structured provenance不得自动进入新 Run Data Plane。

一个 active Run MUST 对应一个 `artifact_run_id` namespace；Run 内全部 Supervisor/Researcher work传播同一值。只有
finalized Run 后的新 research request bootstrap 才创建 fresh namespace；clarification/resume若继续同一 logical Run
MUST 保留原值。

新 Run MUST 在接纳任何新 Source、Evidence 或 Result 前，reset/replace Contracts v1 定义的全部 run-scoped State，
形成 fresh brief/process context、empty Result/legacy ledgers、no prior reports/Manifest/status、empty issues 与 fresh
degradation fact。Exact State values、bootstrap discriminator、reducer/reset mechanism 与 API mapping 属于 PLAN；其
resulting authority isolation 不得改变。

Manifest replay、status/report replacement、issues append/dedup 与 degradation monotonicity只在同一 active Run 内
成立。New Run reset后，Run B Manifest不与Run A构成 divergent replay。

State reset是logical authority reset，不要求删除physical ArtifactStore data。Prior Results/Artifacts不再是active
authority。P2-S5不得引入multi-run Result ledger、ResearchRun registry、run-qualified EvidenceRef、cross-run
Evidence/Citation reuse、cross-run provenance merge或historical Manifest registry。

Reader-facing Source grouping只在同一 owning Run/Artifact namespace内有效；不得以bare `artifact_ref` 推断cross-run
equality。PLAN SHALL 将 current entry/checkpoint/interrupt/resume APIs 映射到上述 lifecycle，但不得重新定义 Run
boundary。

---

## 4. End-to-end Trust Chains（Informative）

本节只提供架构 review 视图，不建立独立 normative requirements；冲突时以 Contracts v1 与 §3 对应 Rxx 为准。

### 4.1 Evidence Grounding provenance

```text
V2 model-generated body paragraph
→ claim_id
→ ClaimRecord
→ ClaimGroundingRecord
→ Citation(claim_id, EvidenceRef)
→ EvidenceRef(task_id, evidence_id)
→ ResearchTaskResult
→ EvidenceRecord
→ SourceRecord
→ ArtifactStore
→ artifact[locator]
→ exact source-derived excerpt
```

### 4.2 Semantic derivation lineage

```text
ClaimRecord
→ FindingRef(task_id, finding_id)
→ ResearchFinding
→ ResearchTaskResult
```

Finding lineage 回答“Agent 如何综合出 Claim”；Evidence provenance 回答“哪些 external Evidence materially
support/contradict Claim”。两条 lineage必须保持不同。

---

## 5. Acceptance Traceability Matrix

Acceptance 只定义 observable pass condition，不重复 requirement semantics。具体 test classes、fixtures、commands 与
verification sequence由 PLAN、TASKS和CHECKLIST定义。

| Requirement | Observable acceptance |
|---|---|
| `S5-R01` | Global Synthesis只从frozen structured inputs建立authority；V2 failure不修改valid S4 Results或upstream provenance。 |
| `S5-R02` | Manifest authority在report rendering前形成；不存在report-first authoritative path，Renderer不能修改Domain authority。 |
| `S5-R03` | Task-qualified refs只在owning Result解析；unknown/dangling/ambiguous refs被拒绝，且不扫描siblings。 |
| `S5-R04` | Claims由Host materialize；FindingRefs non-empty；完整proposition、declared lineage、sibling-stable identity和exact-only dedup成立。 |
| `S5-R05` | Judge Evidence universe精确来自retained Findings；Model A/B allowlists独立且Model B不能扩大Host-derived universe。 |
| `S5-R06` | Judge verdict及material supporting/contradicting subsets满足Contracts定义的所有合法组合，reason不成为report authority。 |
| `S5-R07` | 每个retained Claim恰好一个Grounding；five-state mapping与strict `UNASSESSED` representation成立。 |
| `S5-R08` | revision/report eligibility可由status唯一派生；conflicted Claim可报告且no automatic repair成立。 |
| `S5-R09` | Actual Citation pairs精确等于required pairs；display grouping不改变canonical provenance，并遵守same-run grouping条件。 |
| `S5-R10` | Manifest envelope合法；same-run publication atomic，identical replay幂等，divergent replay冲突且无partial merge。 |
| `S5-R11` | Model/Host权限不越界；valid negative semantic outcome不被retry到期望结果。 |
| `S5-R12` | Invalid aggregate不发布且Gate不修复；valid aggregate只在完整通过Gate后一次发布。 |
| `S5-R13` | `SUCCESS/PARTIAL/FAILED`与frozen failure semantics一致；status由sticky degradation fact而非bounded issue ledger派生。 |
| `S5-R14` | Overflow admission、dedup与canonical output在replay、async completion和unordered containers下保持确定。 |
| `S5-R15` | Model C可组织bounded sections并只读取eligible Claim/material Evidence projection；每个body paragraph绑定eligible Claim且覆盖全部eligible Claims；Host保留Citation authority并注入labels/conflict marker；zero-eligible跳过Model C。 |
| `S5-R16` | Faithfulness evaluator与runtime State/Gate/status隔离，并评估完整Claim proposition及frozen violation dimensions。 |
| `S5-R17` | Required metrics可从Manifest重算、零分母为`None`、不进入Manifest且不构成release threshold。 |
| `S5-R18` | Parent只新增`global_synthesis` node；V2 failure不阻断V1，且不引入forbidden latency-isolation topology。 |
| `S5-R19` | Same logical Run保持Artifact namespace；new Run在admission前隔离prior structured provenance，conversation context不等于provenance reuse。 |

---

## 6. Non-goals and Deferred Decisions

### 6.1 Explicit non-goals

P2-S5 SHALL NOT 实现：

- RAG、embedding、reranking、Vector DB/Index；
- durable EvidenceStore/ProvenanceStore、persistent Citation/Manifest registry；
- global Source/Evidence identity或cross-run dedup/reuse；
- Parent sibling Source/Evidence registry；
- ClaimEvidenceRelation/EvidenceGroup proof graph或relation identity；
- semantic/fuzzy Claim dedup；
- calibrated Evidence/Source quality score、hard-coded evidence hierarchy或required source classifier；
- full medical/PICO ontology；
- iterative Claim/Report repair或runtime semantic verifier loop；
- production Grounding threshold、release gate或V2 rollout；
- `Send`、durable queue、distributed execution、background job或deployment redesign；
- temporal Source versioning或unrelated upstream refactor。

### 6.2 PLAN/Evaluation decisions

以下不由本 SPEC 冻结具体实现：

- physical model/provider mapping；
- numeric context budgets、field bounds、safety reserves、timeouts、retry counts、backoff与concurrency；
- internal model projection/structured-output DTO shape；
- LangGraph State reset/reducer/bootstrap helper；
- helper/module decomposition与ID encoding；
- exact bibliography formatter implementation；
- evaluator model、dataset、rubric与calibrated threshold；
- concrete test files、fixtures、commands与implementation order。

这些 implementation choices必须满足 Contracts v1 与 §3 requirements，不得以“PLAN-level”名义改变 observable
semantics。

---

## 7. Freeze and Reopen Policy

P2-S5 current decision state：

```text
D00–D19
→ RESOLVED
→ PROMOTED TO CONTRACTS V1 AND SPEC

CB01–CB06
→ RESOLVED
→ AUTHORITY-PLACEMENT PROMOTED / RESYNCED

P2_S5_SPEC.md
→ FROZEN
→ CONTRACT-BOUNDARY / RENDERER RESYNCED
```

CB01–CB06 已完成 canonical contract surface refinement：stable records/identity 留在Contracts；observable S5
behavior留在本SPEC；diagnostic taxonomy、display representation/ordering与bibliography style下沉PLAN。该resync不改变
D00–D19的Domain semantics。P01–P10随后已由PLAN final revision独立关闭；D14最新Renderer structure/Evidence
visibility resolution已同步到Contracts §3.14与S5-R15。

后续 source mapping或implementation若暴露新的Domain、State、identity、topology、failure、migration或acceptance
ambiguity，必须重新打开对应Clarification并完成canonical promotion，不得Silent Spec Mutation。

下一工作流仍是：

```text
P2_S5_PLAN.md AUDITED DRAFT / READY_FOR_FREEZE REVIEW
→ P2_S5_TASKS.md FINAL REVISION
→ P2_S5_CHECKLIST.md FINAL REVISION
→ implementation
```
