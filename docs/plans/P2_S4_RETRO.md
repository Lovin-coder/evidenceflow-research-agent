# P2-S4 — Evidence-native Researcher 阶段复盘与 Closeout 记录

## 0. 状态、内容概览与 Review 结论

| 项目 | 结果 |
|---|---|
| 阶段 | P2-S4 |
| Closeout 日期 | 2026-08-22 |
| 文档整理日期 | 2026-08-22 |
| Implementation | **COMPLETE / POST-REVIEW CORRECTED / HUMAN ACCEPTED** |
| Deterministic validation | **PASS** |
| Real medical runtime smoke | **INCOMPLETE — STRUCTURED EXECUTOR PASS; SINGLE RESEARCHER TIMEOUT; FULL GRAPH SKIPPED** |
| Full-graph 处置 | 人工授权本次 Closeout 跳过；仍记为未完成，不得记录为 PASS |
| Corrective human review | **PASS — HUMAN ACCEPTED (2026-08-22)** |
| Closeout classification | `COMPLETE_WITH_RUNTIME_SMOKE_INCOMPLETE` |
| Frozen SPEC | Unchanged |
| Plan/task mapping commit | `11648e4`（`docs: record P2-S4 implementation and corrective mapping`） |
| Implementation commit | `26cab8a`（`feat: implement P2-S4 evidence-native researcher runtime`） |
| Contribution evidence commit | `9e33a75`（`docs: update P2-S4 contribution evidence`） |
| Closeout commit | 本文所在 commit；提交后以 Git history 或可选 `p2-s4-closeout` tag 定位 |

P2-S4 完成了冻结设计中的 Tavily-first Evidence-native vertical slice，以及 D15 self-contained
`ResearchTaskResult` carrier。主要交付覆盖 Source/Evidence ingestion、run-scoped ArtifactStore、
structured Data Plane、Model Context 隔离、Finding materialization、failure preservation、容量准入和
Publication Gate。

本文同时记录四项 post-review corrective finding 的根因、修正与回归证据。P2-S4 没有实现 durable
Evidence persistence、RAG、Claim/Citation、Groundedness redesign、Temporal Source Versioning，也没有
改变 Graph topology。

本次文档 Review 结论如下：

- 实现范围、架构延续、Failure 行为、确定性验证、Runtime smoke、corrective finding、Deferred scope
  和人工验收面均已记录，内容上满足进入 Closeout commit 的要求；
- deterministic validation 可以记为 `PASS`；
- controlled full-graph runtime smoke 仍未完成，只能维持 `INCOMPLETE / SKIPPED`；
- 人工授权跳过 full graph 是一次性 Closeout disposition，不构成 T15 通过证据；
- corrective diff 已通过人工验收；阶段以 `COMPLETE_WITH_RUNTIME_SMOKE_INCOMPLETE` 完成限定式 Closeout，
  不声称 full-graph Runtime PASS。

---

## 1. 已实现内容

### 1.1 T00A / T00 — Contract promotion 与约束保护

- `ResearchTaskResult` 携带有序且紧凑的 `source_records` 和 `evidence_records`，同时保留完全对应的
  `source_ids` 和 `evidence_ids` 有序投影。
- 严格 validator 拒绝重复或 dangling 的 Source/Evidence/Finding identity，并执行单记录与 Result
  provenance 总量约束。
- S3 empty-ledger payload 仍可被升级后的 consumer 读取；strict-old-consumer 确定性测试说明，包含真实
  Source/Evidence 的 S4 producer/consumer 必须采用 atomic promotion。

### 1.2 T01–T05 — Ingestion core

- `normalize_source_text()` 定义 ArtifactStore 中 exact normalized content 的坐标空间。
- `CandidateChunk` 保持 internal frozen dataclass；chunker 使用 deterministic paragraph-first 策略，并按
  sentence、whitespace、hard boundary 依次回退，生成 contiguous、zero-overlap、bounded chunk。
- `LocalFileArtifactStore` 在 run-scoped namespace 中持久化 exact normalized UTF-8 text，并返回 opaque
  content-hash reference。
- `WebpageSelection` 只允许模型返回 derived summary 与 Candidate ID；Host validation 拒绝 unknown 或
  over-bound ID，同时保留合法 sibling selection。
- Source/Evidence ID、`[start,end)` locator、exact excerpt、hash、Source binding 和 deterministic
  provenance replay 均由 Host 控制。

### 1.3 T06–T09 — Structured search 与 dual channel

- `execute_tavily_search_structured()` 返回 transient
  `SearchExecutionResult(model_content, sources, evidences, issues)`，同时保持 agent-visible
  `tavily_search` 名称和参数 Schema 不变。
- 只有具有 usable provider `raw_content` 的 result 才能生成 authoritative Source；provider snippet、
  error、summary、missing content、`AIMessage` 和 `ToolMessage` 均不能成为 Evidence。
- `researcher_tools` 保持 `asyncio.gather()` 的稳定顺序；Tavily 使用 structured branch，非 Tavily Tool
  保留既有 generic safe path。
- Source/Evidence 直接进入 Researcher State；ToolMessage 只接收 bounded Evidence-aware projection，
  Host 不再从其字符串内容重建 Data Plane。
- Model Context bound 以完整 Source/Evidence rendering block 为单位进行准入，不会截断 excerpt 后仍将其
  标记为完整 Evidence。

### 1.4 T10–T12 — Compression、D15 publication 与 failure preservation

- Structured compression 接收 authoritative Evidence ID 和 exact excerpt，只返回 model-owned Finding
  semantics。
- Host 拒绝 unknown Evidence ID，并确定性生成 `ResearchFinding.finding_id` 和 task binding。
- Publication Gate 在 Result 越过 `ResearcherOutputState` 前检查 same-Result reference、ordered
  projection、task identity、configured bound、ArtifactStore resolution、locator equality 和 hash
  equality。
- Supervisor State 保留完整 Result；Supervisor ToolMessage 只接收 bounded status、summary、Finding、
  limitation、conflict 和 error 投影。
- Compression/Finding materialization failure 在 FAILED Result 中保留有效 Source/Evidence；
  selector/provider/result 的局部失败保留合法 sibling，且不会伪造 Evidence。
- Legacy `compressed_research`、`raw_notes` 和 final-writer compatibility channel 继续保留。

### 1.5 T13 — Deterministic integration

固定 fixture 验证了以下完整链路：

```text
Tavily-like response
→ usable-content gate
→ normalized artifact
→ ArtifactStore
→ CandidateChunk
→ selected Candidate IDs
→ Host Evidence
→ bounded Researcher ToolMessage
→ Researcher State
→ structured compression
→ ResearchFinding
→ self-contained ResearchTaskResult
→ Publication Gate
→ compiled ResearcherOutputState
→ Supervisor structured retention
→ bounded Supervisor projection
```

Compiled Researcher regression 证明 Researcher-local channel 消失后，已发布引用链仍然可以解析：

```text
Finding.evidence_id
→ Result.evidence_records
→ Evidence.source_id
→ Result.source_records
→ Source.artifact_ref
→ ArtifactStore
→ artifact[start:end]
→ exact excerpt and hash
```

---

## 2. 冻结架构延续与实现差异

Frozen SPEC 没有改变。Graph nodes/edges、Supervisor–Researcher Tool Loop、dynamic delegation、
concurrency model、public Tavily Tool Schema、strict contract version policy 和 D15 carrier semantics 均保持
不变。

| 实现差异 | 分类 | 处理方式 | 是否修改 SPEC |
|---|---|---|---|
| 新增 ingestion helper 集中在 `evidence_ingestion.py`，structured Tavily transport 仍位于 `utils.py` | `IMPLEMENTATION_LOCAL` | 避免 Candidate/selection/runtime type 进入 Domain Model，并保持 frozen file mapping | No |
| Post-review 需要在 `state.py` 增加 owning-run Artifact identity 与 bounded execution issue channel | `IMPLEMENTATION_DEFECT` | 增加 internal-only State carrier/reducer；没有改变 Domain Contract，也没有增加 Parent Source/Evidence sibling registry | No |
| Invalid/over-bound model ID 被确定性过滤并生成 warning，合法 sibling ID 继续 materialize | `IMPLEMENTATION_LOCAL` | 同时满足 Host trust boundary 与 T12 failure preservation | No |
| Model Context bound 以完整 Source/Evidence block 为单位准入，不在 excerpt 中间截断 | `IMPLEMENTATION_LOCAL` | 保持 Evidence-aware observation 的 exact-excerpt semantics | No |

---

## 3. Failure 行为

| Failure | 系统结果 |
|---|---|
| Tavily/query 整体失败 | 记录 structured degrading issue；不生成虚假的 Source/Evidence |
| `raw_content` 缺失或不可用 | 记录 structured non-evidence diagnostic；provider snippet 不会被提升为 Source |
| 单个 provider/selector result 失败 | 合法 sibling Source/Evidence 保留；已接纳的 Source 可以在没有 Evidence 的情况下保留 |
| Unknown 或 over-bound Candidate ID | 拒绝 invalid ID 并记录 warning；合法 sibling 仍可继续 materialize |
| 单个 Candidate provenance materialization 失败 | Invalid Candidate 不生成 Evidence；其他合法 materialization 结果保留 |
| Publication 阶段出现 invalid Artifact/locator/hash | Publication Gate 抛出异常；invalid/dangling Result 不会越过边界 |
| Compression 引用 unknown Evidence ID 或 Finding batch 无效 | Host 原子拒绝 Finding batch，保留合法 Source/Evidence，构造 FAILED Result，并执行同一个 Publication Gate |
| Compression 重试耗尽 | FAILED Result 保留合法 Source/Evidence，以及此前可用的 Finding |
| PARTIAL termination 或 Tool error | Structured record 保留；status 继续遵循 S3 execution semantics |

该 Failure taxonomy 明确区分：模型语义草稿无效是可恢复的 materialization failure；Result provenance
graph 无效则是不可发布错误。Publication Gate 只验证并拒绝非法候选，不负责静默修复。

---

## 4. 确定性验证证据

### 4.1 `tests/` 目录测试集 — PASS

实际用于 Closeout 的干净退出命令为：

```text
.venv/bin/pytest tests -q

72 passed, 26 warnings in 2.11s
```

该测试集覆盖 promoted contract、P2-S3 regression、Graph topology、deterministic ingestion、structured
Tavily、compression/publication、failure preservation 和 compiled-boundary integration。

早期 `uv run` wrapper invocation 已输出相同的通过结果，但 wrapper 没有正常退出并被人工中断；因此
Closeout evidence 采用后续直接执行且 exit code 为 0 的 `.venv/bin/pytest` 结果。

### 4.2 Targeted Ruff — PASS

```text
.venv/bin/ruff check \
  src/open_deep_research/artifact_store.py \
  src/open_deep_research/evidence_ingestion.py \
  src/open_deep_research/domain_models.py \
  src/open_deep_research/configuration.py \
  src/open_deep_research/state.py \
  src/open_deep_research/prompts.py \
  src/open_deep_research/utils.py \
  src/open_deep_research/deep_researcher.py \
  tests/test_domain_models.py tests/test_evidence_ingestion.py \
  tests/test_tavily_evidence_search.py tests/test_state_contracts.py \
  tests/test_p2_s3_runtime.py tests/test_p2_s4_runtime.py

All checks passed!
```

### 4.3 Scoped mypy — PASS，保留 baseline limitation

```text
MYPYPATH=src .venv/bin/mypy --explicit-package-bases --follow-imports=skip \
  src/open_deep_research/configuration.py \
  src/open_deep_research/domain_models.py \
  src/open_deep_research/state.py \
  src/open_deep_research/artifact_store.py \
  src/open_deep_research/evidence_ingestion.py \
  src/open_deep_research/deep_researcher.py \
  src/open_deep_research/prompts.py

Success: no issues found in 7 source files
```

在普通 mypy invocation 中加入完整既有 `utils.py`，仍会触发 third-party `langsmith` internal error、
missing Tavily stub 和 package-resolution baseline limitation。本阶段没有通过修改 mypy config、依赖、
lockfile 或 ignore rule 隐藏该 baseline。

### 4.4 Compile 与 diff check — PASS

```text
.venv/bin/python -m compileall -q src/open_deep_research tests
git diff --check
```

两个命令均成功退出且没有输出。

### 4.5 Repository-wide baseline — 不声明为 PASS

- Bare `pytest -q` 会收集 `src/legacy/tests/test_report_quality.py`，并在 fixture setup 阶段失败，因为既有
  `--research-agent` option 没有注册；P2-S4 diff 没有修改该 harness。
- `ruff check .` 会报告 199 个既有 legacy/diagnostic/notebook/security/evaluation lint finding；P2-S4
  targeted files 已通过，未修改无关 baseline 文件。

因此本文只声明 `.venv/bin/pytest tests -q` 和 scoped static checks 通过，不将 repository-wide bare
commands 记为 PASS。

---

## 5. Real medical runtime smoke — 部分完成，Full Graph 未完成

现有 compiled graph entry 使用配置中的 `openai:qwen3.7-plus-2026-05-26` model、Tavily、一个 concurrent
Researcher、两个 Supervisor iteration 和三个 Researcher tool turn 进行尝试。

第一次尝试在生成 `MedicalResearchBrief` 前失败：

```text
ImportError: Using SOCKS proxy, but the 'socksio' package is not installed
```

当前环境中的 `ALL_PROXY`/`all_proxy` 使用 `socks5h`。本阶段没有修改依赖或 lockfile。

Corrective retry 只在 smoke process 内移除 `ALL_PROXY`/`all_proxy`，保留已配置的 HTTP(S) proxy，读取既有
`.env`，且没有改变依赖。分阶段结果如下：

1. configured model endpoint connectivity：HTTP 200；
2. Tavily connectivity，使用一个 bounded query：HTTP 200；
3. real `execute_tavily_search_structured`：1 Source、2 Evidence、0 issue、3753 个 Model Context 字符；
4. single compiled Researcher，配置一个 tool-turn budget：Source Artifact 已持久化，但在 60 秒 hard
   timeout 前没有返回最终 `ResearchTaskResult`；
5. full compiled graph：single Researcher 达到停止条件后没有继续执行。

因此 full real smoke 状态必须保持为 **INCOMPLETE**，不能记为 PASS。Staged retry 已将尚未验证的边界
收窄到 external endpoint 和 structured search 之后的 Researcher/compression completion chain。现有证据
无法区分 model latency 与 runtime completion defect，所以不能将 timeout 简单归类为 environment-only
failure。项目没有为此次 smoke 增加 `socksio`。

Deterministic integration evidence 仍然有效，并且不依赖网络或 real LLM。

2026-08-21，human owner 明确授权本次 Closeout 跳过 full-graph retry。该授权只是一项 Closeout
disposition，不是 T15 通过证据：controlled full-graph smoke 仍保持 unchecked，并且必须继续记录为
incomplete。`P2_S4_TASKS.md` 中 T15/T16 的原始 wording 按授权不修改；本 Retro 记录一次性例外及其
剩余风险。

---

## 6. Post-review corrective finding 与经验

| Finding | 根因 | Corrective implementation | Regression evidence |
|---|---|---|---|
| P1-1 Artifact namespace | 错误假设 node-local `RunnableConfig` mutation 会向后传播，同时混淆 `thread_id` 与 owning-run identity | 从 explicit override、root runtime `run_id` 或 UUID 中 bootstrap 一次；通过 internal `artifact_run_id` 在 Parent/Supervisor/Researcher State 和 child call 中传播；Store construction 保持 pure | Multi-node、two-iteration Supervisor test 在没有 explicit ID 时解析早期 Artifact；两个共享 thread ID 的 run 相互隔离；explicit sharing 行为得到验证 |
| P1-2 Finding failure preservation | Model semantic validation 与 Result provenance invalidity 共用 `ProvenancePublicationError` | 使用 `FindingMaterializationError` 将 Finding batch 定义为 atomic/recoverable；重试耗尽后发布保留 Source/Evidence 的 gated FAILED Result；真实 provenance failure 仍由 Gate 拒绝 | Direct compression 和 compiled child-boundary invented-Evidence-ID tests 保留 records；orphan provenance 继续被拒绝 |
| P2-1 Execution issue lifecycle | Warning 只存在于 transient search output/model text，final status 通过 bounded `ToolMessage.content` 反向扫描 | 增加 bounded deterministic `ResearchExecutionIssue` State、idempotent/conflict-detecting reducer、degrading capacity reservation 和 sticky Host failure fact；status 只使用 structured fact | 即使对应 warning 不存在于 ToolMessage，status 仍为 PARTIAL；replay/conflict/sticky-success tests 通过 |
| P2-2 Provenance admission | Configured serialized bound 只在 Publication Gate 执行 | Domain hard bound、stable-order State admission 和 Gate 共用 canonical serialization helper；正常 overflow 跳过超限记录并保留 legal prefix，同时记录 `state_admission` issue | Small valid bound 接纳两个 Source 和第一个 Evidence；被拒绝 Evidence 不进入 State/Model Context；Result 在同一 bound 下成功发布 |

相邻修正还包括：

- configured provenance bound 不允许小于 canonical empty envelope；
- Issue message、identifier、count 和 total payload 均有边界，不保留 raw exception payload 或 traceback；
- T02 直接覆盖 empty input、short single block、explicit small-tail merge 和 exact slicing。

本阶段的主要经验：

- mutable Runnable config 不是 Graph State；
- Model Context 不能作为 Host control plane；
- proactive admission 与 Publication Gate 职责不同但必须共用度量；
- semantic-layer failure 不能与 provenance graph invalidity 混为一类；
- 正常容量 overflow 应保留 deterministic legal subset，而不是在最终发布阶段擦除整个有效前缀。

---

## 7. Deferred scope

以下内容继续位于 P2-S4 范围之外：

- durable EvidenceStore 与 cross-run Evidence persistence；
- global/cross-run Evidence identity 与 Source deduplication；
- RAG、embedding、reranking、semantic chunking 和 Vector Index；
- durable/object ArtifactStore、post-run retention、TTL 和 garbage collection；
- transactionality、multi-process consistency 和 object-storage migration；
- Temporal Source Versioning；
- `QueryRecord`、`RetrievalObservation` 和 `ArtifactSnapshot` Domain；
- Claim、Citation、Groundedness、contradiction judge、Evidence quality/diversity scoring；
- production-grade provider-general Evidence ingestion。

未来 Vector Index 仍应是 derived/rebuildable state，不能成为 authoritative provenance store。

---

## 8. 人工验收与最终 Closeout 结论

P2-S4 deterministic implementation、T17 post-review correction 和 acceptance tests 已完成。当前允许进入
corrective closeout commit，阶段状态必须明确记录为：

```text
COMPLETE_WITH_RUNTIME_SMOKE_INCOMPLETE
```

Human-authorized full-graph skip 不会把 Runtime smoke 转换成 PASS，也不能用于声称 end-to-end
real-provider reliability 已验证。

2026-08-22，human owner 已完成并通过 corrective diff 人工验收。验收直接检查实现，而不是仅根据测试
通过推断正确性。Accepted focused review surface 为：

1. owning-run Artifact identity 只 bootstrap 一次，通过 internal State 传播到 nested Researcher call，且
   默认值不使用 `thread_id`；
2. recoverable Finding materialization failure 与 invalid Result provenance graph 明确分离，能够保留合法
   Source/Evidence，并仍执行同一个 Publication Gate；
3. Host status 从 bounded structured execution issue 和 sticky degrading fact 派生，不依赖
   `ToolMessage` substring matching；
4. deterministic State admission 与 Publication Gate 使用同一个 canonical provenance-size measurement，
   Model Context 只包含已接纳记录。

Implementation commit 与 Reviewer sign-off 均已记录。为避免 Git commit hash 自引用，本文不预填包含
自身的 commit ID；最终 Closeout commit 由 Git history 定位，也可以在提交后增加
`p2-s4-closeout` annotated tag。

因此本次 Closeout 的准确结论是：

- **实现与确定性验证：完成；**
- **Corrective human review：通过；**
- **Closeout classification：`COMPLETE_WITH_RUNTIME_SMOKE_INCOMPLETE`；**
- **Full-graph runtime smoke：经授权跳过但仍未完成；**
- **Closeout commit：由包含本 Retro 与 Checklist 的最终文档 commit 建立。**
