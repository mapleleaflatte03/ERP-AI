"""
ERPX AI - Authentication & Authorization Module
==============================================
JWT validation with Keycloak OIDC.
"""

import logging
import os

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

logger = logging.getLogger("erpx.auth")

# Config
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "erpx")
KEYCLOAK_AUDIENCE = os.getenv("KEYCLOAK_AUDIENCE", "erpx-api")
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"

# JWKS URL for token verification
JWKS_URL = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"

# Security scheme
security = HTTPBearer(auto_error=False)


class User:
    """Authenticated user context"""

    def __init__(self, token_data: dict):
        self.sub = token_data.get("sub", "")
        self.username = token_data.get("preferred_username", "anonymous")
        self.email = token_data.get("email", "")
        self.name = token_data.get("name", "")
        self.roles = self._extract_roles(token_data)
        self.raw_token = token_data

    def _extract_roles(self, token_data: dict) -> list[str]:
        """Extract roles from token"""
        roles = []
        # Realm roles
        realm_access = token_data.get("realm_access", {})
        roles.extend(realm_access.get("roles", []))
        # Resource roles
        resource_access = token_data.get("resource_access", {})
        for resource, access in resource_access.items():
            roles.extend(access.get("roles", []))
        return list(set(roles))

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_any_role(self, roles: list[str]) -> bool:
        return any(r in self.roles for r in roles)


class AnonymousUser(User):
    """Anonymous user for development/testing"""

    def __init__(self):
        self.sub = "anonymous"
        self.username = "anonymous"
        self.email = "anonymous@local"
        self.name = "Anonymous User"
        self.roles = ["viewer"]
        self.raw_token = {}


# Cache JWKS client
_jwks_client = None


def get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        try:
            _jwks_client = PyJWKClient(JWKS_URL, cache_keys=True)
        except Exception as e:
            logger.warning(f"Failed to create JWKS client: {e}")
    return _jwks_client


async def verify_token(token: str) -> dict:
    """Verify JWT token with Keycloak"""
    try:
        jwks_client = get_jwks_client()
        if jwks_client is None:
            raise ValueError("JWKS client not available")

        # Get signing key
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode and verify
        options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_aud": False,  # Keycloak doesn't always set aud
            "verify_iss": True,
        }

        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}",
            options=options,
        )

        return decoded

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(status_code=401, detail="Token verification failed")


async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user from JWT token"""

    # If auth is disabled, return anonymous user
    if not AUTH_ENABLED:
        return AnonymousUser()

    # Check for Authorization header
    if credentials is None:
        # Check for token in query param (for WebSocket/SSE)
        token = request.query_params.get("token")
        if not token:
            raise HTTPException(
                status_code=401, detail="Missing authorization header", headers={"WWW-Authenticate": "Bearer"}
            )
    else:
        token = credentials.credentials

    # Verify token
    token_data = await verify_token(token)
    return User(token_data)


async def get_optional_user(
    request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User | None:
    """Get current user if authenticated, None otherwise"""
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


def require_roles(allowed_roles: list[str]):
    """Decorator to require specific roles"""

    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if not user.has_any_role(allowed_roles):
            raise HTTPException(status_code=403, detail=f"Insufficient permissions. Required roles: {allowed_roles}")
        return user

    return role_checker


# Common role dependencies
require_admin = require_roles(["admin"])
require_accountant = require_roles(["admin", "accountant"])
require_manager = require_roles(["admin", "manager"])
require_approver = require_roles(["admin", "accountant", "manager"])
