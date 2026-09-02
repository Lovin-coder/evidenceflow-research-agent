# EvidenceFlow Development Instructions

## 1. Project Goal

EvidenceFlow is an evidence-centric medical deep research Agent developed from
a frozen Open Deep Research baseline and now evolving as an independent
project-owned fork.

Engineering priorities are:

```text
correctness
→ semantic clarity
→ maintainability
→ testability
→ readability
→ reuse

Detailed engineering guidance lives in:

docs/application_track/EVIDENCEFLOW_ENGINEERING_GUIDELINES.md

Consult only the sections relevant to the current implementation question.
Do not re-read the entire document by default.

2. Authority and Phase Workflow

Engineering governance and frozen semantic authority are distinct.

Repository engineering governance:

AGENTS.md
↓
EVIDENCEFLOW_ENGINEERING_GUIDELINES.md

Frozen semantic and implementation authority:

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

Lower-level artifacts MUST NOT silently override higher-level frozen semantics.

If implementation requires changing a frozen Domain contract, State semantic,
identity/reference rule, topology, persistence rule, migration rule, failure
rule, phase scope, or acceptance criterion, STOP the affected work and surface
the conflict.

Do not make architecture-sensitive decisions implicitly during coding.

Each implementation phase follows:

SPEC
→ CLARIFICATIONS
→ PLAN
→ TASKS
→ CHECKLIST
→ IMPLEMENTATION
→ CLOSEOUT
*_SPEC.md defines baseline, scope, non-goals, invariants, requirements,
acceptance criteria, and architecture-sensitive OPEN decisions.
*_CLARIFICATIONS.md records alternatives, human decisions, rationale,
deferred work, and canonical promotion status.
*_PLAN.md maps frozen semantics to repository implementation.
*_TASKS.md decomposes the PLAN into bounded implementation work.
*_CHECKLIST.md records reproducible verification and closeout evidence.

Blocking OPEN decisions prevent affected implementation.

Use phase-scoped identifiers such as:

S5-R01
S5-D01
S5-T01

and preserve traceability through implementation, tests, verification, and
closeout.

3. Architecture and Contract Boundaries
Preserve the Supervisor–Researcher Tool Loop unless frozen design explicitly
changes it.
Preserve runtime-adaptive Supervisor behavior.
Do not introduce Send, RAG, durable queues, background workers, new
persistence systems, or unrelated platform changes implicitly.
Process artifacts MUST NOT be treated as external factual Evidence.
Raw or large Source artifacts MUST NOT be persisted directly in Graph State.
Preserve stable Source/Evidence provenance and explicit task/result
contracts.
ResearchTaskResult MUST NOT publish dangling provenance references.
Presentation artifacts MUST NOT become provenance authority.
Model output MUST NOT own stable identity where Contracts assign identity to
the Host.
Host logic MUST NOT replace frozen Model semantic authority with undocumented
heuristics.
Schema changes require contract tests and canonical documentation updates.
4. Implementation Hard Rules
Code structure
Split functions by semantic responsibility, not by line count.
Do not extract helpers solely to shorten a function.
Graph nodes and application coordinators SHOULD remain orchestration-thin.
Keep deterministic Domain logic, side effects, and Graph State updates
clearly separated.
Avoid God modules.
Prefer small semantic packages when a subsystem contains multiple
independently testable responsibilities.
Do not create speculative abstractions or frameworks without a current
consumer.
Module-private helpers SHOULD use a leading underscore.
Do not use generic utils.py modules as dumping grounds for Domain-specific
behavior.
State and authority
Internal helpers SHOULD return typed values or outcomes instead of mutating
LangGraph State directly.
Important State fields must have clear writer and lifecycle ownership.
Reducer-backed reset behavior must use the explicitly planned framework
mechanism.
Do not assume an empty collection clears an append reducer.
Concurrent completion order MUST NOT define authoritative ordering.
Validation and failure
Validators reject invalid input; they MUST NOT silently invent semantic
repairs.
Publication Gates are validate-not-repair.
Do not silently convert operational failures into valid semantic
empty/success results.
No bare except:.
Broad except Exception is allowed only at documented isolation boundaries.
Do not swallow cancellation or system-level control-flow exceptions as
ordinary business failures.
Retry
Every logical Model stage MUST have one semantic retry authority.
Do not multiply logical attempts by stacking independent semantic retry
layers.
Valid negative semantic results MUST NOT be retried merely to obtain a more
favorable result.
Typing

Use:

TypedDict
→ LangGraph State schemas

Pydantic
→ stable serialized Contracts and runtime/model-validated structured IO

dataclass(frozen=True)
→ immutable Host-internal value/execution objects
Avoid dict[str, Any] across project-owned semantic boundaries.
New EvidenceFlow modules MUST NOT introduce new mypy errors.
Touched project-owned code SHOULD NOT introduce new type debt.
Do not use broad # type: ignore, # noqa, or rule disabling merely to make
checks pass.
5. Codex Execution Discipline

Confirmed decisions, prior verified analysis, completed work, passing
validations, and accepted Plan handoffs are reusable authority.

Do not rediscover or re-prove confirmed information without concrete
contradictory repository evidence.
When a task specifies exact files, symbols, invariants, implementation shape,
or patch behavior, treat them as the execution specification.
Inspect only the smallest local code range required to apply a specified
change.
Prefer file + symbol over broad module exploration or fragile line numbers.
Do not perform repository-wide or full-document reads for localized changes.
Expand observation only for a concrete unresolved correctness, dependency,
contract, lifecycle, provenance, or architecture question.
Working mode implements settled decisions. It MUST NOT independently redesign
them without contradictory code evidence.
Review mode is diff-focused. It MUST NOT restart repository reconnaissance or
reconsider frozen design without a concrete finding.
Do not split one coherent deterministic patch into multiple Codex turns merely
to make the task appear smaller.
Stop when the requested patch, focused tests, and specified validations are
complete.
Do not search for unrelated cleanup, improvements, speculative risks, or
review-of-the-review.
6. Context and Handoff Continuity

Use the smallest repository working set sufficient for correctness.

Start from:

files and symbols explicitly named by the current task;
current git status and relevant diff;
directly affected interfaces and tests.

Prefer:

exact symbol / Task / requirement / question
→ targeted search
→ smallest relevant code or document range
→ resolve
→ stop

over full-file, full-document, or repository-wide reading.

When a phase is frozen:

use the current TASKS section as the normal implementation entry point;
use the accepted PLAN as implementation-architecture backing authority;
consult SPEC, CLARIFICATIONS, Contracts, or CHECKLIST only for a concrete
unresolved semantic question.

Follow at most one direct dependency hop by default.
Expand further only when concrete evidence requires it for correctness.

A completed Plan is a verified implementation handoff.

Reuse:

confirmed decisions;
mapped files and symbols;
existing interfaces/helpers to reuse;
identified tests;
validation commands;
explicitly excluded scope.

Before Working mode, perform only a lightweight freshness check unless relevant
repository state has materially changed.

Repeat investigation only when:

the repository base materially changed;
a relevant target materially changed;
implementation reveals a concrete contradiction;
focused validation exposes an unknown dependency;
or the handoff lacks information required for correctness.

Use a targeted delta refresh rather than repeating the full planning
investigation.

7. Testing and Validation Discipline

Tests should match the lowest sufficient semantic boundary.

changed invariant              lowest sufficient test

helper                         helper unit test
Host admission                 admission unit test
node behavior                  node test
pipeline interaction           pipeline test
graph topology                 integration test
provider compatibility         provider smoke

Do not test a localized helper invariant through provider/search/runtime
integration when the helper can be exercised directly.

Use progressive validation:

focused test
→ directly affected regression
→ Ruff on touched files
→ scoped mypy where applicable
→ git diff --check
→ one diff-focused sanity review

Do not rerun an unchanged passing validation when no relevant code or dependency
has changed.

Validation Stop-Loss

When a validation command fails:

Determine whether the failure points to touched code.
If yes, fix the owning implementation and rerun the affected validation.
If the failure matches a known baseline, dependency, environment, or tooling
failure, record it and stop investigating that validation path.
Do not experiment with alternate environment variables, invocation modes,
dependency upgrades, cache changes, or unrelated configuration unless the
current task explicitly targets that validation infrastructure.

Do not weaken tests, validators, typing, or acceptance criteria to make a task
pass.

Broader deterministic regression belongs at explicit integration, milestone,
merge, release, or dedicated audit gates.

Provider smoke tests are for provider compatibility boundaries, not substitutes
for local unit tests.

8. Change and Task Discipline

Make the smallest coherent change required by the current task.

Separate BASELINE, IMPLEMENTED, and PROPOSED.
Do not refactor unrelated code.
Do not modify dependencies or lockfiles unless explicitly required.
Do not build future-phase infrastructure during the current phase.
Project-owned modules MAY be reorganized when the frozen PLAN explicitly
requires clearer ownership or maintainability.

A well-specified implementation task should provide, where applicable:

Goal
Known/Frozen Decisions
Target Files and Symbols
Required Change
Invariants
Required Tests
Validation
Forbidden Changes
Stop Conditions

When the implementation shape has already been verified, use it directly.
Do not make Working mode choose among equivalent helper structures, return
shapes, validation locations, or test strategies without a genuine unresolved
reason.

For large phases, use coherent dependency-compatible implementation packets.
Do not artificially split one small deterministic patch across multiple turns.

STOP instead of improvising if implementation unexpectedly requires:

a new stable Domain field;
changed State semantics;
changed identity/reference scope;
changed graph topology;
new persistence behavior;
a new dependency;
new Model authority;
new fallback semantics;
weakened acceptance criteria.
9. Documentation

Python comments and docstrings MUST remain in English.

Project-owned explanatory documentation SHOULD be Chinese-first unless a
canonical artifact explicitly requires English.

File names, paths, class/function names, protocol names, framework names, and
technical identifiers remain in their canonical English form.

Document:

business semantics;
invariants;
authority boundaries;
lifecycle ownership;
failure semantics;
non-obvious engineering trade-offs.

Do not restate obvious code behavior.

Regression tests should identify the invariant they protect when the reason is
not obvious.

Do not create documentation merely to duplicate frozen authority that already
has a canonical home.

10. Completion and Review

Every completed implementation packet should report only what is needed to
continue safely:

files/symbols changed;
behavior changed;
focused tests run;
static validations run;
known validation limitations;
remaining blockers or deferred work.

Do not claim runtime/provider/integration validation when only static or mocked
tests were executed.

A normal Review should inspect the diff and directly affected behavior only.

Review should answer:

Does the diff implement the requested behavior?
Are frozen invariants preserved?
Do tests protect the changed boundary?
Did unrelated changes enter the diff?
Was validation, typing, or acceptance weakened?
Is there a concrete regression caused by this diff?

If no concrete issue remains, stop.

11. Core Engineering Principle

EvidenceFlow implementation should preserve this model:

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

Settled reasoning should be converted into deterministic execution rather than
repeated during implementation.
