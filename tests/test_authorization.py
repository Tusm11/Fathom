"""Tests for authorization and managed execution."""

import pytest
from datetime import datetime, timedelta
from fathom.authorization import (
    AuthorizationStore,
    ExecutionAuthorization,
    BlastRadius,
    BlastRadiusProvenance,
    ResultState,
    VerificationCriteria,
)
from fathom.execution_adapter import ExecutionAdapter
from fathom.models import EvaluationPlan, SkillTestCase, PlanValidationResult, PlanValidityStatus, ValidationMethod
from fathom.execution_adapter_managed import ManagedExecutor


class TestAuthorizationStore:
    """Test authorization registry."""

    def test_authorize_target(self):
        store = AuthorizationStore()
        auth = ExecutionAuthorization(
            target_id="safe_mock_agent",
            blast_radius=BlastRadius.SAFE,
            blast_radius_provenance=BlastRadiusProvenance.VERIFIED,
            blast_radius_reason="Mock agent, no side effects",
            reason="Mock agent for testing",
            authorized_by="test_suite",
        )

        store.authorize(auth)
        retrieved = store.get_authorization("safe_mock_agent")
        assert retrieved is not None
        assert retrieved.target_id == "safe_mock_agent"

    def test_check_authorization_success(self):
        store = AuthorizationStore()
        auth = ExecutionAuthorization(
            target_id="safe_agent",
            blast_radius=BlastRadius.SAFE,
            blast_radius_provenance=BlastRadiusProvenance.VERIFIED,
            blast_radius_reason="Code reviewed",
            reason="Safe mock",
            authorized_by="test",
        )
        store.authorize(auth)

        is_auth, reason = store.check_authorization("safe_agent", require_safe=True)
        assert is_auth is True
        assert reason is None

    def test_check_authorization_missing(self):
        store = AuthorizationStore()
        is_auth, reason = store.check_authorization("unknown_agent")
        assert is_auth is False
        assert "No authorization found" in reason

    def test_check_authorization_declared_safe_blocked_first_run(self):
        """SAFE with DECLARED provenance requires explicit override."""
        store = AuthorizationStore()
        auth = ExecutionAuthorization(
            target_id="declared_safe_agent",
            blast_radius=BlastRadius.SAFE,
            blast_radius_provenance=BlastRadiusProvenance.DECLARED,
            blast_radius_reason="Self-reported as read-only",
            reason="Test declared SAFE",
            authorized_by="test",
        )
        store.authorize(auth)

        # Without allow_declared, should be blocked
        is_auth, reason = store.check_authorization("declared_safe_agent", require_safe=True, allow_declared=False)
        assert is_auth is False
        assert "declared but not verified" in reason

        # With allow_declared, should pass
        is_auth, reason = store.check_authorization("declared_safe_agent", require_safe=True, allow_declared=True)
        assert is_auth is True

    def test_check_authorization_unknown_blocked(self):
        """UNKNOWN blast radius blocked (treated as HIGH)."""
        store = AuthorizationStore()
        auth = ExecutionAuthorization(
            target_id="unknown_agent",
            blast_radius=BlastRadius.UNKNOWN,
            blast_radius_provenance=BlastRadiusProvenance.DECLARED,
            blast_radius_reason="Not yet assessed",
            reason="Test UNKNOWN",
            authorized_by="test",
        )
        store.authorize(auth)

        is_auth, reason = store.check_authorization("unknown_agent", require_safe=True)
        assert is_auth is False
        assert "UNKNOWN" in reason or "not assessed" in reason

        # Even with require_safe=False, should still fail (UNKNOWN stays blocked)
        # Actually, require_safe=False overrides all checks
        is_auth, reason = store.check_authorization("unknown_agent", require_safe=False)
        assert is_auth is True

    def test_mark_verified(self):
        """After successful execution, mark DECLARED as VERIFIED."""
        from fathom.models import ExecutionResult, SkillResult

        store = AuthorizationStore()
        auth = ExecutionAuthorization(
            target_id="to_verify",
            blast_radius=BlastRadius.SAFE,
            blast_radius_provenance=BlastRadiusProvenance.DECLARED,
            blast_radius_reason="Self-reported",
            reason="Test",
            authorized_by="test",
        )
        store.authorize(auth)

        # Before verification, requires allow_declared
        is_auth, _ = store.check_authorization("to_verify", require_safe=True, allow_declared=False)
        assert is_auth is False

        # Create successful skill_result
        skill_result = SkillResult(
            skill_id="test",
            skill_version=1,
            system_id="to_verify",
            execution_results=[
                ExecutionResult(
                    test_case_name="test_1",
                    succeeded=True,
                    output="Success: operation completed",
                ),
                ExecutionResult(
                    test_case_name="test_2",
                    succeeded=True,
                    output="Success: all good",
                ),
            ],
            result_state=ResultState.CONSISTENT,
            evidence_summary="Passed all checks",
        )

        # Mark verified
        was_verified, error = store.mark_verified("to_verify", skill_result)
        assert was_verified is True
        assert error is None

        auth_after = store.get_authorization("to_verify")
        assert auth_after.blast_radius_provenance == BlastRadiusProvenance.VERIFIED
        assert auth_after.blast_radius_verified_at is not None

        # Now auto-invocation allowed
        is_auth, _ = store.check_authorization("to_verify", require_safe=True, allow_declared=False)
        assert is_auth is True

    def test_mark_verified_fails_on_execution_error(self):
        """mark_verified rejects if test case failed."""
        from fathom.models import ExecutionResult, SkillResult

        store = AuthorizationStore()
        auth = ExecutionAuthorization(
            target_id="failed_verify",
            blast_radius=BlastRadius.SAFE,
            blast_radius_provenance=BlastRadiusProvenance.DECLARED,
            blast_radius_reason="Self-reported",
            reason="Test",
            authorized_by="test",
        )
        store.authorize(auth)

        # Skill result with failed test
        skill_result = SkillResult(
            skill_id="test",
            skill_version=1,
            system_id="failed_verify",
            execution_results=[
                ExecutionResult(
                    test_case_name="test_1",
                    succeeded=False,
                    error="Execution error",
                ),
            ],
            result_state=ResultState.INCONCLUSIVE,
            evidence_summary="Failed",
        )

        was_verified, error = store.mark_verified("failed_verify", skill_result)
        assert was_verified is False
        assert "Not all test cases succeeded" in error

        # Still DECLARED
        auth_after = store.get_authorization("failed_verify")
        assert auth_after.blast_radius_provenance == BlastRadiusProvenance.DECLARED

    def test_mark_verified_fails_on_error_output(self):
        """mark_verified rejects if output contains error markers."""
        from fathom.models import ExecutionResult, SkillResult

        store = AuthorizationStore()
        auth = ExecutionAuthorization(
            target_id="error_output",
            blast_radius=BlastRadius.SAFE,
            blast_radius_provenance=BlastRadiusProvenance.DECLARED,
            blast_radius_reason="Self-reported",
            reason="Test",
            authorized_by="test",
        )
        store.authorize(auth)

        # Skill result with error marker in output (no exception, but error in response)
        skill_result = SkillResult(
            skill_id="test",
            skill_version=1,
            system_id="error_output",
            execution_results=[
                ExecutionResult(
                    test_case_name="test_1",
                    succeeded=True,
                    output="ERROR: operation not permitted",
                ),
            ],
            result_state=ResultState.CONSISTENT,
            evidence_summary="Passed",
        )

        was_verified, error = store.mark_verified("error_output", skill_result)
        assert was_verified is False
        assert "contains error marker" in error

        # Still DECLARED
        auth_after = store.get_authorization("error_output")
        assert auth_after.blast_radius_provenance == BlastRadiusProvenance.DECLARED

    def test_check_authorization_expired(self):
        store = AuthorizationStore()
        auth = ExecutionAuthorization(
            target_id="expired_agent",
            blast_radius=BlastRadius.SAFE,
            blast_radius_provenance=BlastRadiusProvenance.VERIFIED,
            blast_radius_reason="Code reviewed",
            expires_at=datetime.utcnow() - timedelta(hours=1),
            reason="Expired",
            authorized_by="test",
        )
        store.authorize(auth)

        is_auth, reason = store.check_authorization("expired_agent")
        assert is_auth is False
        assert "expired" in reason

    def test_revoke_authorization(self):
        store = AuthorizationStore()
        auth = ExecutionAuthorization(
            target_id="revokable",
            blast_radius=BlastRadius.SAFE,
            blast_radius_provenance=BlastRadiusProvenance.VERIFIED,
            blast_radius_reason="Code reviewed",
            reason="Test",
            authorized_by="test",
        )
        store.authorize(auth)
        assert store.get_authorization("revokable") is not None

        store.revoke("revokable")
        assert store.get_authorization("revokable") is None


class TestExecutionAdapterManaged:
    """Test managed execution branching."""

    def test_managed_execution_not_authorized(self):
        auth_store = AuthorizationStore()
        adapter = ExecutionAdapter(auth_store=auth_store)

        plan = EvaluationPlan(
            id="test_plan",
            skill_id="test_skill",
            skill_version=1,
            system_id="unknown_target",
            test_cases=[
                SkillTestCase(
                    name="test_1",
                    description="Test",
                    inputs={"task": "test"},
                )
            ],
            validation_result=PlanValidationResult(
                status=PlanValidityStatus.VALID,
                validation_method=ValidationMethod.DETERMINISTIC,
                structural_passed=True,
                semantic_passed=True,
            ),
        )

        def mock_executor(inputs):
            pass

        skill_result, error = adapter.execute_plan_managed(
            plan,
            "unknown_target",
            mock_executor,
        )

        assert skill_result is None
        assert error is not None
        assert "No authorization found" in error

    def test_managed_execution_authorized(self):
        auth_store = AuthorizationStore()
        auth = ExecutionAuthorization(
            target_id="safe_target",
            blast_radius=BlastRadius.SAFE,
            blast_radius_provenance=BlastRadiusProvenance.VERIFIED,
            blast_radius_reason="Code reviewed",
            reason="Test",
            authorized_by="test",
        )
        auth_store.authorize(auth)

        adapter = ExecutionAdapter(auth_store=auth_store)

        plan = EvaluationPlan(
            id="test_plan",
            skill_id="test_skill",
            skill_version=1,
            system_id="safe_target",
            test_cases=[
                SkillTestCase(
                    name="test_1",
                    description="Test",
                    inputs={"task": "test"},
                )
            ],
            validation_result=PlanValidationResult(
                status=PlanValidityStatus.VALID,
                validation_method=ValidationMethod.DETERMINISTIC,
                structural_passed=True,
                semantic_passed=True,
            ),
        )

        def mock_executor(inputs):
            from fathom.models import ExecutionResult
            return ExecutionResult(
                test_case_name=inputs.get("_test_case_name", "test"),
                succeeded=True,
                output="Test output",
            )

        skill_result, error = adapter.execute_plan_managed(
            plan,
            "safe_target",
            mock_executor,
        )

        assert skill_result is not None
        assert error is None
        assert "MANAGED" in skill_result.evidence_summary
        assert "safe_target" in skill_result.evidence_summary
