from app.services import material_service


def parse_materials(task_id: str):
    return material_service.parse_materials(task_id=task_id)


def list_material_units(task_id: str):
    return material_service.list_material_units(task_id=task_id)


def upload_files(task_id: str, files):
    return material_service.upload_files_async(task_id=task_id, files=files)


def update_file_role(task_id: str, file_id: str, payload):
    return material_service.update_file_role(task_id=task_id, file_id=file_id, payload=payload)
