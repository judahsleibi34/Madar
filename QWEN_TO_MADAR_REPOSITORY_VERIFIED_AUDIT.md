# Qwen → Madar: repository-verified integration audit

**Audit date:** 2026-10-24 (Asia/Hebron)

**Scope:** read-only inspection. No inference was run; no service was started or changed; no test, dependency installation, database operation, deployment, commit, push, or merge was performed. This report is the only file created.

## Executive decision

**Do not connect Qwen to Madar's user-facing analysis path yet.** The current Qwen candidate is a strong, privacy-bounded *reasoning over registered semantics and released evidence* system, but it is not an automatic semantic-understanding system for unfamiliar files. Its newest final-core candidate is also **not accepted**: it improved the R4 baseline from 79/95 to 84/95 correct scored final diagnoses, but produced one wrong `COMPLETE` (C030, a Simpson/composition case), four supported decoys, and five service failures. Under the project's frozen rule that any wrong `COMPLETE` is a failure ([classification criteria](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/QWEN36_MODEL_ABILITY_EVALUATION.md:364>)), the exact current status is **FAIL / no-go**.

The smallest safe next milestone is therefore a separate, offline **semantic-proposal** task: Madar privately profiles one immutable dataset version; Qwen proposes typed meanings from a deliberately approved profile; deterministic validators accept only low-risk, internally consistent mappings; consequential ambiguity requires focused human confirmation. Only approved mappings may create the existing Qwen `AliasPolicy`/registered-measure inputs. The existing evidence-reasoning pipeline should remain unchanged until that semantic task has its own frozen evaluation and the reasoning candidate clears its existing acceptance gate.

## 1. Repository and runtime identity

### 1.1 Audit anchors

| Item | Verified state |
|---|---|
| Qwen checkout lead | `/home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab` exists and contains the inspected implementation. Neither it nor its parent contains `.git`; therefore there is **no verifiable Qwen Git root, revision, branch, or dirty-state record**. File SHA-256 values below are the reproducible identity anchor. This limitation is also recorded by the project itself in [R1](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/QWEN36_TRUSTED_MATERIALITY_REPAIR.md:3>). |
| Madar Git identity | `/home/judah/Madar Projects/Madar`, branch `main`, HEAD `cf444303e55a2c6a214ab53f683442cf2fac15fe` (`Merge Judah_branch: persistent synchronized data sources`, 2026-10-22 15:32:22 +0300). The worktree already contained many unrelated tracked and untracked changes before this report; they were not modified. |
| Qwen runtime now | `qwen-worker`, `qwen-broker`, and `qwen-identity` were all inactive/dead with no main PID; no Qwen/`llama-server` process was present. Consequently **no loaded checkpoint or active inference engine can be runtime-verified today**. |
| Latest candidate identity | Current product files match the candidate hashes frozen before final-core acceptance runs in [freeze.txt](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/runs/final_core/freeze.txt:1>). The freeze explicitly says P1 is active and the secured worker/settings were unchanged. |

### 1.2 Model and engine

The currently available and source-configured artifact is:

- `/home/judah/models/Qwen3.6-35B-A3B-Q4_K_M.gguf`
- size: `20,419,565,568` bytes
- SHA-256: `671e47e0ec53c665d048b98c3ecbfd5236b5ca9c3e02ed19fc8f81f7b85140c7`
- quantization: `Q4_K_M` (from the artifact/configured filename; the stopped runtime prevents an independent loaded-model query)
- configured engine: `/home/judah/tools/llama.cpp/build/bin/llama-server`
- inspected binary version: `0.7.0-dev (build 1, commit 2f729cf)`
- binary SHA-256: `cd189e9d3df649c504323608419006eb23c33bb72b279b035bd6b4f2d133c277`

The source launcher approves the 35B artifact, binds `127.0.0.1:8080`, uses context 4096, one parallel sequence, `--n-predict 1024`, all GPU layers with CPU MoE, reasoning disabled, offline mode, and a 120-second request timeout; it disables the Web UI, slots endpoint, prompt cache, and CORS and reads a bearer credential from a file rather than exposing it in argv ([`llama_worker.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/llama_worker.py:28>), [`llama_worker.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/llama_worker.py:44>)). Sampling defaults are temperature 0.2, top-p 0.9 and 1,024 maximum output tokens ([`config.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/config.py:3>)). No credential value was read or recorded.

This is the historical **35B replacement**, not evidence of a newer model. No newer configured artifact was found. However, old deployment unit/install artifacts still refer to `Qwen3.5-9B-Q4_K_M` ([unit](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/deploy/units/qwen-worker.service:5>), [installer](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/deploy/install-protected-stack.sh:24>)); those are stale relative to the launcher and final-core manifests. Because the services are stopped, the defensible wording is “current candidate is configured for and frozen against the 35B artifact,” not “35B is actively loaded.” Historical reports saying the worker was running describe their run time, not the audit-time state ([R1 worker record](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/QWEN36_TRUSTED_MATERIALITY_REPAIR.md:224>)).

### 1.3 Current source hash identity

The following current files match the final-core candidate freeze byte-for-byte: `analysis_ops.py` `3ada67c6…`, `attribution.py` `10633239…`, `evidence_semantics.py` `1fae4462…`, `investigation.py` `293d5658…`, `recommendation.py` `fdbd8728…`, `investigation_protocol.py` `56411934…`, `diagnostic_planner.py` `e1289318…`, `model_gateway.py` `50538ca7…`, `config.py` `334ef548…`, and `private_schema_aliases.py` `4d240cef…`. The complete hashes and the R4 comparison snapshot are in [the frozen manifest](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/runs/final_core/freeze.txt:12>).

## 2. Actual reasoning pipeline

### 2.1 Source-linked call graph

| Stage | Active code and responsibility |
|---|---|
| Question understanding | [`QuestionUnderstanding.understand`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/question_understanding.py:324>) and its private `_understand`/`resolve` path parse supported objectives, measures, periods, direction and ambiguity deterministically. Free-form model interpretation is disabled in the legacy interpreter ([`request_interpreter.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/request_interpreter.py:70>)). |
| Trusted diagnostic plan | [`DiagnosticPlanner.plan`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/diagnostic_planner.py:77>) constructs registered candidate analyses; candidate construction starts at [line 271](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/diagnostic_planner.py:271>). |
| Private schema boundary | [`AliasPolicy`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/private_schema_aliases.py:133>) is caller-declared; [`AliasSession._create`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/private_schema_aliases.py:407>) creates `field_NNN` aliases while keeping labels in `PrivateRaw`; [`model_schema`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/private_schema_aliases.py:545>) emits only approved alias/type/role metadata; [`build_view`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/private_schema_aliases.py:702>) renames the trusted frame. |
| Private profiling | [`PrivateIntelligenceEngine.profile`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/private_intelligence_engine.py:780>) and `_profile_field` compute exact private facts. These are not semantic proposals and are not model-visible. |
| Trusted analytics | [`DatasetView`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/analysis_ops.py:155>), [`validate_spec`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/analysis_ops.py:253>) and [`execute`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/analysis_ops.py:559>) validate and calculate registered operations. Revenue and COGS definitions are deterministic (`quantity × unit_price`, `quantity × unit_cost`) ([`analysis_ops.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/analysis_ops.py:20>)). |
| Privacy authorization/release | [`privacy_review`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/analysis_ops.py:898>) reviews trusted output; [`build_model_evidence`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evidence_boundary.py:695>) creates the released representation. The product gate/executor separation is in [`investigation_runtime.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/investigation_runtime.py:192>) and [line 288](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/investigation_runtime.py:288>). |
| Investigation state machine | [`InvestigationController`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/investigation.py:355>) manages plans, evidence, budgets and transitions. It builds the model packet at [`packet`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/investigation.py:1658>) and calls the model via [`_ask`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/investigation.py:1766>). |
| Request contract and serialization | Typed investigation requests begin at [`model_gateway.py:1328`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/model_gateway.py:1328>). [`_model_body`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/model_gateway.py:2061>) rejects `PrivateRaw`, validates releases, caps input and scans sensitive tokens. [`send`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/model_gateway.py:2123>) dispatches through the configured transport. |
| Broker/worker path | [`BrokerTransport.dispatch`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/broker_client.py:334>) sends typed IPC. Broker request schemas are enforced in [`qwen_broker.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/qwen_broker.py:211>), handling begins at [line 471](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/qwen_broker.py:471>), and revision/relationship provenance is recorded at [line 543](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/qwen_broker.py:543>). |
| Structured output | Static prompts and JSON schemas are selected at [`model_gateway.py:1561`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/model_gateway.py:1561>). The llama.cpp transport posts OpenAI-style `/v1/chat/completions`, requests non-streamed JSON-schema output and requires `finish_reason=stop` ([`model_gateway.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/model_gateway.py:1881>), [`model_gateway.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/model_gateway.py:1929>), [`model_gateway.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/model_gateway.py:1987>)). |
| Independent verification | Strict JSON and claim checks live in [`answer_verification.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/answer_verification.py:20>) and [`verify_claims`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/answer_verification.py:159>). Trusted evidence interpretation is independent in [`EvidenceSemantics.read`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evidence_semantics.py:181>), [`verdict`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evidence_semantics.py:368>) and [`verify`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evidence_semantics.py:497>). |
| Feedback/retries | Invalid proposals receive bounded, structured correction feedback; correction/failed-branch limits are enforced in [`_reject`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/investigation.py:1593>). Ledger refusal withholds the newest release and retries the step ([`_withhold_newest`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/investigation.py:1554>)). This is bounded state-machine correction, not a provider/model fallback. |
| Completion | [`_checkpoint`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/investigation.py:1500>) requires a concluded stop, supported hypothesis and recommendation; [`completion_gaps`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/investigation.py:1514>) independently checks verified cause, contribution, requested location, decision estimate and recommendation before `COMPLETE`. |
| Customer report | Recommendation validation/rendering is trusted code in [`recommendation.render`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/recommendation.py:736>); reports distinguish verified evidence, unresolved hypotheses, withheld analyses and actions not taken. |

### 2.2 Active paths, retries and fallback

- The final-core runner explicitly defaults to **fast mode** ([`evaluation/final_core/run.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/final_core/run.py:27>)). Deep/adaptive machinery remains present, but R4 documents a duplicated/older mechanism table in the deep path that its live tests did not cover ([R4](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/QWEN_R4_GENERALIZATION.md:35>)). Do not treat deep as equivalent to the accepted fast-path evidence.
- `default_transport()` selects exactly one of llama.cpp loopback, Unix-socket broker, or LM Studio from configuration; it does not fail over between them ([`model_gateway.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/model_gateway.py:2035>)). The inspected default is llama.cpp; broker is a separate configured path. The legacy LM Studio model label is not evidence of an active second model.
- Model-output correction, proposal correction and evidence-withholding retries are bounded inside the investigation. Transport/service failure is surfaced; there is no automatic provider or checkpoint fallback proven by the current source.
- The catalogue experiment gate is explicitly synthetic-only ([`investigation_runtime.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/investigation_runtime.py:213>)); it is not a second production analysis path.

## 3. Model-visible input and API contract

### 3.1 What Qwen receives in the secured reasoning task

| Data class | Received? | Verified boundary |
|---|---:|---|
| Original column names | **No** | Raw labels remain `PrivateRaw`; model schema uses aliases and optionally declared roles ([`private_schema_aliases.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/private_schema_aliases.py:428>), [line 545](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/private_schema_aliases.py:545>)). |
| Technical schema | **Limited** | Alias, type and explicitly disclosed role/catalog facts; not the raw source schema. |
| Raw sample records | **No** | Protocol explicitly excludes records and raw labels ([`investigation_protocol.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/investigation_protocol.py:1>)); gateway rejects `PrivateRaw`. |
| Categorical summaries | **Counts only, not labels** | Dimension roles and anonymous group counts may be sent; groups become `gN`. |
| Exact aggregate numeric values | **No in model request** | Exact trusted rows remain beside released evidence for verification; R2 records that Qwen never sees them ([R2](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/QWEN_GENERALIZED_EVIDENCE_AUDIT.md:38>)). |
| Qualitative evidence tokens | **Yes** | Operation, registered measure, period/grain, `up/down/flat`, magnitude/weight/role, suppression and withholding status, and opaque evidence IDs are serialized by the packet builder ([`investigation.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/investigation.py:1658>)). |
| Opaque identifiers | **Yes** | `field_NNN`, `gN`, `eN`, hypothesis/option IDs, investigation/revision bindings. |
| User wording | **Typed problem, not arbitrary raw request in evidence calls** | The protocol receives objective, registered metric, direction and periods. Free-text request types are disabled by `_model_body`. |

The investigation request contains: protocol/phase; typed problem; registered dimension roles and anonymous group counts; registered measures; available periods, grains and operations; privacy-reviewed qualitative evidence; budgets; prior hypotheses; rejected/withheld metadata; which evidence tests which candidate drivers; untestable reasons; scenario options; and a binding/release approval. The response is phase-specific JSON validated against a static schema: proposed analyses or an interpretation/recommendation with registered drivers, evidence IDs, opaque locations, alternatives, unknowns and follow-up. The model never supplies executable code, source columns, trusted labels or authoritative numbers; trusted code validates every spec and claim ([`analysis_ops.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/analysis_ops.py:1>), [`model_gateway.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/model_gateway.py:1328>)).

At the native worker boundary, the body contains the configured model alias, static system prompt, model input, reasoning mode, maximum output tokens, temperature/top-p, `store=false` and `stream=false`; the llama.cpp adapter maps this to system/user messages plus a JSON response schema ([`model_gateway.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/model_gateway.py:2094>), [line 1929](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/model_gateway.py:1929>)). Authentication is a redacted bearer token loaded from a protected file; loopback/Unix-socket boundaries avoid a public listener.

## 4. Evaluation history and exact current status

### 4.1 Milestones

| Milestone | Frozen result and meaning |
|---|---|
| R1 | **PASS for its scoped materiality repair.** Fixed the V10 immaterial per-record acceptance; nine live runs had zero wrong `COMPLETE`; H8 completed in 2/3 and was incomplete in 1/3, exposing sampling variability. A separate prompt/controller refinement candidate remained rejected and unadopted ([R1](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/QWEN36_TRUSTED_MATERIALITY_REPAIR.md:5>), [remaining weaknesses](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/QWEN36_TRUSTED_MATERIALITY_REPAIR.md:209>), [rejected candidate](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/QWEN36_TRUSTED_MATERIALITY_REPAIR.md:218>)). |
| R2 | **Audit/prototype only.** Found direction-only whole-business materiality and a stock-to-sales unit bug. Fresh cases: R1 13/18, +P1 16/18, +P2 14/18, combined 17/18. Neither proposal was then active ([R2](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/QWEN_GENERALIZED_EVIDENCE_AUDIT.md:11>), [case table](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/QWEN_GENERALIZED_EVIDENCE_AUDIT.md:178>)). |
| R3 | **PASS for P2.** Unit-aware grading was adopted; live correct diagnoses 22/24, locations 21/21, wrong `COMPLETE` 0, with P1 expressly out of scope ([R3](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/QWEN_R3_UNIT_AWARE_GRADING.md:3>), [verdict](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/QWEN_R3_UNIT_AWARE_GRADING.md:15>)). |
| R4 | **QUALIFIED PASS.** 48/48 on 16 unseen cases across 12 business types; 0 wrong `COMPLETE` in 71 live runs; first answers remained weak. P1 was explicitly not active at R4 ([R4](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/QWEN_R4_GENERALIZATION.md:3>), [verdict](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/QWEN_R4_GENERALIZATION.md:13>)). |
| Final core | **FAIL / no-go.** Later candidate, P1 active by default, 100-case frozen cohort. Its product hashes match current source, so it is the latest active development candidate, not the earlier rejected refinement experiment. It has not earned acceptance. |

### 4.2 Final-core frozen artifacts

- Cohort: 100 distinct cases C001–C100 ([`cases.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/final_core/cases.py:1>)); baseline and candidate each attempted 100. Five service failures in each arm left denominator 95.
- Repeat cohort: 30 attempted repetitions over the frozen repeated subset; two service failures left denominator 28.
- `evaluation/runs/final_core/freeze.txt`: SHA-256 `d543ce4690423992e965d8aa60813e216273daf78a003a316f23cf79b4de956e`.
- [`score_summary.txt`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/runs/final_core/score_summary.txt:1>): SHA-256 `6df34fd5dc15dc80e4fff2536fc4142a9bf9956aeb5e9a3415ee3057b864f900`.
- [`scored_230.json`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/runs/final_core/scored_230.json:1>): SHA-256 `607f38e46f09e0e6bf311caa0161bb240115c1866ee6d3ef568094d454b4784c`.
- Cohort generator hash `de8f265b…`; scorer hash `d0fd5549…`; ground truth hash `d5792e61…`; all full values are frozen in [the manifest](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/runs/final_core/freeze.txt:1>). The scorer was frozen before acceptance and checks diagnosis, unsupported causes, completion, location, decompositions, recommendations, decoys and security ([`score.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/final_core/score.py:1>)).

| Arm | Final results | Core/evidence and reliability |
|---|---|---|
| R4 baseline | 79/95 correct; 6 wrong `COMPLETE`; 10 unnecessary `INCOMPLETE`; location 19/20; 14 decoys; useful recommendation 86/95; security findings 0 | First-answer diagnosis 33/50; evidence 59/95. Median 37.96 s, p95 48.20 s, median 2 calls. |
| Candidate/current hashes | **84/95 correct; 1 wrong `COMPLETE`; 10 unnecessary `INCOMPLETE`; location 20/20; 4 decoys; useful recommendation 89/95; security findings 0** | Core no-cause 95/95, level 39/39, outcome 5/5, unsupported 10/10, reconciled 65/65, recommendation 95/95. First-answer diagnosis 31/50 and evidence 67/95. Median 37.91 s, p95 49.34 s, median 2 calls. |
| Repeat | 24/28 correct; 0 wrong `COMPLETE`; 4 unnecessary `INCOMPLETE`; location 5/6; 2 decoys; recommendation 27/28; security 0 | The subset did **not** repeat C030, so zero repeat wrong-completes does not clear the known failure. Two repeat service failures remained. |

The wrong `COMPLETE` is C030: the ground truth is a Simpson/composition case where the aggregate asked measure falls 12% although each product's price rises about 2% ([`ground_truth.json`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/runs/final_core/ground_truth.json:548>)); the candidate nevertheless logged `COMPLETE / CONCLUSION_READY` ([`candidate_a.log`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/runs/final_core/candidate_a.log:30>)). This is the concrete multi-group aggregate/composition failure. Candidate decoys occurred in C030, C077, C080 and C096. The five candidate service errors were C046–C050 (`SERVICE_UNAVAILABLE`) ([`candidate_a.log`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/runs/final_core/candidate_a.log:46>)); repeat service errors recurred on C046 repetitions 2 and 3 ([`candidate_rep.log`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/runs/final_core/candidate_rep.log:7>)). These are operational failures, not scored as improved reasoning.

H8's R1 behavior remains historical evidence, not part of the named final-core cohort. Final-core adds broader independent families and supersedes it as the latest acceptance evidence. P1/relative materiality is current and passed all final-core “level” checks, but did not eliminate the C030 composition error or decoys. Privacy remained clean (0 scorer findings), exact decompositions reconciled 65/65, and independent verification improved markedly; none of those facts waives the wrong-`COMPLETE` hard gate.

## 5. Automatic semantic-interpretation readiness

Classification: **1** implemented/tested; **2** implemented/unverified; **3** experimental; **4** absent; **5** unknown.

| Capability | Class | Repository-backed finding |
|---|---:|---|
| Profile unknown datasets | **1 (technical only)** | Qwen privately profiles types/statistics ([`private_intelligence_engine.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/private_intelligence_engine.py:780>)); Madar profiles columns, missingness, uniqueness, samples and numeric/categorical summaries ([`profile.py`](</home/judah/Madar Projects/Madar/web/backend/data_analysis/ai/profile.py:354>), [dataframe profile](</home/judah/Madar Projects/Madar/web/backend/data_analysis/ai/profile.py:425>)). Neither proves business meaning. |
| Interpret raw column names | **4 in secured Qwen** | The secure path deliberately hides them. Madar passes non-sensitive raw names/kinds to its generic planner ([`service.py`](</home/judah/Madar Projects/Madar/web/backend/data_analysis/ai/service.py:297>)), but its configured real providers are unimplemented ([`planner.py`](</home/judah/Madar Projects/Madar/web/backend/data_analysis/ai/planner.py:89>)); no semantic-mapping workflow/evaluation exists. |
| Infer business meaning | **4** | Qwen consumes caller-declared roles/registered measures. There is no proposal schema, validator or acceptance lifecycle from unknown labels to meanings. |
| Classify transaction types | **4** | Metric/role semantics are declared and validated, not inferred ([`private_schema_aliases.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/private_schema_aliases.py:589>)). |
| Identify currency/units | **2 for declared validation; 4 for inference** | Final-core adds a caller-declared `currency` role at runtime ([`run.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/evaluation/final_core/run.py:18>)); unit-aware evidence grading is tested, but discovery from file values/names is absent. |
| Propose grain/stable keys | **4** | Time grain is selected for analysis after semantics exist. No record-grain/entity-key proposal or uniqueness/stability validator was found. |
| Suggest financial/operational KPIs | **2 within registered catalogue; 4 from unknown schema** | Qwen recommendations select monitors from registered measures; Madar can execute a generic deterministic KPI action. Neither discovers defensible metric definitions from unfamiliar columns. |
| Identify dataset relationships | **2 for privacy provenance; 4 for semantic joins** | Broker records revisions/related datasets to control disclosure ([`qwen_broker.py`](</home/judah/Madar Projects/Qwen 9b/qwen_prompt_lab/qwen_broker.py:543>)); it does not infer join keys, cardinality, temporal alignment or semantic compatibility. |
| Validate proposed mappings | **2 (building blocks only)** | `AliasPolicy` and metric declarations reject invalid caller declarations, but there is no typed proposal object, confidence/evidence contract, comparison against private profiles or approval state machine. |
| Abstain on semantic ambiguity | **3** | Question understanding and schema resolution can reject ambiguity, but no evaluated mapping-specific abstention/confirmation workflow exists. |
| Arabic/mixed-language schemas | **3 in Madar UI prompts; 4 for semantic mapping** | Madar's generic analysis prompt preserves exact Arabic column names and can answer in Arabic ([`prompts.py`](</home/judah/Madar Projects/Madar/web/backend/data_analysis/ai/prompts.py:7>)); its sensitivity keyword list includes Arabic. No frozen Arabic/mixed-schema semantic-mapping cohort was found. Qwen aliases remove source-language labels from its reasoning task. |

**Conclusion:** general LLM language ability is irrelevant to readiness until raw-name/value disclosure is explicitly designed, privacy-reviewed, validated and evaluated. Qwen's current strength begins *after* semantics have been registered.

## 6. Madar compatibility and reusable contracts

### 6.1 Existing reusable components

- **Tenant/project-scoped immutable versions:** `data_datasets` and `data_dataset_versions` store ownership, version number, storage identity, content hash, file metadata and provenance ([migration 147](</home/judah/Madar Projects/Madar/web/database/migrations/147_add_project_datasets.sql:32>), [version table](</home/judah/Madar Projects/Madar/web/database/migrations/147_add_project_datasets.sql:64>)). The service resolves an exact authorized version ([`project_dataset_service.py`](</home/judah/Madar Projects/Madar/web/backend/services/project_dataset_service.py:301>)).
- **Sources and async ingestion:** sources point to their latest committed dataset/version ([migration 148](</home/judah/Madar Projects/Madar/web/database/migrations/148_add_project_data_sources.sql:23>)); ingestion runs provide explicit async state, idempotency and result version ([migration 149](</home/judah/Madar Projects/Madar/web/database/migrations/149_add_source_ingestion_runs.sql:27>)); resources/checkpoints retain revision/cursor/schema fingerprint ([migration 152](</home/judah/Madar Projects/Madar/web/database/migrations/152_add_incremental_source_ingestion.sql:18>), [checkpoint table](</home/judah/Madar Projects/Madar/web/database/migrations/152_add_incremental_source_ingestion.sql:265>)). Reuse this lifecycle instead of inventing another ingestion subsystem.
- **Technical profiler:** Madar already computes a rich private profile. Numeric min/max/mean/quantiles and categorical top values are exact ([`profile.py`](</home/judah/Madar Projects/Madar/web/backend/data_analysis/ai/profile.py:278>), [line 312](</home/judah/Madar Projects/Madar/web/backend/data_analysis/ai/profile.py:312>)).
- **Deterministic analysis executor:** summary, missingness, KPI, group-by, trend, top-N, correlation, distribution and chart operations already exist in [`predefined_executor.py`](</home/judah/Madar Projects/Madar/web/backend/data_analysis/ai/predefined_executor.py:27>). These are safe primitives, not business metric definitions.
- **Version provenance pattern:** the version-aware assisted route resolves the immutable storage identifier and returns project/dataset/version/content-hash provenance ([`analysis_routes.py`](</home/judah/Madar Projects/Madar/web/backend/data_analysis/routes/analysis_routes.py:194>)). This is the pattern the future semantic and reasoning jobs should use.
- **Qwen reusable core:** aliasing/private raw types, registered measure/spec validation, trusted operations, privacy gate/release ledger, typed broker dispatch, evidence semantics, claim/recommendation verification and reporting can be reused once an approved semantic mapping exists.

### 6.2 Missing or incompatible contracts

| Contract | Current gap |
|---|---|
| Privacy-approved schema profile | Madar's planner receives raw non-sensitive column names; its code-generator prompt receives the **full** profile, which can contain sample rows, exact numeric aggregates and categorical values ([`service.py`](</home/judah/Madar Projects/Madar/web/backend/data_analysis/ai/service.py:167>), [`planner.py`](</home/judah/Madar Projects/Madar/web/backend/data_analysis/ai/planner.py:66>)). That is incompatible with Qwen's evidence boundary. A separate allowlisted semantic-profile release is required. |
| Structured semantic proposal | No persisted typed object for column meaning, entity role, measure, unit/currency, grain, key, confidence, alternatives, supporting profile facts or abstention reason. |
| Validated metric definition | Qwen has a fixed registered catalogue and Madar has generic aggregations, but Madar lacks a versioned contract binding a business metric to approved source fields, formula, aggregation, unit, filters and validity interval. |
| Relationship check | No persisted, deterministic join proposal/validation contract covering key uniqueness, cardinality, nulls, match rate, temporal overlap, tenant scope and fan-out risk. |
| Analytical evidence release | Madar lacks Qwen's signed qualitative evidence-release object and ledger integration. Do not send Madar's full profile directly into the existing investigation request. |
| Existing Qwen invocation | None. Madar's AI providers are OpenAI/DeepSeek stubs and no Qwen broker adapter is present ([`planner.py`](</home/judah/Madar Projects/Madar/web/backend/data_analysis/ai/planner.py:89>)). |
| Async semantic/reasoning job | Ingestion offers reusable state/idempotency patterns, but there is no tenant-scoped Qwen job record with input version, mapping version, policy version, deadlines, attempts, cancellation and sanitized result/error. |
| Version-aware cache/invalidation | Qwen has recipe caching and Madar has in-process profiling caches, but no cross-system cache key binds tenant + dataset-version/content hash + profile policy + mapping version + Qwen code/model/protocol hashes. |
| AI route provenance | `/analysis/ai` reads a mutable `input_path` and does not bind its result to a dataset-version record ([`analysis_routes.py`](</home/judah/Madar Projects/Madar/web/backend/data_analysis/routes/analysis_routes.py:256>)). It must not be the integration boundary. |

### 6.3 Multi-dataset readiness

Current readiness is **not sufficient for analytical multi-dataset reasoning**. Madar persists multiple versioned datasets and source relationships operationally. Qwen tracks related revisions/datasets for authorization and differencing safety, but an investigation operates on one declared `DatasetView`; no trusted cross-dataset join planner, semantic relationship inference, cardinality verifier, temporal alignment check or multi-version evidence provenance was found. The first milestone should be single-dataset only. Multi-dataset support should follow only after deterministic relationship checks have an independent adversarial evaluation.

## 7. Minimum safe architecture

1. **Pin input.** Start from Madar's authorized `(tenant_id, project_id, dataset_id, dataset_version_id, content_hash)`, never a mutable path.
2. **Private Python profile.** Reuse Madar parsing/profiling, but keep the full profile inside trusted code. Derive a versioned `SemanticProfileRelease` containing only explicitly approved name/type/statistical/value hints. Default-deny samples, category labels and rare values.
3. **Separate Qwen semantic task.** Add a new typed request/response and broker operation; do not overload `InvestigationRequest` or alter its prompt. Output proposals, alternatives, evidence references, confidence class and abstention reason—never executable code or authoritative mappings.
4. **Trusted validation.** Validate existence/type compatibility, uniqueness, null rates, currency/unit consistency, sign/range rules, formula dimensionality, transaction-class coverage, key stability and relationship cardinality against private data. The model cannot approve itself.
5. **Policy approval.** Auto-approve only low-consequence mappings satisfying explicit deterministic rules. Require focused confirmation for revenue/cost/quantity/currency, transaction class, grain, keys, joins, destructive filters and any ambiguity. Persist approver/policy/model/source hashes.
6. **Deterministic metric registry.** Compile approved mappings into versioned metric definitions and then into Qwen's existing `AliasPolicy`, `DatasetView` and registered measures. Calculate KPIs only in trusted Python.
7. **Existing reasoning task.** Feed only privacy-reviewed qualitative evidence through the unchanged Qwen investigation gateway. Semantic proposal and evidence reasoning remain separate jobs, prompts, schemas, budgets and acceptance suites.
8. **Provenance everywhere.** Dashboards/reports store dataset version(s), semantic mapping version, metric-definition version, analysis spec, evidence-release IDs, Qwen model/code/protocol hashes and verification status. Cache on those immutable identities; invalidate by key change rather than mutation.

This architecture reuses Madar's version/source/ingestion foundations and Qwen's mature post-semantics reasoning boundary. It adds only the missing bridge and avoids replacing either working subsystem.

## 8. Independent evaluation required before integration

Freeze the semantic task before inference: generator/realistic sanitized fixtures, expected mappings and acceptable alternatives, scorer, disclosure policy, model/checkpoint, prompt/schema, validator and runner hashes. Keep semantic scores separate from final-core reasoning scores.

Minimum cohorts should include:

- English, Arabic and mixed-language names; abbreviations, misspellings and opaque ERP codes.
- Currency, percentage, count, mass/volume and scaled units; mixed currencies/units and missing conversion metadata.
- Sales, purchases, returns, refunds, inventory snapshots, ledgers and event tables; negative/sign conventions.
- Line-item versus transaction/customer/product/day/month grain; composite and unstable keys.
- Near-synonyms and adversarial columns (`price` versus `cost`, booked versus paid revenue, order date versus ship date).
- Sparse/high-cardinality/PII fields, rare categories and values that must never be released.
- Relationship cases with one-to-one, one-to-many, many-to-many, partial match, fan-out and time misalignment.
- Ambiguous/unanswerable cases where focused confirmation or abstention is mandatory.

Hard gates should include: **zero privacy leaks; zero silent consequential mis-mappings; zero unit/currency dimensional errors; zero invalid joins/fan-out; 100% provenance binding; explicit abstention/confirmation on ambiguous consequential fields; deterministic replay; service-failure and timeout behavior; and no regression in the existing Qwen final-core suite.** Accuracy must be reported with attempted, service-failed and scored denominators. At least three repetitions are needed for model-sampled mapping cases, and every prior false approval must remain a named regression without tuning the scorer after results.

## 9. Risks and explicit reasons not to integrate now

1. **Acceptance failure:** the current exact candidate has a wrong `COMPLETE`; deploying it would knowingly violate the existing gate.
2. **Missing semantic workflow:** Qwen cannot presently turn unfamiliar raw schemas into approved business semantics. Passing raw names to its reasoning prompt would bypass the architecture that was actually evaluated.
3. **Privacy mismatch:** Madar's current full AI profile can include samples, categorical labels and exact statistics; Qwen's secured reasoning task was tested with none of those.
4. **Runtime unavailable:** no active Qwen worker/broker exists at audit time, and static deployment artifacts still point at an older 9B model. Operational ownership, reconciled units and health/readiness must precede integration testing.
5. **No version-bound invocation:** the current Madar `/ai` path uses `input_path`; an answer could lack immutable dataset-version, semantic and metric provenance.
6. **No multi-dataset correctness boundary:** relationship and join correctness are absent, while composition errors already caused the current candidate's wrong `COMPLETE`.
7. **Deep-path uncertainty:** R4 explicitly left an inconsistent deep-mode mechanism table unexercised. Integration must pin the evaluated fast path unless deep receives separate acceptance.
8. **First-answer weakness and service reliability:** candidate first-answer diagnosis was 31/50 and five of 100 runs failed at the service layer. The trusted loop helps, but latency/failure behavior is not ready for an unqualified synchronous UX.

Changes most likely to threaten existing guarantees are: exposing raw schema/samples through `InvestigationRequest`; combining semantic guessing with evidence interpretation in one prompt; allowing model-defined formulas/code; loosening `PrivateRaw`, signed-release or completion checks; changing qualitative buckets/materiality; enabling deep/fallback paths without frozen tests; sharing caches across versions/tenants; or replacing the fixed model/runtime without rerunning acceptance.

## 10. Recommended next milestone

**Build and evaluate, but do not yet user-enable, a single-dataset semantic-proposal vertical slice.**

It should use one exact Madar dataset version, persist a sanitized `SemanticProfileRelease`, call one new typed local-Qwen semantic endpoint asynchronously, persist proposals and abstentions, run deterministic validators, and produce a review artifact. Limit the first scope to dates, identifiers, dimensions, quantity, unit price, unit cost, revenue, COGS, currency and transaction class. Exclude joins, auto-executed actions and model-generated formulas. A mapping becomes usable only after policy/human approval and compilation into the existing Qwen declaration types.

Exit criteria are: frozen semantic evaluation passes the hard gates above; no customer/private value crosses the approved release; version/protocol/model provenance is complete; timeouts and service failures remain honest; the current Qwen reasoning suite is rerun unchanged and reaches its own acceptance threshold, including **zero wrong `COMPLETE`**. Until then, retain Qwen as an isolated evaluation candidate rather than a Madar production dependency.
