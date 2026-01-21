"""
ERPX AI Accounting - Workflow Tests
===================================
Tests for the LangGraph workflow.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.constants import DocumentType
from orchestrator.states import WorkflowState, WorkflowStep
from orchestrator.workflow import AccountingWorkflow


class TestWorkflowState:
    """Tests for workflow state management"""

    def test_initial_state(self):
        """Test initial workflow state"""
        state = WorkflowState(doc_id="TEST-001", tenant_id="tenant-001")

        assert state.doc_id == "TEST-001"
        assert state.current_step == WorkflowStep.INGEST
        assert state.raw_content is None
        assert state.has_error is False

    def test_state_transitions(self):
        """Test workflow state transitions"""
        state = WorkflowState(doc_id="TEST-002", tenant_id="tenant-001")

        # Simulate transitions
        transitions = [
            WorkflowStep.INGEST,
            WorkflowStep.CLASSIFY,
            WorkflowStep.EXTRACT,
            WorkflowStep.VALIDATE,
            WorkflowStep.RECONCILE,
            WorkflowStep.DECISION,
        ]

        for step in transitions:
            state.current_step = step
            assert state.current_step == step

    def test_error_handling(self):
        """Test error state handling"""
        state = WorkflowState(doc_id="TEST-003", tenant_id="tenant-001")

        # Simulate error
        state.has_error = True
        state.error_message = "Validation failed"

        assert state.has_error is True
        assert "Validation" in state.error_message


class TestAccountingWorkflow:
    """Tests for accounting workflow"""

    def test_workflow_initialization(self):
        """Test workflow can be initialized"""
        workflow = AccountingWorkflow()
        assert workflow is not None

    def test_step_a_ingest(self):
        """Test document ingestion step"""
        workflow = AccountingWorkflow()

        state = WorkflowState(
            doc_id="TEST-004", tenant_id="tenant-001", raw_content="HÓA ĐƠN\nTổng tiền: 1,000,000 VND"
        )

        result = workflow._step_a_ingest(state)

        assert result.current_step == WorkflowStep.CLASSIFY
        assert result.has_error is False

    def test_step_b_classify_invoice(self):
        """Test document classification - invoice"""
        workflow = AccountingWorkflow()

        state = WorkflowState(
            doc_id="TEST-005",
            tenant_id="tenant-001",
            raw_content="HÓA ĐƠN GIÁ TRỊ GIA TĂNG\nSố: HD001\nVAT 10%",
            current_step=WorkflowStep.CLASSIFY,
        )

        result = workflow._step_b_classify(state)

        assert result.doc_type == DocumentType.INVOICE.value
        assert result.current_step == WorkflowStep.EXTRACT

    def test_step_b_classify_receipt(self):
        """Test document classification - receipt"""
        workflow = AccountingWorkflow()

        state = WorkflowState(
            doc_id="TEST-006",
            tenant_id="tenant-001",
            raw_content="PHIẾU THU\nSố: PT001\nNội dung: Tiền mặt",
            current_step=WorkflowStep.CLASSIFY,
        )

        result = workflow._step_b_classify(state)

        assert result.doc_type == DocumentType.RECEIPT.value

    def test_step_b_classify_bank_statement(self):
        """Test document classification - bank statement"""
        workflow = AccountingWorkflow()

        state = WorkflowState(
            doc_id="TEST-007",
            tenant_id="tenant-001",
            raw_content="SÀO KÊ NGÂN HÀNG\nTài khoản: 123456789\nSố dư: 10,000,000",
            current_step=WorkflowStep.CLASSIFY,
        )

        result = workflow._step_b_classify(state)

        assert result.doc_type == DocumentType.BANK_STATEMENT.value

    def test_step_c_extract(self):
        """Test data extraction step"""
        workflow = AccountingWorkflow()

        state = WorkflowState(
            doc_id="TEST-008",
            tenant_id="tenant-001",
            raw_content="HÓA ĐƠN\nTổng tiền hàng: 1,000,000\nVAT 10%: 100,000\nTổng cộng: 1,100,000",
            doc_type=DocumentType.INVOICE.value,
            current_step=WorkflowStep.EXTRACT,
        )

        result = workflow._step_c_extract(state)

        assert result.extracted_data is not None
        assert result.current_step == WorkflowStep.VALIDATE

    def test_step_d_validate_pass(self):
        """Test validation step - passing"""
        workflow = AccountingWorkflow()

        state = WorkflowState(
            doc_id="TEST-009",
            tenant_id="tenant-001",
            raw_content="Total: 1,100,000 VND",
            doc_type=DocumentType.INVOICE.value,
            extracted_data={"subtotal": 1_000_000, "vat_rate": 10, "vat_amount": 100_000, "grand_total": 1_100_000},
            current_step=WorkflowStep.VALIDATE,
        )

        result = workflow._step_d_validate(state)

        assert result.validation_result is not None
        assert result.validation_result.get("is_valid", False) is True

    def test_step_f_decision(self):
        """Test decision step"""
        workflow = AccountingWorkflow()

        state = WorkflowState(
            doc_id="TEST-010",
            tenant_id="tenant-001",
            doc_type=DocumentType.INVOICE.value,
            extracted_data={
                "grand_total": 5_000_000  # Below approval threshold
            },
            validation_result={"is_valid": True},
            current_step=WorkflowStep.DECISION,
        )

        result = workflow._step_f_decision(state)

        assert result.output is not None
        assert "needs_human_review" in result.output


class TestWorkflowIntegration:
    """Integration tests for complete workflow"""

    def test_complete_invoice_workflow(self):
        """Test complete workflow for an invoice"""
        workflow = AccountingWorkflow()

        state = WorkflowState(
            doc_id="TEST-INT-001",
            tenant_id="tenant-001",
            raw_content="""
            HÓA ĐƠN GIÁ TRỊ GIA TĂNG
            Số: HD20240115001
            Ngày: 15/01/2024
            
            Đơn vị bán: Công ty ABC
            MST: 0123456789
            
            Tổng tiền hàng: 10,000,000 VND
            Thuế GTGT 10%: 1,000,000 VND
            Tổng cộng: 11,000,000 VND
            """,
        )

        # Run through all steps
        state = workflow._step_a_ingest(state)
        state = workflow._step_b_classify(state)
        state = workflow._step_c_extract(state)
        state = workflow._step_d_validate(state)
        state = workflow._step_e_reconcile(state)
        state = workflow._step_f_decision(state)

        assert state.output is not None
        assert state.current_step == WorkflowStep.DECISION
        assert state.has_error is False

    def test_workflow_with_error(self):
        """Test workflow handles errors gracefully"""
        workflow = AccountingWorkflow()

        state = WorkflowState(
            doc_id="TEST-INT-002",
            tenant_id="tenant-001",
            raw_content="",  # Empty content should cause error
        )

        state = workflow._step_a_ingest(state)

        # Empty content may flag as needs review or error
        # The workflow should handle this gracefully
        assert state is not None


class TestWorkflowEdgeCases:
    """Tests for edge cases"""

    def test_large_amount_needs_review(self):
        """Test that large amounts trigger human review"""
        workflow = AccountingWorkflow()

        state = WorkflowState(
            doc_id="TEST-EDGE-001",
            tenant_id="tenant-001",
            doc_type=DocumentType.INVOICE.value,
            extracted_data={
                "grand_total": 150_000_000  # 150M - above threshold
            },
            validation_result={"is_valid": True},
            current_step=WorkflowStep.DECISION,
        )

        result = workflow._step_f_decision(state)

        assert result.output.get("needs_human_review", False) is True

    def test_missing_vat_invoice_warning(self):
        """Test warning for missing VAT invoice"""
        workflow = AccountingWorkflow()

        state = WorkflowState(
            doc_id="TEST-EDGE-002",
            tenant_id="tenant-001",
            doc_type=DocumentType.INVOICE.value,
            extracted_data={
                "grand_total": 25_000_000,  # Over 20M
                "has_vat_invoice": False,
            },
            validation_result={"is_valid": True, "warnings": ["missing_vat_invoice"]},
            current_step=WorkflowStep.DECISION,
        )

        result = workflow._step_f_decision(state)

        # Should still process but may have warnings
        assert result.output is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
