"""Tests for system profiler."""

import pytest
from datetime import datetime
from fathom.models import SystemProfile, ProfileFact, Provenance
from fathom.profiler import SystemProfiler


@pytest.fixture
def profiler():
    return SystemProfiler()


class TestProfilerFactCreation:
    """Test declared vs observed fact tracking."""

    def test_add_declared_fact(self, profiler):
        fact = profiler.add_declared_fact("tools", "has_web_access", True)
        assert fact.provenance == Provenance.DECLARED
        assert fact.category == "tools"
        assert fact.key == "has_web_access"
        assert fact.value is True
        assert fact.observed_at is None

    def test_add_observed_fact(self, profiler):
        fact = profiler.add_observed_fact("tools", "has_code_execution", True)
        assert fact.provenance == Provenance.OBSERVED
        assert fact.observed_at is not None
        assert isinstance(fact.observed_at, datetime)

    def test_create_profile(self, profiler):
        facts = [
            profiler.add_declared_fact("tools", "web_access", True),
            profiler.add_observed_fact("state", "memory", True),
        ]
        profile = profiler.create_profile("agent_v1", facts)
        assert profile.system_id == "agent_v1"
        assert len(profile.facts) == 2
        assert profile.profiled_at is not None


class TestProfileMerging:
    """Test profile merging and deduplication."""

    def test_merge_profiles(self, profiler):
        profile1 = profiler.create_profile(
            "agent_v1",
            [
                profiler.add_declared_fact("tools", "web_access", True),
                profiler.add_declared_fact("tools", "code_exec", False),
            ],
        )
        profile2 = profiler.create_profile(
            "agent_v1",
            [
                profiler.add_observed_fact("tools", "web_access", True),  # Overrides
                profiler.add_declared_fact("state", "memory", True),
            ],
        )

        merged = profiler.merge_profiles([profile1, profile2])
        assert merged.system_id == "agent_v1"
        assert len(merged.facts) == 3

        # Check that observed overwrote declared
        web_access_facts = [f for f in merged.facts if f.key == "web_access"]
        assert len(web_access_facts) == 1
        assert web_access_facts[0].provenance == Provenance.OBSERVED

    def test_merge_prevents_cross_system(self, profiler):
        profile1 = profiler.create_profile("agent_v1", [])
        profile2 = profiler.create_profile("agent_v2", [])

        with pytest.raises(ValueError, match="different systems"):
            profiler.merge_profiles([profile1, profile2])

    def test_merge_empty_list(self, profiler):
        with pytest.raises(ValueError):
            profiler.merge_profiles([])


class TestProfileFiltering:
    """Test profile subsetting."""

    def test_filter_by_category(self, profiler):
        facts = [
            profiler.add_declared_fact("tools", "web", True),
            profiler.add_declared_fact("tools", "code", False),
            profiler.add_declared_fact("state", "memory", True),
        ]
        profile = profiler.create_profile("agent_v1", facts)
        filtered = profiler.filter_profile(profile, category="tools")
        assert len(filtered.facts) == 2
        assert all(f.category == "tools" for f in filtered.facts)

    def test_filter_no_category(self, profiler):
        facts = [
            profiler.add_declared_fact("tools", "web", True),
            profiler.add_declared_fact("state", "memory", True),
        ]
        profile = profiler.create_profile("agent_v1", facts)
        filtered = profiler.filter_profile(profile)
        assert len(filtered.facts) == 2


class TestProvenanceSummary:
    """Test provenance statistics."""

    def test_provenance_summary(self, profiler):
        facts = [
            profiler.add_declared_fact("tools", "web", True),
            profiler.add_declared_fact("tools", "code", False),
            profiler.add_observed_fact("state", "memory", True),
        ]
        profile = profiler.create_profile("agent_v1", facts)
        summary = profiler.get_provenance_summary(profile)

        assert summary["total_facts"] == 3
        assert summary["declared"] == 2
        assert summary["observed"] == 1
        assert summary["declared_ratio"] == 2 / 3
        assert summary["observed_ratio"] == 1 / 3

    def test_provenance_summary_empty(self, profiler):
        profile = profiler.create_profile("agent_v1", [])
        summary = profiler.get_provenance_summary(profile)
        assert summary["total_facts"] == 0
        assert summary["declared_ratio"] == 0
        assert summary["observed_ratio"] == 0
