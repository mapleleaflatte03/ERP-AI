#!/usr/bin/env python3
"""
ERPX AI Accounting - End-to-End Demo Script
============================================
Demonstrates the complete workflow with mock data.
"""

import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from data_layer.minio_mock import MinIOMock
from data_layer.postgres_mock import PostgresMock, Transaction
from data_layer.qdrant_mock import KnowledgeBase, QdrantMock
from governance.approval_inbox import ApprovalPriority, ApprovalReason, get_approval_inbox
from governance.audit_store import AuditEventType, get_audit_store
from governance.evidence_store import get_evidence_store
from guardrails.input_validator import InputValidator
from guardrails.output_validator import OutputValidator
from guardrails.policy_checker import PolicyChecker

# Import our modules
from mock_data.generator import MockDataGenerator
from orchestrator.workflow import AccountingWorkflow

console = Console()


def print_header():
    """Print demo header"""
    console.print(
        Panel.fit(
            "[bold blue]ERPX AI Accounting[/bold blue]\n[dim]End-to-End Demo with Mock Data[/dim]", border_style="blue"
        )
    )
    console.print()


def demo_single_document():
    """Demo: Process a single invoice"""
    console.print("[bold yellow]═══ Demo 1: Single Invoice Processing ═══[/bold yellow]")
    console.print()

    # Generate a mock invoice
    generator = MockDataGenerator(seed=42)
    doc = generator.generate_invoice(doc_id="DEMO-INV-001")

    console.print("[cyan]Generated Invoice:[/cyan]")
    console.print(f"  Doc ID: {doc.doc_id}")
    console.print(f"  Type: {doc.doc_type}")
    console.print(f"  Amount: {doc.structured_data.get('grand_total', 0):,.0f} VND")
    console.print()

    # Show raw content (truncated)
    console.print("[cyan]Raw Content (OCR simulation):[/cyan]")
    console.print(Panel(doc.raw_content[:500] + "...", title="Document Text"))
    console.print()

    # Run through workflow
    console.print("[cyan]Running LangGraph Workflow...[/cyan]")

    workflow = AccountingWorkflow()

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Processing document...", total=1)

        # Use the public run method
        result = workflow.run(ocr_text=doc.raw_content, doc_id=doc.doc_id)

        progress.update(task, completed=1)

    console.print()
    console.print("[green]✓ Workflow completed[/green]")

    if result:
        console.print(f"  Document Type: {result.get('asof_payload', {}).get('doc_type', 'N/A')}")
        console.print(f"  Needs Review: {result.get('needs_human_review', False)}")
        console.print(f"  Warnings: {len(result.get('warnings', []))}")

    console.print()
    return result


def demo_guardrails():
    """Demo: Guardrails validation"""
    console.print("[bold yellow]═══ Demo 2: Guardrails Validation ═══[/bold yellow]")
    console.print()

    input_validator = InputValidator()
    output_validator = OutputValidator()
    policy_checker = PolicyChecker()

    # Test Input Validation
    console.print("[cyan]Input Validation Tests:[/cyan]")

    test_inputs = [
        ("Process invoice HD001", True),
        ("Write me a poem about accounting", False),
        ("'; DROP TABLE users; --", False),
    ]

    table = Table(title="Input Validation Results")
    table.add_column("Input", style="cyan")
    table.add_column("Valid", style="green")
    table.add_column("Reason", style="dim")

    for text, expected_valid in test_inputs:
        result = input_validator.validate_coding_request(ocr_text=text)
        status = "✓" if result.is_valid else "✗"
        reason = "Passed" if result.is_valid else (result.errors[0] if result.errors else "Scope violation")
        table.add_row(text[:40], status, reason)

    console.print(table)
    console.print()

    # Test Policy Checking
    console.print("[cyan]Policy Check Tests (R6 - Approval Gate):[/cyan]")

    test_policies = [
        (5_000_000, "invoice"),
        (15_000_000, "invoice"),
        (150_000_000, "invoice"),
    ]

    table = Table(title="Approval Threshold Results")
    table.add_column("Amount (VND)", style="cyan")
    table.add_column("Needs Approval", style="yellow")
    table.add_column("Approver Level", style="green")

    for amount, doc_type in test_policies:
        # Build mock output dict
        mock_output = {"asof_payload": {"doc_type": doc_type, "chi_tiet": {"grand_total": amount}}}
        result = policy_checker.check_policy(output=mock_output)
        needs_approval = result.requires_review
        approver = str(result.approval_level.value) if needs_approval else "0 (Auto)"
        table.add_row(f"{amount:,.0f}", "Yes" if needs_approval else "No", approver)

    console.print(table)
    console.print()


def demo_batch_processing():
    """Demo: Batch processing multiple documents"""
    console.print("[bold yellow]═══ Demo 3: Batch Processing ═══[/bold yellow]")
    console.print()

    # Generate batch
    console.print("[cyan]Generating 10 mock documents...[/cyan]")
    generator = MockDataGenerator(seed=123)
    documents = generator.generate_batch(count=10)

    # Count by type
    by_type = {}
    for doc in documents:
        by_type[doc.doc_type] = by_type.get(doc.doc_type, 0) + 1

    table = Table(title="Generated Documents")
    table.add_column("Type", style="cyan")
    table.add_column("Count", style="green")

    for doc_type, count in by_type.items():
        table.add_row(doc_type, str(count))

    console.print(table)
    console.print()

    # Process batch
    console.print("[cyan]Processing batch...[/cyan]")

    results = []
    errors = 0
    needs_review = 0

    with Progress(console=console) as progress:
        task = progress.add_task("Processing documents", total=len(documents))

        for doc in documents:
            workflow = AccountingWorkflow()

            try:
                result = workflow.run(ocr_text=doc.raw_content, doc_id=doc.doc_id)

                if result and result.get("needs_human_review"):
                    needs_review += 1

                results.append(result)
            except Exception:
                errors += 1

            progress.update(task, advance=1)

    console.print()
    console.print("[green]✓ Batch processing completed[/green]")
    console.print(f"  Total: {len(documents)}")
    console.print(f"  Successful: {len(documents) - errors}")
    console.print(f"  Errors: {errors}")
    console.print(f"  Needs Review: {needs_review}")
    console.print()


def demo_governance():
    """Demo: Governance features (audit, evidence, approval)"""
    console.print("[bold yellow]═══ Demo 4: Governance Features ═══[/bold yellow]")
    console.print()

    # Audit Store
    console.print("[cyan]Audit Store Demo:[/cyan]")
    audit_store = get_audit_store()

    # Log some events
    audit_store.log(
        event_type=AuditEventType.DOCUMENT_PROCESSED,
        tenant_id="demo-tenant-001",
        entity_type="invoice",
        entity_id="DEMO-INV-001",
        action="process_document",
        user_id="system",
        metadata={"doc_type": "invoice", "amount": 11_000_000},
    )

    audit_store.log(
        event_type=AuditEventType.APPROVAL_REQUESTED,
        tenant_id="demo-tenant-001",
        entity_type="invoice",
        entity_id="DEMO-INV-001",
        action="request_approval",
        user_id="system",
        metadata={"reason": "amount_threshold", "amount": 11_000_000},
    )

    console.print("  ✓ Logged 2 audit events")

    # Get history
    history = audit_store.get_entity_history("invoice", "DEMO-INV-001")
    console.print(f"  ✓ Entity history: {len(history)} events")
    console.print()

    # Approval Inbox
    console.print("[cyan]Approval Inbox Demo:[/cyan]")
    inbox = get_approval_inbox()

    request_id = inbox.create_request(
        doc_id="DEMO-INV-002",
        tenant_id="demo-tenant-001",
        reasons=[ApprovalReason.AMOUNT_THRESHOLD],
        priority=ApprovalPriority.HIGH,
        document_type="invoice",
        amount=150_000_000,
        vendor="Công ty ABC",
        assigned_to="kế toán trưởng",
    )

    console.print(f"  ✓ Created approval request: {request_id}")

    pending = inbox.get_pending()
    console.print(f"  ✓ Pending requests: {len(pending)}")

    # Approve
    inbox.approve(request_id, approved_by="manager@company.com", notes="Approved after review")
    console.print(f"  ✓ Approved request: {request_id}")
    console.print()

    # Evidence Store
    console.print("[cyan]Evidence Store Demo:[/cyan]")
    evidence_store = get_evidence_store()

    from governance.evidence_store import EvidenceType

    eid = evidence_store.store(
        doc_id="DEMO-INV-001",
        tenant_id="demo-tenant-001",
        field_name="grand_total",
        field_value=11_000_000,
        evidence_type=EvidenceType.OCR_SNIPPET,
        source="ocr",
        text_snippet="Tổng cộng: 11,000,000 VND",
        source_location="line 15",
        confidence=0.95,
    )

    console.print(f"  ✓ Stored evidence: {eid[:20]}...")

    # Verify integrity
    is_valid = evidence_store.verify_integrity(eid)
    console.print(f"  ✓ Evidence integrity: {'Valid' if is_valid else 'Invalid'}")
    console.print()


def demo_data_layer():
    """Demo: Data layer mocks"""
    console.print("[bold yellow]═══ Demo 5: Data Layer Mocks ═══[/bold yellow]")
    console.print()

    # PostgreSQL Mock
    console.print("[cyan]PostgreSQL Mock:[/cyan]")
    pg = PostgresMock()

    # Insert transaction

    txn = Transaction(
        id="TXN-DEMO-001",
        tenant_id="demo-tenant-001",
        doc_id="DEMO-INV-001",
        doc_type="invoice",
        posting_date=datetime.now().strftime("%Y-%m-%d"),
        doc_date=datetime.now().strftime("%Y-%m-%d"),
        vendor_id="V001",
        vendor_name="Công ty ABC",
        description="Demo invoice",
        currency="VND",
        amount=11_000_000,
        vat_amount=1_000_000,
        status="posted",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        created_by="system",
    )
    tx_id = pg.insert_transaction(txn)
    console.print(f"  ✓ Inserted transaction: {tx_id[:20]}...")

    # Query
    txns = pg.list_transactions(tenant_id="demo-tenant-001")
    console.print(f"  ✓ Found {len(txns)} invoice(s)")
    console.print()

    # Qdrant Mock
    console.print("[cyan]Qdrant Mock (RAG):[/cyan]")
    qdrant = QdrantMock()
    kb = KnowledgeBase(qdrant)

    # Search VN accounting laws
    results = kb.search_laws(query="thuế GTGT đầu vào", limit=2)
    console.print(f"  ✓ Found {len(results)} relevant law(s)")
    for r in results[:2]:
        text = r.get("content", str(r))[:60]
        console.print(f"    - {text}...")
    console.print()

    # MinIO Mock
    console.print("[cyan]MinIO Mock (Object Storage):[/cyan]")
    minio = MinIOMock()

    # List buckets
    buckets = minio.list_buckets()
    console.print(f"  ✓ Buckets: {', '.join([b['name'] for b in buckets])}")

    # Upload document
    minio.put_object("raw-documents", "demo/DEMO-INV-001.txt", b"Invoice content...")
    console.print("  ✓ Uploaded: raw-documents/demo/DEMO-INV-001.txt")

    # List objects
    objects = minio.list_objects("raw-documents")
    console.print(f"  ✓ Objects in raw-documents: {len(objects)}")
    console.print()


def run_all_demos():
    """Run all demos"""
    print_header()

    try:
        demo_single_document()
        demo_guardrails()
        demo_batch_processing()
        demo_governance()
        demo_data_layer()

        console.print("[bold green]═══ All Demos Completed Successfully! ═══[/bold green]")
        console.print()
        console.print(
            Panel.fit(
                "[bold]DONE — READY FOR REAL DATA INTEGRATION[/bold]\n\n"
                "The ERPX AI Accounting system is fully functional with mock data.\n"
                "To integrate real data:\n"
                "1. Replace mock data layers with real PostgreSQL, Qdrant, MinIO\n"
                "2. Configure LLM API key in .env\n"
                "3. Import real Vietnamese accounting laws into Qdrant\n"
                "4. Connect to ERP via API",
                border_style="green",
                title="🎉 Project Complete",
            )
        )

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(run_all_demos())
