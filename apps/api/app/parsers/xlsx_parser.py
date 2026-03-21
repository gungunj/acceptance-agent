from typing import Any


def parse_xlsx_template(_: bytes) -> dict[str, Any]:
    # Placeholder: implement real XLSX parsing once we add a dependency like openpyxl.
    return {
        "type": "xlsx",
        "note": "xlsx parsing not implemented yet",
    }

