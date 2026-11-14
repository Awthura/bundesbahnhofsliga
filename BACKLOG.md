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

**Construction pause.** Stations without ICE/IC service because of a planned closure (e.g. Aschaffenburg, Gemünden to
Aschaffenburg closed 9 Nov to 12 Dec 2026) currently drop out of the league and return at the bottom. Option: pause
them and keep their place.

**Scoring.** The weekly Schnitt averages the daily scores. Options discussed: pool the week (each train counts once),
a Bayesian average against luck (about 11 average trains added), showing binomial intervals, and a "Heimleistung"
ranking by delay added on the section into the station (previous stop is known for 97% of arrivals).
Decision on 2026-11-14: keep the current scoring.

**Forecast threshold.** 0.60 (42% of station-days reach it). 0.55 would be an exact coin flip.
