from datetime import datetime, timezone
from typing import Any

from app.repositories import section_draft_repo as app_section_draft_repo
from app.services import section_draft_service


def save_section_drafts(task_id: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    parsed = [section_draft_service.SectionDraftResult.model_validate(item) for item in results]
    return app_section_draft_repo.save_section_draft_results(
        task_id=task_id,
        results=[item.model_dump() for item in parsed],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
