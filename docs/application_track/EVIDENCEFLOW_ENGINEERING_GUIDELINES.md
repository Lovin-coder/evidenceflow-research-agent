# EvidenceFlow Engineering Guidelines

## 0. 文档目的

本文定义 EvidenceFlow 的 repository-level 工程实现原则。

它不定义新的 Domain semantics，也不替代：

- `EVIDENCEFLOW_CONTRACTS_V1.md`
- phase `SPEC`
- `CLARIFICATIONS`
- `PLAN`
- `TASKS`
- `CHECKLIST`

这些文档回答：

```text
系统应该做什么
```

本文主要回答：

```text
冻结后的设计应该以什么工程方式实现
```

目标不是建立复杂的软件工程制度，而是防止 Agent-assisted coding
逐步产生以下问题：

- Graph node 演化为巨型业务函数；
- 多个 semantic responsibility 混在同一个函数；
- State 被不同 helper 随意写入；
- Model / Host authority 边界逐渐模糊；
- validation 变成 silent repair；
- retry/fallback 越来越隐式；
- `dict[str, Any]` 在模块间传播；
- 为未来需求提前建立无实际 consumer 的框架；
- 单个 phase 的代码最终堆积成难以理解的 God Module。

EvidenceFlow 已作为独立 fork 继续开发，不以未来 merge upstream 为主要约束。

当前工程优先级：

```text
correctness
→ semantic clarity
→ maintainability
→ testability
→ readability
→ reuse
```

对于秋招展示型工程，代码应该让 reviewer 可以从：

```text
directory
→ module
→ type
→ function
→ test
```

快速理解系统结构与关键 invariant。

---

# 1. Authority 与实现边界

实现必须服从：

```text
AGENTS.md
→ Engineering Guidelines
→ Contracts
→ SPEC
→ Clarifications
→ PLAN
→ TASKS
→ code
```

Guidelines 只定义通用 implementation policy。

具体 Phase 的：

- topology；
- State semantics；
- Domain model；
- identity；
- retry behavior；
- failure behavior；
- model role；
- migration strategy；

仍由对应 canonical documents 和 PLAN 决定。

如果 coding 过程中发现 frozen design 无法唯一映射到代码，不得自行选择
architecture-sensitive solution，应停止相关 Task 并回到 Clarification。

---

# 2. 函数与模块职责

## 2.1 函数按 semantic responsibility 拆分

EvidenceFlow **不使用 LOC 作为函数拆分规则**。

是否拆函数取决于该逻辑是否具有独立：

- semantic concept；
- invariant；
- side-effect boundary；
- test boundary；
- reason to change。

例如以下职责通常应该保持可区分：

```text
reference resolution
projection
admission
Model invocation
validation
Domain materialization
State update
presentation rendering
```

一个函数不应该因为代码“比较长”就机械拆分，也不应该为了减少行数生成：

```python
_do_step_1()
_do_step_2()
_process_data()
_handle_result()
```

这种没有独立语义的 helper。

## 2.2 Orchestration 与业务逻辑分离

Graph node 和 application coordinator 主要负责：

```text
State/input extraction
→ stage sequencing
→ failure isolation
→ typed result
→ State update
```

不应该直接内嵌大量：

- reference resolver；
- identity calculation；
- validation；
- Domain materialization；
- Citation logic；
- formatting。

例如：

```python
async def global_synthesis(state, config):
    inputs = ...
    result = await execute_global_synthesis(...)
    return ...
```

比在 node 内直接实现整个 Global Synthesis pipeline 更合适。

## 2.3 Private helper

Module 内部实现细节使用：

```python
_private_helper()
```

跨 sibling modules 具有明确 package semantic 的函数使用正常名字：

```python
derive_claim_evidence_universe()
materialize_grounding_record()
validate_grounding_manifest()
```

`__init__.py` 只 export 少量真正需要的 package-level API。

## 2.4 避免 God Module

当一个 subsystem 已经包含多个可独立测试的责任时，应优先拆成小型 semantic package。

例如 Global Synthesis 更适合：

```text
global_synthesis/
├── __init__.py
├── orchestration.py
├── models.py
├── projection.py
├── grounding.py
├── publication.py
└── rendering.py
```

而不是不断扩张单个：

```text
global_synthesis.py
```

同时也不要走向另一极端：

```text
one helper
→ one file
```

目标是让目录结构反映 architecture，而不是追求文件数量。

## 2.5 不建立无当前 consumer 的抽象

不要仅因为未来“可能需要”就提前建立：

```text
GenericAgentStage
BaseGroundingStrategy
GlobalIdentityManager
ProviderRegistry
PublicationFramework
```

允许少量 duplication，只要不同逻辑具有不同 semantic meaning。

复用应该来自真实共同机制，而不是形式相似。

---

# 3. Type 与 State Ownership

## 3.1 类型选择

统一采用：

```text
TypedDict
→ LangGraph State / framework mapping schema

Pydantic
→ stable serialized Contract
→ LLM structured output
→ runtime validated boundary

dataclass(frozen=True)
→ Host 内部 immutable value / execution object
```

例如：

```text
AgentState
→ TypedDict

ClaimRecord / ClaimDraft / GroundingManifest
→ Pydantic

GlobalSynthesisLimits / SourceDisplayKey / receipts
→ frozen dataclass
```

## 3.2 避免隐式 dict contract

Project-owned subsystem 之间应使用 explicit types。

避免：

```python
dict[str, Any]
```

长期承担：

```text
Claim
Grounding
execution outcome
publication result
State transition
```

等语义。

Provider metadata 等天然不稳定的 external boundary 可以暂时使用 mapping，
但进入内部后应尽早 normalize。

## 3.3 State write ownership

重要 LangGraph State field 必须有明确 writer/lifecycle owner。

内部 helper 通常：

```text
input
→ typed value/outcome
```

而不是直接修改 Graph State。

推荐：

```text
pure/application helpers
→ execution result
→ owning node
→ State update
```

不要让：

```text
projection helper
validator
Judge worker
renderer helper
```

分别自行修改 Parent State。

## 3.4 Reducer 是行为的一部分

Reducer-backed State 不能通过“看起来合理”的普通赋值猜测行为。

例如 append reducer：

```python
field=[]
```

不一定等于 reset。

涉及：

- reset；
- overwrite；
- replay；
- idempotence；

时必须使用 PLAN 明确的 framework mechanism，并建立对应 regression test。

---

# 4. Host、Model 与 Side Effect 边界

## 4.1 Host deterministic logic 优先 pure

Host-owned deterministic behavior 应尽可能实现为 pure function：

```text
same input
→ same output
```

例如：

```text
derive Evidence universe
derive required Citation refs
materialize Grounding status
derive display key
derive metrics
validate Manifest
```

这些 helper 不应隐藏：

- Model call；
- network；
- random；
- current timestamp；
- Graph State mutation。

## 4.2 Side effect 集中在明确边界

主要 side effects 应集中在：

```text
LLM/provider invocation
ArtifactStore I/O
LangGraph State update
logging / telemetry
```

Domain validator/materializer 不应顺便执行 unrelated I/O。

## 4.3 Model output 不拥有 Host identity

如果 Contract 将 identity 交给 Host：

```text
claim_id
citation_id
ordering
display numbering
```

就不能信任 Model 生成的对应字段。

Model reference 也必须验证：

```text
reference resolves
AND
reference belongs to visible allowlist
```

仅“能够 resolve”并不代表 Model 有权引用。

## 4.4 Host 不替代 Model semantic authority

如果某 semantic judgment 被 frozen Contract 分配给 Model，Host 只能：

```text
validate
→ deterministic materialize
```

不能通过：

- Evidence count；
- presence heuristic；
- string matching；
- arbitrary score；

重新定义结论。

---

# 5. Validation、Failure、Retry 与 Concurrency

## 5.1 Validator reject，不做 silent repair

Validator 的职责是：

```text
accept valid input
or
produce explicit failure
```

禁止：

```text
unknown ref → choose another ref
missing metadata → invent value
invalid status → infer a new semantic status
invalid aggregate → silently drop records until valid
```

如果 Contract 明确允许 sibling salvage，则按冻结规则执行。

Publication Gate 始终：

```text
validate-not-repair
```

## 5.2 禁止 silent fallback

Operational failure 不得伪装成 valid semantic result。

例如禁止：

```text
timeout → INSUFFICIENT
Judge error → CONTRADICTED
exception → []
missing provenance → silently skip
```

Failure 必须通过：

- typed outcome；
- issue；
- process status；
- explicit fallback path；

保持可观察。

## 5.3 Exception boundary 要明确

一般 pure helper 不捕获 broad exception。

允许 broad `except Exception` 的典型位置：

- provider/model isolation boundary；
- per-item sibling isolation boundary；
- top-level node safety boundary。

禁止：

```python
except:
```

也不能把 cancellation / process-control exception 当成普通业务失败吞掉。

## 5.4 一个 Model stage 只有一个 logical retry authority

避免：

```text
wrapper semantic retry
×
Host semantic retry
```

产生意外 retry multiplication。

PLAN 应明确谁负责：

```text
invoke
→ parse
→ Host validation
→ retry decision
```

Transport-level provider retry 可以独立存在，但必须 bounded。

Valid negative semantic result 不 retry-to-pass。

Deterministic invalid input 也不应重复提交相同 request。

## 5.5 Async execution 不决定 authority order

允许并发：

```text
Claim A
Claim B
Claim C
```

但最终 materialization 必须按照 canonical input order，而不是 completion order。

Worker 推荐：

```text
one input
→ typed outcome
```

Coordinator：

```text
gather
→ isolate permitted sibling failures
→ reorder by canonical order
→ materialize
```

并发 worker 不应该通过共享 mutable list 决定最终 authority ordering。

---

# 6. Change 与 Abstraction Discipline

## 6.1 Small coherent change

每个 Task 只修改完成当前 frozen behavior 所需的最小 coherent scope。

禁止顺手：

- 清理无关 upstream code；
- rename 大量 API；
- 重构相邻 subsystem；
- 修改无关格式；
- 添加未来 Phase capability。

## 6.2 允许 project-owned package 重组

EvidenceFlow 不再以未来 upstream merge 为目标，因此如果 PLAN 明确认为现有文件结构妨碍：

- semantic ownership；
- readability；
- testing；
- maintainability；

可以重组 project-owned package。

但重组本身必须：

```text
scoped
documented
behavior-preserving outside target subsystem
```

不能以“代码更漂亮”为理由扩大 Phase scope。

## 6.3 Explicit > highly generic

对于秋招展示型工程，优先：

```text
清楚的 module boundary
清楚的 function name
清楚的 typed outcome
清楚的 control flow
```

而不是复杂的 inheritance、meta-programming 或过度 configurable framework。

代码应该容易解释，而不只是“很抽象”。

---

# 7. Testing 与 Static Analysis

## 7.1 Test invariant，不绑死内部实现

测试优先验证：

```text
input
→ observable output
→ invariant
```

例如：

```text
INSUFFICIENT + material contradiction
→ remains INSUFFICIENT
```

或者：

```text
reject one Claim sibling
→ another Claim ID remains stable
```

不要让 correctness 主要依赖：

```text
private helper was called exactly once
```

这种实现细节。

## 7.2 Test naming

测试名应说明保护的行为：

```python
test_rejecting_sibling_claim_does_not_change_other_claim_ids()
```

比：

```python
test_claim_id_case_3()
```

更有价值。

## 7.3 不为测试增加 production special case

禁止仅为了测试加入：

```python
if TESTING:
```

之类 production branch。

应使用：

- dependency injection；
- fake model；
- mock provider；
- existing seam。

## 7.4 mypy

`mypy` 用于 Python static type checking。

本项目原则：

```text
不要求当前 phase 清理全部 upstream historical type debt

但：

new EvidenceFlow modules
→ MUST NOT introduce new mypy errors

touched project-owned code
→ SHOULD NOT introduce new type debt
```

不要用大量：

```python
# type: ignore
```

掩盖真实 type boundary 问题。

必要 ignore 应尽量 specific 并有明确原因。

## 7.5 Ruff

新建和修改的 project-owned code 应通过 repository `ruff` rules。

不要通过：

```text
broad noqa
disable lint rule
```

来规避正常问题。

---

# 8. Task 与 Review Discipline

## 8.1 TASK 必须给 Codex 明确边界

每个 implementation Task 推荐包含：

```text
Goal
Frozen Requirements Implemented
Allowed Files
Forbidden Changes
Implementation Boundaries
Required Tests
Stop Conditions
Acceptance Criteria
Expected Diff Shape
```

其中 `Allowed Files`、`Forbidden Changes` 和 `Stop Conditions`
是 Codex coding 时的重要 guardrail。

## 8.2 Stop Conditions

遇到以下情况不得自行扩展方案：

- 需要新增 stable Domain field；
- 需要改变 State semantics；
- 需要改变 identity/reference scope；
- 需要改变 graph topology；
- 需要新的 persistence semantics；
- 需要未经授权的新 dependency；
- 需要改变 Model/Host authority；
- 需要增加新的 fallback rule；
- 需要弱化 frozen acceptance criterion。

应停止受影响 Task 并报告。

## 8.3 Expected Diff Shape

TASK 可以描述合理的 diff 形态，例如：

```text
Expected:
- one focused subsystem change
- several semantic helpers
- focused tests

Unexpected:
- new dependency
- unrelated graph changes
- S4 contract changes
- large unrelated refactor
```

这是 scope review 工具，不是 LOC constraint。

## 8.4 Code Review Checklist

实现完成后至少检查：

```text
[ ] 函数是否按 semantic responsibility 拆分
[ ] orchestration 是否保持清晰
[ ] 是否出现新的 God Module
[ ] State writer 是否明确
[ ] deterministic Host logic 是否可独立测试
[ ] 是否出现 silent fallback
[ ] validator 是否偷偷 repair semantic input
[ ] retry 是否形成多层 logical multiplication
[ ] async completion order 是否影响 authority
[ ] 是否出现不必要的 dict[str, Any]
[ ] 是否引入 speculative abstraction
[ ] 是否发生 unrelated refactor
[ ] Model 是否获得了不属于它的 identity authority
[ ] tests 是否保护 frozen invariant
[ ] 新 EvidenceFlow code 是否新增 mypy/ruff debt
```

---

# 9. EvidenceFlow 工程原则

EvidenceFlow 的实现应长期保持：

```text
LLM
→ 提议 bounded semantics

Host
→ identity
→ resolution
→ validation
→ materialization
→ deterministic ordering
→ State ownership
→ publication

Presentation
→ derived only

Graph
→ explicit orchestration

Types
→ explicit boundaries

Failures
→ observable

Tests
→ protect invariants
```

最终目标不是最大程度抽象，而是：

> 让架构能够直接从 package、type、function 和 test 中被看见，
> 并让后续开发不会轻易侵蚀已经冻结的 Model / Host / State / provenance 边界。
