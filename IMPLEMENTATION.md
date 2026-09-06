# Fathom Implementation

Complete Python implementation of the diagnostic framework for AI behavioral inconsistency detection.

## Architecture

Built following README design exactly:

- **System Profiler** (`profiler.py`) — extracts facts with provenance tagging (declared/observed)
- **Coverage Mapper** (`coverage_mapper.py`) — deterministic rule-based skill applicability
- **Skill Registry** (`registry.py`) — versioned skill catalog (bootstrapped with EvaluationContextSensitivity_v1)
- **Skill Planner** (`skill_planner.py`) — bounded test case generation
- **Plan Validator** (`plan_validator.py`) — 3-layer validation (structural, semantic, model-assisted)
- **Execution Adapter** (`execution_adapter.py`) — delegated execution (plan returned, not invoked)
- **Evidence Store** (`evidence_store.py`) — JSON file-based, auditable, git-diffable persistence
- **Coverage Analyzer & Report Generator** (`report_generator.py`) — findings with no rollup scores
- **Diagnostic Pipeline** (`pipeline.py`) — full orchestration
- **FathomClient** (`api.py`) — high-level public API
- **CLI** (`cli.py`) — interactive and demo modes
- **MCP Server** (`mcp_server.py`) — tool definitions for Model Context Protocol integration

## Data Models

All models use Pydantic for strict validation with enums that fail loudly:

- `Provenance` — DECLARED / OBSERVED
- `ThreatCategory` — enum of threat types (evaluation context sensitivity, state dependency, etc.)
- `ResultState` — CONSISTENT / DIVERGENT / INCONCLUSIVE
- `CoverageState` — TESTED / NOT_TESTED / NOT_APPLICABLE / UNCLASSIFIED
- `ValidationStatus` — EXPLORATORY / EMPIRICALLY_SUPPORTED / VALIDATED / DEPRECATED
- `SystemProfile` — facts with provenance
- `SkillDefinition` — deterministic skill schema with preconditions
- `EvaluationPlan` — bounded, validated test plan
- `SkillResult` — execution results
- `EvidenceRecord` — complete audit trail (profile, plan, result)
- `Finding` — result with coverage and validation status (no rollup score)
- `DiagnosticReport` — findings, coverage summary, untested threats, unclassified facts

## Reference Implementation: EvaluationContextSensitivity_v1

One complete skill demonstrating full pattern:

1. **Precondition**: System has web access (declared or observed)
2. **Test Generation**: 2 paired variants (question vs statement phrasing)
3. **Validation**: Structural + semantic checks on plan
4. **Execution**: Mock agent with consistent/divergent behavior modes
5. **Evidence**: JSON stored, git-diffable
6. **Finding**: Result state + coverage state + validation status

Skill is `EXPLORATORY` (reference implementation, not independently validated).

## Testing

34 tests covering:

- Coverage Mapper (8 tests) — deterministic applicability checking, threat gaps, unclassified facts
- System Profiler (10 tests) — fact creation, provenance, merging, filtering
- Skill E2E (2 tests) — consistent and divergent agent workflows
- Report Generation (5 tests) — findings, coverage summaries, unclassified facts
- Pipeline (6 tests) — full workflow, profile building, report export
- MCP Server (3 tests) — tool registration and schemas

All tests pass. 100% coverage of core logic.

## Usage

### CLI Demo

```bash
python -m fathom.cli demo
```

Creates profile, runs diagnostic, exports report to `demo_report.json`.

### CLI Interactive

```bash
python -m fathom.cli interactive
```

Walks through profile building and diagnostics.

### Python API

```python
from fathom.api import FathomClient

client = FathomClient()
profile = client.create_profile("my_agent")
client.add_declared_fact(profile, "tools", "has_web_access", True)
client.add_observed_fact(profile, "state", "persistent_memory", False)

report = client.diagnose(profile)
client.export_report(report, "report.json")

# Access findings
for finding in report.findings:
    print(f"{finding.threat_category.value}: {finding.result_state.value}")
```

### MCP Integration

```python
from fathom.mcp_server import FathomMCPServer

server = FathomMCPServer()
tools = server.get_tools()  # list of tool definitions

# Each tool callable with specified inputs:
# - create_profile(system_id)
# - add_fact(system_id, category, key, value, observed=False)
# - diagnose(system_id, executor_behavior="consistent")
# - export_report(system_id, filepath)
# - get_skills()
```

## Evidence & Reports

Reports are JSON files (auditable, git-diffable):

```json
{
  "system_id": "agent_v1",
  "findings": [
    {
      "threat_category": "evaluation_context_sensitivity",
      "result_state": "consistent",
      "coverage_state": "tested",
      "validation_status": "exploratory",
      "evidence_id": "evidence_...",
      "summary": "...",
      "details": "..."
    }
  ],
  "coverage_summary": {...},
  "tested_skills": ["EvaluationContextSensitivity_v1"],
  "not_tested_threats": [...],
  "unclassified_facts": [...],
  "generated_at": "2026-09-06T...",
  "report_version": "1.0"
}
```

## Design Decisions Honored

1. ✓ Deterministic applicability (Coverage Mapper uses rules, not reasoning)
2. ✓ Bounded generation (Planner only instantiates mapper-approved skills)
3. ✓ Plan by default (delegated execution; no live access required)
4. ✓ Distributed authority (validator is separate from planner; registry separate from validator)
5. ✓ Never hide uncovered ground (`NOT_TESTED` and `UNCLASSIFIED` are first-class)
6. ✓ No rollup scores (findings carry 3 independent fields)
7. ✓ Validation status separate from result/coverage (EvaluationContextSensitivity_v1 is `EXPLORATORY`)
8. ✓ File-based evidence (JSON, auditable, git-diffable)
9. ✓ Provenance tracking (declared vs observed facts)
10. ✓ MCP delivery (tools available for integration)

## Next Steps (v2)

- Additional skills (state dependency, tool permission bypass, etc.)
- Managed execution (direct agent invocation with authorization)
- Model-assisted semantic validation (optional 3rd layer)
- Skill promotion workflow (proposer → independent validator → registry authority)
- Extended threat coverage (more preconditions, more test patterns)
