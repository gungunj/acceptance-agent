import struct
from typing import Optional


def parse_png_size(content: bytes) -> Optional[dict[str, int]]:
    if len(content) < 24 or content[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height = struct.unpack(">II", content[16:24])
    return {"width": width, "height": height}


def parse_gif_size(content: bytes) -> Optional[dict[str, int]]:
    if len(content) < 10 or content[:6] not in (b"GIF87a", b"GIF89a"):
        return None
    width, height = struct.unpack("<HH", content[6:10])
    return {"width": width, "height": height}


def parse_jpeg_size(content: bytes) -> Optional[dict[str, int]]:
    if len(content) < 4 or content[:2] != b"\xff\xd8":
        return None

    index = 2
    while index < len(content):
        if content[index] != 0xFF:
            index += 1
            continue

        marker = content[index + 1]
        index += 2

        if marker in (0xD8, 0xD9):
            continue

        if index + 2 > len(content):
            break

        block_length = struct.unpack(">H", content[index : index + 2])[0]

        if marker in (0xC0, 0xC1, 0xC2, 0xC3) and index + 7 <= len(content):
            height, width = struct.unpack(">HH", content[index + 3 : index + 7])
            return {"width": width, "height": height}

        index += block_length

    return None

