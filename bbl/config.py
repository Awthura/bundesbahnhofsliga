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

# League pyramid: numbered leagues of 18, like the Bundesliga. The last one takes the remainder.
LEAGUE_SIZE = 18
MAX_LEAGUES = 12


def league_defs(n_leagues: int = MAX_LEAGUES):
    return [{"id": str(i), "name": f"{i}. Bundesbahnhofsliga", "short": f"{i}. BBL", "size": LEAGUE_SIZE}
            for i in range(1, n_leagues + 1)]


LEAGUES = league_defs()

# Data sources
HF_BASE = "https://huggingface.co/datasets/piebro/deutsche-bahn-data/resolve/main/monthly_processed_data"
HF_FIRST_MONTH = "2026-10"           # demo starts in Oct 2026 (all-station coverage exists since 2025-11)
DB_TIMETABLES_BASE = "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1"
DB_REQUESTS_PER_MIN = 55             # free plan allows about 60
