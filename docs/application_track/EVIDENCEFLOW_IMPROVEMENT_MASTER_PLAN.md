# EvidenceFlow Improvement Master Plan

## 1. Document Purpose / Status

| Field | Value |
|---|---|
| Status | **Design Freeze Candidate** |
| Base | frozen ODR baseline，commit `20aaa0d422bd290c83f93574810ef1244e8d5955` |
| Scope | EvidenceFlow Phase 2 application-track improvement |
| Bridge | P2-S2 source verification → P2-S3 implementation design |

本文是后续开发的设计边界，不是源码总结、实现完成记录或未来功能 Wish List。除特别标注外：

- **Baseline / Implemented**：已由 `notes/p2_s2/source/` 核验的当前行为。
- **Proposed / Freeze Candidate**：本计划拟冻结、尚未实现的设计。
- **Future Work**：不进入第一轮核心实现。
- **TODO**：现有 notes 无法支撑具体结论，必须在实现前验证或另立 ADR。

后续若改变三个核心 Track、ODR Supervisor–Researcher 拓扑或核心数据契约，应更新本文或新增
ADR，不应在实现中静默偏移。

## 2. Baseline Architecture Summary

**Baseline / Implemented** 的主链路是：

```text
Clarify
  → Research Brief
  → Agentic Supervisor
  → ConductResearch Tool Calls
  → concurrent Researcher Subgraph runs
  → Compression
  → Supervisor observes and re-evaluates
  → Final Report
```

这里的 Agentic Supervisor 是运行时自适应的 `Plan → Delegate → Observe → Re-evaluate`，
不是一次性 Planner。Research Brief 只产生一个详细研究规格；具体 topic 和数量由 Supervisor
在 `AIMessage.tool_calls` 中动态生成，Host 再用 `max_concurrent_research_units` 等配置执行硬限制。
Researcher 内部是 Model–Tool–Observation 循环，多个 Researcher 通过 `asyncio.gather()` 并发，
结果压缩为 ToolMessage 返回 Supervisor。

## 3. Four Baseline Limitation Categories

### L1 — Task / Runtime Explicitness

**Baseline / Implemented**：ResearchTask 主要隐含在 Tool Calls、ToolMessages 和消息历史中；没有
一等公民的 task lifecycle。并发超额任务被拒绝而非排队，完整 Subgraph 异常可能使整组
`gather()` 抛出；partial success、per-task retry/status 与失败恢复较粗。

### L2 — Text-centric Evidence Representation

**Baseline / Implemented**：`raw_notes` 是 AIMessage 与 ToolMessage 的文本聚合，`notes` 来自
Supervisor ToolMessages，最终写作主要消费压缩文本。系统没有稳定的 Source、Evidence、Finding、
Claim、Claim-level Grounding 与 Citation provenance；AI 生成内容可能进入 Grounding Context。
这是 EvidenceFlow 最关键的结构性缺口。

### L3 — Evaluation Granularity

**Baseline / Implemented**：L4 Final Artifact Eval 最完整；L1 只有 Supervisor parallelism 的
局部原型；L2 Trajectory 基本缺失；现有 Groundedness 同时抽 Claim 并对混合 `raw_notes`
做粗粒度支持判断，无法验证 Citation 指向的具体 Evidence，也未区分 Groundedness、Citation
placement/faithfulness 与 Factual Correctness。

### L4 — Domain Adaptation Gap

**Baseline / Implemented**：ODR 使用 generic open-domain research contract。它并非设计错误，
但不等同于医学证据研究要求。医学规划需要问题类型、PICO/结构化临床元素、Evidence Need、
study/evidence type、source policy、时间约束与证据层级。已核验 notes 明确指出：领域化不能只在
Prompt 中写死“文献调研/前沿探索/应用”等固定 topic。

## 4. EvidenceFlow Core Thesis

> EvidenceFlow 将保留 ODR 的 Agentic Supervisor–Researcher Deep Research Runtime，重点将
> free-form Research Topic、text-centric Research Notes 和 report-level Groundedness，升级为
> 领域感知 MedicalResearchTask、provenance-preserving Evidence Pipeline 和 Claim-level
> Grounding/Evaluation。

本阶段只有三个核心 Improvement Track：Domain-aware Medical Planning、Evidence-native
Research Pipeline、Claim-level Grounding / Evaluation。其他能力只能作为其支撑项或 Future Work。

## 5. Three Improvement Tracks

### Track A — Domain-aware Medical Planning

**Proposed / Freeze Candidate**，回答“Agent 应该研究什么？”

```text
Natural-language medical question
  → MedicalResearchBrief
      ├── normalized_question
      ├── question_type
      ├── clinical_elements / PICO
      ├── constraints
      ├── research_intent
      └── evidence_needs[]

MedicalResearchBrief
  ↓
Agentic Supervisor
  ↓
MedicalResearchTask(s)
```

Domain planning 不等于固定 topic taxonomy。`MedicalResearchBrief` 统一承载规范化问题、
`question_type + structured clinical elements/PICO + constraints + research intent`，以及需要何类证据的
`evidence_needs[]`。EvidenceNeed 保留领域语义，但只是 Brief 内的 nested domain object，不额外形成一个
Graph Stage。Supervisor 消费 Brief，并仍可根据已有结果动态新增或收敛 MedicalResearchTask。

第一版**保留现有 Supervisor Tool Loop，不迁移 Plan + Send**。这样可减少同时变化的变量、保留
自适应补充研究能力，并先验证 Domain Contract 是否改善任务 coverage、specificity 与 non-overlap。
`Send` 仅为 Future architecture candidate。

### Track B — Evidence-native Research Pipeline

**Proposed / Freeze Candidate**，回答“Researcher 的研究结果应该是什么？”

```text
Search Result → SourceRecord → EvidenceRecord → ResearchFinding
```

核心原则是 Process / Evidence Separation：AIMessage、Tool 计划和错误属于 Process Artifact；
可定位的外部来源片段属于 Evidence Artifact。过程材料继续用于 Debug、Trajectory 和失败归因，
但不得作为外部事实证据。

第一版只冻结 `Source → Evidence → Finding` 的 ID chain 与 ResearchTaskResult 边界，不额外冻结
QueryRecord，也不追求一次填满所有医学元数据。Researcher 本地形成 Evidence/Findings；Supervisor
聚合结构化 Findings，并仍可观察压缩后的 bounded result。迁移采用 dual-write：Legacy
`raw_notes/compressed_research` 暂时保留，新 Evidence Ledger 并行生成，避免一次破坏现有 ODR 输出。

### Track C — Claim-level Grounding / Evaluation

**Proposed / Freeze Candidate**，回答“报告中的关键 Claim 为什么成立？”

```text
ResearchTaskResult[]
  → ClaimRecord[]
  → ClaimGroundingRecord[]
  → Citation[]
  → GroundingManifest
  → V2 Shadow Report
```

P2-S5 采用 Claim-first、claim-centered Grounding：Generator 提出 Claim semantics，Grounding Judge 对 Host-derived
Evidence universe 产生整体 semantic verdict，Host 负责 identity、reference resolution、五态 status、Citation 与
atomic Manifest。V2 Shadow Report 是 Manifest 的 derived artifact；Citation completeness 是 Publication Gate
structural invariant，不作为退化的 quality metric，也不提前合成单一 Truth Score。

## 6. Target Data Flow

```text
Medical Question
  → MedicalResearchBrief（包含 evidence_needs[]）
  → Agentic Supervisor
  → MedicalResearchTask Tool Call(s)
  → existing Researcher Subgraph instances
  → Search Result → SourceRecord → EvidenceRecord
  → ResearchFinding(s) with evidence IDs
  → ResearchTaskResult
  → Supervisor observe / re-evaluate
  → Global Synthesis → ClaimRecord[]
  → ClaimGroundingRecord[] → Citation[]
  → GroundingManifest
  → V2 Shadow Report + external evaluation artifacts
```

该流图冻结“合同先行、拓扑保留”：第一轮仍是 Supervisor–Researcher，而不是新增 RAG、Send
Scheduler 或 Durable Queue。

## 7. Key Domain Contracts

完整目标链仍是 `Source → Evidence → Finding → Claim → Grounding`，但实现级 Contract 按阶段冻结，
避免为后续 Claim/Citation 需求过早固化细节。

**P2-S3 implementation-level freeze** 只覆盖以下 contracts：

| Contract | 最小职责 / 字段 |
|---|---|
| `MedicalResearchBrief` | `normalized_question`、`question_type`、`clinical_elements / PICO`、`constraints`、`research_intent`、`evidence_needs[]`；数组元素保留 EvidenceNeed 的 nested domain object 语义 |
| `MedicalResearchTask` | `task_id`、research question、evidence needs、source preferences、priority |
| `SourceRecord` | `source_id`、`artifact_ref`、`metadata` |
| `EvidenceRecord` | `evidence_id`、`source_id`、`locator`、`excerpt`、`hash` |
| `ResearchFinding` | `finding_id`、task ID、结论、evidence/source IDs、limitations/conflicts |
| `ResearchTaskResult` | 汇总单个 Researcher 的 Source/Evidence/Finding，作为 Supervisor 可观察的 bounded structured result |

`EvidenceNeed` 不作为独立 Graph Stage。医学 question type、PICO 字段、study hierarchy 和 source
policy 的精确枚举仍为 **TODO(P2-S3)**，不能凭通用医学常识自行补全。

**P2-S5 implementation-level freeze** 才覆盖：

- `EvidenceRef` / `FindingRef` 与 `ClaimRecord`；
- claim-centered `ClaimGroundingRecord`，不引入 Relation/EvidenceGroup proof graph；
- Evidence-level canonical `Citation` 与 derived reader-facing Source display；
- atomic `GroundingManifest`、V2 Shadow Renderer 与 Research Run isolation。

因此 P2-S3 只保留这些概念在目标链中的位置，current P2-S5 semantics 由 phase SPEC 与 Contracts v1 冻结。

**Artifact storage boundary（architectural freeze）**：Store 是架构边界，不是 P2-S3 的实现目标。
P2-S3 中 `artifact_ref` 只是 optional / opaque reference，不要求真实 Artifact Store 或解析协议。

> **Invariant:** Graph State MUST NOT persist raw source artifacts such as full HTML, full PDF text,
> large search-provider payloads, or binary documents.

P2-S4 再实现最小存储路径：

```text
ArtifactStore Protocol
  ↓
LocalArtifactStore
```

## 8. Architecture Principles

1. **Preserve topology, change contracts first.**
2. Node 边界由业务责任、State contract、failure boundary 与 eval boundary 决定；Node 不等于一次 LLM call。
3. Semantic judgment 交给 LLM；deterministic enforcement 交给 Code / Runtime。
4. Local Researcher 产生 Evidence / Findings；Global Synthesis 产生 Claims。
5. Generator 与 Verifier 是分离的职责。
6. Process Artifacts 与 Evidence Artifacts 必须分离。
7. 每项架构变更都必须声明可验证的 Eval hypothesis。
8. 不因某种架构“看起来更先进”而迁移；迁移必须解决已证明的问题。

## 9. MVP Scope

第一轮 MVP 是一条可审计的纵向切片：

- P2-S3：单轮医学问题；MedicalResearchBrief（内含 evidence_needs[]）、MedicalResearchTask v1。
- 保留 Agentic Supervisor、`ConductResearch` 语义和 Researcher Subgraph 拓扑。
- P2-S4：先支持当前 Tavily 主路径；生成 SourceRecord、EvidenceRecord、ResearchFinding、
  ResearchTaskResult；ResearchTaskResult 内联 compact Source/Evidence ledger，并落地 run-scoped
  LocalArtifactStore，使 provenance 可完整穿过 Researcher boundary。
- Legacy 文本路径与结构化 Evidence 路径 dual-write / shadow。
- P2-S5：从 `ResearchTaskResult[]` 产生 Claim、Claim-level Grounding、Citation 与 atomic Manifest；运行
  constrained V2 Shadow Report、external faithfulness evaluation，并保持 V1 compatibility 与 one-active-Research-Run
  provenance isolation。
- 少量 Frozen Evidence fixtures，用于 contract、citation、support/contradiction 回归。

## 10. Explicit Non-goals

P2-S3～P2-S5 不以以下内容为核心目标：

- 完整前端或 UI 产品化；医院生产部署。
- 完整医学 RAG 知识库、长期 Memory 或 PubMed 专项集成。
- Plan + Send / Graph-native fan-out 迁移。
- Durable Queue、跨进程 Worker、完整 task orchestration 重构。
- 多租户产品化或现有 Auth 的复杂权限重构。
- 所有 Search Provider 的统一完整 Adapter；MCP/Native Search 只保留 capability contract。
- 完整 Trajectory Harness、完整 Online Eval 或生产反馈闭环。
- 综合 Truth Score、全套医学 risk-of-bias 自动评估。

Evidence Store / RAG is a future reuse/retrieval layer built on top of stable Source/Evidence contracts;
it is not required for the first Evidence-native vertical slice. A future Persistence / Retrieval phase may
introduce durable Evidence persistence and derived, rebuildable retrieval indexes; a Vector Store must not
become the authoritative provenance store.

## 11. P2-S3～P2-S6 Roadmap

| Phase | Focus | Roadmap summary（not implementation evidence；canonical status 由各 phase docs 决定） |
|---|---|---|
| P2-S3 | Domain & Evidence Contracts | 只冻结 MedicalResearchBrief、MedicalResearchTask、SourceRecord、EvidenceRecord、ResearchFinding、ResearchTaskResult；同时冻结 identity/provenance invariants、医学规划 fixtures、legacy compatibility 与 Eval hypotheses；不实现 Artifact Store |
| P2-S4 | Evidence-native Researcher | Tavily structured ingestion；Researcher 输出包含 compact Source/Evidence ledger 的 self-contained ResearchTaskResult；IDs 穿过 compression 与 Supervisor bounded projection；dual-write；实现 run-scoped `ArtifactStore Protocol → LocalArtifactStore` 与 Publication Gate |
| P2-S5 | Claim-centered Grounding | 冻结 ClaimRecord、ClaimGroundingRecord、Citation、GroundingManifest 与 Research Run isolation；实现 Claim-first V2 shadow path 与 V1/V2 comparison |
| P2-S6 | Evaluation & Reliability | Frozen regression、Judge calibration、deterministic hard gates、effective experiment manifest；在三条 Track 内改善 partial-failure 可观测性 |

完整 Trajectory、Provider 扩展、Send、Durable Queue、Online feedback 属于 P2-S6 之后的 Future Work，
除非新的证据和 ADR 调整优先级。

## 12. Acceptance Criteria

设计进入实现与阶段完成必须满足：

1. **Topology**：首版仍使用 ODR Supervisor–Researcher Tool Loop；不存在隐式 Send/RAG 重构。
2. **Planning**：医学 fixture 能输出 schema-valid MedicalResearchBrief/Task，Brief 内含 nested
   evidence_needs；任务不是固定 topic 模板，且可评价 coverage、specificity、non-overlap。具体质量阈值
   **TODO(P2-S3 baseline)**。
3. **Evidence**：每个被接受 Source 有稳定 ID；每个 Evidence 可回到 Source/locator；每个 Finding
   至少引用一个有效 Evidence ID；AIMessage 不能被标记为 external evidence；Graph State 不持久化完整
   HTML、完整 PDF 文本、大型 search-provider payload 或二进制文档。
4. **Provenance**：任意 Final Citation 可确定性解析；未知 ID 作为显式失败；Compression 不得产生
   输入 Registry 中不存在的 Source/Evidence ID。
5. **Grounding**：每个 Support Judgment 保存 label、Evidence IDs 与 reason；Contradiction 单独可见；
   空 Claim 集不产生伪高分或除零。
6. **Migration**：Legacy report 可继续生成；结构化链路可 shadow 对比且有 schema version。
7. **Evaluation**：Frozen fixtures 可重复运行；每个架构改动能关联一个指标或 failure hypothesis；
   Judge/Release 数值阈值必须由人工校准数据决定，当前为 **TODO(P2-S6)**。

## 13. Open Design Decisions

- **TODO(P2-S3)**：MedicalResearchBrief 的 question type、PICO 可选性，以及 nested EvidenceNeed 与
  医学证据层级的精确枚举；需由领域样本/评审支撑。
- **TODO(P2-S3)**：`ConductResearch` 是直接接收完整 MedicalResearchTask，还是保留兼容 envelope；
  两者都不得改变 Supervisor 的运行时再规划能力。
- **TODO(P2-S3)**：Source canonicalization、稳定 source ID、run-local `[S01]` 与内部 ID 的映射规则。
- **TODO(P2-S3)**：EvidenceRecord 的 chunk 粒度与 locator 规则。
- **TODO(P2-S4 implementation)**：ArtifactStore Protocol、run-scoped LocalArtifactStore 的具体适配与
  隐私/版权处理；post-run retention / GC、durable object storage 与迁移策略延后到未来 Persistence
  phase。P2-S3 的 `artifact_ref` 仍只是 optional / opaque reference。
- **TODO(P2-S4 implementation)**：按 frozen S4 SPEC 实现 ResearchFinding structured output 与 legacy
  `compressed_research` dual-write，并保留既有 Finding/Result conflict 字段语义；不得重新选择 Domain
  representation。
- **RESOLVED(P2-S5)**：采用 Claim-first Global Synthesis、独立 Generator/Judge logical roles、Host-owned
  five-state materialization 与 exact Citation Gate；详见 P2-S5 SPEC/Clarifications。
- **DEFERRED(P2-S6)**：Judge calibration、医学 source-quality rubric 与 release thresholds；不得直接沿用未经
  校准的通用 Judge 权重。
- **TODO(P2-S6)**：Frozen Dataset 版本、人工校准规模、Hard Gate 和 Release threshold；阈值不能由
  本计划臆定。
