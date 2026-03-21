from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
API_DIR = ROOT_DIR / "apps" / "api"
DATA_DIR = API_DIR / "data"
EXPORTS_DIR = DATA_DIR / "exports"


def data_paths() -> dict[str, Path]:
    return {
        "tasks": DATA_DIR / "tasks",
        "files": DATA_DIR / "files",
        "fields": DATA_DIR / "fields",
        "template_nodes": DATA_DIR / "template_nodes",
        "materials": DATA_DIR / "materials",
        "matches": DATA_DIR / "matches",
        "fill_results": DATA_DIR / "fill_results",
        "section_drafts": DATA_DIR / "section_drafts",
        "gaps": DATA_DIR / "gaps",
        "resolved_templates": DATA_DIR / "resolved_templates",
        "template_semantic": DATA_DIR / "template_semantic",
        "embeddings": DATA_DIR / "embeddings",
        "exports": EXPORTS_DIR,
    }
