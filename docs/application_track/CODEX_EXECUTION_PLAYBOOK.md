# Codex Execution Playbook

## 1. 目的

本文沉淀 EvidenceFlow 中人和 ChatGPT 形成高效 Codex 工作方式的方法。

目标不是单纯缩短 Prompt，而是在不降低正确性的前提下，减少：

- repository observation（仓库观察）；
- repeated reasoning（重复推理）；
- agent loop（Agent 多轮执行循环）；
- 无效测试脚手架；
- 重复 validation（验证）；
- Context Window（上下文窗口）占用；
- Codex 配额消耗。

核心原则：

```text
已经完成的 reasoning
→ 转换成 deterministic execution specification
→ Codex 直接实施

而不是：

ChatGPT / 人已经分析完成
→ Codex重新搜索
→ Codex重新分析
→ Codex重新选择实现
→ 再开始 Coding
```

本文是工作方法的知识沉淀，不是 frozen architecture authority，也不是
Codex 每个任务都必须全文读取的指令文件。真正的长期工程约束由仓库根目录
`AGENTS.md` 提供；Codex 应按当前任务只读取与问题相关的内容。

## 2. Responsibility Split（职责划分）

### 人 / ChatGPT 负责

当信息已经足够时，应尽量提前确定：

- root cause（根因）；
- semantic decision（语义决策）；
- architecture ownership（架构职责归属）；
- invariant（必须保持的不变量）；
- target file（目标文件）；
- target symbol（目标符号，例如函数、类、helper）；
- implementation shape（实现形状）；
- required test level（需要的测试层级）；
- acceptance criteria（验收条件）。

### Codex 负责

Codex 主要负责：

- 打开指定 symbol 附近的最小代码范围；
- 按既定方案适配当前实现；
- 处理局部 import、typing 和 existing helper reuse；
- 编写或修改指定层级测试；
- 运行指定 validation；
- 报告真实执行结果。

当上游 reasoning 已经完成时，不再让 Codex 重复同一轮架构分析。

## 3. Task Maturity（任务成熟度）

在发送 Codex 任务前，先判断问题所处阶段：

```text
Root cause 未知
→ Analysis / Debug

Root cause 已知，但 architecture decision 未冻结
→ Plan

Decision 已冻结，目标文件/边界已知
→ Deterministic Working

Decision + symbol + implementation shape 已知
→ Patch-spec Working

Implementation 已完成
→ Diff-only Review
```

不要因为习惯而对每一个任务都执行完整 Plan。设计已经确定时，应直接进入
Working。

## 4. Symbol-level Execution Spec（符号级执行说明）

确定性 Working 指令应优先采用：

```text
file
→ symbol
→ known current behavior
→ exact required change
→ invariant
→ exact tests
→ exact validation
→ stop
```

例如：

```text
File:
src/open_deep_research/deep_researcher.py

Symbol:
_materialize_findings()

Known behavior:
当前 helper 会将 compression.findings 物化为 ResearchFinding。

Required change:
evidence_ids=[] 的 draft 不再发布为 ordinary ResearchFinding；
保留其 limitation semantics 到 task-level limitations。

Invariant:
published ResearchFinding 必须解析到至少一个 EvidenceRecord。
```

这比“请分析 ResearchFinding 的整个生命周期并选择最佳方案”更适合作为
Working 指令。

优先使用 file + symbol。line number（行号）只作为可选定位提示，因为代码修改
后容易漂移。

## 5. Implementation Shape（实现形状）

如果实现结构已经经过分析，应直接告诉 Codex。例如已经确定需要：

```python
@dataclass(frozen=True, slots=True)
class _FindingMaterializationOutcome:
    findings: tuple[ResearchFinding, ...]
    limitations: tuple[str, ...]
```

则可以把该 shape 直接写入 Working prompt。

不要让 Codex 再次选择：

```text
tuple
vs
dataclass
vs
mutable result
vs
新 public model
```

除非这个选择本身仍然是需要解决的设计问题。目标不是让 Codex 机械复制代码，
而是避免对已经解决的问题重复支付 reasoning 成本。

## 6. Bounded Observation（有界观察）

默认 repository observation 使用：

```text
exact symbol / question
→ targeted search
→ smallest relevant range
→ resolve
→ stop
```

不要默认：

```text
打开完整 module
→ 找 callers
→ 找 callees
→ 看邻近 modules
→ 读完整 SPEC
→ 读完整 PLAN
→ 读完整 TASKS
```

只有出现具体 unresolved question（未解决问题）时才扩大范围。

有效的 scope expansion trigger（范围扩展触发条件）包括：

- Contract correctness；
- State lifecycle；
- provenance / identity；
- persistence；
- graph topology；
- failure/publication semantics；
- implementation ownership；
- real dependency exposed by tests or typing。

以下理由不能单独触发范围扩展：

```text
for completeness
to be safe
to increase confidence
while we are here
```

## 7. Plan → Working Handoff

Plan 的职责是消除 architecture-sensitive uncertainty（会影响架构正确性的
未决问题）。

Plan 完成后必须产生 compact handoff（紧凑交接信息）：

```text
Decision
Targets
Patch behavior
Existing interfaces/helpers to reuse
Tests
Validation
Do-not-touch scope
Blockers
```

Working 应复用 handoff，不要：

```text
Plan 已经读过 repository
→ Working 再重新读一遍
```

当 Plan Context 已经很大，而 handoff 已完整时：

```text
Plan
→ compact handoff
→ fresh Working context
```

通常比保留大量无用 reconnaissance history（仓库侦察历史）更高效。

## 8. Boundary-aligned Testing（边界对齐测试）

测试层级应匹配被修改的最低充分边界：

| Changed invariant | Lowest sufficient test |
| --- | --- |
| helper | helper unit test |
| Host admission | admission unit test |
| node behavior | node test |
| pipeline interaction | pipeline test |
| graph topology | integration test |
| provider compatibility | provider smoke |

核心原则是：

```text
在哪里修 invariant
→ 优先在哪里直接测试
```

不要把 helper bug 默认升级为 provider/search/runtime/full integration fixture，
除非该 invariant 无法在更低层级可靠测试。

Provider smoke（真实 provider 冒烟测试）用于验证 provider compatibility，不用于
替代普通 unit test。

## 9. Validation Stop-Loss（验证止损）

Validation 失败时：

```text
failure
↓
是否指向 touched code？
```

如果是：

```text
修复 owning implementation
→ rerun failed validation
```

如果是已知的 baseline failure、third-party dependency failure、tooling failure
或 environment failure，则：

```text
记录
→ 停止该 validation 分支
→ 继续其他必要检查
```

不要在无关 Bug 修复任务中继续尝试：

- 改变 `MYPYPATH`；
- alternate mypy invocation；
- dependency upgrade；
- cache manipulation；
- environment reconstruction；
- unrelated config change。

只有任务本身就是修复 validation infrastructure 时，才允许深入排查。

## 10. Validation Sequence（验证顺序）

默认顺序：

```text
smallest focused test
→ directly affected regression
→ Ruff touched files
→ scoped mypy
→ git diff --check
→ one diff-focused review
```

已通过且相关代码没有变化的 validation 不重复运行。Local failure 不先用
full regression debugging；Full regression 应留给：

- integration convergence；
- milestone；
- merge；
- release；
- dedicated audit。

## 11. One Coherent Working Turn（单次连贯执行）

不要把一个本来完整的小改动机械拆成：

```text
Turn 1：改 A
Turn 2：改 B
Turn 3：补 tests
Turn 4：跑 validation
```

这样会重复支付 Context 恢复、repository freshness、git diff 和 task
understanding 的成本。

更好的方式是一个连贯的 Working turn：

```text
One Working turn

Patch A
Patch B
Patch C
Exact tests
Validation
Stop
```

“细粒度”应体现为指令中的确定性步骤更细，而不是 Agent turn 数更多。

## 12. Review Discipline（Review 约束）

Review 默认从 diff 开始，检查：

- requested behavior；
- frozen invariant；
- directly affected regression；
- test effectiveness；
- typing/validation weakening；
- unrelated diff。

Review 不默认：

- 重读 SPEC / PLAN；
- 重做 architecture analysis；
- 查找无关 code smell；
- 提出 optional refactor；
- review-of-the-review。

没有 actionable finding（可执行问题）时：

```text
PASS
→ stop
```

## 13. Context Management（上下文管理）

Context Window 剩余比例本身不是切换 Thread 的唯一理由。

优先在自然边界考虑新 Context：

```text
Plan → Working
Bug → next Bug
Step → next Step
```

如果旧 Context 已经很大，且已有 compact handoff，而下一阶段不需要大量旧
observation details，则优先：

```text
fresh context
+ compact handoff
```

如果刚完成精确 symbol observation，并马上实施同一局部修改，则继续当前
Context 通常更合理。

核心原则：不要因为 Context 百分比机械清空，也不要为了“保留上下文”长期携带
已经无用的 observation history。

## 14. Anti-patterns（应避免模式）

避免：

```text
已经确定 root cause
→ 再让 Working “深入分析根因”

已经知道 file/symbol
→ 再让 Working “自行定位实现边界”

helper invariant
→ 构造 provider/search integration fixture

known mypy tooling failure
→ 连续尝试不同 invocation

diff 已通过
→ 再做 repository-wide review

设计冻结
→ Working 重新比较多个架构方案
```

## 15. Default Workflow（默认工作流）

```text
Real problem
↓
Human / ChatGPT analysis
↓
Root cause
↓
Semantic decision
↓
Implementation boundary
↓
是否存在 architecture-sensitive blocker？

YES
→ targeted Plan
→ compact implementation handoff

NO
→ Patch-spec Working

↓
Focused validation
↓
Diff-only Review
↓
Commit
```

核心目标：

> 已经支付过一次的分析成本，不再让 Codex 重复支付第二次。

## Model Routing（模型选择）

模型选择依据不是 diff 大小，而是 execution specification 完成后仍留给 Codex
的 residual uncertainty（剩余不确定性）。

```text
Exact file + symbol + patch behavior + implementation shape + tests known
→ Luna High

Target boundary known, but local implementation still requires moderate judgment
→ Terra Medium / High

Cross-module implementation with some unresolved local ownership or interaction
→ Sol Medium

Architecture-sensitive reasoning, difficult debugging, lifecycle/concurrency/
Contract uncertainty
→ Sol High
