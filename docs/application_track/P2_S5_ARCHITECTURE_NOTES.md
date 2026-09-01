# Source Identity, Artifact Address, and Reader-facing Display Grouping

> **Authority status:** This note is informative only and carries no independent normative force. Canonical Source、
> Evidence、Artifact 与 Citation semantics 以 `EVIDENCEFLOW_CONTRACTS_V1.md` 为准；reader-facing grouping behavior
> 以 `P2_S5_SPEC.md` S5-R09 为准；internal representation、ordering 与 bibliography formatting 以
> `P2_S5_PLAN.md` 为准。

本文只提供 P2-S5 identity layers 的 mental model。核心思想是：authoritative provenance、Artifact resolution 与
reader-facing presentation 解决不同问题，不因为显示层去重而合并。

---

## 1. Source provenance identity

在 P2-S4 / P2-S5 authoritative provenance 中，一个 Source 的 canonical address 是：

```text
(task_id, source_id)
```

它回答：这条 `SourceRecord` 属于哪个 `ResearchTaskResult`，以及在该 Result 中是哪一条 Source。

不同 Tasks 即使 stored URL 和 Artifact content 相同，也继续保留不同的 task-qualified Source addresses：

```text
Task T1 → Source S1
Task T2 → Source S7

(T1, S1) != (T2, S7)
```

Current S5 design does not introduce cross-task canonical Source merge。

---

## 2. Artifact provenance address

`artifact_ref` 不是 Source identity，也不是 filesystem path。它是交给 `ArtifactStore.put_text()` 的最终 logical text
value 的 content-addressed reference；exact wire encoding 由 Contracts v1 定义，本文不维护第二份公式。

`ArtifactStore` 按 `artifact_run_id` 隔离，因此完整可解析 address 是：

```text
(artifact_run_id, artifact_ref)
```

可以理解为：

```text
artifact_run_id = run-scoped namespace
artifact_ref    = content-addressed reference
```

Physical directory、filename 与 storage backend 都不属于这个 identity model。

---

## 3. `artifact_ref` equality 的准确含义

Artifact persistence 前通常存在 upstream preparation：

```text
provider content
    ↓
configured truncation / cleanup
    ↓
normalize_source_text()
    ↓
final logical text value
    ↓
ArtifactStore.put_text()
    ↓
artifact_ref
```

因此，同一个 Run 中相同 `artifact_ref` 表示 EvidenceFlow 实际持久化并审计的 final logical text content 相同。
它不证明：

- original provider response 完全相同；
- original webpage bytes 完全相同；
- 截断边界之后的原始内容相同；
- 两个不同 Runs 共享同一 Artifact address。

例如，两个 provider payload 在 configured truncation 之后可能得到相同 final text，进而得到相同
`artifact_ref`，即使未持久化的尾部内容不同。

---

## 4. Why Artifact identity is sufficient for EvidenceFlow audit

EvidenceFlow 实际能够审计和重放的是 persisted logical Artifact，而不是未持久化的完整 provider payload：

```text
SourceRecord.artifact_ref
        ↓
ArtifactStore in owning artifact_run_id
        ↓
persisted logical Artifact
        ↓
EvidenceRecord.locator
        ↓
exact Evidence excerpt
```

这个边界足以支持 locator replay、exact excerpt verification 与 Evidence → Source provenance audit。

---

## 5. Reader-facing grouping eligibility

Reader-facing Citation display 是 derived presentation view，不是新的 provenance identity。

跨 Task Source entries 只有在以下三个条件同时成立时，才具备共享一个 reader-facing Source entry 的资格：

```text
same Research Run
AND
same validated stored URL value
AND
same artifact_ref
```

其中 URL comparison 直接使用 resolved `SourceRecord.metadata["url"]` 的 validated stored value，并采用 exact stored
string equality。Current S4 writer 在 materialization 前使用 shared upstream URL canonicalizer，但 S5 grouping layer
不重新 canonicalize、normalize、clean 或 infer URL。

URL unavailable、stored value不同、Artifact不同或Run不同的 entries 保持分开。Reader-facing grouping leaves all
canonical Citation、EvidenceRef 与 SourceRecord addresses unchanged。

---

## 6. Three identity layers

### Layer 1 — Source provenance identity

```text
(task_id, source_id)
```

回答：provenance graph 中这条 Source 是谁？

用于 Source resolution、Evidence → Source binding、task-local audit 与 canonical Data Plane。

### Layer 2 — Artifact provenance address

```text
(artifact_run_id, artifact_ref)
```

回答：EvidenceFlow 实际持久化并审计的是哪份 logical Artifact？

用于 ArtifactStore resolution、locator/excerpt replay 与 provenance validation。

### Layer 3 — Reader-facing grouping eligibility

```text
same Run
+ exact validated stored URL equality
+ artifact_ref equality
```

回答：多个 canonical Citations 是否可以在当前报告中共享一个 Source reference entry？

这是 presentation eligibility condition，不是新的 Domain identity 或 stable serialized type。

---

## 7. Cross-task grouping example

假设：

```text
Task T1
Source S1
stored URL = https://example.com/paper
artifact_ref = artifact:sha256:AAA
Evidence E1, E2

Task T2
Source S7
stored URL = https://example.com/paper
artifact_ref = artifact:sha256:AAA
Evidence E9
```

Canonical provenance 继续是：

```text
Sources:
(T1, S1)
(T2, S7)

Evidence:
(T1, E1)
(T1, E2)
(T2, E9)
```

Canonical Citations 也继续逐 `(claim_id, EvidenceRef)` 存在。由于这些 Sources 属于同一 Research Run，并具有 exact
equal stored URL 与相同 `artifact_ref`，reader-facing report may show one shared Source label。Audit view 仍可展开所有
contributing Sources 与 EvidenceRefs。

这体现：

> reader-facing dedup without provenance dedup

---

## 8. Grouping cases

| Scenario | Reader-facing outcome |
|---|---|
| Same Run、same stored URL、same persisted Artifact | May share one Source entry |
| Same stored URL、different Artifact | Remain separate |
| Different stored URL、same Artifact | Remain separate |
| Stored URL unavailable | Remain separate across Tasks |
| Same `artifact_ref` string across different Runs | Does not imply shared Artifact identity or grouping eligibility |

URL equality alone不能证明两个 Tasks 审阅的是同一份 persisted content；Artifact equality alone也不能证明两个不同
Source locations 是同一个 reader-facing source。三个 grouping conditions 共同避免这两类误合并。

---

## 9. Architectural summary

```text
Source provenance identity
!=
Artifact provenance address
!=
Reader-facing grouping eligibility
```

三者分别回答：

1. Who is this Source in the provenance graph?
2. Which persisted logical Artifact was actually audited?
3. Which Citations may share one reader-facing Source entry in this Run?

Reader-facing grouping leaves unchanged：

- `Citation`；
- `EvidenceRef`；
- `SourceRecord`；
- `ResearchTaskResult`；
- `source_id` / `evidence_id` / `task_id`；
- `artifact_ref` 与 `ArtifactStore` namespace semantics。

It does not introduce global Source/Evidence identity、cross-run dedup、persistent Source registry 或 provenance merge。

---

## 10. Design principle

> Deduplicate at the lowest-authority layer that actually needs deduplication.

```text
Canonical Data Plane
→ preserve exact task-scoped provenance

Derived Presentation View
→ reduce duplicate reader-facing references when eligibility conditions hold
```

这比把 Source identity 升级为跨 Task/global identity 更小、更清晰，也保持 Evidence-level auditability。

# ClaimDraftBatch Provider Schema 与 Runtime Salvage 边界分析

## 背景

EvidenceFlow 的 Global Synthesis 阶段中：

- ClaimDraft 表示 Model A 生成的 Claim proposal；
- ClaimRecord 表示经过 Host validation、identity assignment 和 provenance binding 后的 canonical record。

当前链路：

Model A
→ ClaimDraftBatch
→ ClaimDraft validation
→ ClaimRecord materialization

其中：

ClaimDraft 不代表可信最终对象，而是模型生成后的中间 proposal。

Host 仍然拥有最终 validation ownership。

## 当前设计中的 ClaimDraftBatch 取舍

当前 ClaimDraftBatch 使用 raw sibling container：

claims: list[object]

该设计不是临时绕过，也不是类型缺失，而是为了满足 EvidenceFlow 的 reliability 目标：

- sibling-level validation；
- invalid sibling isolation；
- partial salvage；
- 避免单个错误 Claim 导致整个 batch failure。

如果直接使用：

claims: list[ClaimDraft]

Pydantic nested validation 会表现为 batch atomic validation：

- 任意 sibling 不满足 ClaimDraft contract；
- 整个 ClaimDraftBatch 构造失败；
- 其他合法 sibling 无法继续 materialize。

因此：

list[object]

体现的是：

Runtime salvage boundary。

它保证 Host 可以逐 sibling 判断：

valid sibling:
→ ClaimDraft
→ ClaimRecord

invalid sibling:
→ diagnostic issue

而不是整个 batch 失败。

## 当前暴露的问题

该设计同时带来了 Provider-facing schema 弱化问题。

由于：

claims: list[object]

structured output schema 无法向模型明确暴露 ClaimDraft 字段。

Provider 看到：

claims:
  array
    items: {}

而不是：

claims:
  array
    items:
      text
      materiality
      finding_refs
      qualifiers

因此：

- Model A 缺少明确 wire contract；
- 可能生成语义正确但字段不符合 Host contract 的 JSON；
- Host validation 可以发现问题，但无法提前约束模型输出。

该问题属于：

Provider-facing schema 与 Runtime validation ownership 的边界问题。

不是：

- ClaimDraft domain contract 错误；
- ClaimRecord 设计错误；
- Grounding 设计错误；
- Manifest / Publication 设计错误。

## Considered Solutions

### Solution 1: list[ClaimDraft]

优势：

- Provider schema 完整；
- Structured Output 约束增强；
- 模型输出格式更加稳定。

问题：

- 重新引入 batch atomic validation；
- invalid sibling 会导致整个 batch rejection；
- 与 EvidenceFlow 当前 sibling salvage 设计冲突。

当前不采用。

### Solution 2: list[ClaimDraft | object]

优势：

表面上同时包含 ClaimDraft schema 和 raw object 能力。

问题：

联合 schema 会退化为宽松 object 分支：

- Provider 约束不可靠；
- 合法 sibling 也不会稳定获得 ClaimDraft runtime 类型；
- 仍需要 Host 二次 validation。

当前不推荐。

### Solution 3: SkipValidation[SerializeAsAny[ClaimDraft]]

目标：

同时满足：

- Provider schema 暴露 ClaimDraft；
- runtime 保留 raw sibling；
- Host 继续拥有 validation ownership。

该方向属于：

minimal invasive fix。

实施前需要验证：

- generated JSON schema；
- Structured Output provider compatibility；
- runtime object behavior；
- serializer behavior。

### Solution 4: Custom Admission Layer（未来升级方向）

未来更彻底的架构方向：

LLM JSON output

↓

Custom Admission Layer

↓

ClaimDraft validation

↓

ClaimRecord materialization

该方案进一步解耦：

- Provider-facing generation schema；
- Runtime admission；
- Domain contract。

优势：

- 明确 LLM output 是 untrusted artifact；
- 支持更细粒度 failure isolation；
- 更符合复杂 Agent production system 的可靠性设计。

但当前阶段不实施。

原因：

- S5 frozen semantics 已满足；
- 当前问题属于 schema boundary 优化；
- 引入 custom admission 会扩大修改范围。

## Current Decision

当前保持：

ClaimDraft
→ ClaimRecord

领域边界不变。

保持：

ClaimDraftBatch sibling salvage 设计。

Custom Admission Layer 记录为未来 architecture upgrade option，而不是当前 S5 implementation requirement。
