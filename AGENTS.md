# EvidenceFlow Development Instructions

## 1. Project Goal

EvidenceFlow is an evidence-centric medical deep research Agent developed from
a frozen Open Deep Research baseline.

It is now an independently evolving project-owned fork.

Engineering priorities are:

```text
correctness
→ semantic clarity
→ maintainability
→ testability
→ readability
→ reuse
```

Detailed implementation guidance lives in:

```text
docs/application_track/EVIDENCEFLOW_ENGINEERING_GUIDELINES.md
```

Read it before substantial project-owned implementation work.

## 2. Authority

Follow repository authority in this order:

```text
AGENTS.md
    ↓
EVIDENCEFLOW_ENGINEERING_GUIDELINES.md
    ↓
EVIDENCEFLOW_CONTRACTS_V1.md
    ↓
phase *_SPEC.md
    ↓
phase *_CLARIFICATIONS.md
    ↓
phase *_PLAN.md
    ↓
phase *_TASKS.md
    ↓
phase *_CHECKLIST.md
    ↓
implementation
```

Lower-level artifacts MUST NOT silently override higher-level semantics.

If implementation requires changing a frozen Domain contract, State semantic,
identity/reference rule, topology, persistence rule, migration rule, failure
rule, phase scope, or acceptance criterion, STOP the affected work and surface
the ambiguity through the phase clarification process.

Do not make architecture-sensitive decisions implicitly during coding.

## 3. Phase Workflow

Every implementation phase follows:

```text
SPEC
→ CLARIFICATIONS
→ PLAN
→ TASKS
→ CHECKLIST
→ IMPLEMENTATION
→ CLOSEOUT
```

- `*_SPEC.md` defines audited baseline, scope, non-goals, invariants,
  requirements, acceptance criteria, and architecture-sensitive OPEN decisions.
- `*_CLARIFICATIONS.md` records alternatives, human decisions, rationale,
  impact, deferred work, and canonical promotion status.
- `*_PLAN.md` maps frozen semantics to repository files, implementation
  structure, runtime integration, sequencing, migration, failure handling, and
  validation. PLAN MUST NOT invent architecture to fill a SPEC gap.
- `*_TASKS.md` decomposes the frozen PLAN into bounded and reviewable work.
- `*_CHECKLIST.md` records reproducible verification and closeout evidence. It
  is not a second PLAN.

Blocking OPEN decisions prevent PLAN/TASKS freeze and affected implementation.

A commit existing in history does not by itself prove review or acceptance.

Use phase-scoped identifiers such as:

```text
S5-R01
S5-D01
S5-T01
```

and preserve traceability through PLAN, TASKS, CHECKLIST, tests, and closeout.

## 4. Architecture and Contract Constraints

- Preserve the Supervisor–Researcher Tool Loop unless frozen design explicitly
  changes it.
- Preserve runtime-adaptive Supervisor behavior.
- Do not introduce Send, RAG, durable queues, background workers, new
  persistence systems, or unrelated platform changes implicitly.
- Process artifacts MUST NOT be treated as external factual Evidence.
- Raw or large Source artifacts MUST NOT be persisted directly in Graph State.
- Preserve stable Source/Evidence provenance and explicit task/result
  contracts.
- `ResearchTaskResult` MUST NOT publish dangling provenance references.
- Presentation artifacts MUST NOT become provenance authority.
- Model output MUST NOT own stable identity where Contracts assign identity to
  the Host.
- Host logic MUST NOT replace frozen Model semantic authority with undocumented
  heuristics.
- Schema changes require contract tests and canonical documentation updates.

## 5. Implementation Hard Rules

### Code structure

- Split functions by semantic responsibility, not by line count.
- Do not extract helpers solely to shorten a function.
- Graph nodes and application coordinators SHOULD remain orchestration-thin.
- Keep deterministic Domain logic, side effects, and Graph State updates
  clearly separated.
- Avoid God modules. Prefer small semantic packages when a subsystem contains
  multiple independently testable responsibilities.
- Do not create speculative abstractions or frameworks without a current
  consumer.
- Module-private helpers SHOULD use a leading underscore.
- Do not use generic `utils.py` modules as dumping grounds for Domain-specific
  behavior.

### State and authority

- Internal helpers SHOULD return typed values or outcomes instead of mutating
  LangGraph State directly.
- Important State fields must have clear writer/lifecycle ownership.
- Reducer-backed reset behavior must use the explicitly planned framework
  mechanism; do not assume an empty collection clears an append reducer.
- Concurrent completion order MUST NOT define authoritative ordering.

### Validation and failure

- Validators reject invalid input; they MUST NOT silently invent semantic
  repairs.
- Publication Gates are validate-not-repair.
- Do not silently convert operational failures into valid semantic
  empty/success results.
- No bare `except:`.
- Broad `except Exception` is allowed only at documented isolation boundaries.
- Do not swallow cancellation or system-level control-flow exceptions as
  ordinary business failures.

### Retry

- Every logical Model stage MUST have one semantic retry authority.
- Do not multiply logical attempts by stacking independent semantic retry
  layers.
- Valid negative semantic results MUST NOT be retried merely to obtain a more
  favorable result.

### Typing

Use:

```text
TypedDict
→ LangGraph State schemas

Pydantic
→ stable serialized Contracts and runtime/model-validated structured IO

dataclass(frozen=True)
→ immutable Host-internal value/execution objects
```

- Avoid `dict[str, Any]` across project-owned semantic boundaries.
- New EvidenceFlow modules MUST NOT introduce new mypy errors.
- Touched project-owned code SHOULD NOT introduce new type debt.
- Do not use broad `# type: ignore`, `# noqa`, or rule disabling merely to make
  checks pass.

## 6. Change Discipline

- Make the smallest coherent change required by the current task.
- Separate BASELINE, IMPLEMENTED, and PROPOSED.
- Do not refactor unrelated code.
- Project-owned modules MAY be reorganized when the frozen PLAN explicitly
  requires clearer ownership, readability, or maintainability.
- Do not modify dependencies or lockfiles unless explicitly required and
  reported.
- Do not build future-phase infrastructure during the current phase.
- Do not weaken tests, validators, typing, or acceptance gates to make a task
  pass.

## 7. Task Execution

Each implementation task should define:

- Goal
- Frozen Requirements Implemented
- Allowed Files
- Forbidden Changes
- Implementation Boundaries
- Required Tests
- Stop Conditions
- Acceptance Criteria
- Expected Diff Shape

Task scope is binding.

STOP instead of improvising if a task unexpectedly requires:

- a new stable Domain field;
- changed State semantics;
- changed identity/reference scope;
- changed topology;
- new persistence behavior;
- a new dependency;
- new Model authority;
- new fallback behavior;
- weakened acceptance criteria.

## 8. Validation

For relevant changes:

- run focused pytest;
- run required regression tests;
- run ruff;
- run mypy for applicable new/touched EvidenceFlow code.

Tests should primarily verify observable behavior and frozen invariants rather
than private call structure.

External Model/search calls are integration or evaluation work, not unit tests.

Do not add production behavior solely for testing.

## 9. Documentation

Python comments and docstrings MUST remain in English.

Document business semantics, invariants, authority boundaries, and non-obvious
trade-offs rather than restating code.

Project-owned Domain contracts and non-trivial reducers, lifecycle controllers,
adapters, Publication Gates, renderers, and failure boundaries should have
concise useful documentation.

Regression tests should identify the invariant they protect when the reason is
not obvious.

## 10. Completion Report

Every completed implementation task must report:

- Files Changed
- Behavior Changed
- Requirements/Decisions Implemented
- Tests Run
- Static Checks Run
- Remaining Risks
- Remaining TODOs / Deferred Work
- Unexpected Scope Changes

Do not claim runtime or integration validation when only static or mocked tests
were executed.

## 11. Core Engineering Principle

EvidenceFlow implementation should preserve this model:

```text
LLMs propose bounded semantics.

The Host owns deterministic identity, resolution, validation,
materialization, ordering, State ownership, and publication.

Graph orchestration remains explicit.

Typed boundaries prevent implicit data contracts.

Failure behavior remains observable.

Tests protect invariants.

Code structure should make the architecture visible.
```
