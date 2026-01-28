import importlib
import os
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))


class TestStoreJobResultActivity(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Create a clean slate for sys.modules
        self.modules_patcher = patch.dict(sys.modules)
        self.modules_patcher.start()

        # Mock temporalio
        mock_temporal = types.ModuleType("temporalio")
        mock_activity = types.ModuleType("temporalio.activity")
        mock_workflow = types.ModuleType("temporalio.workflow")

        def identity(obj):
            return obj

        mock_activity.defn = identity
        mock_workflow.defn = identity
        mock_workflow.run = identity
        mock_workflow.signal = identity

        sys.modules["temporalio"] = mock_temporal
        sys.modules["temporalio.activity"] = mock_activity
        sys.modules["temporalio.workflow"] = mock_workflow
        sys.modules["temporalio.client"] = MagicMock()
        sys.modules["temporalio.common"] = MagicMock()
        sys.modules["temporalio.worker"] = MagicMock()

        # Mock src.db
        self.mock_db = MagicMock()
        self.mock_db.update_job_status = AsyncMock()
        self.mock_db.log_audit = AsyncMock()
        sys.modules["src.db"] = self.mock_db

        # Remove src.workflows from sys.modules if present to ensure fresh import
        if "src.workflows" in sys.modules:
            del sys.modules["src.workflows"]

        import src.workflows

        # Reloading is safer if we want to be sure
        importlib.reload(src.workflows)

        self.module = src.workflows

    def tearDown(self):
        self.modules_patcher.stop()

    async def test_success(self):
        # Arrange
        job_id = "test-job-123"
        result = {
            "status": "completed",
            "proposal": {"some": "data"},
            "extracted_data": {"field": "value"},
            "validation_result": {"valid": True},
            "doc_type": "invoice",
        }

        # Act
        ret = await self.module.store_job_result_activity(job_id, result)

        # Assert
        self.assertTrue(ret)

        self.mock_db.update_job_status.assert_awaited_once_with(
            job_id,
            "completed",
            journal_proposal={"some": "data"},
            extracted_data={"field": "value"},
            validation_result={"valid": True},
            document_type="invoice",
            error_message=None,
        )

        self.mock_db.log_audit.assert_awaited_once_with(
            action="job_completed",
            entity_type="job",
            entity_id=job_id,
            job_id=job_id,
            new_value={"status": "completed"},
        )

    async def test_failure(self):
        # Arrange
        job_id = "test-job-error"
        result = {"status": "failed", "error_message": "Something went wrong"}

        # Act
        ret = await self.module.store_job_result_activity(job_id, result)

        # Assert
        self.assertTrue(ret)

        self.mock_db.update_job_status.assert_awaited_once_with(
            job_id,
            "failed",
            journal_proposal=None,
            extracted_data=None,
            validation_result=None,
            document_type=None,
            error_message="Something went wrong",
        )

        self.mock_db.log_audit.assert_awaited_once_with(
            action="job_failed", entity_type="job", entity_id=job_id, job_id=job_id, new_value={"status": "failed"}
        )


if __name__ == "__main__":
    unittest.main()
