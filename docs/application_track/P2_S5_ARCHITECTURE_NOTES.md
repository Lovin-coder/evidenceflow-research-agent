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
