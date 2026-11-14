"""Generate our own league crests (SVG). Original designs, no DB marks.
python scripts/make_logos.py  -> docs/assets/logos/*.svg
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "assets" / "logos"
RED, WHITE, INK = "#C8102E", "#FFFFFF", "#1A1A1A"
SHIELD = "M60 6 L110 20 V68 C110 102 88 124 60 136 C32 124 10 102 10 68 V20 Z"


def track(color, dashed=False):
    """Two rails running towards a horizon, plus sleepers. Kept well inside the shield."""
    sleepers = []
    for y, half in ((114, 20), (105, 17), (97, 14.5), (90, 12.5)):
        sleepers.append(f'<line x1="{60-half}" y1="{y}" x2="{60+half}" y2="{y}" stroke="{color}" stroke-width="3" stroke-linecap="round"/>')
    dash = ' stroke-dasharray="5 3"' if dashed else ""
    rails = (f'<path d="M47 118 L56 86 M73 118 L64 86" stroke="{color}" stroke-width="3.5" '
             f'stroke-linecap="round" fill="none"{dash}/>')
    return "".join(sleepers) + rails


BOLT = "M1.5 -6.5 L-4 1 L-0.5 1 L-2 6.5 L4 -1.2 L0.5 -1.2 Z"
TURTLE_BODY = ("M-6 1.5 A6 5.5 0 0 1 6 1.5 Z"                            # shell
               "M6.2 0.3 a2.5 2.3 0 1 1 0.1 0 Z"                          # head
               "M-5 1 h2.6 v3.4 h-2.6 Z M2.4 1 h2.6 v3.4 h-2.6 Z"         # legs
               "M-6 0.6 l-2.6 1.4 l2.6 0.4 Z")                            # tail
TURTLE_SHELL = "M-3.6 0.2 L-1.8 -2.6 L1.8 -2.6 L3.6 0.2"                 # shell pattern


def icons(kind, n, color, bg, y=24):
    """A row of n icons (bolts = fast leagues, turtles = slow leagues) across the top of the shield."""
    if not n:
        return ""
    if kind == "bolt":
        step, scale = 13, 1.35
        one = lambda x: f'<path d="{BOLT}" transform="translate({x:.1f} {y}) scale({scale})" fill="{color}"/>'
    else:
        step, scale = (20, 1.35) if n <= 2 else (17.5, 0.88)
        one = lambda x: (f'<g transform="translate({x - 1:.1f} {y + 1}) scale({scale})"><path d="{TURTLE_BODY}" fill="{color}"/>'
                         f'<path d="{TURTLE_SHELL}" fill="none" stroke="{bg}" stroke-width="1.1" stroke-linejoin="round"/></g>')
    x0 = 60 - step * (n - 1) / 2
    return "".join(one(x0 + i * step) for i in range(n))


def league_icons(tier: int):
    """Speed scale: BBL 3 bolts (the round badge), 2. BBL 2, 3. BBL 1.
    From the 4th tier down: turtles, 1 for the Regionalbahnhofsligen and one more per tier below."""
    if tier <= 3:
        return "bolt", 4 - tier
    return "turtle", tier - 3


def crest(num, bg, fg, border, extra="", dashed=False, icon=None, band=None):
    band_svg = ""
    num_color = fg
    if band:
        band_svg = f'<rect x="10" y="36" width="100" height="42" fill="{band}"/>'
        num_color = bg
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 142" role="img" aria-label="{num}">
<defs><clipPath id="c"><path d="{SHIELD}"/></clipPath></defs>
<path d="{SHIELD}" fill="{bg}"/>
<g clip-path="url(#c)">{band_svg}</g>
{icons(icon[0], icon[1], fg, bg) if icon else ""}
<text x="60" y="71" text-anchor="middle" font-family="Arial Black, Helvetica, Arial, sans-serif" font-weight="900" font-size="{40 if len(num) == 1 else 30}" fill="{num_color}">{num}</text>
<g clip-path="url(#c)">{track(fg, dashed)}</g>
{extra}
<path d="{SHIELD}" fill="none" stroke="{border}" stroke-width="5" stroke-linejoin="round"/>
</svg>'''


def site_logo():
    """Round badge: red disc, white ring, 'BBL' with clear space, a short track underneath."""
    sleepers = "".join(f'<line x1="{x}" y1="80" x2="{x}" y2="90" stroke="{WHITE}" stroke-width="3" stroke-linecap="round"/>'
                       for x in range(40, 84, 8))
    stars = "".join(f'<path d="{BOLT}" transform="translate({x} 31) scale(1.1)" fill="{WHITE}"/>' for x in (48, 60, 72))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" role="img" aria-label="Bundesbahnhofsliga">
<circle cx="60" cy="60" r="58" fill="{RED}"/>
<circle cx="60" cy="60" r="50" fill="none" stroke="{WHITE}" stroke-width="4"/>
{stars}
<text x="60" y="69" text-anchor="middle" font-family="Arial Black, Helvetica, Arial, sans-serif" font-weight="900" font-size="27" letter-spacing="1" fill="{WHITE}">BBL</text>
<line x1="34" y1="82" x2="86" y2="82" stroke="{WHITE}" stroke-width="3" stroke-linecap="round"/>
<line x1="34" y1="88" x2="86" y2="88" stroke="{WHITE}" stroke-width="3" stroke-linecap="round"/>
{sleepers}
</svg>'''


def favicon():
    """Tab icon: at 16px only a bold B and one rail survive."""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<circle cx="32" cy="32" r="31" fill="{RED}"/>
<text x="32" y="43" text-anchor="middle" font-family="Arial Black, Helvetica, Arial, sans-serif" font-weight="900" font-size="34" fill="{WHITE}">B</text>
<line x1="17" y1="51" x2="47" y2="51" stroke="{WHITE}" stroke-width="4" stroke-linecap="round"/>
</svg>'''


def main():
    import sys
    sys.path.insert(0, str(OUT.parent.parent.parent))
    from bbl import config
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("liga-*.svg"):
        old.unlink()
    (OUT / "liga-1.svg").write_text(site_logo())   # the top league IS the BBL: same round badge
    (OUT / "liga-2.svg").write_text(crest("2", WHITE, RED, RED, icon=league_icons(2)))
    (OUT / "liga-3.svg").write_text(crest("3", RED, WHITE, RED, band=WHITE, icon=league_icons(3)))
    for k, rid in enumerate(config.REGIONS):   # Regionalbahnhofsligen: region code, alternating colours
        bg, fg = (WHITE, RED) if k % 2 == 0 else (RED, WHITE)
        (OUT / f"liga-RL-{rid}.svg").write_text(crest(rid, bg, fg, RED, dashed=True, icon=league_icons(4)))
    (OUT / "bbl.svg").write_text(site_logo())
    (OUT / "favicon.svg").write_text(favicon())
    print(f"logos written to {OUT}")


if __name__ == "__main__":
    main()
