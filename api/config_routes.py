"""
ERPX AI Accounting - Config Routes
==================================
Endpoints:
- GET /config - Get public configuration for UI
- POST /import/server - Import files from server directory (admin only)
- GET /import/server/list - List available server directories
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel

from core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Config"])


# =============================================================================
# Public Config
# =============================================================================

@router.get("/config")
async def get_public_config() -> dict:
    """
    Get public configuration settings for the UI.
    Does not expose sensitive credentials.
    """
    return {
        "success": True,
        "data": {
            "upload": {
                "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
                "max_upload_count": settings.MAX_UPLOAD_COUNT,
                "allowed_extensions": [".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".xls"],
            },
            "features": {
                "server_import_enabled": bool(settings.ALLOWED_SERVER_PATHS),
                "ocr_enabled": True,
                "ai_assistant_enabled": True,
            },
            "version": "1.0.3",
        }
    }


# =============================================================================
# Server Directory Import (Admin Only)
# =============================================================================

class ServerImportRequest(BaseModel):
    directory: str
    file_pattern: str = "*"  # Glob pattern like *.pdf, *.xlsx
    recursive: bool = False


class ServerFile(BaseModel):
    path: str
    filename: str
    size: int
    modified: str


@router.get("/import/server/list")
async def list_server_directories(
    x_role: Optional[str] = Header(None, alias="X-User-Role")
) -> dict:
    """
    List available server directories for import.
    Restricted to admin role.
    """
    # Role check - in production this would use proper auth
    if x_role != "admin" and x_role != "accountant":
        raise HTTPException(status_code=403, detail="Admin or accountant role required")

    allowed_paths = settings.ALLOWED_SERVER_PATHS.split(",")
    directories = []

    for base_path in allowed_paths:
        base_path = base_path.strip()
        if not base_path:
            continue
        
        path = Path(base_path)
        if path.exists() and path.is_dir():
            # List immediate subdirectories
            try:
                subdirs = [
                    {
                        "path": str(d),
                        "name": d.name,
                        "file_count": len(list(d.glob("*.*")))
                    }
                    for d in path.iterdir()
                    if d.is_dir()
                ]
                directories.append({
                    "base_path": str(path),
                    "name": path.name,
                    "subdirectories": subdirs,
                    "file_count": len(list(path.glob("*.*")))
                })
            except PermissionError:
                logger.warning(f"Permission denied for path: {path}")

    return {
        "success": True,
        "data": {
            "allowed_paths": allowed_paths,
            "directories": directories
        }
    }


@router.get("/import/server/files")
async def list_server_files(
    directory: str = Query(..., description="Directory path to list files from"),
    pattern: str = Query("*", description="File pattern (glob): *.pdf, *.xlsx, etc"),
    x_role: Optional[str] = Header(None, alias="X-User-Role")
) -> dict:
    """
    List files in a server directory that can be imported.
    Restricted to admin/accountant role.
    """
    # Role check
    if x_role not in ["admin", "accountant"]:
        raise HTTPException(status_code=403, detail="Admin or accountant role required")

    # Security: validate directory is within allowed paths
    allowed_paths = [p.strip() for p in settings.ALLOWED_SERVER_PATHS.split(",") if p.strip()]
    
    dir_path = Path(directory).resolve()
    is_allowed = any(
        str(dir_path).startswith(str(Path(allowed).resolve()))
        for allowed in allowed_paths
    )
    
    if not is_allowed:
        raise HTTPException(status_code=403, detail="Directory not in allowed paths")

    if not dir_path.exists() or not dir_path.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")

    try:
        files = []
        for file_path in dir_path.glob(pattern):
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "path": str(file_path),
                    "filename": file_path.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "extension": file_path.suffix.lower()
                })
        
        # Sort by filename
        files.sort(key=lambda x: x["filename"])

        return {
            "success": True,
            "data": {
                "directory": str(dir_path),
                "pattern": pattern,
                "files": files,
                "total": len(files)
            }
        }
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied to read directory")


@router.post("/import/server")
async def import_from_server(
    body: ServerImportRequest,
    x_role: Optional[str] = Header(None, alias="X-User-Role"),
    x_tenant_id: Optional[str] = Header("default", alias="X-Tenant-ID")
) -> dict:
    """
    Import files from a server directory into the document processing pipeline.
    Restricted to admin/accountant role.
    
    Files are:
    1. Validated against allowed paths
    2. Copied to MinIO storage
    3. Created as new document jobs
    """
    import uuid
    from datetime import datetime
    from src.storage import upload_document_v2
    from src.db import get_pool as get_db_pool

    # Role check
    if x_role not in ["admin", "accountant"]:
        raise HTTPException(status_code=403, detail="Admin or accountant role required")

    # Validate directory
    allowed_paths = [p.strip() for p in settings.ALLOWED_SERVER_PATHS.split(",") if p.strip()]
    dir_path = Path(body.directory).resolve()
    
    is_allowed = any(
        str(dir_path).startswith(str(Path(allowed).resolve()))
        for allowed in allowed_paths
    )
    
    if not is_allowed:
        raise HTTPException(status_code=403, detail="Directory not in allowed server paths")

    if not dir_path.exists() or not dir_path.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")

    # Collect files
    if body.recursive:
        files = list(dir_path.rglob(body.file_pattern))
    else:
        files = list(dir_path.glob(body.file_pattern))
    
    files = [f for f in files if f.is_file()]

    if not files:
        return {
            "success": True,
            "data": {
                "imported": 0,
                "message": "No files matched the pattern"
            }
        }

    # Check count limit
    if len(files) > settings.MAX_UPLOAD_COUNT:
        raise HTTPException(
            status_code=400, 
            detail=f"Too many files ({len(files)}). Maximum is {settings.MAX_UPLOAD_COUNT}"
        )

    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    imported = []
    errors = []

    for file_path in files:
        try:
            # Determine content type
            ext = file_path.suffix.lower()
            content_type_map = {
                ".pdf": "application/pdf",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".xls": "application/vnd.ms-excel",
            }
            content_type = content_type_map.get(ext, "application/octet-stream")

            # Read file
            with open(file_path, "rb") as f:
                file_data = f.read()

            # Check file size
            if len(file_data) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                errors.append({
                    "file": str(file_path),
                    "error": f"File too large (max {settings.MAX_FILE_SIZE_MB}MB)"
                })
                continue

            # Upload to MinIO
            job_id = str(uuid.uuid4())
            bucket, key, checksum, size = upload_document_v2(
                file_data=file_data,
                filename=file_path.name,
                content_type=content_type,
                tenant_id=x_tenant_id,
                job_id=job_id
            )

            # Create job record
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO jobs (id, tenant_id, filename, content_type, file_size, 
                                     minio_bucket, minio_key, checksum, status, source, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'new', 'server_import', NOW())
                    """,
                    job_id, x_tenant_id, file_path.name, content_type, size,
                    bucket, key, checksum
                )

            imported.append({
                "job_id": job_id,
                "filename": file_path.name,
                "size": size
            })

        except Exception as e:
            logger.error(f"Failed to import {file_path}: {e}")
            errors.append({
                "file": str(file_path),
                "error": str(e)
            })

    return {
        "success": True,
        "data": {
            "imported": len(imported),
            "errors": len(errors),
            "files": imported,
            "error_details": errors if errors else None
        }
    }
