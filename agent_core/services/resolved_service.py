from app.services import resolved_template_service


def build_resolved_template(task_id: str):
    return resolved_template_service.build_resolved_template(task_id=task_id)


def get_resolved_template(task_id: str):
    return resolved_template_service.get_resolved_template(task_id=task_id)
