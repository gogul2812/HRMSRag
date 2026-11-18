"""
rag_platform_schemas
====================
Shared Pydantic v2 models for the RAG Platform.
Import from this package; never redefine these models inside a service.
"""

from rag_platform_schemas.auth import (
    JWTClaims,
    LoginRequest,
    RegisterRequest,
    Tenant,
    TenantCreate,
    TokenResponse,
    User,
    UserRole,
)
from rag_platform_schemas.chat import (
    ChatMessage,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSession,
    ChatSessionCreate,
    ChatSessionDetail,
    Feedback,
    FeedbackCreate,
)
from rag_platform_schemas.common import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    PaginatedResponse,
)
from rag_platform_schemas.config import (
    GuardrailPolicy,
    GuardrailPolicyCreate,
    PromptConfig,
    PromptConfigCreate,
)
from rag_platform_schemas.documents import (
    DocType,
    Document,
    DocumentStatus,
    DocumentUploadResponse,
    TransientParseResponse,
)
from rag_platform_schemas.orchestration import (
    Citation,
    ContextChunk,
    ExtractRequirementsRequest,
    ExtractRequirementsResponse,
    OrchestrateRequest,
    OrchestrateResponse,
)
from rag_platform_schemas.retrieval import (
    RetrieveRequest,
    RetrieveResponse,
    RetrievedChunk,
)

__all__ = [
    # auth
    "JWTClaims",
    "LoginRequest",
    "RegisterRequest",
    "Tenant",
    "TenantCreate",
    "TokenResponse",
    "User",
    "UserRole",
    # common
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "PaginatedResponse",
    # config
    "GuardrailPolicy",
    "GuardrailPolicyCreate",
    "PromptConfig",
    "PromptConfigCreate",
    # documents
    "DocType",
    "Document",
    "DocumentStatus",
    "DocumentUploadResponse",
    "TransientParseResponse",
    # retrieval
    "RetrieveRequest",
    "RetrieveResponse",
    "RetrievedChunk",
    # orchestration
    "Citation",
    "ContextChunk",
    "ExtractRequirementsRequest",
    "ExtractRequirementsResponse",
    "OrchestrateRequest",
    "OrchestrateResponse",
    # chat
    "ChatMessage",
    "ChatMessageCreate",
    "ChatMessageResponse",
    "ChatSession",
    "ChatSessionCreate",
    "ChatSessionDetail",
    "Feedback",
    "FeedbackCreate",
]
