"""사진 전처리: 회전 보정 → RGB → 긴 변 1600px → JPEG. 서버와 일괄 평가가 같은 함수를 쓴다."""
from __future__ import annotations

import io

from PIL import Image, ImageOps

MAX_SIDE = 1600  # 프론트도 같은 크기로 줄여 보낸다. 서버는 한 번 더 지킨다.


def to_jpeg(data: bytes, max_side: int = MAX_SIDE) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=88)
        return buf.getvalue()
