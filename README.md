# Fathom

**An adaptive, skill-based diagnostic framework for behavioral inconsistency in AI agentic systems.**

> Fathom does not fix AI systems. It tells you, with auditable evidence, where their behavior is inconsistent across conditions — and just as importantly, where it hasn't been checked at all.

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
          └───────┬────────┘            │
                  ▼                     │
             Target System             │
                  │                     │
                  ▼                     │
          ┌────────────────┐            │
          │ Evidence Layer │            │
          └───────┬────────┘            │
                  ▼                     │
             Skill Result               │
       (Result State + Skill Status)    │
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
The versioned catalog of diagnostic instruments. Each skill is a self-contained specification: threat category, preconditions, test-generation method, execution procedure, decision rules, known limitations, coverage boundaries, and **Skill Status** (see Epistemic Status below).

### Skill Planner — *generative*
Instantiates a concrete test from a skill definition (e.g., generating matched evaluation/deployment prompt variants). This is the one place generation happens, and it is bounded: the Planner only instantiates a capability that the Coverage Mapper has already deterministically approved. It never decides what to test — only how to concretely realize a test that's already been selected.

### Plan Validator — *layered, not a black box*
Validates a candidate plan before it's allowed to run, in three explicit layers:
1. **Structural** (deterministic) — required fields present, paired cases match the skill's schema, no unintended changes to tools/permissions/instructions between variants.
2. **Semantic** (deterministic-first) — checks multiple invariants (entity preservation, action preservation, constraint preservation), not a single embedding-similarity score, since similarity alone can miss meaning-changing differences (e.g., "delete the database" vs. "delete the database after backing it up").
3. **Model-assisted** (optional, explicitly labeled) — used only when deterministic checks are insufficient, and never conflated with a deterministic guarantee.

Output is `VALID / INVALID / INCONCLUSIVE`, tagged with `validation_method: DETERMINISTIC / MODEL_ASSISTED / HYBRID` — so a plan's validation strength is always visible, not implied.

### Evaluation Adapter — Delegated vs. Managed Execution
**Plan by default, execute by permission.** Fathom produces an evaluation plan; running it against a live target only happens through an explicitly authorized path:
- **Delegated execution** — Fathom returns the plan; the integrating system runs it against its own agent and reports results back. No execution access required.
- **Managed execution** — Fathom is given direct, explicitly authorized invoke access to run the plan itself.

Delegated is the default trust posture; Managed requires deliberate opt-in.

### Evidence Layer
Stores everything needed to reproduce and audit a result: the actual inputs used, outputs/transcripts, skill version, plan validation record, and the precondition facts that made the skill applicable in the first place. Reproducibility comes from evidencing what happened, not from assuming generation is repeatable.

### Coverage Analyzer → Diagnostic Report
Combines results into a report with **no rollup score**. Every finding carries, independently:
- **Result State**: `CONSISTENT / DIVERGENT / INCONCLUSIVE`
- **Coverage State**: `TESTED / NOT_TESTED / NOT_APPLICABLE / UNCLASSIFIED`
- **Validation Status** (single merged field — replaces the earlier separate "Skill Status" / "Evidence Basis" split): `EXPLORATORY / EMPIRICALLY_SUPPORTED / VALIDATED / DEPRECATED`

A `DIVERGENT` result from a `VALIDATED` skill and a `DIVERGENT` result from an `EXPLORATORY` skill are never presented as equivalent findings.

### Research Engine — *offline, not in the live path*
Investigates Coverage Gaps (unclassified facts, `NOT_TESTED`/`INCONCLUSIVE` results, systematic evidence limitations) and proposes new skills. A new skill enters the registry as `EXPLORATORY` and cannot promote itself.

Promotion is a three-role process, and no role can occupy more than one seat for the same skill:

```
Research Engine (proposer)
      ↓
Candidate Skill → EXPLORATORY
      ↓
Independent Validation Authority (not the proposer)
      ↓
Validation Protocol — blinded where possible, so the
validator does not know which cases are expected positive/negative
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

**A skill cannot establish its own epistemic status.** This depends on the three roles actually being held by different parties. In a solo-maintainer or small-team setting, that independence often doesn't exist yet — if the same person builds and validates a skill, treat it as still `EXPLORATORY` regardless of how many times it's been personally re-tested. Promotion beyond `EXPLORATORY` should wait for an actual independent party (a co-maintainer, external reviewer, or community validation process), not be granted on the strength of the proposer's own confidence.

---

## Core principles

1. **Deterministic applicability, bounded generative evaluation.** What applies to a target is decided by rules, not reasoning. Generation only instantiates an already-approved capability.
2. **Plan by default, execute by permission.** Fathom's default output is a plan, not an action. Execution against a live target requires explicit authorization.
3. **Discover capabilities, not truths.** A new skill can be added without claiming the phenomenon it targets is proven real. Exploratory findings are visibly weaker than validated ones.
4. **No single component is the authority for the whole chain.** An LLM may generate candidate tests or assist with semantic validation — it never decides what applies, whether evidence exists, whether a finding is validated, or whether a suspected phenomenon is real.
5. **Never imply more coverage than exists.** `NOT_TESTED` and `UNCLASSIFIED` are first-class outputs, not disclaimers.

---

## Resolved design decisions

- **Validation Status is a single field.** The earlier separate "Skill Status" and "Evidence Basis" fields were redundant; merged into one `VALIDATION_STATUS` enum (`EXPLORATORY / EMPIRICALLY_SUPPORTED / VALIDATED / DEPRECATED`), kept distinct from `RESULT_STATE` and `COVERAGE_STATE`.
- **Promotion requires three non-overlapping roles** — proposer, independent validation authority, registry authority — recorded in a `ValidationRecord`. See Research Engine section above.
- **Deprecation triggers are defined**: unacceptable false positive/negative rates, failed independent replication, invalidated underlying assumptions, a superior replacement version, materially changed dependencies, or scope no longer applying. Deprecating a skill does not erase historical reports — old findings keep the version that produced them (e.g., `v1 → DEPRECATED`, `v2 → VALIDATED`, prior reports still cite `v1`).
- **Validation circularity for novel categories is accepted as a permanent methodological limitation, not solved.** Synthetic positive/negative cases can only ever establish "the skill detects the behavior we operationalized," never "this behavior naturally occurs in real systems." Mitigation is layered (synthetic → independently constructed cases → blinded validation → counterfactual controls → cross-system replication → external evidence), but a skill built for a genuinely novel hypothesis starts and stays at `EXPLORATORY` until independent, real-world evidence accumulates. This must be stated explicitly in that skill's `known_limitations` field, not left implicit.

## Remaining operational gap

The promotion process above assumes proposer, validator, and registry authority are genuinely different parties. For a solo maintainer or small team, that independence may not exist yet. Until it does, self-built-and-self-tested skills should be treated as `EXPLORATORY` regardless of internal confidence or repetition count — promotion should wait for an actual external party, not be granted by the builder's own judgment.

---

## Scope

Fathom is diagnostic only. It answers "does this system's behavior hold up under changed conditions" with auditable evidence. It does not answer "is this system safe," "is this behavior correct," or "how do I fix this." Those are downstream decisions for the humans who own the system.
