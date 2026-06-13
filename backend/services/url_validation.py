import os
import re
from urllib.parse import urlparse

from fastapi import HTTPException


BLOCKED_SCHEMES = {"javascript", "data", "vbscript", "file", "ftp"}
CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x1f\x7f]")
CAROUSEL_ELEMENT_TYPES = {"carousel", "carouselCards", "carouselSplit", "circularGallery"}
URL_LIKE_KEYS = {"href", "image", "imageUrl", "logoUrl", "madarLink", "src", "url"}


def env_flag_enabled(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def allow_insecure_http_urls() -> bool:
    return env_flag_enabled("ALLOW_INSECURE_HTTP_URLS")


def reject_url(field_name: str, detail: str) -> None:
    raise HTTPException(status_code=400, detail=f"{field_name} {detail}")


def is_svg_url(parsed_url) -> bool:
    path = (parsed_url.path or "").strip().lower()
    return path.endswith(".svg") or path.endswith(".svgz")


def validate_public_url(
    value,
    *,
    field_name: str = "URL",
    allow_empty: bool = True,
    allow_relative: bool = False,
):
    if value is None:
        if allow_empty:
            return ""

        reject_url(field_name, "is required")

    if not isinstance(value, str):
        reject_url(field_name, "must be a string URL")

    clean_value = value.strip()

    if not clean_value:
        if allow_empty:
            return ""

        reject_url(field_name, "is required")

    if CONTROL_CHARACTER_PATTERN.search(clean_value):
        reject_url(field_name, "contains invalid characters")

    if clean_value.startswith("//"):
        reject_url(field_name, "must not be protocol-relative")

    if clean_value.startswith("/"):
        if not allow_relative:
            reject_url(field_name, "must use https://")

        if "\\" in clean_value:
            reject_url(field_name, "contains invalid characters")

        parsed_relative = urlparse(clean_value)

        if is_svg_url(parsed_relative):
            reject_url(field_name, "must not be an SVG URL")

        return clean_value

    parsed_url = urlparse(clean_value)
    scheme = (parsed_url.scheme or "").lower()

    if not scheme or not parsed_url.netloc:
        reject_url(field_name, "must be an absolute URL or allowed internal path")

    if scheme in BLOCKED_SCHEMES:
        reject_url(field_name, f"must not use the {scheme}: scheme")

    if scheme == "https":
        if is_svg_url(parsed_url):
            reject_url(field_name, "must not be an SVG URL")

        return clean_value

    if scheme == "http" and allow_insecure_http_urls():
        if is_svg_url(parsed_url):
            reject_url(field_name, "must not be an SVG URL")

        return clean_value

    if scheme == "http":
        reject_url(field_name, "must use https://")

    reject_url(field_name, f"must not use the {scheme}: scheme")


def validate_builder_schema_urls(schema: dict, *, field_name: str = "draft_schema") -> dict:
    validate_known_url_values(schema.get("siteChrome"), f"{field_name}.siteChrome")
    walk_builder_schema(schema, field_name)
    return schema


def validate_known_url_values(value, path: str) -> None:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            nested_path = f"{path}.{key}"

            if key in URL_LIKE_KEYS and isinstance(nested_value, str):
                validate_public_url(
                    nested_value,
                    field_name=nested_path,
                    allow_relative=True,
                )
                continue

            validate_known_url_values(nested_value, nested_path)

    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_known_url_values(item, f"{path}[{index}]")


def walk_builder_schema(value, path: str) -> None:
    if isinstance(value, dict):
        validate_builder_element(value, path)

        for key, nested_value in value.items():
            walk_builder_schema(nested_value, f"{path}.{key}")

    elif isinstance(value, list):
        for index, item in enumerate(value):
            walk_builder_schema(item, f"{path}[{index}]")


def validate_builder_element(element: dict, path: str) -> None:
    element_type = element.get("type")

    if element_type == "image":
        validate_public_url(
            element.get("content"),
            field_name=f"{path}.content",
            allow_relative=True,
        )

    if element_type == "embed":
        validate_public_url(
            element.get("content"),
            field_name=f"{path}.content",
            allow_relative=False,
        )

    if element_type in CAROUSEL_ELEMENT_TYPES:
        validate_carousel_slide_urls(
            element.get("content") or "",
            field_name=f"{path}.content",
        )

    action = element.get("action")

    if isinstance(action, dict) and action.get("url"):
        validate_public_url(
            action.get("url"),
            field_name=f"{path}.action.url",
            allow_relative=True,
        )


def validate_carousel_slide_urls(content: str, *, field_name: str) -> None:
    if not content:
        return

    if not isinstance(content, str):
        reject_url(field_name, "must be text")

    blocks = [block.strip() for block in content.split("\n\n") if block.strip()]

    for index, block in enumerate(blocks):
        lines = [line.strip() for line in block.splitlines()]
        image_url = lines[2] if len(lines) >= 3 else ""

        if image_url:
            validate_public_url(
                image_url,
                field_name=f"{field_name}.slide[{index}].image",
                allow_relative=True,
            )
