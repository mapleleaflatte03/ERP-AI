import os
import sys
import unittest
import uuid
from datetime import datetime
from unittest.mock import ANY, MagicMock

# Add project root to path
sys.path.insert(0, os.getcwd())

from domain.enums import InvoiceStatus, ProposalStatus
from domain.models import Invoice, LedgerEntry, Proposal
from services.ledger.ledger_writer import LedgerWriter


class TestLedgerWriterPerformance(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.writer = LedgerWriter(self.mock_db)

        # Setup common objects
        self.invoice_id = uuid.uuid4()
        self.tenant_id = "tenant-1"
        self.proposal_id = uuid.uuid4()

        self.proposal = Proposal(
            id=self.proposal_id,
            tenant_id=self.tenant_id,
            invoice_id=self.invoice_id,
            status=ProposalStatus.APPROVED,
            approved_at=datetime.utcnow(),
            suggested_entries=[
                {
                    "debit_account": "100",
                    "debit_account_name": "Cash",
                    "credit_account": "200",
                    "credit_account_name": "Revenue",
                    "amount": 100.0,
                    "description": "Test Entry",
                    "currency": "USD",
                }
            ],
        )

        self.invoice = Invoice(id=self.invoice_id, tenant_id=self.tenant_id, status=InvoiceStatus.APPROVED)

    def test_post_to_ledger_query_count_baseline(self):
        """
        Baseline test: confirm that post_to_ledger queries for the invoice
        when it is not provided.
        """
        # Mock the query for Invoice
        # db.query(Invoice).filter(...).first()
        mock_query = self.mock_db.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = self.invoice

        # Mock the query for LedgerEntry (journal number generation)
        # db.query(LedgerEntry).filter(...).filter(...).distinct(...).count()
        # This is for _generate_journal_number
        (
            self.mock_db.query.return_value.filter.return_value.filter.return_value.distinct.return_value.count.return_value
        ) = 0

        self.writer.post_to_ledger(self.proposal, "approver-1")

        # Verification
        # Check that db.query(Invoice) was called
        self.mock_db.query.assert_any_call(Invoice)

        # Verify invoice status was updated
        self.assertEqual(self.invoice.status, InvoiceStatus.POSTED)

        print("\n[Baseline] db.query(Invoice) called as expected.")

    def test_post_to_ledger_query_elimination(self):
        """
        Optimization test: confirm that post_to_ledger DOES NOT query for the invoice
        when it IS provided.
        """
        # Mock the query for LedgerEntry (journal number generation)
        (
            self.mock_db.query.return_value.filter.return_value.filter.return_value.distinct.return_value.count.return_value
        ) = 0

        # Reset mock to clear previous calls if any (though setUp creates new one)
        self.mock_db.query.reset_mock()

        # Pass the invoice object
        self.writer.post_to_ledger(self.proposal, "approver-1", invoice=self.invoice)

        # Verification
        # Check that db.query(Invoice) was NOT called
        # We need to check call args.
        # calls = self.mock_db.query.call_args_list
        # for call in calls:
        #    if call.args[0] == Invoice:
        #        self.fail("db.query(Invoice) should not be called when invoice is provided")

        # Or simpler, since distinct.count calls query(LedgerEntry), we can just check query arguments

        invoice_queries = [call for call in self.mock_db.query.call_args_list if call.args and call.args[0] == Invoice]
        self.assertEqual(len(invoice_queries), 0, "db.query(Invoice) should not be called")

        # Verify invoice status was updated
        self.assertEqual(self.invoice.status, InvoiceStatus.POSTED)

        print("\n[Optimization] db.query(Invoice) eliminated as expected.")


if __name__ == "__main__":
    unittest.main()
