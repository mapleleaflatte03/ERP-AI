import asyncio
import os
import sys
import time
import httpx
import uuid

# Configuration
API_URL = "http://localhost:8000"
TEST_FILE_PATH = "/root/erp-ai/samples/sample_invoice.pdf"

async def run_e2e_test():
    if not os.path.exists(TEST_FILE_PATH):
        print(f"Test file not found: {TEST_FILE_PATH}")
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"1. Uploading document: {TEST_FILE_PATH}...")
        files = {"file": open(TEST_FILE_PATH, "rb")}
        data = {"tenant_id": "default"}
        
        resp = await client.post(f"{API_URL}/v1/upload", files=files, data=data)

        if resp.status_code != 200:
            print(f"Upload failed: {resp.text}")
            return
            
        doc_id = resp.json()["job_id"]
        print(f"   Upload successful. Doc ID: {doc_id}")
        
        # 2. Extract
        print("2. Triggering Extraction...")
        resp = await client.post(f"{API_URL}/v1/documents/{doc_id}/extract")
        if resp.status_code != 200:
            print(f"Extraction trigger failed: {resp.text}")
            return
            
        # Poll for extraction completion
        print("   Waiting for extraction...", end="", flush=True)
        for _ in range(20):
            resp = await client.get(f"{API_URL}/v1/documents/{doc_id}")
            status = resp.json()["status"]
            if status == "extracted":
                print(" Done!")
                break
            if status == "failed":
                print(" Failed!")
                return
            print(".", end="", flush=True)
            await asyncio.sleep(1)
        else:
            print(" Timeout!")
            return
            
        # 3. Propose
        print("3. Triggering Proposal...")
        resp = await client.post(f"{API_URL}/v1/documents/{doc_id}/propose")
        if resp.status_code != 200:
            print(f"Proposal trigger failed: {resp.text}")
            return
        
        # Poll for proposal completion
        print("   Waiting for proposal...", end="", flush=True)
        for _ in range(20):
            resp = await client.get(f"{API_URL}/v1/documents/{doc_id}")
            status = resp.json()["status"]
            if status in ["proposed", "pending_approval"]:
                print(" Done!")
                break
            if status == "failed":
                print(" Failed!")
                return
            print(".", end="", flush=True)
            await asyncio.sleep(1)
        else:
            print(" Timeout!")
            return

        # 4. Submit
        print("4. Submitting for Approval...")
        # First get the proposal ID to confirm
        resp = await client.get(f"{API_URL}/v1/documents/{doc_id}/proposal")
        proposal_id = resp.json()["id"]
        
        resp = await client.post(f"{API_URL}/v1/documents/{doc_id}/submit", json={"proposal_id": proposal_id})
        if resp.status_code != 200:
            print(f"Submit failed: {resp.text}")
            return
        
        approval_id = resp.json()["approval_id"]
        print(f"   Submitted. Approval ID: {approval_id}")
        
        # 5. Approve
        print("5. Approving...")
        resp = await client.post(f"{API_URL}/v1/approvals/{approval_id}/approve", json={"approver": "e2e_test", "comment": "Auto verified"})
        if resp.status_code != 200:
            print(f"Approve failed: {resp.text}")
            return
            
        # Verify Posted
        print("6. Verifying Ledger Posting...")
        resp = await client.get(f"{API_URL}/v1/documents/{doc_id}")
        status = resp.json()["status"]
        if status == "posted":
            print("   SUCCESS: Document status is 'posted'")
        else:
            print(f"   WARNING: Document status is '{status}' (expected 'posted' or 'approved')")
            
        resp = await client.get(f"{API_URL}/v1/documents/{doc_id}/ledger")
        if resp.status_code == 200 and resp.json().get("posted"):
            print("   SUCCESS: Ledger entry found.")
            print("E2E VERIFICATION PASSED!")
        else:
            print("   FAILED: No ledger entry found.")

if __name__ == "__main__":
    asyncio.run(run_e2e_test())
