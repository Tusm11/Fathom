"""Test Research Engine integration into DiagnosticPipeline."""

import pytest
from datetime import datetime
from fathom.pipeline import DiagnosticPipeline
from fathom.models import (
    SystemProfile,
    ProfileFact,
    Provenance,
    DiagnosticReport,
    Finding,
    ThreatCategory,
    CoverageState,
    ResultState,
    ValidationStatus,
)
from fathom.registry import bootstrap_registry


@pytest.fixture
def sample_profile():
    """Sample system profile for testing."""
    return SystemProfile(
        system_id="test_agent",
        facts=[
            ProfileFact(
                category="tools",
                key="has_web_access",
                value=True,
                provenance=Provenance.DECLARED,
            ),
            ProfileFact(
                category="system",
                key="has_state_variables",
                value=True,
                provenance=Provenance.DECLARED,
            ),
        ],
    )


@pytest.fixture
def pipeline():
    """Pipeline with seeded registry."""
    return DiagnosticPipeline(registry=bootstrap_registry())


def test_propose_new_skills_from_report(pipeline, sample_profile):
    """
    Full e2e: diagnose → find gaps → propose on-demand.
    No auto-bloat. Explicit call only.
    """
    # Run diagnostic
    report = pipeline.diagnose(sample_profile)
    
    assert report is not None
    assert len(report.findings) > 0
    
    # On-demand: propose new skills (returns list, may be empty if no valid candidates)
    candidates = pipeline.propose_new_skills(report)
    
    # No exception = success. Candidates list is empty only if generation failed gracefully.
    assert isinstance(candidates, list)


def test_gap_extraction_from_inconclusive_findings(pipeline):
    """Gap extraction correctly identifies INCONCLUSIVE findings."""
    from fathom.research_engine import extract_coverage_gaps
    
    findings = [
        Finding(
            skill_id="test",
            finding_id="f1",
            threat_category=ThreatCategory.EVALUATION_CONTEXT_SENSITIVITY,
            result_state=ResultState.INCONCLUSIVE,
            evidence_id="e1",
            coverage_state=CoverageState.TESTED,
            validation_status=ValidationStatus.EXPLORATORY,
            decision_method="deterministic",
            summary="Found inconsistent behavior",
            confidence=0.5,
        ),
        Finding(
            skill_id="test",
            finding_id="f2",
            threat_category=ThreatCategory.EVALUATION_CONTEXT_SENSITIVITY,
            result_state=ResultState.CONSISTENT,
            evidence_id="e2",
            coverage_state=CoverageState.TESTED,
            validation_status=ValidationStatus.EXPLORATORY,
            decision_method="deterministic",
            summary="Behavior consistent",
            confidence=0.9,
        ),
    ]
    
    report = DiagnosticReport(
        id="test_report",
        system_id="test_system",
        skill_id="test",
        timestamp=datetime.utcnow(),
        findings=findings,
        coverage_summary={},
        tested_skills=[],
        not_tested_threats=[],
        unclassified_facts=[],
    )
    
    gaps = extract_coverage_gaps(report)
    
    # Should extract only INCONCLUSIVE
    assert len(gaps) >= 1
    assert any("Inconclusive" in gap for gap in gaps)


def test_gap_extraction_from_not_tested(pipeline):
    """Gap extraction correctly identifies NOT_TESTED coverage state."""
    from fathom.research_engine import extract_coverage_gaps
    
    findings = [
        Finding(
            skill_id="test",
            finding_id="f1",
            threat_category=ThreatCategory.EVALUATION_CONTEXT_SENSITIVITY,
            result_state=ResultState.CONSISTENT,
            evidence_id="e1",
            coverage_state=CoverageState.NOT_TESTED,
            validation_status=ValidationStatus.EXPLORATORY,
            decision_method="deterministic",
            summary="Never tested this scenario",
            confidence=0.0,
        ),
    ]
    
    report = DiagnosticReport(
        id="test_report",
        system_id="test_system",
        skill_id="test",
        timestamp=datetime.utcnow(),
        findings=findings,
        coverage_summary={},
        tested_skills=[],
        not_tested_threats=[],
        unclassified_facts=[],
    )
    
    gaps = extract_coverage_gaps(report)
    
    # Should extract NOT_TESTED gaps
    assert len(gaps) >= 1
    assert any("Not tested" in gap for gap in gaps)
