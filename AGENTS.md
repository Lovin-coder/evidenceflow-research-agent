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

Detailed engineering guidance lives in:

```text
docs/application_track/EVIDENCEFLOW_ENGINEERING_GUIDELINES.md
```

Consult the relevant sections before substantial project-owned implementation
work. Do not re-read the entire document by default when only a bounded section
is relevant.

## 2. Authority Model

Engineering governance and semantic authority are related but distinct.

Repository engineering governance:

```text
AGENTS.md
↓
EVIDENCEFLOW_ENGINEERING_GUIDELINES.md
```

Frozen semantic and implementation authority:

```text
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

Engineering governance defines how work is performed.

Frozen phase artifacts define what behavior, semantics, scope, architecture,
dependencies, and acceptance criteria must be implemented.

Lower-level artifacts MUST NOT silently override higher-level frozen semantics.

If engineering constraints and frozen semantic authority appear incompatible,
STOP the affected work and surface the conflict. Do not silently reinterpret
either authority.

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
- Avoid God modules.
- Prefer small semantic packages when a subsystem contains multiple
  independently testable responsibilities.
- Do not create speculative abstractions or frameworks without a current
  consumer.
- Module-private helpers SHOULD use a leading underscore.
- Do not use generic `utils.py` modules as dumping grounds for Domain-specific
  behavior.

### State and authority

- Internal helpers SHOULD return typed values or outcomes instead of mutating
  LangGraph State directly.
- Important State fields must have clear writer and lifecycle ownership.
- Reducer-backed reset behavior must use the explicitly planned framework
  mechanism.
- Do not assume an empty collection clears an append reducer.
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

## 6. Context and Observation Discipline

Use the smallest repository working set that is sufficient to complete the
current task correctly.

Start from:

- files and symbols explicitly named by the current task;
- the current git status and relevant diff;
- directly affected callers, callees, State/Contract boundaries, and tests.

Prefer search before reading:

- locate symbols, requirements, and task sections with targeted search;
- read relevant sections or line ranges instead of entire large files;
- do not read large frozen documents in full unless a concrete unresolved
  correctness question requires the whole document.

A larger repository context is not automatically better context.

When a phase is frozen and implementation is authorized:

- use the current TASKS section as the normal implementation entry point;
- use the accepted PLAN as the implementation-architecture backing source;
- consult SPEC, CLARIFICATIONS, or Contracts only for the specific semantic
  question that requires higher authority;
- do not repeatedly reconstruct the phase design from all frozen documents.

Expand scope only when a concrete unresolved question could materially change:

- contract correctness;
- State or lifecycle semantics;
- provenance or identity;
- persistence behavior;
- graph topology;
- failure/publication behavior;
- implementation ownership;
- or required validation.

Follow at most one direct dependency hop by default.

Expand further only when the current evidence shows that another dependency is
required for correctness.

Do not recursively inspect neighboring modules, historical documents, archived
reviews, or unrelated tests merely for completeness or additional confidence.

## 7. Planning-to-Implementation Continuity

A completed planning pass is a verified handoff, not disposable analysis.

When implementation follows an accepted execution plan:

- reuse confirmed decisions;
- reuse the implementation file/symbol map;
- reuse identified tests and validation commands;
- reuse explicitly excluded scope;
- do not independently rediscover the same architecture or contracts.

Before implementation, perform only a lightweight freshness check of the
repository base and relevant working-tree changes.

Repeat investigation only when:

- the repository base materially changed;
- a relevant file materially changed;
- implementation reveals a concrete contradiction;
- a test or type failure exposes a previously unknown dependency;
- or the handoff lacks a fact required for correctness.

When refresh is required, prefer a targeted delta refresh over repeating the
entire planning investigation.

## 8. Change and Task Discipline

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

For large phases, execute bounded implementation packets rather than expanding
one working turn across the entire phase by default.

A packet should contain a coherent set of dependency-compatible Tasks with a
clear validation boundary.

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

## 9. Review and Validation Discipline

Use progressive validation.

During implementation:

- run the narrowest relevant tests first;
- run targeted checks for the files or behavior currently being changed;
- fix failures at the owning implementation boundary;
- avoid repeatedly running broad validation while the packet is still
  incomplete.

When a coherent implementation packet is complete:

- run its focused tests;
- run directly affected regression tests;
- run Ruff on new/touched files;
- run scoped mypy on applicable new/touched project-owned code;
- run `git diff --check`;
- perform one diff-focused sanity review.

The diff-focused review should check:

- correctness against the accepted task;
- frozen contract adherence;
- directly affected regression risk;
- accidental unrelated changes;
- test or validation weakening.

Do not perform a repository-wide architecture audit after each edit or packet.

Do not repeatedly audit a frozen decision merely because implementation changed.

Broader deterministic regression and architecture-level review belong at
explicit convergence, milestone, merge, release, or dedicated audit gates.

If targeted validation exposes concrete evidence of a wider regression, expand
validation only to the affected area first.

## 10. Documentation

Python comments and docstrings MUST remain in English.

Document business semantics, invariants, authority boundaries, and non-obvious
trade-offs rather than restating code.

Project-owned Domain contracts and non-trivial reducers, lifecycle controllers,
adapters, Publication Gates, renderers, and failure boundaries should have
concise useful documentation.

Regression tests should identify the invariant they protect when the reason is
not obvious.

Do not create documentation merely to duplicate frozen authority that already
has a canonical home.

## 11. Completion and Handoff

Every completed implementation packet must report concisely:

- Tasks completed
- Files changed
- Behavior changed
- Requirements/decisions implemented
- Focused tests run
- Static checks run
- Remaining risks
- Remaining TODOs or deferred work
- Unexpected scope changes
- Blockers
- Next dependency-ready packet

Do not claim runtime or integration validation when only static or mocked tests
were executed.

Do not re-summarize frozen architecture or documents in routine completion
reports.

## 12. Stopping Rule

Stop repository exploration when:

- the implementation surface is known;
- the relevant frozen requirements are resolved;
- the requested behavior is implemented;
- directly affected validation passes;
- and there is no concrete evidence of an out-of-scope regression.

Do not continue searching for additional improvements, refactors, cleanup
opportunities, or review findings unless required by the current task.

Do not expand scope merely to increase confidence.

When uncertainty remains, distinguish between:

- uncertainty that can materially change correctness or architecture; and
- uncertainty that can be resolved safely and locally during implementation.

Only the former justifies significant scope expansion.

## 13. Core Engineering Principle

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

Repository observation should remain bounded by the concrete correctness
questions of the current task.
```
