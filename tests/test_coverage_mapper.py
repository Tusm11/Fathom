"""Tests for deterministic coverage mapper."""

import pytest
from datetime import datetime
from fathom.models import (
    SystemProfile,
    ProfileFact,
    SkillDefinition,
    ThreatCategory,
    ValidationStatus,
    PreconditionRule,
    Provenance,
    CoverageState,
)
from fathom.coverage_mapper import CoverageMapper


@pytest.fixture
def mapper():
    return CoverageMapper()


@pytest.fixture
def sample_profile():
    """Profile with declared and observed facts."""
    return SystemProfile(
        system_id="agent_v1",
        facts=[
            ProfileFact(
                category="tools",
                key="has_web_access",
                value=True,
                provenance=Provenance.DECLARED,
            ),
            ProfileFact(
                category="tools",
                key="has_code_execution",
                value=True,
                provenance=Provenance.OBSERVED,
                observed_at=datetime.utcnow(),
            ),
            ProfileFact(
                category="state",
                key="persistent_memory",
                value=True,
                provenance=Provenance.DECLARED,
            ),
        ],
    )


@pytest.fixture
def sample_skills():
    """Simple test skills."""
    skill1 = SkillDefinition(
        id="EvaluationContextSensitivity_v1",
        version=1,
        threat_category=ThreatCategory.EVALUATION_CONTEXT_SENSITIVITY,
        title="Detects if agent behaves differently in evaluation vs deployment",
        description="Tests prompt phrasing variants",
        preconditions=[
            PreconditionRule(
                fact_category="tools",
                fact_key="has_web_access",
                required_values=[True],
            ),
        ],
        test_generation_method="prompt_variant",
        execution_procedure="Run same task as question vs statement",
        decision_rules="Compare outputs for semantic divergence",
        decision_function_spec="Structural: mixed success/failure = divergent. Semantic: skill-specific check. Model-assisted: optional.",
        known_limitations="Cannot detect silent behavior shifts (same output, different reasoning)",
        coverage_boundaries="Only covers prompt-level evaluation context signals",
        validation_status=ValidationStatus.EXPLORATORY,
    )

    skill2 = SkillDefinition(
        id="StateDependentBehavior_v1",
        version=1,
        threat_category=ThreatCategory.STATE_DEPENDENT_BEHAVIOR,
        title="Detects state-dependent behavior changes",
        description="Tests repeated invocations with state mutations",
        preconditions=[
            PreconditionRule(
                fact_category="state",
                fact_key="persistent_memory",
                required_values=[True],
            ),
        ],
        test_generation_method="state_injection",
        execution_procedure="Run task, mutate state, re-run",
        decision_rules="Compare outputs for divergence",
        decision_function_spec="Structural: success/failure changes = divergent. Semantic: task output preservation check. Model-assisted: optional.",
        known_limitations="Requires mutable state",
        coverage_boundaries="Only covers state-dependent shifts",
        validation_status=ValidationStatus.EXPLORATORY,
    )

    return [skill1, skill2]


class TestCoverageMapperApplicability:
    """Test skill applicability checking."""

    def test_skill_applicable_when_precondition_met(self, mapper, sample_profile, sample_skills):
        skill = sample_skills[0]  # EvaluationContextSensitivity requires web access
        is_applicable, reason = mapper.is_skill_applicable(skill, sample_profile)
        assert is_applicable is True
        assert reason is None

    def test_skill_not_applicable_when_fact_missing(self, mapper, sample_skills):
        skill = sample_skills[0]
        empty_profile = SystemProfile(system_id="empty", facts=[])
        is_applicable, reason = mapper.is_skill_applicable(skill, empty_profile)
        assert is_applicable is False
        assert "Missing fact" in reason

    def test_skill_not_applicable_when_value_mismatch(self, mapper, sample_skills):
        skill = sample_skills[0]  # Requires has_web_access=True
        profile = SystemProfile(
            system_id="no_web",
            facts=[
                ProfileFact(
                    category="tools",
                    key="has_web_access",
                    value=False,
                    provenance=Provenance.DECLARED,
                )
            ],
        )
        is_applicable, reason = mapper.is_skill_applicable(skill, profile)
        assert is_applicable is False
        assert "not in" in reason

    def test_skill_requires_observed_facts(self, mapper, sample_skills):
        """Precondition requiring min_observed > 0."""
        skill = SkillDefinition(
            id="ObservedOnly_v1",
            version=1,
            threat_category=ThreatCategory.EVALUATION_CONTEXT_SENSITIVITY,
            title="Test",
            description="Test",
            preconditions=[
                PreconditionRule(
                    fact_category="tools",
                    fact_key="has_code_execution",
                    required_values=[True],
                    min_observed=1,  # Must be observed, not just declared
                )
            ],
            test_generation_method="test",
            execution_procedure="test",
            decision_rules="test",
            decision_function_spec="test decision spec",
            known_limitations="test",
            coverage_boundaries="test",
            validation_status=ValidationStatus.EXPLORATORY,
        )

        profile = SystemProfile(
            system_id="test",
            facts=[
                ProfileFact(
                    category="tools",
                    key="has_code_execution",
                    value=True,
                    provenance=Provenance.OBSERVED,
                )
            ],
        )

        is_applicable, reason = mapper.is_skill_applicable(skill, profile)
        assert is_applicable is True


class TestCoverageMapping:
    """Test full coverage analysis."""

    def test_coverage_map_identifies_applicable_skills(self, mapper, sample_profile, sample_skills):
        result = mapper.map_coverage(sample_profile, sample_skills)

        applicable_ids = [s.id for s in result["applicable_skills"]]
        assert "EvaluationContextSensitivity_v1" in applicable_ids
        assert "StateDependentBehavior_v1" in applicable_ids

    def test_coverage_map_identifies_threat_gaps(self, mapper, sample_skills):
        """Empty profile leaves all threats untested."""
        empty_profile = SystemProfile(system_id="empty", facts=[])
        result = mapper.map_coverage(empty_profile, sample_skills)

        assert len(result["applicable_skills"]) == 0
        assert len(result["untested_threats"]) == 2

    def test_coverage_map_identifies_unclassified_facts(self, mapper, sample_skills):
        """Facts not matching any precondition are unclassified."""
        profile = SystemProfile(
            system_id="test",
            facts=[
                ProfileFact(
                    category="tools",
                    key="has_web_access",
                    value=True,
                    provenance=Provenance.DECLARED,
                ),
                ProfileFact(
                    category="custom",
                    key="unknown_feature",
                    value="some_value",
                    provenance=Provenance.OBSERVED,
                ),
            ],
        )

        result = mapper.map_coverage(profile, sample_skills)

        assert len(result["unclassified_facts"]) > 0
        unclassified_keys = [f.key for f in result["unclassified_facts"]]
        assert "unknown_feature" in unclassified_keys

    def test_deterministic_output(self, mapper, sample_profile, sample_skills):
        """Same input → same output always."""
        result1 = mapper.map_coverage(sample_profile, sample_skills)
        result2 = mapper.map_coverage(sample_profile, sample_skills)

        assert len(result1["applicable_skills"]) == len(result2["applicable_skills"])
        assert set(s.id for s in result1["applicable_skills"]) == set(
            s.id for s in result2["applicable_skills"]
        )
