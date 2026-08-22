# EvidenceFlow Development Instructions

## Project Goal
Evidence-centric medical deep research agent built on frozen ODR baseline.

## Architecture Constraints
- Preserve Supervisor–Researcher Tool Loop unless a phase plan/ADR says otherwise.
- Preserve runtime-adaptive Supervisor behavior.
- Do not introduce Send, RAG, durable queues or unrelated platform changes implicitly.
- Process artifacts must never be treated as external evidence.
- Raw source artifacts must not be persisted directly in Graph State.

## Contract Rules
- Read EVIDENCEFLOW_CONTRACTS_V1.md before changing domain/state models.
- Preserve stable Source/Evidence provenance.
- Parent/Researcher communicate through explicit task/result contracts.
- ResearchTaskResult must not publish dangling provenance references; compact Source/Evidence records remain in the structured Data Plane while large artifacts remain externalized.
- Schema changes require contract tests and documentation update.

## Change Discipline
- Make the smallest change needed for the current phase.
- Separate BASELINE / IMPLEMENTED / PROPOSED.
- Do not refactor unrelated upstream code.
- Do not modify dependencies/lockfile unless necessary and reported.

## Phase Documentation Workflow

Every implementation phase MUST progress through the following document sequence:

```text
SPEC → PLAN → TASKS → CHECKLIST → IMPLEMENTATION → CLOSEOUT
```

- `*_SPEC.md` defines the audited baseline, problem, scope/non-goals,
  invariants, requirements, acceptance criteria, and architecture-sensitive
  OPEN decisions. A SPEC must distinguish facts from proposals.
- The phase `*_CLARIFICATIONS.md` is the decision buffer for OPEN items found
  during specification or implementation. It records alternatives, trade-offs,
  the human decision, rationale, impact, and canonical promotion status.
- `*_PLAN.md` maps a reviewed SPEC and resolved decisions to the repository's
  actual files, implementation sequence, migration strategy, and validation.
  It must not invent new architecture to fill a SPEC gap.
- `*_TASKS.md` decomposes the frozen PLAN into executable, reviewable work
  items. Every task must trace to SPEC requirements and relevant decisions.
- `*_CHECKLIST.md` is the verification and closeout ledger. It records evidence
  for acceptance criteria, tests, integration/eval runs, documentation sync,
  review findings, commits, and remaining limitations; it is not a second plan.

Workflow gates:

1. Source audit and SPEC drafting may proceed while decisions are OPEN.
2. Architecture-sensitive decisions must remain explicitly `OPEN`; an agent
   must not select an option by implication, examples, task wording, or code.
3. A blocking OPEN decision prevents PLAN freeze, TASKS freeze, and production
   implementation. A provisional PLAN may exist only when clearly marked
   `DRAFT / BLOCKED` and must preserve every unresolved alternative.
4. Before production changes, the SPEC must be reviewed/frozen, blocking
   decisions must be RESOLVED and PROMOTED where required, and PLAN/TASKS/
   CHECKLIST must be mutually traceable.
5. If implementation exposes a new contract, topology, persistence, migration,
   failure, or acceptance ambiguity, stop the affected task and return to the
   Clarification Log. Update canonical documents before resuming.
6. Closeout may mark an item complete only with reproducible evidence. A commit
   existing in history does not by itself prove human review or acceptance.

Suggested requirement identifiers are phase-scoped, for example `S4-R01` for
SPEC requirements, `S4-D01` for decisions, and `S4-T01` for tasks. PLAN, TASKS,
CHECKLIST, tests, and completion reports should preserve these identifiers.

## Validation
- Run relevant pytest.
- Run ruff.
- Run mypy where applicable.
- External model/search calls are integration/eval work, not unit tests.

## Completion Report
Always report:
- files changed
- behavior changed
- tests run
- remaining risks/TODOs

## Code Documentation

For project-owned domain contracts and non-trivial runtime boundaries,
document business semantics rather than restating code.

- Pydantic Domain Models should have concise class docstrings and meaningful
  field descriptions where field intent is not self-evident.
- Non-trivial adapters, reducers, renderers, and failure-handling helpers
  should document important Args/Returns/Raises and contract behavior.
- Regression tests should briefly state the invariant or behavior they
  protect.
- Avoid line-by-line comments and documentation that merely repeats names or
  type annotations.
- Keep Python code comments and docstrings in English.

## Clarification and Canonical Document Rule

When repository inspection or implementation reveals an ambiguity that cannot be uniquely resolved from the frozen Plan or Contracts, do not silently make an architectural assumption. Surface the ambiguity for clarification before continuing if it affects domain contracts, state semantics, runtime behavior, migration rules, phase scope, or acceptance criteria.

The current phase Clarification Log is a decision buffer between the frozen design and repository reality; it is not a new source of truth.

For material clarifications:

1. Record the problem, relevant baseline, considered options, decision, rationale, impact, and deferred work in the current phase Clarification Log.
2. If the decision changes a Domain Contract, State semantic, phase scope, migration rule, or Acceptance Criteria, update the corresponding canonical document before treating the decision as implementation truth.
3. Mark such clarification as `PROMOTED`.
4. Explanatory clarifications that do not change canonical semantics may remain only in the Clarification Log.
5. Temporary migration exceptions must identify the phase responsible for removing them.
6. Do not continue implementation while a blocking clarification remains `OPEN`.

Canonical documents define the current design. Clarification Logs preserve why that design changed.
