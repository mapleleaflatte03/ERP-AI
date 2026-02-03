"""
Tests for ActionProposalService
===============================

Tests the Plan → Confirm → Execute pattern for AI action gating.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.action_proposals import (
    ActionProposalService,
    ModuleScope,
    ActionStatus,
    MODULE_ALLOWED_ACTIONS,
)


class MockConnection:
    """Mock database connection for testing."""
    
    def __init__(self):
        self.executed = []
        self.fetched = []
        self._next_fetch_result = None
        self._next_fetchrow_result = None
    
    async def execute(self, query, *args):
        self.executed.append((query, args))
    
    async def fetch(self, query, *args):
        self.fetched.append((query, args))
        return self._next_fetch_result or []
    
    async def fetchrow(self, query, *args):
        self.fetched.append((query, args))
        return self._next_fetchrow_result


class MockPool:
    """Mock connection pool."""
    
    def __init__(self, conn=None):
        self.conn = conn or MockConnection()
    
    def acquire(self):
        return self
    
    async def __aenter__(self):
        return self.conn
    
    async def __aexit__(self, *args):
        pass


@pytest.fixture
def mock_pool():
    """Create a mock database pool."""
    return MockPool()


@pytest.fixture
def service(mock_pool):
    """Create ActionProposalService with mock pool."""
    return ActionProposalService(mock_pool)


class TestModuleAllowedActions:
    """Test module scope validation."""
    
    def test_documents_allowed_actions(self):
        """Documents module should allow extract and propose actions."""
        allowed = MODULE_ALLOWED_ACTIONS[ModuleScope.DOCUMENTS]
        assert "extract_fields" in allowed
        assert "propose_journal" in allowed
        assert "approve_proposal" not in allowed
    
    def test_approvals_allowed_actions(self):
        """Approvals module should allow approve/reject actions."""
        allowed = MODULE_ALLOWED_ACTIONS[ModuleScope.APPROVALS]
        assert "approve_proposal" in allowed
        assert "reject_proposal" in allowed
        assert "extract_fields" not in allowed
    
    def test_analyze_allowed_actions(self):
        """Analyze module should allow query execution."""
        allowed = MODULE_ALLOWED_ACTIONS[ModuleScope.ANALYZE]
        assert "execute_query" in allowed
        assert "approve_proposal" not in allowed
    
    def test_global_is_read_only(self):
        """Global scope should only allow navigation."""
        allowed = MODULE_ALLOWED_ACTIONS[ModuleScope.GLOBAL]
        assert "navigate_to_module" in allowed
        assert len(allowed) == 1  # Only navigation


class TestCreateProposal:
    """Test proposal creation."""
    
    @pytest.mark.asyncio
    async def test_create_proposal_success(self, service, mock_pool):
        """Should create a proposal and return it."""
        # Setup mock
        proposal_id = str(uuid.uuid4())
        mock_pool.conn._next_fetchrow_result = {
            "id": uuid.UUID(proposal_id),
            "action_type": "approve_proposal",
            "target_entity": "approval",
            "target_id": None,
            "description": "Test approval",
            "reasoning": "Test reason",
            "status": "proposed",
            "action_params": {"_module": "approvals"},
            "result": None,
            "error_message": None,
            "created_at": datetime.now(),
            "confirmed_at": None,
            "executed_at": None,
        }
        
        result = await service.create_proposal(
            module=ModuleScope.APPROVALS,
            action_type="approve_proposal",
            payload={"approval_id": "test-123"},
            description="Test approval",
            reasoning="Test reason",
        )
        
        assert result["status"] == "proposed"
        assert result["action_type"] == "approve_proposal"
        assert result["module"] == "approvals"
    
    @pytest.mark.asyncio
    async def test_create_proposal_invalid_action_type(self, service):
        """Should raise error for invalid action type in module."""
        with pytest.raises(ValueError) as exc_info:
            await service.create_proposal(
                module=ModuleScope.DOCUMENTS,
                action_type="approve_proposal",  # Not allowed in documents
                payload={},
                description="Test",
            )
        
        assert "not allowed in module" in str(exc_info.value)


class TestConfirmProposal:
    """Test proposal confirmation and execution."""
    
    @pytest.mark.asyncio
    async def test_confirm_proposed_action(self, service, mock_pool):
        """Should confirm and execute a proposed action."""
        proposal_id = str(uuid.uuid4())
        
        # First call returns proposed status
        mock_pool.conn._next_fetchrow_result = {
            "id": uuid.UUID(proposal_id),
            "action_type": "approve_proposal",
            "target_entity": "approval",
            "target_id": None,
            "description": "Test",
            "reasoning": None,
            "status": "proposed",
            "action_params": {"approval_id": "test-123", "_module": "approvals"},
            "result": None,
            "error_message": None,
            "created_at": datetime.now(),
            "confirmed_at": None,
            "executed_at": None,
        }
        
        # Mock the executor
        with patch('src.services.action_proposals.ACTION_EXECUTORS') as mock_executors:
            mock_executor = AsyncMock(return_value={"success": True})
            mock_executors.get.return_value = mock_executor
            
            # After execution, return executed status
            executed_result = dict(mock_pool.conn._next_fetchrow_result)
            executed_result["status"] = "executed"
            executed_result["result"] = {"success": True}
            
            # Patch to return different results on subsequent calls
            call_count = [0]
            original_fetchrow = mock_pool.conn.fetchrow
            
            async def multi_fetchrow(query, *args):
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_pool.conn._next_fetchrow_result
                return executed_result
            
            mock_pool.conn.fetchrow = multi_fetchrow
            
            result = await service.confirm(proposal_id, "user-123")
            
            assert result["status"] == "executed"
    
    @pytest.mark.asyncio
    async def test_confirm_already_executed(self, service, mock_pool):
        """Should raise error when confirming already executed action."""
        proposal_id = str(uuid.uuid4())
        
        mock_pool.conn._next_fetchrow_result = {
            "id": uuid.UUID(proposal_id),
            "status": "executed",  # Already executed
            "action_type": "approve_proposal",
            "action_params": {},
        }
        
        with pytest.raises(ValueError) as exc_info:
            await service.confirm(proposal_id, "user-123")
        
        assert "Cannot confirm" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_confirm_not_found(self, service, mock_pool):
        """Should raise error when proposal not found."""
        mock_pool.conn._next_fetchrow_result = None
        
        # Use valid UUID format for proposal_id
        nonexistent_uuid = "00000000-0000-0000-0000-000000000000"
        
        with pytest.raises(ValueError) as exc_info:
            await service.confirm(nonexistent_uuid, "user-123")
        
        assert "not found" in str(exc_info.value)


class TestCancelProposal:
    """Test proposal cancellation."""
    
    @pytest.mark.asyncio
    async def test_cancel_proposed_action(self, service, mock_pool):
        """Should cancel a proposed action."""
        proposal_id = str(uuid.uuid4())
        
        mock_pool.conn._next_fetchrow_result = {
            "id": uuid.UUID(proposal_id),
            "status": "proposed",
            "action_type": "approve_proposal",
            "action_params": {},
        }
        
        result = await service.cancel(proposal_id, "user-123")
        
        assert result["success"] is True
        assert result["status"] == "cancelled"
        
        # Verify update was called
        assert any("cancelled" in str(q) for q, _ in mock_pool.conn.executed)
    
    @pytest.mark.asyncio
    async def test_cancel_already_executed(self, service, mock_pool):
        """Should raise error when cancelling already executed action."""
        proposal_id = str(uuid.uuid4())
        
        mock_pool.conn._next_fetchrow_result = {
            "id": uuid.UUID(proposal_id),
            "status": "executed",
            "action_type": "approve_proposal",
            "action_params": {},
        }
        
        with pytest.raises(ValueError) as exc_info:
            await service.cancel(proposal_id, "user-123")
        
        assert "Cannot cancel" in str(exc_info.value)


class TestAuditLogging:
    """Test audit event creation."""
    
    @pytest.mark.asyncio
    async def test_proposal_creates_audit_event(self, service, mock_pool):
        """Should create audit event when proposal is created."""
        mock_pool.conn._next_fetchrow_result = {
            "id": uuid.uuid4(),
            "action_type": "approve_proposal",
            "target_entity": "approval",
            "target_id": None,
            "description": "Test",
            "reasoning": None,
            "status": "proposed",
            "action_params": {"_module": "approvals"},
            "result": None,
            "error_message": None,
            "created_at": datetime.now(),
            "confirmed_at": None,
            "executed_at": None,
        }
        
        await service.create_proposal(
            module=ModuleScope.APPROVALS,
            action_type="approve_proposal",
            payload={},
            description="Test",
        )
        
        # Check audit_events insert was called
        audit_inserts = [
            q for q, _ in mock_pool.conn.executed 
            if "audit_events" in q and "INSERT" in q
        ]
        assert len(audit_inserts) > 0


class TestListPending:
    """Test listing pending proposals."""
    
    @pytest.mark.asyncio
    async def test_list_pending_by_module(self, service, mock_pool):
        """Should filter pending proposals by module."""
        mock_pool.conn._next_fetch_result = [
            {
                "id": uuid.uuid4(),
                "action_type": "approve_proposal",
                "target_entity": "approval",
                "target_id": None,
                "description": "Test",
                "reasoning": None,
                "status": "proposed",
                "action_params": {"_module": "approvals"},
                "result": None,
                "error_message": None,
                "created_at": datetime.now(),
                "confirmed_at": None,
                "executed_at": None,
            }
        ]
        
        results = await service.list_pending(module=ModuleScope.APPROVALS)
        
        assert len(results) == 1
        assert results[0]["module"] == "approvals"


# Integration-style tests (would need real DB)
class TestExecutors:
    """Test action executors."""
    
    @pytest.mark.asyncio
    async def test_execute_query_validates_select_only(self):
        """execute_query should reject non-SELECT queries."""
        from src.services.action_proposals import execute_query
        
        conn = MockConnection()
        
        # Should reject INSERT
        with pytest.raises(ValueError) as exc_info:
            await execute_query({"sql": "INSERT INTO users VALUES (1)"}, conn)
        assert "Only SELECT" in str(exc_info.value)
        
        # Should reject DELETE
        with pytest.raises(ValueError) as exc_info:
            await execute_query({"sql": "DELETE FROM users"}, conn)
        assert "Only SELECT" in str(exc_info.value)
        
        # Should reject DROP
        with pytest.raises(ValueError) as exc_info:
            await execute_query({"sql": "DROP TABLE users"}, conn)
        assert "Only SELECT" in str(exc_info.value)
