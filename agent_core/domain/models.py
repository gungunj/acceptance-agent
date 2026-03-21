"""Canonical model exports for agent_core callers.

This module intentionally aliases existing Pydantic models to keep
incremental migration safe while routes/CLI are switched to agent_core.
"""

from app.services.export_service import ExportDocument
from app.services.fill_review_service import ReviewableFillNodeResult
from app.services.gap_review_service import GapGenerationResponse, GapItem
from app.services.material_service import (
    CreateTaskRequest,
    FillNodeMatch,
    FillNodeMatchResponse,
    FillNodeResolveResponse,
    FieldSpec,
    MaterialUnit,
    ParseTemplateResponse,
    Task,
    TemplateNode,
    UpdateFieldRequest,
    UpdateFileRoleRequest,
    UpdateTemplateNodeRequest,
    UploadedFileRecord,
)
from app.services.resolved_template_service import ResolvedTemplate
from app.services.section_draft_service import SectionDraftGenerationResponse, SectionDraftResult
from app.services.semantic_normalizer_service import SemanticNormalizeResponse
from app.services.semantic_retrieval_service import EmbeddingBuildResponse

__all__ = [
    "CreateTaskRequest",
    "UpdateFileRoleRequest",
    "UpdateFieldRequest",
    "UpdateTemplateNodeRequest",
    "Task",
    "UploadedFileRecord",
    "FieldSpec",
    "MaterialUnit",
    "TemplateNode",
    "ParseTemplateResponse",
    "FillNodeMatch",
    "FillNodeMatchResponse",
    "FillNodeResolveResponse",
    "ReviewableFillNodeResult",
    "SectionDraftResult",
    "SectionDraftGenerationResponse",
    "GapItem",
    "GapGenerationResponse",
    "ResolvedTemplate",
    "ExportDocument",
    "SemanticNormalizeResponse",
    "EmbeddingBuildResponse",
]
