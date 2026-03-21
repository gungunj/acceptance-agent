from app.services import export_service


def export_markdown(task_id: str, rebuild: bool = True):
    return export_service.export_markdown(task_id=task_id, rebuild=rebuild)


def get_markdown_export(task_id: str):
    return export_service.get_markdown_export(task_id=task_id)


def export_html(task_id: str, rebuild: bool = False):
    return export_service.export_html(task_id=task_id, rebuild=rebuild)


def get_html_export(task_id: str):
    return export_service.get_html_export(task_id=task_id)


def export_docx(task_id: str, rebuild: bool = True):
    return export_service.export_word(task_id=task_id, rebuild=rebuild)


def get_docx_export(task_id: str):
    return export_service.get_word_export(task_id=task_id)
