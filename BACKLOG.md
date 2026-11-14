# Backlog

Ideas we decided to keep for later. Nothing here is built yet.

## Big

**Regional trains (RE and RB).** A second league, or a wider one, that also counts regional express and regional
trains. Qualification would be at least 10 RE/RB arrivals per day. Much bigger: thousands of stations instead of about
160, new league structure (probably by Bundesland), more data per day, and a check of how reliable the regional
change data is in the archive.

**Our own data collection on the Hetzner server.** Archive per-day stops and our own DB Timetables API dumps on the
server, so the league keeps running if the Hugging Face archive stops. Code and setup are ready (`scripts/collect.py`,
`ops/`), it needs the server details, an SSH key and DB API credentials as GitHub secrets.

## Rules, decided to keep as is for now

**Construction pause.** Since 2026-11-15 members stay while they play on at least half of the last 28 days, so short
closures no longer cost membership. Long closures (e.g. Aschaffenburg, Gemünden to Aschaffenburg closed 9 Nov to
12 Dec 2026) still end membership after about two weeks. Option if that still feels harsh: days with zero ICE/IC
arrivals don't count against a member for up to 6 weeks ("paused").

**Scoring.** The weekly Schnitt averages the daily scores. Options discussed: pool the week (each train counts once),
a Bayesian average against luck (about 11 average trains added), showing binomial intervals, and a "Heimleistung"
ranking by delay added on the section into the station (previous stop is known for 97% of arrivals).
Decision on 2026-11-14: keep the current scoring.

**At least 2 separate ICE/IC lines per member.** Idea from 2026-11-15. DB's data has no line numbers for ICE/IC,
so lines must be derived. Counting compass directions (rough estimate: about 45 of 161 stations would go) is not a
valid method, because one track often carries several lines (e.g. Hamburg to Berlin) and termini like Dresden Hbf have
two lines but only one direction. A proper version would group trains into lines by their routes.

**Forecast threshold.** 0.60 (42% of station-days reach it). 0.55 would be an exact coin flip.
