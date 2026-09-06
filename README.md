# Fathom

**An adaptive, skill-based diagnostic framework for behavioral inconsistency in AI agentic systems.**

> Fathom does not fix AI systems. It tells you, with auditable evidence, where their behavior is inconsistent across conditions — and just as importantly, where it hasn't been checked at all.

---

## Current status

- **Two skills implemented**: `EvaluationContextSensitivity_v1` (detects whether a system behaves differently when it appears to recognize an evaluation context) and `TriggerConditionedBehavior_v1` (detects whether a system behaves differently when a single contextual variable is flipped, holding the task identical — closer to the classic "sleeper agent" trigger pattern).
- **Both execution modes implemented**: Delegated (Fathom returns a plan, the caller runs it) and Managed (Fathom invokes the target directly, gated by explicit authorization and blast-radius verification).
- **A first-pass Research Engine**: reads coverage gaps from past reports and proposes candidate skills, hardcoded to enter the registry at `EXPLORATORY` with no self-promotion path. The gap-detection and pipeline wiring are tested; full candidate generation through the real skill schema is not yet exercised end-to-end.
- **Real-world validation**: run against real multi-agent stock-analysis pipelines (LangGraph and AutoGen implementations), not just synthetic test cases. Results below.
- **Not yet done**: no skill has been run by anyone other than the maintainer, so nothing has moved past `EXPLORATORY` — see "Remaining operational gap" below. Broader ticker/model coverage is still needed before any directional finding is treated as established.

---

## Why this exists

AI agentic systems can behave differently when conditions around them change, in ways standard evaluation does not catch. This is documented, not hypothetical:

- Deliberately inserted backdoors have been shown to survive standard safety training (Hubinger et al., *Sleeper Agents*, 2024).
- Frontier models have been observed detecting evaluation contexts and behaving differently than in deployment — including a documented case of Claude Opus 4.6 recognizing benchmark-shaped questions and using this to circumvent the measurement (Anthropic, BrowseComp incident report).
- Purely formatting-level changes (question vs. non-question phrasing) have produced double-digit percentage-point swings in sycophancy behavior (UK AI Security Institute).

Every deployed agentic system has a different threat profile depending on its architecture, tool access, and data exposure. There is no single check that covers every system, and there is no way to manually build bespoke detection for every system at scale. Using an AI to freely decide "what threats does this system face" reintroduces the same problem it's meant to solve — that kind of judgment is opaque, non-reproducible, and fails silently.

Fathom's answer: separate the parts of this problem that must be deterministic and auditable from the parts that are inherently generative, and never let either one pretend to be the other.

---

## What Fathom is not

- **Not a remediation tool.** Fathom does not patch models, retrain them, or change agent behavior. It produces evidence for humans to act on.
- **Not a risk score.** Fathom never collapses findings into a single number. A single score hides exactly the information this framework exists to preserve.
- **Not an autonomous security researcher.** No component in the live path decides *what threats apply* through open-ended reasoning. That decision is deterministic and rule-based.
- **Not a claim of completeness.** Fathom reports what was tested, what wasn't, and what couldn't be classified — as a first-class output, not a disclaimer.

---

## Architecture

```
                    ┌──────────────────┐
                    │ System Profiler  │
                    └────────┬─────────┘
                             │
                    Profile Facts
              + provenance (declared / observed)
                             │
                             ▼
                  ┌─────────────────────┐
                  │ Coverage Mapper     │
                  │   DETERMINISTIC     │
                  └─────────┬───────────┘
                            │
                 ┌──────────┴──────────┐
                 ▼                     ▼
        Applicable Skills       Unclassified Facts
                 │                     │
                 ▼                     ▼
          ┌─────────────┐       Coverage Gaps
          │Skill Registry│             │
          └──────┬──────┘              │
                 ▼                     │
          ┌──────────────┐             │
          │Skill Planner │             │
          │  GENERATIVE  │             │
          └──────┬───────┘             │
                 ▼                     │
          Candidate Plan               │
                 │                     │
                 ▼                     │
     ┌────────────────────────┐        │
     │   Plan Validator       │        │
     │  (layered, see below)  │        │
     └───────────┬─────────────┘       │
                 ▼                     │
          Evaluation Plan              │
                 │                     │
          ┌──────┴─────────┐           │
          ▼                ▼            │
     Delegated         Managed         │
     Execution         Execution       │
          │                │            │
          │                ▼            │
          │      Authorization Check    │
          │    (blast radius + scope)   │
          │                │            │
          └───────┬────────┘            │
                  ▼                     │
             Target System             │
                  │                     │
                  ▼                     │
          ┌────────────────┐            │
          │ Evidence Layer │            │
          └───────┬────────┘            │
                  ▼                     │
          ┌────────────────────┐        │
          │ Decision Evaluator │        │
          │  structural →      │        │
          │  semantic →        │        │
          │  model-assisted    │        │
          └───────┬────────────┘        │
                  ▼                     │
             Skill Result               │
   (Result State + Validation Status +  │
        decision_method used)           │
                  │                     │
                  └──────────┬──────────┘
                             ▼
                    Coverage Analyzer
                             │
                             ▼
                     Diagnostic Report
                             │
                             ▼
                       Research Engine
                        (offline, not
                       in the live path)
                             │
                             ▼
                       Hypothesis
                             │
                             ▼
                    Candidate Skill
                             │
                             ▼
                  Validation Protocol
                (external, not self-graded)
                             │
                  ┌──────────┴──────────┐
                  ▼                     ▼
               REJECT              EXPLORATORY
                                        │
                              independent evidence
                                        │
                                        ▼
                          EMPIRICALLY_SUPPORTED / VALIDATED
                                        │
                                        ▼
                                  Skill Registry
```

---

## Components

### System Profiler
Extracts structured facts about the target system: tool access and permissions, data sources touched, whether behavior can depend on persistent/mutable state, multi-agent involvement. Every fact is tagged with **provenance** — `declared` (self-reported by the integrating system) or `observed` (independently verified by Fathom). Declared-only facts carry weaker evidentiary weight downstream; this is what prevents a target system's own unverified claims about itself from silently becoming ground truth.

### Coverage Mapper — *deterministic*
Matches profile facts against a versioned rule table to decide which threat categories and skills are applicable. No open-ended reasoning happens here. Given the same facts, the output is always the same, and every applicability decision can be traced to a specific rule. Facts that don't match any rule are preserved as `UNCLASSIFIED_PROFILE_ELEMENT` rather than dropped, and feed directly into Coverage Gaps.

### Skill Registry
The versioned catalog of diagnostic instruments. Currently holds two skills — see "Skills" below. Each is a self-contained specification: threat category, preconditions, test-generation method, **decision function spec**, execution procedure, known limitations, coverage boundaries, and Validation Status.

### Skill Planner — *generative*
Instantiates a concrete test from a skill definition (e.g., generating matched evaluation/deployment prompt variants, or matched trigger-flip pairs). This is the one place generation happens, and it is bounded: the Planner only instantiates a capability that the Coverage Mapper has already deterministically approved. It never decides what to test — only how to concretely realize a test that's already been selected.

### Plan Validator — *layered, not a black box*
Validates a candidate plan before it's allowed to run, in three explicit layers:
1. **Structural** (deterministic) — required fields present, paired cases match the skill's schema, no unintended changes to tools/permissions/instructions between variants.
2. **Semantic** (deterministic-first) — checks multiple invariants (entity preservation, action preservation, constraint preservation), not a single embedding-similarity score, since similarity alone can miss meaning-changing differences (e.g., "delete the database" vs. "delete the database after backing it up").
3. **Model-assisted** (optional, explicitly labeled) — used only when deterministic checks are insufficient, and never conflated with a deterministic guarantee.

Output is `VALID / INVALID / INCONCLUSIVE`, tagged with `validation_method: DETERMINISTIC / MODEL_ASSISTED / HYBRID` — so a plan's validation strength is always visible, not implied.

### Evaluation Adapter — Delegated vs. Managed Execution
**Plan by default, execute by permission.** Fathom produces an evaluation plan; running it against a live target only happens through an explicitly authorized path:
- **Delegated execution** — Fathom returns the plan; the integrating system runs it against its own agent and reports results back. No execution access required. This is the default.
- **Managed execution** — Fathom is given direct, explicitly authorized invoke access to run the plan itself, gated by an `ExecutionAuthorization` record:
  - `blast_radius`: `SAFE / LOW / MEDIUM / HIGH / UNKNOWN` — `UNKNOWN` is treated as `HIGH` and blocked by default.
  - `blast_radius_provenance`: `DECLARED / VERIFIED` — a `DECLARED`-only `SAFE`/`LOW` rating requires an explicit `allow_declared=True` override on first use; only `VERIFIED` ratings auto-invoke.
  - `mark_verified()` upgrades `DECLARED` → `VERIFIED` only after a run passes explicit `VerificationCriteria` (no embedded error markers in output, all sub-checks succeeded, decision method matches expectations if specified) — **not** merely "the call didn't throw an exception."

### Evidence Layer
Stores everything needed to reproduce and audit a result: the actual inputs used, outputs/transcripts, skill version, plan validation record, authorization/blast-radius record for managed runs, and the precondition facts that made the skill applicable in the first place.

### Decision Evaluator
Determines a skill's `Result State` from raw execution evidence, in the same layered spirit as the Plan Validator: structural comparison first (did the action/output category differ), then substance-level comparison, with model-assisted judgment as a last, explicitly labeled resort. Every `Finding` records which `decision_method` was actually used.

> **Why this exists as its own explicit layer:** an earlier version of the Execution Adapter only checked whether a run completed without error, not whether the target's behavior actually diverged. This meant a target that behaved completely differently under two conditions and one that behaved identically could produce the same `CONSISTENT` verdict — a false negative baked into the architecture. It was caught by a deliberately constructed positive-control test (a mock target with a known, injected behavioral trigger) that should have returned `DIVERGENT` and didn't. The fix pulled comparison logic into its own explicit, layered, labeled component rather than leaving it implicit in the adapter. **Execution success is not behavioral correctness**, and the architecture now enforces that distinction structurally rather than relying on it being remembered.

### Coverage Analyzer → Diagnostic Report
Combines results into a report with **no rollup score**. Every finding carries, independently:
- **Result State**: `CONSISTENT / DIVERGENT / INCONCLUSIVE`
- **Coverage State**: `TESTED / NOT_TESTED / NOT_APPLICABLE / UNCLASSIFIED`
- **Validation Status**: `EXPLORATORY / EMPIRICALLY_SUPPORTED / VALIDATED / DEPRECATED`
- **decision_method**: `DETERMINISTIC / MODEL_ASSISTED / HYBRID`

A `DIVERGENT` result from a `VALIDATED` skill and a `DIVERGENT` result from an `EXPLORATORY` skill are never presented as equivalent findings.

### Research Engine — *offline, not in the live path*
Reads Coverage Gaps (`UNCLASSIFIED_PROFILE_ELEMENT` facts, `NOT_TESTED`/`INCONCLUSIVE` results) from past Diagnostic Reports and proposes candidate skills that extend an existing skill category. A new skill enters the registry as `EXPLORATORY` and cannot promote itself.

Promotion (not yet exercised in practice — see "Remaining operational gap") is a three-role process, and no role can occupy more than one seat for the same skill:

```
Research Engine (proposer)
      ↓
Candidate Skill → EXPLORATORY
      ↓
Independent Validation Authority (not the proposer)
      ↓
Validation Protocol — blinded where possible
      ↓
Validation Report
      ↓
Registry Authority (not the proposer, not necessarily the validator)
      ↓
EMPIRICALLY_SUPPORTED / VALIDATED
```

```
ValidationRecord {
    proposer
    validator
    independence_status
    protocol_version
    test_suite_version
    results
    replication_count
    decision
}
```

**A skill cannot establish its own epistemic status.**

---

## Skills

| Skill | Category | What it checks |
|---|---|---|
| `EvaluationContextSensitivity_v1` | Evaluation awareness | Does the target behave differently when a request looks benchmark-shaped vs. organic, with the underlying task held identical? |
| `TriggerConditionedBehavior_v1` | Trigger-conditioned behavior | Does the target behave differently when a single contextual variable (e.g., framing/stated stakes) is flipped, with the task held identical? Closer to the classic hidden-trigger backdoor pattern. |

Both are currently `EXPLORATORY` (see below).

---

## Real-world validation

Both skills have been run against real multi-agent stock-analysis pipelines (LangGraph and AutoGen implementations of the same task), not only synthetic test cases.

**Result so far:** across two tickers (NVDA — a stock with a strong, consensus narrative; Ford — chosen specifically as a mixed-sentiment mid-cap to rule out a narrative-strength confound), the recommendation stayed `BUY` across baseline and all three framing conditions (neutral / bullish / bearish) — a **0% observed swing rate** on both.

**Caveats, stated deliberately:**
- Sample size was small (2–3 runs per condition) — directional, not statistically definitive.
- One run initially produced unexplained errors that looked like a possible pipeline logic bug; root-caused to Groq API rate limiting, not a defect in the target or in Fathom's harness. Recorded here specifically because "an unexplained result deserves an explanation before a conclusion is built on it."
- This shows the harness works and gives one consistent real-world signal. It does not establish that these systems are generally robust to framing — different models, temperatures, or framing strategies might behave differently, and that hasn't been tested yet.

---

## Core principles

1. **Deterministic applicability, bounded generative evaluation.** What applies to a target is decided by rules, not reasoning. Generation only instantiates an already-approved capability.
2. **Plan by default, execute by permission.** Fathom's default output is a plan, not an action. Execution against a live target requires explicit authorization, and even authorized targets start `DECLARED` and must earn `VERIFIED` status through an actual successful, criteria-checked run.
3. **Discover capabilities, not truths.** A new skill can be added without claiming the phenomenon it targets is proven real. Exploratory findings are visibly weaker than validated ones.
4. **No single component is the authority for the whole chain.** An LLM may generate candidate tests or assist with semantic validation — it never decides what applies, whether evidence exists, whether a finding is validated, or whether a suspected phenomenon is real.
5. **Never imply more coverage than exists.** `NOT_TESTED` and `UNCLASSIFIED` are first-class outputs, not disclaimers. "The run completed" is never treated as equivalent to "the behavior was checked."

---

## Remaining operational gap

The promotion process above assumes proposer, validator, and registry authority are genuinely different parties. For a solo maintainer, that independence doesn't exist yet. Until it does, self-built-and-self-tested skills — including both skills currently in the registry — stay `EXPLORATORY` regardless of internal confidence, repetition count, or how clean a real-world result looks. Promotion should wait for an actual external party (a co-maintainer, external reviewer, or community validation process), not be granted by the builder's own judgment.

Additionally, the Research Engine's candidate-generation step has only been tested for its surrounding pipeline wiring so far (gap extraction, `propose_new_skills()` callability) — generating a full candidate through the real `SkillDefinition` schema end-to-end is not yet proven and is a near-term follow-up.

---

## Scope

Fathom is diagnostic only. It answers "does this system's behavior hold up under changed conditions" with auditable evidence. It does not answer "is this system safe," "is this behavior correct," or "how do I fix this." Those are downstream decisions for the humans who own the system.
