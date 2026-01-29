import inspect
import sys
import os

# Add project root
sys.path.insert(0, "/root/erp-ai")

try:
    from src.storage import upload_document
    print("Function:", upload_document)
    print("Signature:", inspect.signature(upload_document))
    print("File:", inspect.getfile(upload_document))
except Exception as e:
    print(f"Error importing: {e}")
