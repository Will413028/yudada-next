import io

import pytest
from PIL import Image

from app.uploads import decode_image


@pytest.mark.parametrize(
    "image_format, media_type",
    [
        ("PNG", "image/png"),
        ("JPEG", "image/jpeg"),
        ("WEBP", "image/webp"),
    ],
)
def test_images_are_decoded_and_reencoded_without_trailing_payload(
    image_format: str, media_type: str
) -> None:
    stream = io.BytesIO()
    Image.new("RGB", (8, 9), "red").save(stream, format=image_format)
    result, mime, width, height = decode_image(stream.getvalue() + b"<script>test</script>")
    assert mime == media_type and (width, height) == (8, 9)
    assert b"<script>" not in result
    with Image.open(io.BytesIO(result)) as image:
        image.load()
        assert image.size == (8, 9)


def test_rejects_disguised_svg_truncation_and_oversized_dimensions() -> None:
    stream = io.BytesIO()
    Image.new("RGB", (4097, 1), "red").save(stream, format="PNG")
    for data in (b"<svg></svg>", b"\x89PNG\r\n", stream.getvalue()):
        with pytest.raises(ValueError, match="valid PNG"):
            decode_image(data)
