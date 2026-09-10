"""Generate production-ready vector SVG and 1024x1024 JPG artwork for Allomorph Tone3000 Tone Packs.

Features:
- Pure dark-mode hardware aesthetic with precision CAD engineering grid
- Authentic 4-string bass pickup geometry (2 Alnico V poles per string)
- Flush P-split bobbins with ZERO vertical gap (bottom of upper half aligns flush with top of lower half)
- Spacious vertical separation between P/J (72px) and J/J (159px) pickups
- Generous side margins (all text stays safely inside >= 130px from borders)
- Multi-line word-wrapped descriptions and stacked datum callouts for pristine typography
- High-resolution SVG and converted JPG assets for Tone3000 storefront
"""

from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def make_pole(x: float, y: float, r: float = 13.0) -> str:
    """Generate an anatomically accurate cylindrical Alnico V pole piece with metallic shading."""
    return f"""
    <!-- Pole piece at {x:.1f}, {y:.1f} -->
    <g transform="translate({x:.1f}, {y:.1f})">
      <circle cx="0" cy="0" r="{r+2.5:.1f}" fill="#080a0f" opacity="0.85"/>
      <circle cx="0" cy="0" r="{r:.1f}" fill="url(#poleGrad)"/>
      <circle cx="0" cy="0" r="{r-1.5:.1f}" fill="none" stroke="#f8fafc" stroke-width="0.85" opacity="0.75"/>
      <ellipse cx="-3" cy="-3" rx="{r*0.4:.1f}" ry="{r*0.25:.1f}" fill="#ffffff" opacity="0.65" transform="rotate(-30, -3, -3)"/>
      <circle cx="0" cy="0" r="{r*0.5:.1f}" fill="none" stroke="#64748b" stroke-width="0.5" opacity="0.5"/>
    </g>
    """


def make_pbass_half(
    cx: float,
    cy: float,
    x_strings: tuple[float, float],
    accent: str,
    label: str = "",
) -> str:
    """Generate a bold Precision Bass split bobbin with mounting ears and exactly 4 poles (2 per string)."""
    w, h, rx = 270.0, 114.0, 16.0
    x = cx - w / 2
    y = cy - h / 2

    ear_w, ear_h = 22.0, 34.0
    left_ear_x = x - ear_w + 5
    right_ear_x = x + w - 5

    s1, s2 = x_strings
    pole_offset = 18.0

    return f"""
    <!-- P-Bass Bobbin Half at {cx:.1f}, {cy:.1f} ({label}) -->
    <g filter="url(#dropShadow)">
      <!-- Left Mounting Tab -->
      <path d="M {x+12:.1f} {cy-17:.1f} L {left_ear_x+8:.1f} {cy-17:.1f} A 12 12 0 0 0 {left_ear_x+8:.1f} {cy+17:.1f} L {x+12:.1f} {cy+17:.1f} Z" fill="url(#coverGrad)" stroke="#222938" stroke-width="1.8"/>
      <circle cx="{left_ear_x+9:.1f}" cy="{cy:.1f}" r="4.5" fill="#080a0f" stroke="#475569" stroke-width="1"/>
      <circle cx="{left_ear_x+9:.1f}" cy="{cy:.1f}" r="2" fill="#1e293b"/>

      <!-- Right Mounting Tab -->
      <path d="M {x+w-12:.1f} {cy-17:.1f} L {right_ear_x+ear_w-8:.1f} {cy-17:.1f} A 12 12 0 0 1 {right_ear_x+ear_w-8:.1f} {cy+17:.1f} L {x+w-12:.1f} {cy+17:.1f} Z" fill="url(#coverGrad)" stroke="#222938" stroke-width="1.8"/>
      <circle cx="{right_ear_x+ear_w-9:.1f}" cy="{cy:.1f}" r="4.5" fill="#080a0f" stroke="#475569" stroke-width="1"/>
      <circle cx="{right_ear_x+ear_w-9:.1f}" cy="{cy:.1f}" r="2" fill="#1e293b"/>

      <!-- Main Bobbin Casing -->
      <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx:.1f}" fill="url(#coverGrad)" stroke="#334155" stroke-width="1.8"/>
      <rect x="{x+3:.1f}" y="{y+3:.1f}" width="{w-6:.1f}" height="{h-6:.1f}" rx="{rx-2:.1f}" fill="none" stroke="#64748b" stroke-width="0.75" opacity="0.4"/>
      <rect x="{x+8:.1f}" y="{y+8:.1f}" width="{w-16:.1f}" height="{h-16:.1f}" rx="{rx-6:.1f}" fill="#0f131a" stroke="#1c2330" stroke-width="1.2"/>

      <!-- Internal Coil Indicator -->
      <rect x="{x+16:.1f}" y="{y+16:.1f}" width="{w-32:.1f}" height="{h-32:.1f}" rx="8" fill="none" stroke="{accent}" stroke-width="0.75" stroke-opacity="0.35" stroke-dasharray="5 5"/>
      
      <!-- 4 Poles (2 pairs straddling each string) -->
      {make_pole(s1 - pole_offset, cy)}
      {make_pole(s1 + pole_offset, cy)}
      {make_pole(s2 - pole_offset, cy)}
      {make_pole(s2 + pole_offset, cy)}
    </g>
    """


def make_jbass_pickup(
    cx: float,
    cy: float,
    x_strings: list[float],
    accent: str,
    w: float = 530.0,
    h: float = 76.0,
    label: str = "",
) -> str:
    """Generate a Jazz Bass single-coil pickup with mounting tabs and exactly 8 poles (4 pairs of 2)."""
    rx = 12.0
    x = cx - w / 2
    y = cy - h / 2
    pole_offset = 16.0

    return f"""
    <!-- Jazz Bass Bobbin at {cx:.1f}, {cy:.1f} ({label}) -->
    <g filter="url(#dropShadow)">
      <!-- Left Mounting Tab Pair -->
      <path d="M {cx - 160:.1f} {y:.1f} L {cx - 160:.1f} {y - 14:.1f} A 7 7 0 0 1 {cx - 140:.1f} {y - 14:.1f} L {cx - 140:.1f} {y:.1f} Z" fill="url(#coverGrad)" stroke="#222938" stroke-width="1.5"/>
      <circle cx="{cx - 150:.1f}" cy="{y - 7:.1f}" r="3" fill="#080a0f" stroke="#475569" stroke-width="0.8"/>
      
      <path d="M {cx - 160:.1f} {y + h:.1f} L {cx - 160:.1f} {y + h + 14:.1f} A 7 7 0 0 0 {cx - 140:.1f} {y + h + 14:.1f} L {cx - 140:.1f} {y + h:.1f} Z" fill="url(#coverGrad)" stroke="#222938" stroke-width="1.5"/>
      <circle cx="{cx - 150:.1f}" cy="{y + h + 7:.1f}" r="3" fill="#080a0f" stroke="#475569" stroke-width="0.8"/>

      <!-- Right Mounting Tab Pair -->
      <path d="M {cx + 140:.1f} {y:.1f} L {cx + 140:.1f} {y - 14:.1f} A 7 7 0 0 1 {cx + 160:.1f} {y - 14:.1f} L {cx + 160:.1f} {y:.1f} Z" fill="url(#coverGrad)" stroke="#222938" stroke-width="1.5"/>
      <circle cx="{cx + 150:.1f}" cy="{y - 7:.1f}" r="3" fill="#080a0f" stroke="#475569" stroke-width="0.8"/>
      
      <path d="M {cx + 140:.1f} {y + h:.1f} L {cx + 140:.1f} {y + h + 14:.1f} A 7 7 0 0 0 {cx + 160:.1f} {y + h + 14:.1f} L {cx + 160:.1f} {y + h:.1f} Z" fill="url(#coverGrad)" stroke="#222938" stroke-width="1.5"/>
      <circle cx="{cx + 150:.1f}" cy="{y + h + 7:.1f}" r="3" fill="#080a0f" stroke="#475569" stroke-width="0.8"/>

      <!-- Main Bobbin Casing -->
      <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx:.1f}" fill="url(#coverGrad)" stroke="#334155" stroke-width="1.8"/>
      <rect x="{x+3:.1f}" y="{y+3:.1f}" width="{w-6:.1f}" height="{h-6:.1f}" rx="{rx-2:.1f}" fill="none" stroke="#64748b" stroke-width="0.75" opacity="0.4"/>
      <rect x="{x+6:.1f}" y="{y+6:.1f}" width="{w-12:.1f}" height="{h-12:.1f}" rx="{rx-4:.1f}" fill="#0f131a" stroke="#1c2330" stroke-width="1.2"/>

      <!-- Internal Coil Indicator -->
      <rect x="{x+14:.1f}" y="{y+14:.1f}" width="{w-28:.1f}" height="{h-28:.1f}" rx="6" fill="none" stroke="{accent}" stroke-width="0.75" stroke-opacity="0.35" stroke-dasharray="6 6"/>

      <!-- 8 Poles (4 pairs of 2 straddling E, A, D, G) -->
      {make_pole(x_strings[0] - pole_offset, cy)}
      {make_pole(x_strings[0] + pole_offset, cy)}
      {make_pole(x_strings[1] - pole_offset, cy)}
      {make_pole(x_strings[1] + pole_offset, cy)}
      {make_pole(x_strings[2] - pole_offset, cy)}
      {make_pole(x_strings[2] + pole_offset, cy)}
      {make_pole(x_strings[3] - pole_offset, cy)}
      {make_pole(x_strings[3] + pole_offset, cy)}
    </g>
    """


def generate_pack_svg(model_key: str) -> str:
    """Generate pristine standalone SVG for a Tone3000 Tone Pack edition."""
    strings = [420.0, 540.0, 660.0, 780.0]  # E, A, D, G string axes

    configs = {
        "precision": {
            "accent": "#f59e0b",
            "title": "STANDARD PRECISION BASS",
            "desc_line1": "Calibrated for 34&quot; Standard Fender Precision Bass",
            "desc_line2": "Alnico V Split-Coil Bobbins • 11.2 kΩ DC Resistance • 5.8 H Inductance",
            "scale": "34&quot; SCALE",
            "badge2": "ALNICO V SPLIT-P",
            "badge3": "11.2 kΩ DUAL-COIL",
            "content": lambda acc: f"""
                <!-- Background Flux Lines -->
                <g fill="none" stroke="{acc}" stroke-opacity="0.14" stroke-width="1.2">
                  <ellipse cx="480" cy="480" rx="160" ry="90"/>
                  <ellipse cx="480" cy="480" rx="230" ry="135" stroke-dasharray="8 6"/>
                  <ellipse cx="720" cy="594" rx="160" ry="90"/>
                  <ellipse cx="720" cy="594" rx="230" ry="135" stroke-dasharray="8 6"/>
                </g>
                <!-- RLC Inductance Curve -->
                <path d="M 160 760 Q 320 755 480 730 T 660 610 T 780 735 T 1040 805" fill="none" stroke="{acc}" stroke-opacity="0.22" stroke-width="2.5" stroke-dasharray="6 6"/>
                <!-- P-Bass Split Coils (EA at 480, DG at 594: Exactly 0.0px vertical gap, flush alignment) -->
                {make_pbass_half(480, 480, (strings[0], strings[1]), acc, "BASS E/A")}
                {make_pbass_half(720, 594, (strings[2], strings[3]), acc, "TREBLE D/G")}
                <!-- Datum labels (Word-wrapped and safely placed within margins >= 130px) -->
                <g font-family="system-ui, -apple-system, sans-serif" fill="#cbd5e1" font-weight="800" letter-spacing="1">
                  <!-- Left Datum -->
                  <text x="130" y="472" font-size="14">SPLIT-P COIL</text>
                  <text x="130" y="492" font-size="12" fill="#94a3b8" font-weight="600">125mm BRIDGE DATUM</text>
                  <line x1="130" y1="502" x2="330" y2="502" stroke="#334155" stroke-dasharray="3 3" stroke-width="1"/>

                  <!-- Right Datum -->
                  <text x="1070" y="586" text-anchor="end" font-size="14">DUAL-DATUM SPLIT</text>
                  <text x="1070" y="606" text-anchor="end" font-size="12" fill="#94a3b8" font-weight="600">REVERSE-COIL OFFSET</text>
                  <line x1="870" y1="616" x2="1070" y2="616" stroke="#334155" stroke-dasharray="3 3" stroke-width="1"/>
                </g>
            """,
        },
        "jazz": {
            "accent": "#0ea5e9",
            "title": "STANDARD JAZZ BASS",
            "desc_line1": "Calibrated for 34&quot; Standard Fender Jazz Bass (60s Spacing)",
            "desc_line2": "Dual Alnico V Single Coils • 8-Pole Staggered Apertures • 250kΩ Vol/Tone",
            "scale": "34&quot; SCALE",
            "badge2": "ALNICO V DUAL-J",
            "badge3": "60s PICKUP SPACING",
            "content": lambda acc: f"""
                <!-- Background Flux Lines -->
                <g fill="none" stroke="{acc}" stroke-opacity="0.14" stroke-width="1.2">
                  <ellipse cx="600" cy="430" rx="300" ry="85"/>
                  <ellipse cx="600" cy="430" rx="380" ry="120" stroke-dasharray="8 6"/>
                  <ellipse cx="600" cy="665" rx="300" ry="85"/>
                  <ellipse cx="600" cy="665" rx="380" ry="120" stroke-dasharray="8 6"/>
                </g>
                <!-- RLC Inductance Curve -->
                <path d="M 160 760 Q 340 755 500 710 T 680 580 T 800 720 T 1040 805" fill="none" stroke="{acc}" stroke-opacity="0.22" stroke-width="2.5" stroke-dasharray="6 6"/>
                <!-- Neck and Bridge J Pickups (Vertical clearance = 159px) -->
                {make_jbass_pickup(600, 430, strings, acc, w=510, h=76, label="NECK PICKUP")}
                {make_jbass_pickup(600, 665, strings, acc, w=530, h=76, label="BRIDGE PICKUP")}
                <!-- Datum labels (Word-wrapped and safely placed within margins >= 130px) -->
                <g font-family="system-ui, -apple-system, sans-serif" fill="#cbd5e1" font-weight="800" letter-spacing="1">
                  <!-- Left Datums -->
                  <text x="130" y="422" font-size="14">NECK COIL</text>
                  <text x="130" y="442" font-size="12" fill="#94a3b8" font-weight="600">155.6mm DATUM</text>
                  
                  <text x="130" y="657" font-size="14">BRIDGE COIL</text>
                  <text x="130" y="677" font-size="12" fill="#94a3b8" font-weight="600">63.5mm DATUM</text>

                  <!-- Right Datum -->
                  <text x="1070" y="540" text-anchor="end" font-size="14">PARALLEL SUMMATION</text>
                  <text x="1070" y="560" text-anchor="end" font-size="12" fill="#94a3b8" font-weight="600">HUM-CANCELLATION COMB</text>
                </g>
            """,
        },
        "pj": {
            "accent": "#a855f7",
            "title": "STANDARD P/J BASS",
            "desc_line1": "Calibrated for 34&quot; Standard Fender P/J Bass",
            "desc_line2": "Split-P Neck &amp; J-Bridge Dual Topology • True Differential Deconvolution",
            "scale": "34&quot; SCALE",
            "badge2": "P/J HYBRID COILS",
            "badge3": "ACTIVE/PASSIVE HARNESS",
            "content": lambda acc: f"""
                <!-- Background Flux Lines -->
                <g fill="none" stroke="{acc}" stroke-opacity="0.14" stroke-width="1.2">
                  <ellipse cx="480" cy="410" rx="150" ry="75"/>
                  <ellipse cx="720" cy="524" rx="150" ry="75"/>
                  <ellipse cx="600" cy="690" rx="280" ry="75"/>
                  <ellipse cx="600" cy="690" rx="360" ry="110" stroke-dasharray="8 6"/>
                </g>
                <!-- RLC Inductance Curve -->
                <path d="M 160 760 Q 320 755 480 720 T 640 590 T 780 710 T 1040 805" fill="none" stroke="{acc}" stroke-opacity="0.22" stroke-width="2.5" stroke-dasharray="6 6"/>
                <!-- Split-P at Neck (EA at 410, DG at 524: Exactly 0.0px vertical gap, flush alignment) -->
                {make_pbass_half(480, 410, (strings[0], strings[1]), acc, "P-BASS EA")}
                {make_pbass_half(720, 524, (strings[2], strings[3]), acc, "P-BASS DG")}
                <!-- Jazz Pickup at Bridge (y=690: 72px vertical clearance below DG) -->
                {make_jbass_pickup(600, 690, strings, acc, w=530, h=74, label="J-BRIDGE")}
                <!-- Datum labels (Word-wrapped and safely placed within margins >= 130px) -->
                <g font-family="system-ui, -apple-system, sans-serif" fill="#cbd5e1" font-weight="800" letter-spacing="1">
                  <!-- Left Datums -->
                  <text x="130" y="402" font-size="14">SPLIT-P COIL</text>
                  <text x="130" y="422" font-size="12" fill="#94a3b8" font-weight="600">125mm DATUM</text>

                  <text x="130" y="682" font-size="14">J-BRIDGE COIL</text>
                  <text x="130" y="702" font-size="12" fill="#94a3b8" font-weight="600">63.5mm DATUM</text>

                  <!-- Right Datum -->
                  <text x="1070" y="540" text-anchor="end" font-size="14">BLEND MATRIX</text>
                  <text x="1070" y="560" text-anchor="end" font-size="12" fill="#94a3b8" font-weight="600">DUAL-TOPOLOGY SUM</text>
                </g>
            """,
        },
        "mustang": {
            "accent": "#f43f5e",
            "title": "MUSTANG P/J BASS",
            "desc_line1": "Calibrated for 30&quot; Short-Scale Fender Mustang P/J Bass",
            "desc_line2": "Compact P/J Hybrid Routing • Low-Tension Attack &amp; Fast Transient Bloom",
            "scale": "30&quot; SHORT SCALE",
            "badge2": "MUSTANG P/J HYBRID",
            "badge3": "FAST TRANSIENT DYNAMICS",
            "content": lambda acc: f"""
                <!-- Racing Stripes Aesthetic (Mustang Heritage) -->
                <g opacity="0.12">
                  <line x1="880" y1="60" x2="880" y2="1140" stroke="{acc}" stroke-width="28"/>
                  <line x1="915" y1="60" x2="915" y2="1140" stroke="{acc}" stroke-width="12"/>
                </g>
                <!-- Background Flux Lines -->
                <g fill="none" stroke="{acc}" stroke-opacity="0.14" stroke-width="1.2">
                  <ellipse cx="480" cy="410" rx="150" ry="75"/>
                  <ellipse cx="720" cy="524" rx="150" ry="75"/>
                  <ellipse cx="600" cy="690" rx="280" ry="75"/>
                  <ellipse cx="600" cy="690" rx="360" ry="110" stroke-dasharray="8 6"/>
                </g>
                <!-- RLC Inductance Curve -->
                <path d="M 160 760 Q 300 755 450 710 T 620 570 T 760 705 T 1040 805" fill="none" stroke="{acc}" stroke-opacity="0.22" stroke-width="2.5" stroke-dasharray="6 6"/>
                <!-- Split-P at Neck (EA at 410, DG at 524: Exactly 0.0px vertical gap, flush alignment) -->
                {make_pbass_half(480, 410, (strings[0], strings[1]), acc, "MUSTANG P-EA")}
                {make_pbass_half(720, 524, (strings[2], strings[3]), acc, "MUSTANG P-DG")}
                <!-- Jazz Pickup at Bridge (y=690: 72px vertical clearance below DG) -->
                {make_jbass_pickup(600, 690, strings, acc, w=530, h=74, label="MUSTANG J-BRIDGE")}
                <!-- Datum labels (Word-wrapped and safely placed within margins >= 130px) -->
                <g font-family="system-ui, -apple-system, sans-serif" fill="#cbd5e1" font-weight="800" letter-spacing="1">
                  <!-- Left Datums -->
                  <text x="130" y="402" font-size="14">30&quot; MUSTANG P</text>
                  <text x="130" y="422" font-size="12" fill="#94a3b8" font-weight="600">110mm DATUM</text>

                  <text x="130" y="682" font-size="14">J-BRIDGE COIL</text>
                  <text x="130" y="702" font-size="12" fill="#94a3b8" font-weight="600">56mm DATUM</text>

                  <!-- Right Datum -->
                  <text x="1070" y="540" text-anchor="end" font-size="14">30&quot; SHORT SCALE</text>
                  <text x="1070" y="560" text-anchor="end" font-size="12" fill="#94a3b8" font-weight="600">LOW-TENSION BLOOM</text>
                </g>
            """,
        },
    }

    cfg = configs[model_key]
    acc = cfg["accent"]

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1200" width="1200" height="1200">
  <defs>
    <!-- Background Radial Gradient -->
    <radialGradient id="bgGrad" cx="50%" cy="45%" r="70%">
      <stop offset="0%" stop-color="#151922"/>
      <stop offset="45%" stop-color="#0e1117"/>
      <stop offset="100%" stop-color="#07080a"/>
    </radialGradient>

    <!-- Outer Bezel Linear -->
    <linearGradient id="bezelGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2a3342"/>
      <stop offset="30%" stop-color="#181f2a"/>
      <stop offset="70%" stop-color="#0f141c"/>
      <stop offset="100%" stop-color="#222a36"/>
    </linearGradient>

    <!-- Pickup Cover Gradient -->
    <linearGradient id="coverGrad" x1="20%" y1="0%" x2="80%" y2="100%">
      <stop offset="0%" stop-color="#242c3b"/>
      <stop offset="50%" stop-color="#181d26"/>
      <stop offset="100%" stop-color="#101319"/>
    </linearGradient>

    <!-- Metallic Pole Gradient -->
    <radialGradient id="poleGrad" cx="35%" cy="35%" r="70%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="25%" stop-color="#e2e8f0"/>
      <stop offset="60%" stop-color="#64748b"/>
      <stop offset="100%" stop-color="#334155"/>
    </radialGradient>

    <!-- Steel String Linear -->
    <linearGradient id="stringGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#475569" stop-opacity="0.4"/>
      <stop offset="40%" stop-color="#f8fafc" stop-opacity="0.9"/>
      <stop offset="70%" stop-color="#94a3b8" stop-opacity="0.7"/>
      <stop offset="100%" stop-color="#334155" stop-opacity="0.4"/>
    </linearGradient>

    <!-- Drop Shadow Filter -->
    <filter id="dropShadow" x="-25%" y="-25%" width="150%" height="150%">
      <feDropShadow dx="0" dy="18" stdDeviation="16" flood-color="#000000" flood-opacity="0.85"/>
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.5"/>
    </filter>
  </defs>

  <!-- Canvas Background -->
  <rect width="1200" height="1200" fill="url(#bgGrad)"/>

  <!-- Outer Precision Enclosure Bezel -->
  <rect x="24" y="24" width="1152" height="1152" rx="28" fill="none" stroke="url(#bezelGrad)" stroke-width="4"/>
  <rect x="36" y="36" width="1128" height="1128" rx="20" fill="none" stroke="#ffffff" stroke-opacity="0.04" stroke-width="1"/>

  <!-- Technical Coordinate Grid -->
  <g stroke="#ffffff" stroke-opacity="0.025" stroke-width="1">
    <line x1="120" y1="60" x2="120" y2="1140"/>
    <line x1="240" y1="60" x2="240" y2="1140"/>
    <line x1="360" y1="60" x2="360" y2="1140"/>
    <line x1="480" y1="60" x2="480" y2="1140"/>
    <line x1="600" y1="60" x2="600" y2="1140" stroke-opacity="0.06"/>
    <line x1="720" y1="60" x2="720" y2="1140"/>
    <line x1="840" y1="60" x2="840" y2="1140"/>
    <line x1="960" y1="60" x2="960" y2="1140"/>
    <line x1="1080" y1="60" x2="1080" y2="1140"/>

    <line x1="60" y1="180" x2="1140" y2="180"/>
    <line x1="60" y1="300" x2="1140" y2="300"/>
    <line x1="60" y1="420" x2="1140" y2="420"/>
    <line x1="60" y1="540" x2="1140" y2="540"/>
    <line x1="60" y1="660" x2="1140" y2="660"/>
    <line x1="60" y1="780" x2="1140" y2="780"/>
    <line x1="60" y1="900" x2="1140" y2="900"/>
    <line x1="60" y1="1020" x2="1140" y2="1020"/>
  </g>

  <!-- Precision Corner Registration Crosshairs -->
  <g stroke="{acc}" stroke-width="1.5" stroke-opacity="0.6">
    <line x1="60" y1="75" x2="90" y2="75"/><line x1="75" y1="60" x2="75" y2="90"/><circle cx="75" cy="75" r="5" fill="none"/>
    <line x1="1110" y1="75" x2="1140" y2="75"/><line x1="1125" y1="60" x2="1125" y2="90"/><circle cx="1125" cy="75" r="5" fill="none"/>
    <line x1="60" y1="1125" x2="90" y2="1125"/><line x1="75" y1="1110" x2="75" y2="1140"/><circle cx="75" cy="1125" r="5" fill="none"/>
    <line x1="1110" y1="1125" x2="1140" y2="1125"/><line x1="1125" y1="1110" x2="1125" y2="1140"/><circle cx="1125" cy="1125" r="5" fill="none"/>
  </g>

  <!-- Top Metadata Bar (Safely within margins at 130px and 1070px) -->
  <text x="130" y="80" fill="#94a3b8" font-size="15" font-family="system-ui, -apple-system, sans-serif" font-weight="700" letter-spacing="3">// ALLOMORPH ANALOG TWIN PIPELINE</text>
  <text x="1070" y="80" fill="#94a3b8" font-size="15" font-family="system-ui, -apple-system, sans-serif" font-weight="700" letter-spacing="3" text-anchor="end">TONE3000 EDITION // BLOCK 1 PREAMP</text>

  <!-- Primary Branding Header -->
  <g transform="translate(600, 175)">
    <text x="0" y="0" fill="#ffffff" font-size="70" font-family="system-ui, -apple-system, sans-serif" font-weight="900" letter-spacing="14" text-anchor="middle">ALLOMORPH</text>
    <text x="0" y="40" fill="#94a3b8" font-size="18" font-family="system-ui, -apple-system, sans-serif" font-weight="700" letter-spacing="6" text-anchor="middle">ANALOG PICKUP DIGITAL TWIN ARCHITECTURE</text>
  </g>

  <!-- Header Technical Divider -->
  <line x1="180" y1="245" x2="1020" y2="245" stroke="#334155" stroke-width="1"/>
  <line x1="520" y1="245" x2="680" y2="245" stroke="{acc}" stroke-width="2.5"/>

  <!-- Center Hardware Visual &amp; Specs -->
  {cfg["content"](acc)}

  <!-- Physical Bass Strings (Vertical Over Pickups) -->
  <g>
    <!-- E String (Heavy Gauge ~4.8px) -->
    <line x1="{strings[0]:.1f}" y1="295" x2="{strings[0]:.1f}" y2="820" stroke="url(#stringGrad)" stroke-width="4.8"/>
    <line x1="{strings[0]:.1f}" y1="295" x2="{strings[0]:.1f}" y2="820" stroke="#ffffff" stroke-width="0.8" opacity="0.6"/>
    <text x="{strings[0]:.1f}" y="282" fill="#94a3b8" font-size="16" font-family="system-ui, -apple-system, sans-serif" font-weight="800" text-anchor="middle">E (105)</text>

    <!-- A String (Gauge ~3.8px) -->
    <line x1="{strings[1]:.1f}" y1="295" x2="{strings[1]:.1f}" y2="820" stroke="url(#stringGrad)" stroke-width="3.8"/>
    <line x1="{strings[1]:.1f}" y1="295" x2="{strings[1]:.1f}" y2="820" stroke="#ffffff" stroke-width="0.7" opacity="0.6"/>
    <text x="{strings[1]:.1f}" y="282" fill="#94a3b8" font-size="16" font-family="system-ui, -apple-system, sans-serif" font-weight="800" text-anchor="middle">A (85)</text>

    <!-- D String (Gauge ~3.0px) -->
    <line x1="{strings[2]:.1f}" y1="295" x2="{strings[2]:.1f}" y2="820" stroke="url(#stringGrad)" stroke-width="3.0"/>
    <line x1="{strings[2]:.1f}" y1="295" x2="{strings[2]:.1f}" y2="820" stroke="#ffffff" stroke-width="0.6" opacity="0.6"/>
    <text x="{strings[2]:.1f}" y="282" fill="#94a3b8" font-size="16" font-family="system-ui, -apple-system, sans-serif" font-weight="800" text-anchor="middle">D (65)</text>

    <!-- G String (Gauge ~2.2px) -->
    <line x1="{strings[3]:.1f}" y1="295" x2="{strings[3]:.1f}" y2="820" stroke="url(#stringGrad)" stroke-width="2.2"/>
    <line x1="{strings[3]:.1f}" y1="295" x2="{strings[3]:.1f}" y2="820" stroke="#ffffff" stroke-width="0.5" opacity="0.6"/>
    <text x="{strings[3]:.1f}" y="282" fill="#94a3b8" font-size="16" font-family="system-ui, -apple-system, sans-serif" font-weight="800" text-anchor="middle">G (45)</text>
  </g>

  <!-- Bottom Hero Section -->
  <!-- Accent Line -->
  <line x1="130" y1="860" x2="1070" y2="860" stroke="#1e293b" stroke-width="2"/>
  <line x1="130" y1="860" x2="420" y2="860" stroke="{acc}" stroke-width="3.5"/>

  <!-- Edition Title -->
  <text x="130" y="915" fill="#ffffff" font-size="46" font-family="system-ui, -apple-system, sans-serif" font-weight="900" letter-spacing="3">{cfg["title"]}</text>
  
  <!-- Edition Subtitle / Voicing Count -->
  <text x="130" y="955" fill="{acc}" font-size="19" font-family="system-ui, -apple-system, sans-serif" font-weight="800" letter-spacing="2.5">22 DIGITAL TWIN VOICINGS  //  HIGH-IMPEDANCE PASSIVE EMULATION</text>
  
  <!-- Word-Wrapped Description (Line 1 & Line 2, safe margins >= 130px) -->
  <text x="130" y="988" fill="#cbd5e1" font-size="16" font-family="system-ui, -apple-system, sans-serif" font-weight="600" letter-spacing="0.5">{cfg["desc_line1"]}</text>
  <text x="130" y="1012" fill="#94a3b8" font-size="15" font-family="system-ui, -apple-system, sans-serif" font-weight="500" letter-spacing="0.5">{cfg["desc_line2"]}</text>

  <!-- Bottom Hardware Specification Chips (Comfortable widths, safe within margin) -->
  <g transform="translate(130, 1042)">
    <!-- Chip 1 (Scale) -->
    <rect x="0" y="0" width="165" height="42" rx="8" fill="#141822" stroke="#2a3344" stroke-width="1.6"/>
    <text x="82" y="27" fill="#f8fafc" font-size="14.5" font-family="system-ui, -apple-system, sans-serif" font-weight="800" letter-spacing="1" text-anchor="middle">{cfg["scale"]}</text>

    <!-- Chip 2 (Pickup Style) -->
    <rect x="178" y="0" width="195" height="42" rx="8" fill="#141822" stroke="#2a3344" stroke-width="1.6"/>
    <text x="275" y="27" fill="#f8fafc" font-size="14.5" font-family="system-ui, -apple-system, sans-serif" font-weight="800" letter-spacing="1" text-anchor="middle">{cfg["badge2"]}</text>

    <!-- Chip 3 (Topology) -->
    <rect x="386" y="0" width="225" height="42" rx="8" fill="#141822" stroke="#2a3344" stroke-width="1.6"/>
    <text x="498" y="27" fill="#f8fafc" font-size="14.5" font-family="system-ui, -apple-system, sans-serif" font-weight="800" letter-spacing="1" text-anchor="middle">{cfg["badge3"]}</text>

    <!-- Chip 4 (Platform) -->
    <rect x="624" y="0" width="195" height="42" rx="8" fill="#141822" stroke="#2a3344" stroke-width="1.6"/>
    <text x="721" y="27" fill="#f8fafc" font-size="14.5" font-family="system-ui, -apple-system, sans-serif" font-weight="800" letter-spacing="1" text-anchor="middle">BLOCK 1 NAM + IR</text>

    <!-- Chip 5 (Certified) -->
    <rect x="832" y="0" width="105" height="42" rx="8" fill="#182030" stroke="{acc}" stroke-width="1.6"/>
    <text x="884" y="27" fill="{acc}" font-size="14.5" font-family="system-ui, -apple-system, sans-serif" font-weight="900" letter-spacing="1" text-anchor="middle">NAM A2</text>
  </g>
</svg>
"""
    # Strict validation of XML syntax
    ET.fromstring(svg)
    return svg


def main():
    assets_dir = Path("tone3000/assets")
    assets_dir.mkdir(parents=True, exist_ok=True)

    editions = {
        "precision": "allomorph_standard_precision_bass",
        "jazz": "allomorph_standard_jazz_bass",
        "pj": "allomorph_standard_pj_bass",
        "mustang": "allomorph_mustang_pj_bass",
    }

    # Remove obsolete coilshift placeholders if present
    for old_file in assets_dir.glob("coilshift_*.jpg"):
        print(f"Removing obsolete placeholder: {old_file}")
        old_file.unlink()

    for key, name in editions.items():
        svg_code = generate_pack_svg(key)
        svg_path = assets_dir / f"{name}.svg"
        jpg_path = assets_dir / f"{name}.jpg"

        svg_path.write_text(svg_code, encoding="utf-8")
        print(f"Generated valid SVG: {svg_path}")

        # Render 1024x1024 PNG via qlmanage, then convert to high-quality JPG via sips
        res = subprocess.run(
            ["qlmanage", "-t", "-s", "1024", "-o", str(assets_dir), str(svg_path)],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            print(f"qlmanage error for {svg_path}: {res.stderr}")
            continue

        png_rendered = assets_dir / f"{name}.svg.png"
        if png_rendered.exists():
            subprocess.run(
                [
                    "sips",
                    "-s",
                    "format",
                    "jpeg",
                    "-s",
                    "formatOptions",
                    "95",
                    str(png_rendered),
                    "--out",
                    str(jpg_path),
                ],
                check=True,
                capture_output=True,
            )
            png_rendered.unlink()
            print(f"Rendered production JPG: {jpg_path}")


if __name__ == "__main__":
    main()
