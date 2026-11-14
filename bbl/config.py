"""All league rules live here so the rules page and the code can't drift apart."""

# Which trains count
TRAIN_TYPES = ("ICE", "IC")          # EC/ECE excluded (M0 decision, revisit later)
PUNCTUAL_LIMIT_MIN = 6               # punctual = arrival delay < 6 min (DB threshold)

# Daily qualification ("Spieltag")
MIN_ARRIVALS = 5                     # a station plays a day only with MORE than 5 ICE/IC arrivals
POINTS_DECIMALS = 2                  # daily points are 0.00 .. 1.00

# League membership
MEMBERSHIP_WINDOW_DAYS = 28          # look back this many days before each week
MIN_DAY_SHARE = 1.0                  # must have > MIN_ARRIVALS on EVERY day of that window
DATA_GAP_SHARE = 0.85                # days with < 85% of the usual total arrivals are data gaps, ignored for membership
SEED_MIN_DAYS = 7                    # first season starts after at least this much history

# Weekly season (Mon..Sun). Tables move daily, promotion/relegation after Sunday.
MIN_PLAYED_SHARE = 0.5               # need to have played half the matchdays so far to be ranked normally
DIRECT_MOVERS = 2                    # 17th and 18th go down, 1st and 2nd of the league below go up
PLAYOFF = True                       # 16th vs 3rd below: higher punctuality on the week's last day wins

# League pyramid, like German football: national leagues of 18 at the top (BBL, 2. BBL, 3. BBL),
# then Regionalbahnhofsligen by region (DFB regions) as the 4th tier.
LEAGUE_SIZE = 18                     # default size of a national league
LEAGUE_SIZES = {1: 18, 2: 18, 3: 20}  # like football: Bundesliga 18, 2. Bundesliga 18, 3. Liga 20
NATIONAL_TIERS = 3

# 3. BBL <-> Regionalbahnhofsligen, modelled on 3. Liga <-> Regionalliga (DFB, since 2020/21):
# places 17-20 of the 3. BBL go down directly (no playoff); 4 regional champions go up:
# West and Suedwest directly, one of Nord/Nordost/Bayern directly by rotation (football: yearly,
# here: every calendar week), the other two play off for the 4th place (Sunday punctuality).
RL_RELEGATED = 4
RL_DIRECT_REGIONS = ["W", "SW"]
RL_ROTATION = ["N", "NO", "BY"]


def league_size(tier: int) -> int:
    return LEAGUE_SIZES.get(tier, LEAGUE_SIZE)


def rotation_region(week_number: int) -> str | None:
    """Which of Nord/Nordost/Bayern gets the direct promotion spot in this calendar week."""
    return RL_ROTATION[week_number % len(RL_ROTATION)] if RL_ROTATION else None
REGIONS = {   # id: (name, Bundeslaender)
    "N": ("Nord", ["Niedersachsen", "Bremen", "Hamburg", "Schleswig-Holstein"]),
    "NO": ("Nordost", ["Berlin", "Brandenburg", "Mecklenburg-Vorpommern", "Sachsen", "Sachsen-Anhalt", "Thüringen"]),
    "W": ("West", ["Nordrhein-Westfalen"]),
    "SW": ("Südwest", ["Hessen", "Rheinland-Pfalz", "Saarland", "Baden-Württemberg"]),
    "BY": ("Bayern", ["Bayern"]),
}
STATE_OVERRIDES = {   # stations whose platform-level EVA is missing in the station data
    "08098160": "Berlin",                 # Berlin Hbf (tief)
    "08073368": "Nordrhein-Westfalen",    # Köln Messe/Deutz Gl.11-12
}
DEFAULT_REGION = "NO"


def national_league(tier: int):
    """Like football: the top tier is just 'the Bundesbahnhofsliga' (BBL), then the 2. and 3. Bundesbahnhofsliga."""
    if tier == 1:
        return {"id": "1", "name": "Bundesbahnhofsliga", "short": "BBL", "tier": 1}
    return {"id": str(tier), "name": f"{tier}. Bundesbahnhofsliga", "short": f"{tier}. BBL", "tier": tier}


def regional_league(rid: str):
    return {"id": f"RL-{rid}", "name": f"Regionalbahnhofsliga {REGIONS[rid][0]}", "short": f"RBL {REGIONS[rid][0]}",
            "tier": NATIONAL_TIERS + 1, "region": rid}


def region_of(state: str | None) -> str | None:
    for rid, (_, states) in REGIONS.items():
        if state in states:
            return rid
    return None


# Data sources
HF_BASE = "https://huggingface.co/datasets/piebro/deutsche-bahn-data/resolve/main/monthly_processed_data"
HF_FIRST_MONTH = "2026-10"           # demo starts in Oct 2026 (all-station coverage exists since 2025-11)
DB_TIMETABLES_BASE = "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1"
DB_REQUESTS_PER_MIN = 55             # free plan allows about 60
