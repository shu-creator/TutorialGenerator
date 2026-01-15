"""Theme schema definitions."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

# Regex for hex color validation (#RRGGBB format)
HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Default theme values - single source of truth
DEFAULT_PRIMARY_COLOR = "#667eea"
DEFAULT_SHOW_LOGO = True
DEFAULT_SHOW_FOOTER = True
MAX_FOOTER_LENGTH = 100
MAX_LOGO_SIZE_BYTES = 1 * 1024 * 1024  # 1MB
ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ALLOWED_LOGO_CONTENT_TYPES = {"image/png", "image/jpeg"}


class Theme(BaseModel):
    """Theme configuration for PPTX generation.

    Attributes:
        primary_color: Hex color code for titles and headings (#RRGGBB format)
        footer_text: Optional text to display at the bottom of each slide
        logo_uri: Optional internal storage URI for logo image
        show_logo: Whether to display logo on slides (default: True)
        show_footer: Whether to display footer on slides (default: True)
    """

    primary_color: str = Field(
        default=DEFAULT_PRIMARY_COLOR,
        description="Hex color code (#RRGGBB) for titles and headings",
    )
    footer_text: str | None = Field(
        default=None,
        max_length=MAX_FOOTER_LENGTH,
        description=f"Footer text to display on each slide (max {MAX_FOOTER_LENGTH} chars)",
    )
    logo_uri: str | None = Field(
        default=None,
        description="Internal storage URI for logo image",
    )
    show_logo: bool = Field(
        default=DEFAULT_SHOW_LOGO,
        description="Whether to display logo on slides",
    )
    show_footer: bool = Field(
        default=DEFAULT_SHOW_FOOTER,
        description="Whether to display footer on slides",
    )

    @field_validator("primary_color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        """Validate hex color format."""
        if not HEX_COLOR_PATTERN.match(v):
            raise ValueError(f"Invalid color format: {v}. Must be #RRGGBB format (e.g., #667eea)")
        return v.upper()  # Normalize to uppercase

    @field_validator("footer_text")
    @classmethod
    def validate_footer_text(cls, v: str | None) -> str | None:
        """Validate and sanitize footer text."""
        if v is not None:
            # Strip whitespace and check length
            v = v.strip()
            if len(v) == 0:
                return None
            if len(v) > MAX_FOOTER_LENGTH:
                raise ValueError(
                    f"Footer text too long ({len(v)} chars). Maximum: {MAX_FOOTER_LENGTH}"
                )
        return v


class ThemeUpdate(BaseModel):
    """Request body for updating theme settings (without logo_uri)."""

    primary_color: str | None = Field(
        default=None,
        description="Hex color code (#RRGGBB) for titles and headings",
    )
    footer_text: str | None = Field(
        default=None,
        max_length=MAX_FOOTER_LENGTH,
        description="Footer text to display on each slide",
    )
    show_logo: bool | None = Field(
        default=None,
        description="Whether to display logo on slides",
    )
    show_footer: bool | None = Field(
        default=None,
        description="Whether to display footer on slides",
    )

    @field_validator("primary_color")
    @classmethod
    def validate_hex_color(cls, v: str | None) -> str | None:
        """Validate hex color format."""
        if v is not None and not HEX_COLOR_PATTERN.match(v):
            raise ValueError(f"Invalid color format: {v}. Must be #RRGGBB format (e.g., #667eea)")
        return v.upper() if v else None


def get_default_theme() -> Theme:
    """Get the default theme configuration."""
    return Theme()


def merge_theme_with_defaults(theme_json: dict | None) -> Theme:
    """Merge stored theme JSON with defaults.

    Args:
        theme_json: Stored theme configuration (may be None or partial)

    Returns:
        Complete Theme object with defaults applied
    """
    if theme_json is None:
        return get_default_theme()

    # Create theme from stored data, Pydantic will apply defaults
    return Theme(**theme_json)
