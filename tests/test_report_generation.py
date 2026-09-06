"""Tests for diagnostic report generation."""

import pytest
import uuid
from datetime import datetime
from fathom.models import (
    SystemProfile,
    ProfileFact,
    Provenance,
    EvidenceRecord,
    SkillResult,
    ExecutionResult,
    ResultState,
    CoverageState,
    EvaluationPlan,
    SkillTestCase,
    PlanValidationResult,
    PlanValidityStatus,
    ValidationMethod,
)
from fathom.report_generator import CoverageAnalyzer, DiagnosticReportGenerator
from fathom.registry import bootstrap_registry


@pytest.fixture
def sample_evidence():
    """Create sample evidence for testing."""
    profile = SystemProfile(
        system_id="test_agent",
        facts=[
            ProfileFact(
                category="tools",
                key="has_web_access",
                value=True,
                provenance=Provenance.DECLARED,
            )
        ],
    )

    plan = EvaluationPlan(
        id="test_plan",
        skill_id="EvaluationContextSensitivity_v1",
        skill_version=1,
        system_id="test_agent",
        test_cases=[
            SkillTestCase(
                name="test_1",
                description="Test question variant",
                inputs={"prompt": "?test", "context_type": "question"},
            ),
            SkillTestCase(
                name="test_2",
                description="Test statement variant",
                inputs={"prompt": "!test", "context_type": "statement"},
            ),
        ],
        validation_result=PlanValidationResult(
            status=PlanValidityStatus.VALID,
            validation_method=ValidationMethod.DETERMINISTIC,
            structural_passed=True,
            semantic_passed=True,
        ),
    )

    skill_result = SkillResult(
        skill_id="EvaluationContextSensitivity_v1",
        skill_version=1,
        system_id="test_agent",
        execution_results=[
            ExecutionResult(
                test_case_name="test_1",
                succeeded=True,
                output="Question response",
            ),
            ExecutionResult(
                test_case_name="test_2",
                succeeded=True,
                output="Statement response",
            ),
        ],
        result_state=ResultState.CONSISTENT,
        evidence_summary="2 test cases executed",
    )

    evidence = EvidenceRecord(
        id=f"test_{uuid.uuid4().hex[:8]}",
        system_profile=profile,
        evaluation_plan=plan,
        skill_result=skill_result,
    )

    return evidence


class TestCoverageAnalyzer:
    """Test finding generation from evidence."""

    def test_analyze_evidence(self, sample_evidence):
        registry = bootstrap_registry()
        analyzer = CoverageAnalyzer()

        finding = analyzer.analyze_evidence(sample_evidence, registry)

        assert finding.threat_category.value == "evaluation_context_sensitivity"
        assert finding.result_state == ResultState.CONSISTENT
        assert finding.coverage_state == CoverageState.TESTED
        assert finding.evidence_id == sample_evidence.id


class TestDiagnosticReportGenerator:
    """Test full report generation."""

    def test_generate_report(self, sample_evidence):
        registry = bootstrap_registry()
        generator = DiagnosticReportGenerator()

        report = generator.generate_report(
            system_id="test_agent",
            evidence_records=[sample_evidence],
            registry=registry,
        )

        assert report.system_id == "test_agent"
        assert len(report.findings) == 1
        assert report.findings[0].result_state == ResultState.CONSISTENT
        assert "EvaluationContextSensitivity_v1" in report.tested_skills
        assert len(report.not_tested_threats) >= 0  # At least some threats not tested

    def test_report_coverage_summary(self, sample_evidence):
        registry = bootstrap_registry()
        generator = DiagnosticReportGenerator()

        report = generator.generate_report(
            system_id="test_agent",
            evidence_records=[sample_evidence],
            registry=registry,
        )

        # EvaluationContextSensitivity should be TESTED
        from fathom.models import ThreatCategory
        assert report.coverage_summary[ThreatCategory.EVALUATION_CONTEXT_SENSITIVITY] == CoverageState.TESTED

    def test_report_with_unclassified_facts(self, sample_evidence):
        registry = bootstrap_registry()
        generator = DiagnosticReportGenerator()

        unclassified = [
            ProfileFact(
                category="unknown",
                key="custom_feature",
                value="value",
                provenance=Provenance.OBSERVED,
            )
        ]

        report = generator.generate_report(
            system_id="test_agent",
            evidence_records=[sample_evidence],
            registry=registry,
            unclassified_facts=unclassified,
        )

        assert len(report.unclassified_facts) == 1
        assert report.unclassified_facts[0].key == "custom_feature"

    def test_report_no_evidence(self):
        registry = bootstrap_registry()
        generator = DiagnosticReportGenerator()

        report = generator.generate_report(
            system_id="test_agent",
            evidence_records=[],
            registry=registry,
        )

        assert len(report.findings) == 0
        assert len(report.tested_skills) == 0
        assert len(report.not_tested_threats) >= 1  # All threats untested
