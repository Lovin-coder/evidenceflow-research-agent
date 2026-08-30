# P2-S5 — Global Claim, Citation and Grounding Closeout Record

## 0. Status and verdict

| Item | Result |
|---|---|
| Phase | P2-S5 |
| Closeout date | 2026-08-29 |
| Verification base | `dc43cd83b4f2c6716c82cd791d0ad28fe9e0d51a` |
| Branch | `p2-s5-claim-citation-grounding` |
| T00–T23 | **DONE** |
| S5-R01–R19 | **19/19 PASS** |
| Implementation verification | **PASS** |
| Real-provider smoke | **PASS** |
| External evaluator | **IMPLEMENTED / DETERMINISTICALLY VERIFIED / LIVE OPERATIONAL FAILURE RECORDED** |
| Contract drift | **NONE** |
| SPEC drift | **NONE** |
| Architecture drift | **NONE** |
| Implementation commit | Not created; the user did not request a commit |

P2-S5 introduces the frozen Claim-first Global Synthesis path while preserving the
existing Supervisor–Researcher Tool Loop and the V1 final writer. The Host owns
task-qualified resolution, deterministic Claim/Citation identity, Grounding and
publication validation, ordering, display labels, report bindings, State updates,
and lifecycle admission. Models remain bounded semantic proposers for Claims,
Grounding verdicts, and report prose/structure.

## 1. Implementation footprint

### 1.1 Added production package

`src/open_deep_research/global_synthesis/` contains:

- `types.py` — immutable internal DTOs, frozen limits, receipts, and the single
  Host retry/request boundary;
- `projection.py` — strict task-qualified resolution and bounded whole-unit Model
  A/B/C projections;
- `claims.py` — Model A invocation, sibling validation, exact deduplication,
  deterministic Claim identity, and capacity selection;
- `grounding.py` — Finding-derived Evidence universes, concurrent Model B
  execution, five-state Grounding validation, and strict UNASSESSED handling;
- `publication.py` — exact Citation materialization, replay disposition, derived
  metrics, and the atomic validate-not-repair Manifest Gate;
- `renderer.py` — display grouping, deterministic bibliography, renderer
  projection validation, Host citation injection, and report finalization;
- `pipeline.py` — process-local staged orchestration and bounded issue/status
  outcomes without Parent State writes;
- `__init__.py` — the minimal public pipeline facade.

### 1.2 Modified production surfaces

- `domain_models.py` adds the stable P2-S5 Claim, Grounding, Citation, and Manifest
  Contracts under `evidenceflow.contracts.v1`.
- `state.py` adds Global Synthesis status/issues, Research Run lifecycle State, and
  frozen reducer/reset behavior.
- `deep_researcher.py` adds P01/D20 lifecycle admission, the thin
  `global_synthesis` node, the frozen graph edge, bounded V1 fallback, and terminal
  Run finalization.
- `configuration.py` adds the frozen Model B concurrency limit.
- `evidence_ingestion.py` and `utils.py` add compact best-effort Source metadata
  without changing Evidence identity or persisting provider payloads.
- `prompts.py` adds the bounded Model A, Model B, and Model C prompts.

No dependency, lockfile, queue, worker, Send path, RAG/vector store, generalized
provider framework, generalized evaluation platform, or second provenance/Citation
authority was added.

### 1.3 Tests

Focused tests cover stable serialization, reducers, P01/D20 checkpoint behavior,
retry timing and ownership, task-qualified resolution, Claim identity/salvage,
Grounding concurrency and all five states, Gate mutation/replay/metrics, Citation
completeness, display grouping, renderer coverage/conflict disclosure, pipeline and
Parent graph isolation, external evaluator behavior, and the opt-in provider smoke.

## 2. Deterministic verification

### 2.1 Focused P2-S5 and directly affected coverage — PASS

```text
.venv/bin/pytest \
  tests/test_p2_s5_*.py \
  tests/test_evidence_ingestion.py \
  tests/test_tavily_evidence_search.py \
  tests/test_state_contracts.py \
  tests/test_p2_s4_runtime.py -q

150 passed, 1 skipped, 26 warnings
```

The one skip is the real-provider smoke, which is intentionally disabled during
deterministic testing. The same smoke was executed separately under T22.

### 2.2 Full deterministic regression — PASS

```text
.venv/bin/pytest -q \
  --deselect src/legacy/tests/test_report_quality.py::test_response_criteria_evaluation

190 passed, 1 skipped, 1 deselected, 48 warnings
```

Compared with the accepted T00 baseline of 72 passed, 1 deselected, and 48
warnings, P2-S5 adds deterministic coverage without a regression failure. The
legacy live-provider quality test remains excluded from ordinary deterministic
testing as frozen.

### 2.3 Ruff — no new P2-S5 violations

The canonical target retains exactly the accepted 12 pre-existing violations in
untouched evaluation scripts:

```text
.venv/bin/ruff check src/open_deep_research tests

Found 12 errors.
```

The explicit new/touched S5 production and test target passes:

```text
All checks passed!
```

No unrelated evaluation script was modified to make the baseline green.

### 2.4 Mypy — no new P2-S5 errors

The bounded full production invocation with imports skipped reports the accepted
nine pre-existing errors, all in `src/open_deep_research/utils.py`. The other 14
new/touched production modules pass together:

```text
Success: no issues found in 14 source files
```

The external evaluator and provider-smoke modules also pass their scoped mypy
target. No blanket ignore, broad configuration change, or unrelated legacy type
repair was introduced.

### 2.5 Diff quality — PASS

`git diff --check` passes. Intended untracked source/test files were separately
included in Ruff, mypy where applicable, and deterministic test validation. The
pre-existing user-owned `AGENTS.md` change and unrelated untracked governance file
were preserved and excluded from P2-S5 ownership.

## 3. Controlled real-provider smoke

T22 Task Status is `DONE`; Smoke Outcome is `PASS`.

The initial sandbox attempt stopped before any provider request because the
sandbox-injected SOCKS proxy required an unavailable optional `socksio` package.
Following the environment policy, the unchanged smoke was rerun through the
approved unrestricted network path with proxy variables removed. It completed the
actual frozen control flow:

| Role/gate | Result |
|---|---|
| Model A | 1 request, 0 retries, 25.881s |
| Model B | 2 Claim-local requests, 0 retries, 7.306s and 9.632s |
| Manifest Gate | PASS |
| Model C | 1 request, 0 retries, 50.499s |
| Claims | 2 |
| Grounding | 2 SUPPORTED; all other states 0 |
| Citations | 2 |
| Renderer | MODEL_C_PASS |
| GlobalSynthesisStatus | SUCCESS |
| Issues | none |

The physical A/B/C mapping was
`openai:qwen3.7-plus-2026-05-26` for all three configured roles. Claims and
Grounding were produced by the real configured models; no Claim was invented to
force downstream calls.

The external evaluator live entry executed with the frozen default `gpt-4.1`, but
the configured endpoint returned `NotFoundError` because that model is not exposed.
This operational failure is recorded separately and does not change the required
runtime Smoke Outcome from PASS. Evaluator structure, all six fixed dimensions,
operational retry, and terminal semantic FAIL behavior are deterministically
verified.

## 4. Authority and failure audit

- Contracts v1 and the frozen SPEC were not changed.
- P01/D20 preserves framework-admitted conflicting HumanMessage occurrences while
  leaving cursor, Run identity/status, artifacts, Results, Manifest, reports, and
  issues unchanged.
- Model A proposes Claim semantics and FindingRefs only; the Host assigns identity.
- Model B cannot enlarge the Host-derived Evidence universe and no Host heuristic
  overrides a valid semantic verdict.
- Publication remains atomic and validate-not-repair; invalid replay envelopes are
  contained without regenerating or replacing an existing Manifest.
- Model C owns bounded section organization and prose, while the Host owns eligible
  Claims, Claim bindings, citations, labels, bibliography, conflict disclosure,
  coverage, and final-size validation.
- Ordinary pre-Gate failure produces no Manifest and FAILED; post-Gate renderer
  failure preserves the Manifest and produces PARTIAL; cancellation propagates.
- The graph-external evaluator does not enter runtime State, the Manifest, the Gate,
  or the public Global Synthesis API.
- V2 failure cannot erase or block Results, notes, raw notes, or the bounded V1 final
  writer path.

## 5. Known non-blocking limitations

- The external evaluator default `gpt-4.1` model is unavailable at the configured
  endpoint; its live operational failure is recorded separately from runtime PASS.
- Twelve accepted Ruff findings remain in untouched legacy evaluation scripts.
- Nine accepted mypy errors remain in `src/open_deep_research/utils.py`.
- Existing Pydantic/LangGraph deprecation warnings remain unchanged from the
  deterministic baseline.

## 6. Closeout conclusion

T00–T23 are complete, S5-R01–R19 are 19/19 PASS, relevant Contract invariants pass,
focused and full deterministic suites pass, no new S5 Ruff or mypy violations were
introduced, diff quality passes, and the required real-provider smoke passes.

P2-S5 implementation is ready for final implementation review and commit/closeout.
