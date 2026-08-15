# P2-S3 — Domain & Evidence Contracts Retro

## 0. Status

**Status**: Implementation Review Candidate  
**Date**: 2026-08-15  
**Closeout**: Not complete

P2-S3 的 domain/state/runtime implementation candidate 已完成 deterministic validation。真实模型 smoke
在 external OpenAI-compatible endpoint 等待响应时阻塞并被人工终止，因此本 Step 尚未满足 closeout
条件，也尚未进入 commit。

## 1. Delivered

- 新增严格 Pydantic v2 contracts：MedicalResearchBrief、EvidenceNeed、MedicalResearchTask、
  SourceRecord、EvidenceRecord、ResearchFinding、ResearchTaskResult。
- Parent/Supervisor/Researcher State 增加 structured channels 和 ID-aware reducers。
- `write_research_brief` 直接生成 typed Brief，并由 deterministic renderer dual-write legacy Markdown。
- LLM-facing ConductResearch 只表达 task semantics；Host 使用 namespaced tool-call identity 构造 Task。
- Researcher output 接通 shadow ResearchTaskResult，同时保留 compressed_research/raw_notes。
- Supervisor 对 child execution failure 和 concurrency admission failure 逐任务产出 FAILED Result，并保留
  legacy error ToolMessage。
- 保留原有 Supervisor–Researcher topology、Agentic planning loop、search providers 和 final writer path。

## 2. Validation Evidence

Deterministic tests：

```text
.venv/bin/pytest -q \
  tests/test_domain_models.py \
  tests/test_state_contracts.py \
  tests/test_p2_s3_runtime.py

24 passed
```

Static checks：

```text
.venv/bin/ruff check <changed source and tests>
All checks passed

MYPYPATH=src .venv/bin/mypy --explicit-package-bases --follow-imports=skip \
  src/open_deep_research/domain_models.py \
  src/open_deep_research/state.py \
  src/open_deep_research/deep_researcher.py
Success: no issues found in 3 source files
```

测试覆盖 strict schema、status wire values、provenance references、process/raw artifact rejection、
identity replay/conflict semantics、frozen topology、brief dual-write、host task IDs、0/1/N delegation、
admission/child/tool/compression failure 和 shadow Result。

Repository-wide bare `pytest -q` 额外收集 upstream `src/legacy/tests/test_report_quality.py` 时，在 fixture
setup 因 `--research-agent` option 未注册而报错；该次运行时已有的 P2-S3 tests 全部通过，随后补充的
compiled Researcher boundary test 也通过，targeted suite 最终为 24 passed。该 legacy
harness 配置问题已存在于本阶段范围外，P2-S3 不修改其 conftest/runner。

## 3. Runtime Smoke Attempt

受控 smoke 计划只运行：

```text
Question
→ Clarify routing
→ MedicalResearchBrief
→ Supervisor
→ MedicalResearchTask tool call
```

并在首个 ConductResearch 后停止，不执行搜索。

结果：Clarify 的 disabled routing 正常；首次 `write_research_brief` external structured-output request 在
120 秒以上没有收到 response，人工终止。Trace 位于模型 HTTP response wait；没有进入 Supervisor 或
Tavily。该结果说明当前 external endpoint/runtime environment 未提供可完成的 smoke，不构成 contract
unit-test failure，也不能计为 smoke pass。

## 4. Design Adjustments Applied

- Task ID ownership 冻结为 Host/Dispatcher，而不是模型。
- status 冻结为 uppercase Python enum members 和 lowercase wire values。
- Result reducer 冻结为 distinct append、identical replay dedup、conflicting replay failure。
- P2-S3 shadow Result 的空 structured collections 表示尚未 population，不表示没有使用来源。
- raw artifact invariant 限定于新 structured channels；legacy ToolMessage/raw_notes fallback 是不可扩大的
  临时例外，P2-S4 必须移除。

## 5. Remaining Before Closeout

- [ ] external model endpoint 可用后重跑真实 structured Brief → Task smoke；
- [ ] human core diff review；
- [ ] 确认 P2-S3 canonical docs 最终 freeze；
- [ ] 记录 human learning checkpoints；
- [ ] 创建 closeout commit 并将 Contribution Map 状态升级为 IMPLEMENTED/VALIDATED；
- [ ] 确认工作树只包含预期文件并 clean。

## 6. Deferred to P2-S4

- Tavily result → SourceRecord/EvidenceRecord ingestion；
- ResearchFinding 和 Result structured collections 的真实 population；
- ArtifactStore Protocol / LocalArtifactStore；
- 移除 legacy raw-content fallback；
- locator + hash 对真实 artifact 的端到端审计。

Claim、Citation、Claim–Evidence Grounding、Evidence Store 和 RAG 仍按计划分别延期到 P2-S5 或 Future。
