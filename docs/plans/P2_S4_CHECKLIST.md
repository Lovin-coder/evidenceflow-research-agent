# P2-S4 — Conformance Checklist

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

- [ ] Graph topology 未改变。
- [ ] 现有 Supervisor–Researcher Tool Loop 保持不变。
- [ ] 未引入 `QueryRecord`、`RetrievalObservation`、`Claim` 或 `Citation`。
- [ ] 未引入 RAG、embedding retrieval 或 reranker。
- [ ] 未引入 Parent sibling Source/Evidence registries 或 store-backed ID-only Result。
- [ ] 未将 ArtifactStore 扩展成 durable EvidenceStore。
- [ ] structured Data Plane 与 model-facing rendering 保持分离。
- [ ] `CandidateChunk`、`WebpageSelection` 与 `SearchExecutionResult` 仍是 internal representation，不是
  first-class Domain Model。

---

## 3. SearchResult / Source Acceptance

- [ ] Provider `SearchResult` 未被自动视为 authoritative `SourceRecord`。
- [ ] 只有具有 usable normalized source content 的 accepted result 才 materialize `SourceRecord`。
- [ ] 缺少或无法提供 usable source content 的 result 只记录 retrieval/ingestion warning 或 trace。
- [ ] 缺少或无法提供 usable source content 的 result 不生成 `SourceRecord` 或 `EvidenceRecord`。
- [ ] Provider snippet、formatted content、Tool Error 或 model summary 未作为 raw-content fallback 越过
  source-content gate。
- [ ] 每个 accepted `SourceRecord` 都能解析到 persisted normalized artifact。
- [ ] ArtifactStore 是 run-scoped 而不是 Researcher-call-scoped。
- [ ] originating Researcher 返回后，published `artifact_ref` 在同一 Run 内仍可解析。

---

## 4. Candidate Chunking

- [ ] Chunk boundary 完全由 Host 生成。
- [ ] Locator 针对 persisted normalized artifact。
- [ ] Locator 使用 `[start, end)`。
- [ ] `chunk.text == artifact[start:end]`。
- [ ] 每个 Chunk contiguous。
- [ ] 相同 normalized artifact 与 chunking config/version 产生相同 Chunk boundaries、IDs 与 ordering。
- [ ] 每个 Chunk 满足 frozen boundedness / maximum-size guardrail。
- [ ] 当前 MVP 未使用 overlap。
- [ ] `CandidateChunk` 未升级为 first-class Domain Model。

---

## 5. Evidence

- [ ] LLM 不生成 Evidence excerpt。
- [ ] LLM 不生成 Evidence locator。
- [ ] LLM 不生成 Evidence ID。
- [ ] selected Candidate ID 在 materialization 前经过 Host validation。
- [ ] Unknown Candidate ID 不生成 `EvidenceRecord`。
- [ ] `EvidenceRecord.excerpt` 可确定性回到 Source artifact。
- [ ] `EvidenceRecord.excerpt == artifact[start:end]`。
- [ ] Evidence content hash 与 exact excerpt 一致。
- [ ] One Evidence → exactly one Source。
- [ ] 每个 `EvidenceRecord.source_id` 都能解析到 authoritative `SourceRecord`。
- [ ] Different Sources 的 Evidence 未 semantic merge。
- [ ] `AIMessage`、model summary、Tool Error 与其他 process artifacts 未进入 authoritative Evidence collection。

---

## 6. Runtime

- [ ] Tavily structured execution 同时产生 Data Plane 与 model-facing content。
- [ ] 下游不通过 parse `ToolMessage` 恢复 Source/Evidence。
- [ ] Raw artifact 未进入新的 structured Graph State。
- [ ] Graph State 仅保存 artifact reference、compact metadata、bounded Evidence excerpt 与 structured records。
- [ ] Researcher 看到的是 bounded Source/Evidence rendering，而不是 raw webpage dump。
- [ ] Derived summary 在 model-facing content 中被明确标记为 non-evidence。
- [ ] 非 Tavily Tool path 未被无关重构。
- [ ] 现有 Tool-call concurrency 与 observation ordering 保持不变。

---

## 7. Compression

- [ ] `compress_research` 只引用已有 Evidence IDs。
- [ ] Unknown Evidence ID 被 Host validator 拒绝。
- [ ] Compression 不创建或修改 Evidence。
- [ ] Compression 不创建 Source 或重新绑定 Source/Evidence identity。
- [ ] Structured Findings 与 legacy `compressed_research` dual-write。
- [ ] 每个 `ResearchFinding.evidence_ids` 都能解析到 authoritative Evidence collection。
- [ ] `ResearchTaskResult` 保留 downstream 所需的可解析 Source/Evidence/Finding provenance。
- [ ] Supervisor 主要 observe Findings、summary、limitations、conflicts 与 status，而不是完整 raw Evidence。
- [ ] 完整 structured result 与 bounded Supervisor model context 保持分离。

---

## 8. Cross-Agent Provenance Publication

- [ ] `ResearchTaskResult` inline compact `source_records` / `evidence_records`。
- [ ] `ResearchTaskResult` has no dangling Source/Evidence references。
- [ ] `source_ids` exactly match `source_records` IDs and ordering。
- [ ] `evidence_ids` exactly match `evidence_records` IDs and ordering。
- [ ] Every Evidence Source resolves within the same Result。
- [ ] Every Finding Evidence resolves within the same Result。
- [ ] Every published `artifact_ref` survives the Researcher boundary。
- [ ] Artifact round-trip reproduces the exact Evidence excerpt。
- [ ] Recomputed excerpt hash matches `EvidenceRecord.hash`。
- [ ] Raw Source artifact is not embedded in Result。
- [ ] Result total provenance payload respects configured bounds independently of search iteration count。
- [ ] Full inline Result is not automatically rendered into the Supervisor prompt。
- [ ] `FAILED` / `PARTIAL` Result may retain valid Source/Evidence records。
- [ ] `ResearcherOutputState` publishes the self-contained Result without publishing complete Researcher process State。
- [ ] Parent/Supervisor State has no sibling Source/Evidence registry。

---

## 9. Failure

- [ ] Tavily request/Search failure 不产生 Source 或 Evidence。
- [ ] Tool Error 不进入 Evidence。
- [ ] 缺少 usable source content 不产生 Source/Evidence。
- [ ] Selector failure 不伪造 Evidence。
- [ ] Unknown selected Candidate ID 不 materialize Evidence。
- [ ] Evidence provenance validation failure 只拒绝 invalid Evidence，不删除其他 valid artifacts。
- [ ] Compression failure 不删除已经 valid 且在 failure boundary 可见的 Source/Evidence。
- [ ] Selector/compression/publication failure 不擦除 prior valid compact records。
- [ ] Publication gate failure 不发布 invalid/dangling Result。
- [ ] Sibling result failure 不删除成功 sibling results。
- [ ] Source/Artifact 已成功 materialize 后发生 selector failure时，已有 Source/Artifact 得到保留。
- [ ] Task status 继续遵循 S3 frozen `SUCCESS / PARTIAL / FAILED` semantics。
- [ ] 未为 hard child exception 隐式引入 checkpoint recovery、retry lifecycle、durable persistence 或 topology
  change。

---

## 10. Dual-write 与 Compatibility

- [ ] Structured Source/Evidence 与 legacy `ToolMessage` rendering 来自同一次 Search execution。
- [ ] Structured ResearchFinding 与 legacy `compressed_research` 来自同一次 compression。
- [ ] Structured artifacts 是 authoritative data path。
- [ ] Legacy strings 仅作为 compatibility/model-facing projection。
- [ ] Legacy ODR Researcher/Supervisor path 仍可运行。
- [ ] 未通过解析 legacy string 重建 authoritative structured records。
- [ ] S3 shadow Result empty-ledger payload 仍可被 S4 consumer 读取。
- [ ] Populated S4 producer/consumer 按 atomic upgrade policy 使用同一 v1 schema。

---

## 11. Validation Evidence

- [ ] Source ID determinism test 通过。
- [ ] Normalization / Candidate chunk determinism tests 通过。
- [ ] Locator / artifact exact-slice tests 通过。
- [ ] Evidence ID、excerpt 与 hash tests 通过。
- [ ] Usable source-content gate boundary tests 通过。
- [ ] Invalid Candidate selection tests 通过。
- [ ] Process/Evidence isolation tests 通过。
- [ ] Cross-Source Evidence independence tests 通过。
- [ ] Compression Finding-resolution tests 通过。
- [ ] Failure-preservation tests 通过。
- [ ] Result inline ledger / deterministic projection contract tests 通过。
- [ ] Same-Result Source/Evidence/Finding resolution tests 通过。
- [ ] Compiled Researcher boundary artifact-lifetime test 通过。
- [ ] Result provenance total-bound tests 通过。
- [ ] Supervisor full-ledger exclusion test 通过。
- [ ] Structured/legacy dual-write tests 通过。
- [ ] Graph topology regression test 通过。
- [ ] Targeted P2-S4 pytest 通过。
- [ ] Ruff 通过。
- [ ] Scoped Mypy 通过，或 baseline limitation 已如实记录。
- [ ] `compileall` 通过。
- [ ] `git diff --check` 通过。
- [ ] Full existing test suite 未出现 P2-S4 regression。
- [ ] Controlled real medical runtime smoke 通过并已记录 runtime evidence。

---

## 12. Scope

- [ ] Temporal Source Versioning 仍为 **DEFERRED**。
- [ ] Cross-run Search Cache / freshness policy 仍为 **DEFERRED**。
- [ ] Evidence diversity scoring 仍为 **DEFERRED**。
- [ ] Semantic Evidence merge 仍未进入 P2-S4。
- [ ] Production database / distributed ArtifactStore 仍未进入 P2-S4。
- [ ] Durable EvidenceStore / cross-run Evidence persistence 仍为 **DEFERRED**。
- [ ] Global Evidence identity / cross-run Source dedup 仍为 **DEFERRED**。
- [ ] Embedding lifecycle / vector index synchronization 仍为 **DEFERRED**。
- [ ] Artifact retention/GC、object-storage migration、transactional persistence 仍为 **DEFERRED**。
- [ ] Vector index 未被描述为 authoritative provenance storage。
- [ ] Claim / Citation / Groundedness 未提前进入 P2-S4。
- [ ] Final report architecture 未在 P2-S4 中重构。
- [ ] 未将 deferred work 写成 P2-S4 已实现能力。

---

## 13. Closeout

- [ ] `P2_S4_RETRO.md` 已记录 Implemented、Deviation、Deferred、Tests 与 Runtime evidence。
- [ ] `CONTRIBUTION_MAP.md` 已同步 P2-S4 validated status。
- [ ] 所有未勾选条目均有明确 blocker、risk 或 deferred disposition。
- [ ] P2-S4 满足 Exit Criteria，可以进入 closeout commit。
