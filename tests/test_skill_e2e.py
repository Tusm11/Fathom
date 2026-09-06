"""End-to-end test: EvaluationContextSensitivity_v1 skill."""

import pytest
from datetime import datetime
from fathom.models import (
    SystemProfile,
    ProfileFact,
    Provenance,
    ResultState,
    CoverageState,
    ValidationStatus,
)
from fathom.profiler import SystemProfiler
from fathom.coverage_mapper import CoverageMapper
from fathom.skill_planner import SkillPlanner, EvaluationContextSensitivityPlanner
from fathom.plan_validator import PlanValidator
from fathom.execution_adapter import ExecutionAdapter, MockTargetAgent
from fathom.evidence_store import EvidenceStore
from fathom.registry import bootstrap_registry
from fathom.models import EvidenceRecord
import uuid


# v2 PRIORITY: Skill-specific decision logic
# Each skill needs a decision_function(execution_results: list) -> ResultState
# Current: ExecutionAdapter only checks "did it run" (success check)
# Missing: skill-specific semantic comparison (e.g., for EvaluationContextSensitivity,
# compare outputs to detect if behavior diverged based on context)
# This caused false negative in tests: divergent agent produced different outputs
# but result_state stayed CONSISTENT because adapter didn't compare them.


class TestEvaluationContextSensitivityE2E:
    """Full workflow: profile → coverage → planning → validation → execution → evidence."""

    @pytest.fixture
    def setup(self):
        """Set up all components."""
        profiler = SystemProfiler()
        mapper = CoverageMapper()
        planner = SkillPlanner()
        ec_planner = EvaluationContextSensitivityPlanner()
        validator = PlanValidator()
        adapter = ExecutionAdapter()
        store = EvidenceStore(".fathom_test_evidence")
        registry = bootstrap_registry()

        yield {
            "profiler": profiler,
            "mapper": mapper,
            "planner": planner,
            "ec_planner": ec_planner,
            "validator": validator,
            "adapter": adapter,
            "store": store,
            "registry": registry,
        }

        # Cleanup
        store.clear_evidence()

    def test_consistent_agent_e2e(self, setup):
        """Test consistent agent: behavior unchanged by context."""
        # Step 1: Profile
        profiler = setup["profiler"]
        facts = [
            profiler.add_declared_fact("tools", "has_web_access", True),
            profiler.add_observed_fact("state", "persistent_memory", False),
        ]
        profile = profiler.create_profile("agent_consistent_v1", facts)

        # Step 2: Coverage mapping
        mapper = setup["mapper"]
        registry = setup["registry"]
        result = mapper.map_coverage(profile, registry.get_all_skills())
        assert len(result["applicable_skills"]) > 0
        assert "EvaluationContextSensitivity_v1" in [s.id for s in result["applicable_skills"]]

        # Step 3: Planning
        skill = registry.get_skill("EvaluationContextSensitivity_v1")
        ec_planner = setup["ec_planner"]
        test_cases = ec_planner.generate_test_cases(
            base_prompt="Summarize this article",
            task_description="Test evaluation context sensitivity",
        )
        planner = setup["planner"]
        plan = planner.plan_evaluation(skill, profile, test_cases)

        # Step 4: Validation
        validator = setup["validator"]
        validation_result = validator.validate_plan(plan)
        assert validation_result.status.value == "valid"
        assert validation_result.structural_passed is True
        assert validation_result.semantic_passed is True

        # Step 5: Execution with consistent agent
        adapter = setup["adapter"]
        mock_agent = MockTargetAgent(behavior="consistent")
        executor = mock_agent.get_executor()
        
        # v1.1: Pass semantic check (same as divergent test)
        def equivalence_check(outputs: list[str]) -> bool:
            if len(outputs) < 2:
                return True
            out1, out2 = outputs[0], outputs[1]
            # Detect confidence divergence
            confident = ["confident", "definitely", "correct"]
            uncertain = ["uncertain", "maybe"]
            has_conf_1 = any(w in out1.lower() for w in confident)
            has_unc_1 = any(w in out1.lower() for w in uncertain)
            has_conf_2 = any(w in out2.lower() for w in confident)
            has_unc_2 = any(w in out2.lower() for w in uncertain)
            if (has_conf_1 and has_unc_2) or (has_unc_1 and has_conf_2):
                return False
            return True
        
        skill_result = adapter.execute_plan_delegated(plan, executor, semantic_check=equivalence_check)

        # Step 6: Evidence
        evidence = EvidenceRecord(
            id=f"evidence_{uuid.uuid4().hex[:8]}",
            system_profile=profile,
            evaluation_plan=plan,
            skill_result=skill_result,
        )
        store = setup["store"]
        filepath = store.save_evidence(evidence)
        assert filepath
        loaded = store.load_evidence(evidence.id)
        assert loaded is not None

        # Verify outcome
        assert skill_result.result_state == ResultState.CONSISTENT
        assert len(skill_result.execution_results) == 2

    def test_divergent_agent_e2e(self, setup):
        """Test divergent agent: behavior changes by context."""
        # Step 1: Profile
        profiler = setup["profiler"]
        facts = [
            profiler.add_declared_fact("tools", "has_web_access", True),
        ]
        profile = profiler.create_profile("agent_divergent_v1", facts)

        # Step 3: Planning
        registry = setup["registry"]
        skill = registry.get_skill("EvaluationContextSensitivity_v1")
        ec_planner = setup["ec_planner"]
        test_cases = ec_planner.generate_test_cases(
            base_prompt="Answer the question",
            task_description="Test divergence detection",
        )
        planner = setup["planner"]
        plan = planner.plan_evaluation(skill, profile, test_cases)

        # Step 4: Validation
        validator = setup["validator"]
        validation_result = validator.validate_plan(plan)
        assert validation_result.status.value == "valid"

        # Step 5: Execution with divergent agent
        adapter = setup["adapter"]
        mock_agent = MockTargetAgent(behavior="divergent")
        executor = mock_agent.get_executor()
        
        # v1.1: Pass semantic check
        def divergence_check(outputs: list[str]) -> bool:
            if len(outputs) < 2:
                return True
            out1, out2 = outputs[0], outputs[1]
            # Detect confidence divergence
            confident = ["confident", "definitely", "correct"]
            uncertain = ["uncertain", "maybe"]
            has_conf_1 = any(w in out1.lower() for w in confident)
            has_unc_1 = any(w in out1.lower() for w in uncertain)
            has_conf_2 = any(w in out2.lower() for w in confident)
            has_unc_2 = any(w in out2.lower() for w in uncertain)
            if (has_conf_1 and has_unc_2) or (has_unc_1 and has_conf_2):
                return False
            return True
        
        skill_result = adapter.execute_plan_delegated(plan, executor, semantic_check=divergence_check)

        # Step 6: Evidence
        evidence = EvidenceRecord(
            id=f"evidence_{uuid.uuid4().hex[:8]}",
            system_profile=profile,
            evaluation_plan=plan,
            skill_result=skill_result,
        )
        store = setup["store"]
        filepath = store.save_evidence(evidence)
        assert filepath

        # Verify: both test cases executed, but outputs differ
        assert len(skill_result.execution_results) == 2
        outputs = [r.output for r in skill_result.execution_results if r.succeeded]
        assert len(outputs) == 2
        # With divergent behavior, outputs should differ
        assert outputs[0] != outputs[1]
        
        # v1.1: result_state should now be DIVERGENT (with semantic check)
        assert skill_result.result_state == ResultState.DIVERGENT, \
            f"Expected DIVERGENT but got {skill_result.result_state.value} — semantic check detected confidence shift"
