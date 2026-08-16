# P2-S3 — Domain & Evidence Contracts Retro

## 0. 状态与文档边界

| 项目 | 当前状态 |
|---|---|
| 阶段状态 | **IMPLEMENTED / VALIDATED** |
| 日期 | 2026-08-16 |
| Frozen ODR baseline | `20aaa0d422bd290c83f93574810ef1244e8d5955` |
| Implementation commit | `ab34591`（`feat: implement P2-S3 domain and evidence contracts`） |
| 本次重写 Retro 前的 branch HEAD | `f6dd746` |
| Deterministic validation | 已通过；41 targeted tests |
| Real runtime smoke | **PASS**；Qwen3.7 typed Brief → ConductResearch → Host Task |
| Review disposition | 已按 accepted frozen triage 处理并验证 |
| Closeout | 实现与验证完成；等待 closeout commit |

本文明确区分四类内容：

- **BASELINE**：来自 frozen ODR application 的已有行为；
- **IMPLEMENTED**：当前 P2-S3 branch 已经存在的行为；
- **REVIEW FINDING**：Review 已确认、但当前尚未修复的实现缺口；
- **PROPOSED**：P2-S4 或更后续阶段的建议，不是当前实现事实。

Retro 用于记录本阶段发生了什么、哪些假设没有成立，以及个人认知发生了什么变化。它不替代
frozen Plan、Contracts 或已 PROMOTED 的 Clarification。若 Review resolution 改变 Domain Contract、
State semantic、phase boundary、migration rule 或 Acceptance Criteria，必须先更新对应 canonical
document，之后才能将该 resolution 视为 implementation truth。

---

## 1. 本阶段没有改变的战略架构

### 1.1 BASELINE — Supervisor–Researcher 架构保持不变

P2-S3 没有重写 ODR 的 Graph topology，也没有替换 runtime-adaptive planning：

```text
Question
  ↓
MedicalResearchBrief
  ↓
Supervisor
  ↓ 运行时决定 ConductResearch tool calls
N × Researcher subgraph invocation
  ↓
ResearchTaskResult observations
  ↓
Supervisor 判断是否完成
  ↓
Final report
```

以下战略决策从 Plan 到实现始终没有变化：

- 保留 Supervisor–Researcher Tool Loop；
- 保留 Supervisor 在运行时自适应规划和委派任务的能力；
- 不隐式引入 `Send`、RAG、durable queue 或无关 platform change；
- Domain Model 与 Graph State schema 保持分离；
- Parent 与 Researcher 通过显式的 `ResearchTask → ResearchTaskResult` contract 通信；
- 保持 evidence-centric 方向，但不提前实现属于 P2-S4 的 evidence-native pipeline；
- migration 期间 structured contract 与 legacy text channel 并存；
- `SourceRecord`、`EvidenceRecord`、`ResearchFinding` 的真实 population 仍属于 P2-S4。

### 1.2 Graph topology 没变，但 runtime semantics 变丰富了

P2-S3 基本没有改变 Graph 的 Node/Edge，真正发生变化的是：

```text
Task identity
Result lifecycle
Failure isolation
State reducer semantics
Contract version discovery
Structured ↔ legacy compatibility
```

因此，本阶段带来的一个重要认识是：

> Agent 系统可以在 Node/Edge 基本不变的情况下，完成非常实质的 business contract 与 runtime
> semantic 升级。

---

## 2. P2-S3 实际交付内容

### 2.1 IMPLEMENTED — Domain 与 State contracts

- 新增严格 Pydantic v2 contracts：`MedicalResearchBrief`、`EvidenceNeed`、
  `MedicalResearchTask`、`SourceRecord`、`EvidenceRecord`、`ResearchFinding`、
  `ResearchTaskResult`；
- Parent、Supervisor、Researcher State 增加 structured channels；
- Source、Evidence、Finding、Task Result 增加 identity-aware reducers；
- exact replay 具有幂等语义；same-ID different-payload replay 作为 conflict 抛错；
- `contract_version` 在 Parent-visible `ResearchTaskResult` 中序列化，成为可发现的 wire
  contract version。

### 2.2 IMPLEMENTED — Runtime contract migration

- `write_research_brief` 生成 typed `MedicalResearchBrief`；
- deterministic renderer 将 typed Brief dual-write 成 legacy Markdown；
- LLM-facing `ConductResearch` schema 只表达 task semantics；Host/Dispatcher 负责真正
  materialize `MedicalResearchTask`；
- Host 使用 run-local、namespaced、injective percent encoding 从 `tool_call_id` 构造
  `task_id`；
- compiled Researcher 接收 typed Task，并输出 shadow `ResearchTaskResult`；
- migration 期间继续保留 `compressed_research` 和 `raw_notes`；
- Supervisor 对 concurrency admission failure 与普通 child execution failure 逐 Task 生成 FAILED
  Result envelope，同时保留 legacy error `ToolMessage`；
- SUCCESS/PARTIAL/FAILED 被收窄为 execution/termination semantics，不再表示 evidence strength。
- production `Configuration` 增加 typed `research_model_enable_thinking: bool | None`；仅显式
  `True/False` 在内部 model boundary 转译为 `extra_body.enable_thinking`，默认 `None` 不发送 override。

### 2.3 “Shadow Result”具体表示什么

Structured Result boundary 已经接通，但 baseline search path 还不会真正创建 Source、Evidence 和
Finding。当前典型 Result 可能是：

```text
ResearchTaskResult
├── task_id = task:...
├── status = success | partial | failed
├── findings = []
├── evidence_ids = []
├── source_ids = []
└── summary = legacy compressed research 或 failure summary
```

空 structured collections 的准确含义是：

> P2-S3 尚未实现真实 structured population。

它不表示 Researcher 没有使用 web source，也不能被当作 evidence-native output。

---

## 3. Validation 与 runtime evidence

### 3.1 Deterministic validation rerun

本次 Retro 更新期间重新运行了 P2-S3 targeted suite：

```text
UV_CACHE_DIR=/tmp/evidenceflow-uv-cache \
uv run --frozen --extra dev pytest -q \
  tests/test_domain_models.py \
  tests/test_state_contracts.py \
  tests/test_p2_s3_runtime.py

41 passed, 26 warnings
```

26 个 warnings 来自现有 Pydantic/LangGraph deprecated APIs，没有导致 test failure。

Static checks：

```text
uv run --frozen --extra dev ruff check \
  src/open_deep_research/configuration.py \
  src/open_deep_research/domain_models.py \
  src/open_deep_research/state.py \
  src/open_deep_research/deep_researcher.py \
  src/open_deep_research/prompts.py \
  tests/test_domain_models.py \
  tests/test_state_contracts.py \
  tests/test_p2_s3_runtime.py

All checks passed!
```

```text
MYPYPATH=src .venv/bin/mypy \
  --explicit-package-bases \
  --follow-imports=skip \
  src/open_deep_research/configuration.py \
  src/open_deep_research/domain_models.py \
  src/open_deep_research/state.py \
  src/open_deep_research/deep_researcher.py \
  src/open_deep_research/prompts.py

Success: no issues found in 5 source files
```

当前 41 个 tests 覆盖：

- strict schemas 与 wire values；
- basic provenance references；
- 已知 raw/process payload rejection；
- reducer replay/conflict semantics；
- frozen Graph topology；
- structured Brief dual-write；
- Host-owned task IDs；
- 0/1/N delegation behavior；
- admission/child/tool/compression failure envelope；
- compiled Researcher boundary。
- Researcher-local provenance publish gate；
- metadata/excerpt 8000-character compactness boundaries；
- typed Thinking policy 的 `None/False/True` forwarding；
- arbitrary configurable `extra_body` 无法绕过 typed Configuration boundary。

### 3.2 Repository-wide test harness limitation

Implementation cycle 中执行 bare `pytest -q` 时，还会收集 upstream
`src/legacy/tests/test_report_quality.py`。其 fixture setup 因 `--research-agent` option 未注册而
失败。这是 existing legacy harness configuration issue，不是 P2-S3 unit-test failure；本阶段没有修改
该 runner 或 `conftest.py`。

### 3.3 Controlled real-model smoke — PASS

最终受控 smoke 使用：

```text
model = qwen3.7-plus-2026-05-26
allow_clarification = False
research_model_enable_thinking = False
```

验证路径：

```text
Question
→ Clarify routing
→ MedicalResearchBrief
→ deterministic legacy research_brief
→ Supervisor think_tool planning turn
→ Supervisor ConductResearch tool call
→ Host materializes MedicalResearchTask
→ STOP before supervisor_tools handles ConductResearch
```

停止机制没有修改 production Graph topology：

```text
Parent graph:
interrupt_before=["research_supervisor"]

Supervisor subgraph:
astream(stream_mode="updates")
→ 允许安全的 think_tool-only turn 继续
→ 观察到 ConductResearch update 后立即关闭 stream
→ supervisor_tools 未执行该 call
```

Timing：

| Measurement | Result |
|---|---:|
| Total elapsed | 24.161 s |
| Brief stage | 9.477 s |
| Supervisor stage | 14.684 s |

Supervisor 实际运行了两个 planning turns：

```text
iteration 1 → think_tool
iteration 2 → ConductResearch
```

Serialized `MedicalResearchBrief`：

```json
{
  "normalized_question": "Compare the efficacy and safety of Angiotensin-Converting Enzyme (ACE) inhibitors versus Angiotensin Receptor Blockers (ARBs) in adults with mild primary hypertension and no chronic kidney disease, specifically focusing on blood pressure control, major clinical outcomes, and important adverse effects.",
  "question_type": "Comparative Effectiveness and Safety Review",
  "clinical_elements": {
    "population": "Adults with mild primary hypertension and no chronic kidney disease",
    "intervention": "ACE inhibitors",
    "comparator": "ARBs",
    "outcomes": [
      "Blood-pressure control",
      "Major clinical outcomes (e.g., cardiovascular events, mortality, stroke, myocardial infarction)",
      "Important adverse effects (e.g., cough, angioedema, hyperkalemia, renal function changes)"
    ]
  },
  "constraints": [],
  "research_intent": "Comparison",
  "evidence_needs": [
    {
      "evidence_types": ["Randomized Controlled Trials", "Systematic Reviews", "Meta-analyses"],
      "study_types": ["Head-to-head comparative trials", "Large-scale outcome trials"],
      "source_policy": ["Prioritize original peer-reviewed publications and official journal articles over secondary summaries or survey papers"],
      "date_constraints": ["No specific date constraint; prioritize most recent high-quality evidence while including seminal trials"],
      "coverage_dimensions": [
        "Efficacy in lowering systolic and diastolic blood pressure",
        "Incidence of major adverse cardiovascular events (MACE)",
        "All-cause and cardiovascular mortality",
        "Drug-specific adverse event profiles (e.g., ACE inhibitor-induced cough vs. ARB tolerability)",
        "Renal safety profiles in patients without pre-existing CKD"
      ]
    }
  ]
}
```

Legacy adapter evidence：

```text
research_brief present = true
research_brief characters = 1630
```

Supervisor `ConductResearch` call：

```json
{
  "name": "ConductResearch",
  "id": "call_f8f50aafdeb246b8b126968f",
  "args": {
    "research_question": "Compare the efficacy and safety of Angiotensin-Converting Enzyme (ACE) inhibitors versus Angiotensin Receptor Blockers (ARBs) in adults with mild primary hypertension who do not have chronic kidney disease. Specifically evaluate blood pressure control, major clinical outcomes, and adverse effect profiles using direct comparative evidence.",
    "evidence_needs": [
      {
        "evidence_types": ["Randomized Controlled Trials", "Systematic Reviews", "Meta-analyses"],
        "study_types": ["Head-to-head comparative trials", "Large-scale outcome trials"],
        "source_policy": ["Prioritize original peer-reviewed publications and official journal articles over secondary summaries or survey papers"],
        "date_constraints": ["No specific date constraint; prioritize most recent high-quality evidence while including seminal trials"],
        "coverage_dimensions": [
          "Blood-pressure efficacy",
          "Major cardiovascular outcomes and mortality",
          "Drug-specific adverse effects",
          "Renal safety without pre-existing CKD"
        ]
      }
    ],
    "source_preferences": [],
    "priority": 1
  }
}
```

Identity boundary：

```text
LLM supplied task_id = false
runtime tool_call_id = call_f8f50aafdeb246b8b126968f
Host-materialized MedicalResearchTask.task_id
  = task:call_f8f50aafdeb246b8b126968f
```

Provider request observation：

```text
Request 1: structured Brief, response_format=json_schema, enable_thinking=false
Request 2: Supervisor think_tool turn, tools bound, enable_thinking=false
Request 3: Supervisor ConductResearch turn, tools bound, enable_thinking=false
```

Boundary confirmation：

```text
researcher_executed = false
research_tools_executed = false
tavily_executed = false
```

因此该 smoke 验证了 typed planning contract、legacy adapter、LLM-facing Tool Schema、Host identity
ownership 和 Thinking=False provider propagation，同时明确没有验证 Researcher/Tavily execution。

---

## 4. Plan Assumptions That Did Not Hold

### 4.1 Assumption 1 — Contract Freeze 后，implementation 基本可以机械映射

#### Before

最初的隐含推理是：

```text
Domain Contract 已冻结
+ State boundary 已设计
+ Parent ↔ Researcher contract 已设计
→ implementation 应该接近直接映射
```

#### Implementation Reality

落到真实源码后，仍然出现了大量无法由 schema 字段列表直接回答的问题：

- `task_id` 由谁创建，如何编码；
- same-ID Result replay 是 dedup、merge 还是 conflict；
- 每一个 FAILED delegation 是否仍必须产生 Result envelope；
- status 表示 execution result、evidence strength，还是两者；
- typed Brief/Task 如何进入 frozen legacy prompt path；
- `contract_version` 应在哪个 serialized boundary 被发现；
- hard `ainvoke()` exception 发生后如何取得 child partial state。

#### After

> Contract-first development 不会消除 implementation ambiguity。它真正的价值，是让新的
> ambiguity 能够被识别为 Contract gap，而不是由实现者在代码中静默决定。

因此，Clarification Log 的出现不说明 Contract Freeze 失败。恰恰相反，它避免了局部实现选择在没有
讨论的情况下变成 architecture truth。

---

### 4.2 Assumption 2 — `tool_call_id → task_id` 是简单字符串转换

#### Before

最初容易把它理解成一个 formatting 问题：将 provider Tool Call ID normalize 成更整洁的 Domain ID。

#### Implementation Reality

有损 normalization 会压缩不同 runtime identities：

```text
"call a" ──normalize──> "call-a"
"call-a" ─normalize──> "call-a"
```

此时两个不同 delegation 被错误映射成同一个 Domain Task。真正的问题不是 ID “不够好看”，而是
identity semantics 被破坏。

#### After

> ID normalization 不是字符串美化问题，而是 identity-preserving encoding 问题。

当前 percent encoding 是为了满足以下 invariant 的 implementation correction：

```text
different valid tool_call_id
→ different task_id
```

这里需要明确区分两个层次：

```text
Contract clarification
→ Host owns task identity；identity 是 run-local、stable、injective

Implementation correction
→ 使用 percent encoding 保持该 identity invariant
```

Percent encoding 本身不是 strategic architecture change。

#### `/plan` 是否可以提前避免 collision？

不一定，而且本阶段本来已经使用了 `/plan`。

不同阶段擅长发现的问题并不相同：

```text
/plan
→ 谁拥有 task_id？
→ UUID 还是 tool-call based？
→ retry/re-planning identity 如何区分？

implementation tests
→ 具体 helper 是否保持 injective？
→ adversarial inputs 是否 collision？

/review
→ 主动寻找 tests 未覆盖的 edge cases 和 contract violations
```

不能期待 Plan mode 预知以后某个 normalization helper 的所有实现缺陷。

---

### 4.3 Assumption 3 — Failure 只需要描述最终 Task Result

#### Before

最初更多考虑：

```text
Researcher success
Researcher partial
Researcher failed
concurrency overflow
```

也就是 Task 最终处于什么 status。

#### Implementation Reality

Failure 可能发生在已经取得有效数据之后：

```text
Search
  ↓
Source/Evidence/Finding 已 materialized
  ↓
Compression / Finalization
  ↓
FAIL
```

后置步骤失败，不表示此前已经 materialized 的 records 不存在。FAILED 不能自动等价为：

```text
everything produced before failure = discarded
```

#### After

> Failure 不只是一个最终 status，还具有发生 phase。Result status 表示 termination semantics，但不能
> 擦除失败前已经成功产生的 structured work。

因此 FAILED Result 仍可能合法携带 partial Sources、Evidence 和 Findings。

#### Compression 节点未来是否会消失？

不应简单写成“最终不会有这个节点”。更准确的判断是：

> Baseline 的 `compress_research` 可能会被弱化或演化，但 Researcher Finalization 这一业务责任不会
> 消失。

可能的演化方向是：

```text
compress_research
        ↓
finalize_research_task
        ↓
validate provenance
finalize Source/Evidence/Finding
construct ResearchTaskResult
produce legacy compression compatibility output
```

因此长期有效的问题不是函数是否改名，而是：

> Finalization failure 应如何保留此前已经取得的 partial artifacts？

---

### 4.4 Assumption 4 — Result 中有 IDs 就代表 provenance 完整

#### Before

`ResearchTaskResult` 包含 `source_ids` 和 `evidence_ids`，直觉上就像已经具备 provenance。

#### Implementation Reality

```text
ResearchTaskResult.evidence_ids = ["E1"]

Parent:
没有 EvidenceRecord("E1")
没有 run-scoped registry
没有 Evidence Store 可以 resolve "E1"
```

这种情况下，`E1` 只是 dangling identifier，不是真正可用的 provenance relation。

#### After

```text
Reference ID
+ inline record 或 resolvable Registry/Store target
= usable provenance reference
```

ID 只是 relation 的一端。对应 record 必须在 Researcher output projection 后仍然存活，并能从 Parent
boundary resolve。

---

### 4.5 Assumption 5 — 将“禁止 raw artifact”写成 schema rule 就足够

#### Before

禁止 `raw_html`、`raw_content` 等 metadata keys，看起来已经将 architecture constraint 变成 schema
validation。

#### Implementation Reality

只依赖字段名 denylist 仍可能被绕过：

```text
content
page_content
rawHtml
其他 provider-specific alias
```

同时，`EvidenceRecord.excerpt` 目前只要求 non-empty。如果没有长度/总大小限制，它仍可能装入完整的
多 MB HTML、PDF text 或 API response。

#### After

> Architectural invariant 必须转化成可执行、可测量的 bounded contract，不能只依赖字段命名约定或
> 少量 denylist。

更成熟的边界应明确：

```text
SourceRecord.metadata
→ compact metadata only
→ normalized reserved aliases
→ per-value / total-size bounds

EvidenceRecord.excerpt
→ bounded source-derived passage
→ not a full artifact

full HTML / PDF / API response
→ ArtifactStore
→ SourceRecord.artifact_ref
```

具体 size limit 与 normalization rules 当前没有被本 Retro 静默冻结。如果这些规则改变 Domain
Contract，必须先进入 Clarification 并更新 canonical document。

---

## 5. Clarifications：哪些真正改变或补充了 Contract

### 5.1 Strategic architecture unchanged

以下内容从头到尾没有改变：

- Supervisor–Researcher Tool Loop；
- runtime-adaptive Supervisor；
- 不使用 `Send`；
- Domain Model 与 State 分离；
- Task → Result explicit boundary；
- evidence-centric direction；
- structured + legacy migration；
- P2-S4 再实现 evidence-native population。

这说明 Master Plan 的战略层是稳定的。

### 5.2 Contract-level amendments

以下决策真正补充或修正了 Contract，并通过 P2-S3 Clarification Log PROMOTED：

| Decision | Contract impact | Clarification |
|---|---|---|
| P2-S3 实际接通 shadow `ResearchTaskResult` | Boundary wiring 提前到 P2-S3；真实 population 仍留在 P2-S4 | C02 |
| Every materialized Task → one Result envelope | 补全 failure/admission lifecycle contract | C07 |
| `task_id` 由 Host 创建且为 run-local identity | 冻结 identity ownership 与 scope | C01/C04 |
| distinct append / identical dedup / different conflict | 冻结 Result replay 与 reducer lifecycle semantics | C06 |
| `contract_version` 进入 serialized Result | 让 cross-subgraph wire contract 可发现 | C09 |
| SUCCESS/PARTIAL/FAILED 只表达 execution/termination | 将 status 与 evidence quality 分离 | C05 |
| legacy raw-content fallback 是 temporary exception | 明确 migration debt 与 removal phase | C03 |
| structured object → deterministic Markdown → legacy prompt | 冻结 compatibility adapter，避免两个 semantic source of truth | C08 |

### 5.3 Implementation correction 不是战略设计改变

`tool_call_id` 的 percent encoding 是最典型例子：

```text
Contract decision
→ identity 必须 Host-owned、run-local、stable、injective

Implementation choice
→ percent encoding provider Tool Call ID
```

这种分层可以避免把一个具体 helper 误写成 strategic architecture decision。

---

## 6. Implementation Reality vs Original Plan

### 6.1 原预期

最初的 P2-S3 很像一个较窄的 schema introduction：

```text
定义 Domain Models
↓
扩展 State
↓
增加 contract tests
```

### 6.2 实际实现

最终 P2-S3 变成：

```text
Domain Models
+ State channels / reducers
+ Host-owned Task identity
+ structured Brief dual-write
+ structured Task adapter
+ shadow ResearchTaskResult
+ per-task failure isolation
+ status semantics
+ contract versioning
+ legacy compatibility
+ 29 deterministic tests
```

这并不是无关 scope expansion。只有让 typed contract 真正穿过下面的 runtime path，才能验证它是否
可用：

```text
Question
→ Brief
→ Supervisor
→ Tool Call
→ Task
→ Researcher
→ Result
→ Parent State
```

### 6.3 本阶段最准确的定位

> P2-S3 最终更接近一次 runtime contract migration，而不只是 schema introduction。

Graph topology 基本没变，但 State、Tool Schema、Task identity、failure semantics、Result envelope、
legacy adapter 都发生了实质变化。

---

## 7. Resolved Review Findings and Their Design Impact

Post-implementation review 的 5 个 code-level comments 被归并为 4 个 themes，并已按冻结 triage 完成
处置。P2-S3 没有借此引入 Parent registry、EvidenceStore、checkpoint recovery、retry lifecycle 或
Graph topology 变化。

| Theme | P2-S3 disposition | Validation / deferred boundary |
|---|---|---|
| R1 — dangling Source/Evidence IDs | 通过 PROMOTED clarification 与 canonical Contracts 明确：P2-S3 只保证 Researcher-local provenance consistency，不在本阶段增加 Parent registry 或 EvidenceStore | populated IDs 的 cross-boundary resolvability 是 P2-S4 开始真实 structured population 前的 mandatory prerequisite |
| R2 — provenance validator 未成为 publish gate | 已修复：normal 与 failure/finalization Result 在跨越 Researcher boundary 前调用 provenance validation；invalid references 不得发布 | focused runtime regression tests 覆盖 invalid Source/Evidence/Finding reference |
| R3 — structured State compactness 不可执行 | 已冻结并实现：`EvidenceRecord.excerpt <= 8000` characters；`SourceRecord.metadata` serialized total `<= 8000` characters；normalized content-bearing-key rejection 作为 defense-in-depth | boundary tests 覆盖长度与 provider key spelling；这些限制是 runtime compactness guardrails，不是医学证据语义 |
| R4 — hard child exception 丢失 partial State | 已作为 known P2-S3 runtime limitation 记录：只保证 finalization/failure boundary 能看见的 artifacts 被保留 | state-aware recovery 延后 P2-S4/P2-S6；本阶段不增加 persistence、checkpoint recovery 或 topology changes |

这次处置带来的核心认识没有变化：reference 必须能够 resolve，validator 必须位于 publish boundary，
architectural invariant 必须转化为可执行 guardrail，而 failure preservation 的保证范围必须与 runtime
实际能够访问的 State 一致。

---

## 8. Temporary Debt and P2-S4 Inputs

### 8.1 Tavily result → SourceRecord/EvidenceRecord ingestion

P2-S3 只是定义了 `SourceRecord` 与 `EvidenceRecord`。真实 Tavily result 仍主要走 baseline text path。

P2-S4 需要实际实现：

```text
Tavily Search Result
↓ parse / normalize
full artifact → ArtifactStore
↓
SourceRecord + artifact_ref
↓ locate bounded useful passage
EvidenceRecord
```

即从：

```text
Schema exists
```

升级为：

```text
Runtime actually creates and preserves these objects
```

### 8.2 ResearchFinding 与 Result collections 的真实 population

Population 不是重新设计这些 Domain Model 字段。字段已在 P2-S3 定义。

Population 指 runtime 真正填入业务数据：

```text
Search result
↓
SourceRecord S1/S2
↓
EvidenceRecord E1/E2/E3
↓
ResearchFinding F1
    evidence_ids=[E1,E3]
↓
ResearchTaskResult
    findings=[F1]
    evidence_ids=[E1,E2,E3]
    source_ids=[S1,S2]
```

### 8.3 ArtifactStore Protocol / LocalArtifactStore

当前 `SourceRecord.artifact_ref` 只是 abstraction。P2-S4 应使它进入真实数据流：

```text
raw HTML / raw PDF / full API response
↓
LocalArtifactStore
↓
artifact_ref
↓
SourceRecord
```

这样 Graph State 只保存 compact structured records，不再承担 raw data storage。

### 8.4 移除 legacy raw-content fallback

当前 temporary migration path：

```text
Tavily summarization fail
↓
raw content
↓
ToolMessage / raw_notes
```

P2-S4 在 ArtifactStore 可用后应改成：

```text
raw page
↓
ArtifactStore
↓
artifact_ref
↓
compact Evidence / compact Tool observation
```

到这一步，P2-S3 C03 temporary exception 才算真正还债完成。

### 8.5 locator + hash 的真实 audit

P2-S3 只能验证：

```text
locator != empty
hash != empty
evidence.source_id exists in supplied collection
```

它不能证明 `EvidenceRecord.excerpt` 真的来自实际 source artifact。

P2-S4 有真实 ArtifactStore 后才能完成：

```text
artifact_ref
↓ load immutable source snapshot
locator
↓ recover passage
recompute / compare hash
↓
Evidence audit PASS / FAIL
```

### 8.6 PROPOSED P2-S4 implementation sequence

下面是 P2-S4 Plan 的输入，不替代未来 canonical Plan：

1. 将 P2-S3 已固定的 local validation publish gate 作为入口，并先设计 Parent-visible record
   reachability；
2. 定义 `ArtifactStore Protocol` 和 minimal `LocalArtifactStore`；
3. 将 Tavily result normalize 成 `SourceRecord + artifact_ref`；
4. 从 stored artifact 提取 bounded Evidence passage，并生成 stable locator/hash；
5. 基于明确 Evidence IDs 生成 `ResearchFinding`；
6. 将所有 Parent-visible Source/Evidence targets 跨 child boundary carry 或 register；
7. 在 dedicated finalization boundary 构造并验证 `ResearchTaskResult`，并设计 state-aware partial
   recovery；
8. 移除 legacy raw-content fallback；
9. 增加完整 provenance chain 的 contract/integration tests。

### 8.7 仍然属于后续阶段的内容

- Claim、Citation、Claim–Evidence Grounding 仍属于 P2-S5；
- 更完整的 retry、recovery、observability 与 evaluation reliability 按 canonical roadmap 进入 P2-S6；
- RAG、durable queues 和其他 platform change 仍不属于当前 phase，不得隐式引入。

---

## 9. What I Learned — 认知变化而不是知识点清单

### 9.1 对 Contract-first 的理解

**Before**

冻结 Schema 后，实现应该相对机械。

**After**

Contract Freeze 的真正作用不是消除 ambiguity，而是提供稳定边界，让 ambiguity 可以被识别、讨论、
PROMOTE 或延期，不再隐藏在 implementation detail 中。

### 9.2 对 Identity 的理解

**Before**

`task_id` 只是给 Task 增加一个唯一字符串。

**After**

Identity 必须回答：

```text
ownership
scope
lifecycle
encoding
```

run-local logical delegation identity、cross-run business identity、retry-attempt identity 是三个不同
问题。Encoding 必须保留 identity relation，而不是只做 text normalization。

### 9.3 对 Reducer 的理解

**Before**

Reducer 就是 State merge function。

**After**

Reducer semantics 必须建立在业务 lifecycle semantics 上。如果不知道两个 same-ID Result 是 replay、
retry、supersede 还是 conflict，就无法合理定义 merge。

P2-S3 能够冻结：

```text
distinct ID → append
same ID + identical payload → dedup
same ID + different payload → conflict
```

是因为先明确了当前 lifecycle 不包含 field merge、attempt merge 或 supersession。

### 9.4 对 Failure 的理解

**Before**

Task 最终只有 success、partial、failed。

**After**

还必须考虑 failure 发生在哪个 phase、失败前哪些 artifacts 已经 materialized、失败后哪些内容仍应
保留。FAILED Result 可以合法携带 partial records。

### 9.5 对 Provenance 的理解

**Before**

Evidence 有 `source_id`、locator、hash 就有 provenance。

**After**

- ID 必须 resolve 到 surviving target；
- validator 必须位于 publish boundary；
- locator/hash 必须能够回到真实 artifact；
- field presence 不等于 end-to-end audit。

### 9.6 对 Graph State 的理解

**Before**

不定义 `raw_html` 字段，就能避免 raw artifact 进入 State。

**After**

还必须在 schema 层限制 compactness。否则 metadata 和 excerpt 一样可以成为 disguised raw-artifact
channel。

### 9.7 对 AI-assisted development 的理解

本阶段有价值的过程不是“让 Codex 写代码”，而是：

```text
Codex /plan
→ 发现 design ambiguity

Human Clarification
→ 做出并 PROMOTE Contract decision

Codex implementation + tests
→ 将 decision 映射到 runtime code 与 deterministic checks

Codex /review
→ 主动攻击已有 assumptions 与未覆盖 boundary

Human Retro
→ 将发现转化成自己的工程认知
```

核心总结：

> AI-assisted development 的价值不只是提高写代码的速度，而是利用 Plan、Clarification、
> Implementation、Review、Retro 五个阶段，把原本容易被 implementation details 掩盖的工程决策显式化。

---

## 10. What Codex Handled vs What I Personally Decided

### 10.1 Codex 主要承担

- repository 与 frozen baseline scan；
- 将 frozen Contracts 映射到真实 source locations；
- Pydantic models 与 reducers 的 implementation mechanics；
- deterministic renderer 和 runtime adapters；
- test scaffolding、adversarial examples 与 static validation；
- review candidate discovery 与 code-level boundary analysis。

### 10.2 我本人主要决定

- Host 与 LLM 之间的 Task identity ownership；
- run-local Task lifecycle semantics；
- same-ID Result replay dedup/conflict policy；
- P2-S3 是否实际接通 shadow Result boundary；
- SUCCESS/PARTIAL/FAILED 的准确语义；
- legacy raw-artifact exception 及其 removal phase；
- `contract_version` 的 wire-visible boundary；
- P2-S3 boundary wiring 与 P2-S4 population 的 scope 分界；
- Review finding 应当本阶段修复、PROMOTE 为 temporary exception，还是进入后续 canonical phase。

这一分工很重要：Codex 可以提出实现机制，但 Contract ownership、可接受的 migration debt 与 phase scope
仍然是 human architecture decisions。

---

## 11. Remaining Closeout Items

### 11.1 已完成

- [x] P2-S3 implementation candidate 已进入 `ab34591`；
- [x] accepted Review triage 已实现并同步 canonical documents；
- [x] 41 个 targeted deterministic tests 通过；
- [x] P2-S3 source/tests Ruff 通过；
- [x] scoped mypy 与 compileall 通过；
- [x] post-implementation `/review` 已完成；
- [x] 关键 Contract decisions 已记录到 PROMOTED Clarifications；
- [x] typed `research_model_enable_thinking` policy 与 bypass regression tests 已实现；
- [x] controlled real-model Brief → ConductResearch → Host Task smoke 通过；
- [x] 本 Retro 已区分 IMPLEMENTED、VALIDATED、KNOWN LIMITATION 与 PROPOSED。

### 11.2 P2-S3 closeout 前仍需完成

- [ ] human review 最终 core diff；
- [ ] 提交当前 closeout changes，并确认 worktree clean。

---

## 12. Impact on P2-S4

P2-S4 不能只从“给当前空 collections 填数据”开始。P2-S3 Review 已经明确了四个 P2-S4 boundary
inputs：

1. 每个 Parent-visible Source/Evidence ID 都有 resolvable record target；
2. 延续 P2-S3 已实现的 Result publish validation，并覆盖真实 populated records；
3. structured Graph State 具有 enforceable compactness bounds，full artifacts 进入
   `ArtifactStore`；
4. 在已记录的 hard-exception limitation 基础上设计 state-aware recovery，保留后置 failure 前已经
   materialized 的 records。

因此，P2-S4 更准确的目标不是：

```text
populate Source/Evidence/Finding fields
```

而是：

```text
real search result
→ artifact storage
→ structured Source/Evidence/Finding population
→ boundary validation
→ resolvable ResearchTaskResult publication
→ auditable Parent-visible provenance
```

P2-S3 最重要的成果也不只是“41 tests passed”，而是 implementation 与 Review 将原本隐藏的 runtime
contract questions 显式化：

```text
Identity 是 lifecycle concern
Failure 具有 phase
Reference 需要 resolver
Validator 必须成为 publish gate
Architectural invariant 需要 enforceable bounds
```

这些认知将直接决定 P2-S4 能否从“structured schemas 已存在”真正进入“evidence-native runtime 已
成立”。
