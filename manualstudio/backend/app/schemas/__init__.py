"""Schema definitions."""

from .theme import (
    ALLOWED_LOGO_CONTENT_TYPES,
    ALLOWED_LOGO_EXTENSIONS,
    DEFAULT_PRIMARY_COLOR,
    MAX_FOOTER_LENGTH,
    MAX_LOGO_SIZE_BYTES,
    Theme,
    ThemeUpdate,
    get_default_theme,
    merge_theme_with_defaults,
)

__all__ = [
    "Theme",
    "ThemeUpdate",
    "get_default_theme",
    "merge_theme_with_defaults",
    "DEFAULT_PRIMARY_COLOR",
    "MAX_FOOTER_LENGTH",
    "MAX_LOGO_SIZE_BYTES",
    "ALLOWED_LOGO_EXTENSIONS",
    "ALLOWED_LOGO_CONTENT_TYPES",
]
