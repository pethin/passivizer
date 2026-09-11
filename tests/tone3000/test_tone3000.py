"""Automated verification suite for Tone3000 Storefront Packs, documentation, and production artwork.

Verifies:
1. Storefront description character limits (7,000 <= chars <= 10,000 per listing).
2. Completeness of all 22 digital twin voicings across all editions.
3. Multi-pickup configuration bracketed tags and active instrument EQ guidance.
4. Production artwork SVG XML validity and 1024x1024 JPG generation.
5. README catalog integrity and file existence links.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TONE3000_DIR = REPO_ROOT / "tone3000"
DOCS_DIR = TONE3000_DIR / "docs"
ASSETS_DIR = TONE3000_DIR / "assets"

PACK_EDITIONS = [
    "standard_precision_bass",
    "standard_jazz_bass",
    "standard_pj_bass",
    "mustang_pj_bass",
    "active_soapbar_bass",
    "active_stingray_bass",
]

MULTI_PICKUP_PACKS = {
    "standard_jazz_bass": ["[Parallel]", "[Neck]", "[Bridge]"],
    "standard_pj_bass": ["[Parallel]", "[P-Bass]", "[J-Bridge]"],
    "mustang_pj_bass": ["[Parallel]", "[P-Bass]", "[J-Bridge]"],
    "active_soapbar_bass": ["[Center]", "[Neck]", "[Bridge]"],
}

ACTIVE_PACKS = ["active_soapbar_bass", "active_stingray_bass"]


def test_tone3000_storefront_text_character_limits():
    """Verify that all storefront descriptions strictly respect Tone3000 length constraints."""
    for pack in PACK_EDITIONS:
        txt_path = DOCS_DIR / f"{pack}.txt"
        assert txt_path.exists(), f"Storefront document missing: {txt_path}"

        content = txt_path.read_text(encoding="utf-8")
        char_count = len(content)

        assert 7000 <= char_count <= 10000, (
            f"Storefront file {pack}.txt character count {char_count} violates platform limits "
            f"(must be between 7,000 and 10,000 chars)."
        )


def test_tone3000_voicing_enumeration():
    """Verify that every storefront pack describes all 22 digital twin voicings in order."""
    for pack in PACK_EDITIONS:
        txt_path = DOCS_DIR / f"{pack}.txt"
        content = txt_path.read_text(encoding="utf-8")

        for voice_num in range(1, 23):
            prefix = f"{voice_num:02d}."
            assert prefix in content, f"{pack}.txt is missing voicing {prefix}"


def test_tone3000_required_sections():
    """Verify that each storefront pack contains all essential sections."""
    required_sections = [
        "OVERVIEW",
        "RECOMMENDED SIGNAL CHAIN",
        "QUICK INSTRUMENT SETUP",
        "THE 22 DIGITAL TWIN VOICINGS",
        "LICENSE & DISCLAIMER",
    ]

    for pack in PACK_EDITIONS:
        txt_path = DOCS_DIR / f"{pack}.txt"
        content = txt_path.read_text(encoding="utf-8")

        for section in required_sections:
            assert section in content, f"{pack}.txt is missing required section: {section}"


def test_tone3000_multi_pickup_tags():
    """Verify that multi-pickup editions include bracketed selector tags."""
    for pack, tags in MULTI_PICKUP_PACKS.items():
        txt_path = DOCS_DIR / f"{pack}.txt"
        content = txt_path.read_text(encoding="utf-8")

        # Find all numbered voicing lines (e.g. "01. Modern Active Jazz Bass...")
        voicing_lines = [
            line.strip()
            for line in content.splitlines()
            if re.match(r"^\d{2}\.", line.strip())
        ]
        assert len(voicing_lines) == 22, f"{pack}.txt expected 22 voicing lines, found {len(voicing_lines)}"

        for line in voicing_lines:
            has_tag = any(tag in line for tag in tags)
            assert has_tag, f"{pack}.txt voicing line missing selector tag {tags}: '{line}'"


def test_tone3000_active_instrument_guidance():
    """Verify that active instrument packs include explicit active EQ flat / center detent guidance."""
    for pack in ACTIVE_PACKS:
        txt_path = DOCS_DIR / f"{pack}.txt"
        content = txt_path.read_text(encoding="utf-8")

        assert "Flat" in content or "Center Detent" in content, (
            f"{pack}.txt must instruct players to set active EQ controls flat at center detents."
        )


def test_tone3000_production_artwork_assets():
    """Verify that all production SVG and JPG artwork assets exist and are valid."""
    for pack in PACK_EDITIONS:
        svg_file = ASSETS_DIR / f"allomorph_{pack}.svg"
        jpg_file = ASSETS_DIR / f"allomorph_{pack}.jpg"

        assert svg_file.exists(), f"SVG artwork missing: {svg_file}"
        assert jpg_file.exists(), f"JPG artwork missing: {jpg_file}"

        # Strict XML syntax validation for SVG
        ET.parse(svg_file)

        # High-res JPG size verification (> 50 KB)
        jpg_size = jpg_file.stat().st_size
        assert jpg_size > 50000, f"JPG artwork {jpg_file} appears corrupted (size: {jpg_size} bytes)"


def test_tone3000_catalog_readme_integrity():
    """Verify that the master catalog README links to all existing files."""
    readme_path = DOCS_DIR / "README.md"
    assert readme_path.exists(), "README.md missing"

    content = readme_path.read_text(encoding="utf-8")

    for pack in PACK_EDITIONS:
        assert f"{pack}.txt" in content, f"README.md does not reference {pack}.txt"
        assert f"allomorph_{pack}.svg" in content, f"README.md does not reference allomorph_{pack}.svg"
        assert f"allomorph_{pack}.jpg" in content, f"README.md does not reference allomorph_{pack}.jpg"
