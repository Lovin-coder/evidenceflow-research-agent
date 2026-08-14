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
