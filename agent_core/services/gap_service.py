from app.services import gap_review_service


def generate_gaps(task_id: str):
    return gap_review_service.generate_gap_items(task_id=task_id)


def list_gaps(task_id: str):
    return gap_review_service.list_gap_items(task_id=task_id)
