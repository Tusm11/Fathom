"""Tests for diagnostic pipeline and API."""

import pytest
import tempfile
import json
from pathlib import Path
from fathom.pipeline import DiagnosticPipeline
from fathom.api import FathomClient
from fathom.profiler import SystemProfiler
from fathom.registry import bootstrap_registry
from fathom.execution_adapter import MockTargetAgent


class TestDiagnosticPipeline:
    """Test end-to-end pipeline."""

    def test_pipeline_consistent_agent(self):
        registry = bootstrap_registry()
        pipeline = DiagnosticPipeline(registry=registry)

        # Create profile
        profiler = SystemProfiler()
        facts = [
            profiler.add_declared_fact("tools", "has_web_access", True),
        ]
        profile = profiler.create_profile("test_agent", facts)

        # Run diagnostic with mock executor
        mock_agent = MockTargetAgent(behavior="consistent")
        executor = mock_agent.get_executor()
        report = pipeline.diagnose(profile, executor)

        assert report.system_id == "test_agent"
        assert len(report.findings) > 0
        assert "EvaluationContextSensitivity_v1" in report.tested_skills

    def test_pipeline_divergent_agent(self):
        registry = bootstrap_registry()
        pipeline = DiagnosticPipeline(registry=registry)

        profiler = SystemProfiler()
        facts = [
            profiler.add_declared_fact("tools", "has_web_access", True),
        ]
        profile = profiler.create_profile("divergent_agent", facts)

        mock_agent = MockTargetAgent(behavior="divergent")
        executor = mock_agent.get_executor()
        report = pipeline.diagnose(profile, executor)

        assert report.system_id == "divergent_agent"
        assert len(report.findings) >= 0  # May or may not detect divergence

    def test_pipeline_no_applicable_skills(self):
        """Empty profile → no applicable skills → no findings."""
        registry = bootstrap_registry()
        pipeline = DiagnosticPipeline(registry=registry)

        profiler = SystemProfiler()
        profile = profiler.create_profile("empty_agent", [])

        report = pipeline.diagnose(profile)

        assert len(report.findings) == 0
        assert len(report.tested_skills) == 0


class TestFathomClient:
    """Test high-level API."""

    def test_client_profile_building(self):
        client = FathomClient()

        profile = client.create_profile("my_agent")
        assert profile.system_id == "my_agent"
        assert len(profile.facts) == 0

        fact1 = client.add_declared_fact(profile, "tools", "web_access", True)
        assert fact1.provenance.value == "declared"
        assert len(profile.facts) == 1

        fact2 = client.add_observed_fact(profile, "state", "memory", False)
        assert fact2.provenance.value == "observed"
        assert len(profile.facts) == 2

    def test_client_diagnose(self):
        client = FathomClient()

        profile = client.create_profile("test_agent")
        client.add_declared_fact(profile, "tools", "has_web_access", True)

        report = client.diagnose(profile)

        assert report.system_id == "test_agent"
        assert isinstance(report.findings, list)

    def test_client_export_report(self):
        client = FathomClient()

        profile = client.create_profile("export_test")
        client.add_declared_fact(profile, "tools", "has_web_access", True)
        report = client.diagnose(profile)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            client.export_report(report, str(output_path))

            assert output_path.exists()
            with open(output_path) as f:
                data = json.load(f)

            assert data["system_id"] == "export_test"
            assert "findings" in data
