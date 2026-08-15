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
- Schema changes require contract tests and documentation update.

## Change Discipline
- Make the smallest change needed for the current phase.
- Separate BASELINE / IMPLEMENTED / PROPOSED.
- Do not refactor unrelated upstream code.
- Do not modify dependencies/lockfile unless necessary and reported.

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