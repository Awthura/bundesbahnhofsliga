"""
Count stations that qualify for the Bundesbahnhofliga, using one month of the piebro DB dataset (CC BY 4.0).
Qualification per day: more than MIN_ARRIVALS scheduled ICE/IC arrivals at the station.
League membership: station qualifies on at least MIN_DAY_SHARE of the days in the month.

pip install duckdb
Reads the parquet directly from Hugging Face (about 370 MB per month since Nov 2025), no download step needed.
"""
import duckdb

MONTH = "2026-10"
TYPES = ("ICE", "IC")          # add "EC", "ECE" if wanted
MIN_ARRIVALS = 5               # "more than 5" -> > 5
MIN_DAY_SHARE = 0.8            # must qualify on 80% of days
URL = f"hf://datasets/piebro/deutsche-bahn-data/monthly_processed_data/data-{MONTH}.parquet"

con = duckdb.connect()
con.sql("INSTALL httpfs; LOAD httpfs;")

daily = con.sql(f"""
    SELECT eva, any_value(station_name) AS station, CAST(arrival_planned_time AS DATE) AS day,
           count(DISTINCT id) AS arrivals,
           count(DISTINCT id) FILTER (WHERE NOT coalesce(arrival_is_canceled, false) AND delay_in_min < 6) AS punctual
    FROM read_parquet('{URL}')
    WHERE train_type IN {TYPES} AND arrival_planned_time IS NOT NULL
    GROUP BY eva, day
""")
con.register("daily", daily)

n_days = con.sql("SELECT count(DISTINCT day) FROM daily").fetchone()[0]
summary = con.sql(f"""
    SELECT eva, any_value(station) AS station,
           count(*) FILTER (WHERE arrivals > {MIN_ARRIVALS}) AS qualified_days,
           round(avg(arrivals), 1) AS avg_daily_arrivals,
           round(100.0 * sum(punctual) / sum(arrivals), 1) AS punctual_pct
    FROM daily GROUP BY eva
    ORDER BY avg_daily_arrivals DESC
""")
con.register("summary", summary)

league = con.sql(f"SELECT * FROM summary WHERE qualified_days >= {MIN_DAY_SHARE} * {n_days}")
print(f"Days in month: {n_days}")
print("Stations with any ICE/IC arrival:", con.sql("SELECT count(*) FROM summary").fetchone()[0])
print("Stations qualifying on at least one day:", con.sql("SELECT count(*) FROM summary WHERE qualified_days > 0").fetchone()[0])
print(f"League members (qualify on >= {int(MIN_DAY_SHARE*100)}% of days):", league.count("*").fetchone()[0])
league.write_csv("bundesbahnhofliga_stations.csv")
print(league.limit(20))
