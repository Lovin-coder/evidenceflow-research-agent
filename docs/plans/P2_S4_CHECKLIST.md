# P2-S4 — Conformance Checklist

> Status: **CORRECTIVE IMPLEMENTATION COMPLETE / DETERMINISTICALLY VALIDATED / HUMAN REVIEW ACCEPTED**.
> Closeout classification: `COMPLETE_WITH_RUNTIME_SMOKE_INCOMPLETE`.
> The external full-graph smoke remains separately blocked as documented below.

## 1. 使用规则

本 Checklist 用于验证 P2-S4 implementation 是否符合：

```text
EVIDENCEFLOW_CONTRACTS_V1.md
→ P2_S4_SPEC.md
→ P2_S4_CLARIFICATIONS.md
→ P2_S4.md
→ P2_S4_TASKS.md
```

所有条目在取得对应 deterministic test、integration evidence 或 runtime evidence 后才能勾选。发现与 frozen
SPEC 冲突时，不得通过修改 Checklist 静默放宽约束；必须停止受影响实现并返回 Clarification / SPEC review。

---

## 2. Architecture

- [x] Graph topology 未改变。
- [x] 现有 Supervisor–Researcher Tool Loop 保持不变。
- [x] 未引入 `QueryRecord`、`RetrievalObservation`、`Claim` 或 `Citation`。
- [x] 未引入 RAG、embedding retrieval 或 reranker。
- [x] 未引入 Parent sibling Source/Evidence registries 或 store-backed ID-only Result。
- [x] 未将 ArtifactStore 扩展成 durable EvidenceStore。
- [x] structured Data Plane 与 model-facing rendering 保持分离；Host execution issues 不依赖 bounded
  `ToolMessage` 反向重建。
- [x] `CandidateChunk`、`WebpageSelection` 与 `SearchExecutionResult` 仍是 internal representation，不是
  first-class Domain Model。

---

## 3. SearchResult / Source Acceptance

- [x] Provider `SearchResult` 未被自动视为 authoritative `SourceRecord`。
- [x] 只有具有 usable normalized source content 的 accepted result 才 materialize `SourceRecord`。
- [x] 缺少或无法提供 usable source content 的 result 只记录 retrieval/ingestion warning 或 trace。
- [x] 缺少或无法提供 usable source content 的 result 不生成 `SourceRecord` 或 `EvidenceRecord`。
- [x] Provider snippet、formatted content、Tool Error 或 model summary 未作为 raw-content fallback 越过
  source-content gate。
- [x] 每个 accepted `SourceRecord` 都能解析到 persisted normalized artifact。
- [x] 默认 ArtifactStore namespace 在同一 owning graph run 的全部节点/子图迭代中稳定。
- [x] originating Researcher 返回后，published `artifact_ref` 在同一 Run 内仍可解析。

---

## 4. Candidate Chunking

- [x] Chunk boundary 完全由 Host 生成。
- [x] Locator 针对 persisted normalized artifact。
- [x] Locator 使用 `[start, end)`。
- [x] `chunk.text == artifact[start:end]`。
- [x] 每个 Chunk contiguous。
- [x] 相同 normalized artifact 与 chunking config/version 产生相同 Chunk boundaries、IDs 与 ordering。
- [x] 每个 Chunk 满足 frozen boundedness / maximum-size guardrail。
- [x] 当前 MVP 未使用 overlap。
- [x] `CandidateChunk` 未升级为 first-class Domain Model。

---

## 5. Evidence

- [x] LLM 不生成 Evidence excerpt。
- [x] LLM 不生成 Evidence locator。
- [x] LLM 不生成 Evidence ID。
- [x] selected Candidate ID 在 materialization 前经过 Host validation。
- [x] Unknown Candidate ID 不生成 `EvidenceRecord`。
- [x] `EvidenceRecord.excerpt` 可确定性回到 Source artifact。
- [x] `EvidenceRecord.excerpt == artifact[start:end]`。
- [x] Evidence content hash 与 exact excerpt 一致。
- [x] One Evidence → exactly one Source。
- [x] 每个 `EvidenceRecord.source_id` 都能解析到 authoritative `SourceRecord`。
- [x] Different Sources 的 Evidence 未 semantic merge。
- [x] `AIMessage`、model summary、Tool Error 与其他 process artifacts 未进入 authoritative Evidence collection。

---

## 6. Runtime

- [x] Tavily structured execution 同时产生 Data Plane 与 model-facing content。
- [x] 下游不通过 parse `ToolMessage` 恢复 Source/Evidence。
- [x] Raw artifact 未进入新的 structured Graph State。
- [x] Graph State 仅保存 artifact reference、compact metadata、bounded Evidence excerpt 与 structured records。
- [x] Researcher 看到的是 bounded Source/Evidence rendering，而不是 raw webpage dump。
- [x] Derived summary 在 model-facing content 中被明确标记为 non-evidence。
- [x] 非 Tavily Tool path 未被无关重构。
- [x] 现有 Tool-call concurrency 与 observation ordering 保持不变。

---

## 7. Compression

- [x] `compress_research` 只引用已有 Evidence IDs。
- [x] Unknown Evidence ID 被 Host validator 拒绝。
- [x] Compression 不创建或修改 Evidence。
- [x] Compression 不创建 Source 或重新绑定 Source/Evidence identity。
- [x] Structured Findings 与 legacy `compressed_research` dual-write。
- [x] 每个 `ResearchFinding.evidence_ids` 都能解析到 authoritative Evidence collection。
- [x] `ResearchTaskResult` 保留 downstream 所需的可解析 Source/Evidence/Finding provenance。
- [x] Supervisor 主要 observe Findings、summary、limitations、conflicts 与 status，而不是完整 raw Evidence。
- [x] 完整 structured result 与 bounded Supervisor model context 保持分离。

---

## 8. Cross-Agent Provenance Publication

- [x] `ResearchTaskResult` inline compact `source_records` / `evidence_records`。
- [x] `ResearchTaskResult` has no dangling Source/Evidence references。
- [x] `source_ids` exactly match `source_records` IDs and ordering。
- [x] `evidence_ids` exactly match `evidence_records` IDs and ordering。
- [x] Every Evidence Source resolves within the same Result。
- [x] Every Finding Evidence resolves within the same Result。
- [x] Every published `artifact_ref` survives the Researcher boundary。
- [x] Artifact round-trip reproduces the exact Evidence excerpt。
- [x] Recomputed excerpt hash matches `EvidenceRecord.hash`。
- [x] Raw Source artifact is not embedded in Result。
- [x] deterministic state admission 主动满足 configured Result provenance payload bound。
- [x] Publication Gate 使用相同 canonical measurement 二次验证 Result provenance payload bound。
- [x] Full inline Result is not automatically rendered into the Supervisor prompt。
- [x] `FAILED` / `PARTIAL` Result may retain valid Source/Evidence records。
- [x] `ResearcherOutputState` publishes the self-contained Result without publishing complete Researcher process State。
- [x] Parent/Supervisor State has no sibling Source/Evidence registry。

---

## 9. Failure

- [x] Tavily request/Search failure 不产生 Source 或 Evidence。
- [x] Tool Error 不进入 Evidence。
- [x] 缺少 usable source content 不产生 Source/Evidence。
- [x] Selector failure 不伪造 Evidence。
- [x] Unknown selected Candidate ID 不 materialize Evidence。
- [x] Evidence provenance validation failure 只拒绝 invalid Evidence，不删除其他 valid artifacts。
- [x] Recoverable Finding/compression materialization failure 不删除已经 valid 且在 child boundary 可见的
  Source/Evidence。
- [x] Selector/recoverable compression failure 不擦除 prior valid compact records；真正的 Publication
  failure 拒绝整个 invalid candidate Result。
- [x] Publication gate failure 不发布 invalid/dangling Result。
- [x] Sibling result failure 不删除成功 sibling results。
- [x] Source/Artifact 已成功 materialize 后发生 selector failure时，已有 Source/Artifact 得到保留。
- [x] Task status 继续遵循 S3 frozen `SUCCESS / PARTIAL / FAILED` semantics。
- [x] 未为 hard child exception 隐式引入 checkpoint recovery、retry lifecycle、durable persistence 或 topology
  change。

---

## 10. Dual-write 与 Compatibility

- [x] Structured Source/Evidence 与 legacy `ToolMessage` rendering 来自同一次 Search execution。
- [x] Structured ResearchFinding 与 legacy `compressed_research` 来自同一次 compression。
- [x] Structured artifacts 是 authoritative data path。
- [x] Legacy strings 仅作为 compatibility/model-facing projection。
- [x] Legacy ODR Researcher/Supervisor path 仍可运行。
- [x] 未通过解析 legacy string 重建 authoritative structured records。
- [x] S3 shadow Result empty-ledger payload 仍可被 S4 consumer 读取。
- [x] Populated S4 producer/consumer 按 atomic upgrade policy 使用同一 v1 schema。

---

## 11. Validation Evidence

- [x] Source ID determinism test 通过。
- [x] Normalization / Candidate chunk determinism tests 通过。
- [x] Locator / artifact exact-slice tests 通过。
- [x] Evidence ID、excerpt 与 hash tests 通过。
- [x] Usable source-content gate boundary tests 通过。
- [x] Invalid Candidate selection tests 通过。
- [x] Process/Evidence isolation tests 通过。
- [x] Cross-Source Evidence independence tests 通过。
- [x] Compression Finding-resolution tests 通过。
- [x] Failure-preservation tests 通过。
- [x] Result inline ledger / deterministic projection contract tests 通过。
- [x] Same-Result Source/Evidence/Finding resolution tests 通过。
- [x] 未显式配置 `artifact_run_id` 时，compiled multi-node/multi-iteration artifact-lifetime test 通过。
- [x] Configured Result provenance admission-bound 与 Publication Gate defense-in-depth tests 通过。
- [x] Structured execution issue 在对应 warning 不可见于 bounded `ToolMessage` 时仍正确降级 status。
- [x] Invalid Finding batch 保全 Source/Evidence 且不越过 Researcher child boundary。
- [x] Supervisor full-ledger exclusion test 通过。
- [x] Structured/legacy dual-write tests 通过。
- [x] Graph topology regression test 通过。
- [x] Targeted P2-S4 pytest 通过。
- [x] Ruff 通过。
- [x] Scoped Mypy 通过，或 baseline limitation 已如实记录。
- [x] `compileall` 通过。
- [x] `git diff --check` 通过。
- [x] Full existing test suite 未出现 P2-S4 regression。
- [ ] Controlled real medical runtime smoke 通过并已记录 runtime evidence。— **BLOCKED**：清理 SOCKS
  变量后 model endpoint、Tavily endpoint 与 structured Tavily executor 均通过；single Researcher 已产生
  artifacts，但在 60 秒上限内没有返回 Result，因此未继续 full graph，且未增加 `socksio`。

---

## 12. Scope

- [x] Temporal Source Versioning 仍为 **DEFERRED**。
- [x] Cross-run Search Cache / freshness policy 仍为 **DEFERRED**。
- [x] Evidence diversity scoring 仍为 **DEFERRED**。
- [x] Semantic Evidence merge 仍未进入 P2-S4。
- [x] Production database / distributed ArtifactStore 仍未进入 P2-S4。
- [x] Durable EvidenceStore / cross-run Evidence persistence 仍为 **DEFERRED**。
- [x] Global Evidence identity / cross-run Source dedup 仍为 **DEFERRED**。
- [x] Embedding lifecycle / vector index synchronization 仍为 **DEFERRED**。
- [x] Artifact retention/GC、object-storage migration、transactional persistence 仍为 **DEFERRED**。
- [x] Vector index 未被描述为 authoritative provenance storage。
- [x] Claim / Citation / Groundedness 未提前进入 P2-S4。
- [x] Final report architecture 未在 P2-S4 中重构。
- [x] 未将 deferred work 写成 P2-S4 已实现能力。

---

## 13. Closeout

- [x] `P2_S4_RETRO.md` 已记录 post-review findings、root cause、corrective implementation、tests 与
  Runtime evidence。
- [x] `CONTRIBUTION_MAP.md` 已同步 corrective validation evidence。
- [x] 所有未勾选条目均有明确 blocker、risk 或 deferred disposition。
- [x] Corrective diff 已完成人工验收，四个 focused implementation boundary 均已接受。
- [x] Closeout 状态保留 full-graph runtime smoke 未完成的限定，没有将授权跳过改写为 PASS。
- [x] T17 满足 Exit Criteria，已具备创建 corrective closeout commit 的条件。

## 14. Unchecked-item disposition

唯一未勾选项是 controlled real medical full-graph runtime smoke。T17 corrective implementation 与
deterministic validation 已完成；外部 staged smoke 的已通过边界与 60 秒停止条件记录在
`P2_S4_RETRO.md`，不得通过增加依赖或伪造完成状态关闭该项。
