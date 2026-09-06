"""Tests for Research Engine: candidate validation logic."""

import pytest
from fathom.research_engine import validate_candidate
from fathom.models import ValidationStatus


def test_validate_candidate_requires_fields():
    """Candidate must have all required fields."""
    bad_candidate = {"id": "test"}
    
    is_valid, error = validate_candidate(bad_candidate)
    assert is_valid is False
    assert "Missing required field" in error


def test_validate_candidate_checks_enum():
    """Candidate must have valid validation_status enum value."""
    bad_candidate = {
        "id": "test",
        "version": 1,
        "description": "test",
        "test_structure": [],
        "expected_behavior": [],
        "validation_status": "INVALID_STATUS",
    }
    
    is_valid, error = validate_candidate(bad_candidate)
    assert is_valid is False
    assert "validation_status" in error


def test_validate_candidate_accepts_valid():
    """Valid candidate passes all checks."""
    good_candidate = {
        "id": "test",
        "version": 1,
        "description": "test",
        "test_structure": [],
        "expected_behavior": [],
        "validation_status": ValidationStatus.EXPLORATORY.value,
    }
    
    is_valid, error = validate_candidate(good_candidate)
    assert is_valid is True
    assert error is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
