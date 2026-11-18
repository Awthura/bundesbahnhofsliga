// Bundesbahnhofsliga: tiny static frontend, no build step. Bilingual (de/en).
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const getJSON = (p) => fetch(p, { cache: "no-cache" }).then((r) => {
  if (!r.ok) { const e = new Error(`${p}: HTTP ${r.status}`); e.status = r.status; throw e; }
  return r.json();
});
const fmt = (x, d = 2) => (x == null ? "-" : Number(x).toFixed(d));
const logo = (lid) => `assets/logos/liga-${lid}.svg`;

// Language: set early by the inline snippet in each page's <head> (URL ?lang=, then saved choice, then browser).
const LANG = document.documentElement.dataset.lang === "de" ? "de" : "en";
try { if (new URLSearchParams(location.search).get("lang")) localStorage.setItem("bbl-lang", LANG); } catch (e) { /* storage blocked */ }

const STR = {
  de: {
    nav: ["Home", "Tabellen", "Rangliste", "Karte", "Statistik", "Meister", "Regeln", "Methodik"],
    home_nat: "Deutschland: Wie pünktlich sind die Fernzüge?", home_nat_link: "Alle Statistiken, auch nach Bundesland",
    ns_title: "Statistik Deutschland", ns_title_land: (s) => `Statistik ${s}`, ns_all: "Ganz Deutschland", ns_intro: "Wie pünktlich sind ICE, IC und EC bundesweit oder in einem Bundesland? Alle planmäßigen Fernverkehrsankünfte an allen Halten, jeder Zug zählt einmal.",
    ns_period: ["Tag", "Woche (KW)", "Letzte 28 Tage", "Seit Beginn"],
    ns_kpi: ["Ankünfte", "pünktlich (< 6 Min.)", "verspätet (≥ 6 Min.)", "ausgefallen", "über 1 Std. verspätet"],
    ns_cmp: "Zeiträume im Vergleich", ns_cmp_rows: ["Diese Woche", "Letzte abgeschlossene Woche", "Letzte 28 Tage", "Seit Beginn"],
    ns_cmp_cols: ["Zeitraum", "Ankünfte", "Pünktl.", "6–15", "16–30", "31–60", "1–2 Std.", "> 2 Std.", "Ausgef."],
    ns_note: (a, b) => `Daten vom ${a} bis ${b} · Verspätung bei der Ankunft in ganzen Minuten. Pünktlich heißt weniger als 6 Minuten zu spät, wie bei der Deutschen Bahn; ausgefallene Ankünfte zählen hier gesondert.`,
    footer: `Fanprojekt, nicht mit der Deutschen Bahn verbunden. Daten: Deutsche Bahn Timetables API über
      <a href="https://huggingface.co/datasets/piebro/deutsche-bahn-data">piebro/deutsche-bahn-data</a>, CC BY 4.0.
      Die Tabellen zeigen die Pünktlichkeit, wie Fahrgäste sie am Bahnhof erleben; über die Ursache einer Verspätung sagen sie nichts.`,
    updated: (d, g) => `Daten bis ${d}, erstellt ${g} UTC.`,
    days: ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"],
    cols: ["Platz", "Bahnhof", "Tage", "Punkte", "Schnitt", "Form"], col_canc: "Ausfälle",
    canc_tip: "Anteil ausgefallener Ankünfte in dieser Woche. Ausfälle zählen in den Punkten bereits als unpünktlich; die Spalte zeigt nur, wie viele es waren.",
    canc_note: "Ausfälle: Anteil ausgefallener ICE/IC/EC-Ankünfte. Sie zählen in den Punkten bereits als unpünktlich und werden hier nur zusätzlich gezeigt.",
    canc_cards: [(p) => `${p} % ausgefallen (seit Beginn)`, (p) => `${p} % ausgefallen (letzte 28 Tage)`,
      (c, a) => `diese Woche ausgefallen (${c} von ${a})`, (d, c, a) => `meiste Ausfälle: ${d} (${c} von ${a})`],
    canc_day: (c) => `${c} ausgefallen`,
    mix_title: "Pünktlich, verspätet, ausgefallen", mix_periods: ["Diese Woche", "Letzte 28 Tage", "Seit Beginn"],
    mix_all: "Alle Ankünfte", mix_dis: "Nur Störungen", mix_cats: ["Pünktlich (< 6 Min.)", "Verspätet (≥ 6 Min.)", "Ausgefallen"],
    mix_bins: ["6 bis 15 Min.", "16 bis 30 Min.", "31 bis 60 Min.", "1 bis 2 Std.", "über 2 Std.", "Ausgefallen"],
    mix_center: ["Ankünfte", "Störungen"], mix_none: "Für diesen Zeitraum liegen noch keine Daten vor.", mix_nodis: "Keine Störungen in diesem Zeitraum.",
    mix_note: (d) => `${d} Tage. Verspätung bei der Ankunft in ganzen Minuten; „Störungen“ sind alle verspäteten und ausgefallenen Ankünfte. Ausgefallen ist zusätzlich schraffiert.`,
    map_metric: ["Pünktlichkeit", "Ausfälle"],
    map_metric_l: "Anzeigen:",
    map_fixed: ["über 55 % pünktlich (dunkler = besser)", "45 bis 55 %", "unter 45 % (dunkler = schlechter)"],
    map_metrics: ["Pünktlich (unter 6 Min.)", "Verspätet (6 Min. und mehr)", "Verspätet 6 bis 15 Min.", "Verspätet 16 bis 30 Min.",
      "Verspätet 31 bis 60 Min.", "Verspätet 1 bis 2 Std.", "Verspätet über 2 Std.", "Verspätet über 30 Min.", "Verspätet über 1 Std.", "Ausgefallen"],
    map_short: ["Pünktl.", "6–15", "16–30", "31–60", "1–2 Std.", "> 2 Std.", "Ausgef."],
    map_nat_m: (lbl, pct, k, n) => `Deutschland gesamt, ${lbl}: ${pct} % (${k} von ${n} Ankünften)`,
    map_leg_m: (pts) => ["besser als Deutschland", `ähnlich (± ${pts} Punkte)`, "schlechter als Deutschland", "keine Daten"],
    map_tip_m: (lbl, pct, k, n, d) => `${lbl}: <b>${pct} %</b> (${k} von ${n}) · ${d} Punkte gegenüber Deutschland`,
    map_cols_m: ["Platz", "Bundesland", "Ankünfte", "vs. DE"], map_de: "Deutschland",
    map_nat_c: (pct, c, n) => `Deutschland gesamt: ${pct} % ausgefallen (${c} von ${n} Ankünften)`,
    map_tip_c: (pct, c, n, d) => `${pct} % ausgefallen · ${c} von ${n} Ankünften · ${d} Punkte gegenüber Deutschland`,
    map_legend_c: ["deutlich weniger Ausfälle als Deutschland", "ähnlich (± 1 Punkt)", "deutlich mehr Ausfälle", "keine Daten"],
    map_cols_c: ["Platz", "Bundesland", "Ausgefallen", "Ankünfte", "vs. Deutschland"],
    called_off: "nicht gewertet", new_tag: "NEU", live: "LIVE",
    season_label: "Saison (KW)", to: "bis",
    season_done: "Saison beendet, Auf- und Abstieg vollzogen.",
    season_live: (n) => `Wertungstag ${n} von 7. Auf- und Abstieg nach dem Sonntag.`,
    sub: (n, id, day) => `${n} Bahnhöfe · Saison ${id} · Tabelle nach ${day}`,
    matchday: "Wertungstag", running: "läuft", pending: "Daten folgen",
    no_data_today: "Für heute liegen noch keine Daten vor. Die Datenquelle veröffentlicht ihre Dateien etwa zweimal am Tag (gegen 2 und 14 Uhr).",
    view_week: "Woche", view_day: "Nur dieser Tag", day_cols: ["Platz", "Bahnhof", "Ankünfte", "Tagespunkte"],
    day_note: (d) => `Nur ${d}: Rangfolge nach den Punkten dieses einen Tages (Anteil pünktlicher Ankünfte). Bei Gleichstand zählen mehr Ankünfte. Auf- und Abstieg entscheidet die ganze Woche.`,
    leader_top: "Tabellenführer", leader: "Spitzenreiter", lantern: "Rote Laterne", day_winner: (d) => `Tagessieger ${d}`,
    legend: ["Aufstieg", "Relegation / Aufstiegsrunde", "Abstieg",
      "Sortiert nach Schnitt = durchschnittliche Tagespunkte (0 bis 1). Graue Zeilen haben bisher zu wenige gewertete Tage."],
    moves_title: "Auf- und Abstieg",
    first_season: "Erste Saison, noch keine Bewegungen.",
    after: (id) => `Nach der Saison ${id}:`,
    round_title: "Aufstieg in die 3. BL: die fünf Meister, sortiert nach Schnitt (die besten 4 steigen auf)",
    round_res: { up: "steigt auf", stays: "bleibt (5. von 5)" },
    po_title: "Relegation (Pünktlichkeit am Sonntag)",
    tagline: "Die Bundesliga der Bahnhöfe, entschieden von pünktlichen Fernzügen.",
    score_hint: "Punkte = Anteil pünktlicher Ankünfte (weniger als 6 Minuten zu spät). 0,82 heißt: 82 % der ICE/IC/EC kamen pünktlich an.",
    po_up: "steigt auf", po_stays: "bleibt oben",
    up_into: (l) => `Aufsteiger in die ${l}`, down_from: (l) => `Absteiger aus der ${l}`,
    load_error: (m) => `Daten konnten nicht geladen werden (${m}).`,
    fc_title: "Prognose für heute (live)",
    fc_live: (k, m, n) => `Bisher ${k} von ${m} fälligen Ankünften pünktlich (${Math.round(100 * k / m)} %), heute insgesamt etwa ${n} erwartet. Die Prognose wird mit jedem Update angepasst.`,
    fc_pre: (p) => `Vor Tagesbeginn: ${p} % Ja.`, fc_waiting: "Noch keine Daten für heute: Prognose aus der Vorgeschichte. Die Datenquelle veröffentlicht etwa um 2 und 14 Uhr.",
    fc_decided: { yes: "Entschieden: Ja. Die 60 % sind heute schon sicher.", no: "Entschieden: Nein. 60 % sind heute nicht mehr erreichbar." },
    fc_q: (n, d, t) => `Kommen am ${d} mindestens ${t} % der Fernzüge in ${n} pünktlich an?`,
    yes: "Ja", no: "Nein",
    fc_expected: (e, l, h) => `Erwartet: ${e} % pünktlich (80-%-Bereich ${l} bis ${h} %)`,
    fc_brier: (b, n) => `Treffsicherheit der letzten ${n} Prognosen: Brier ${b} (Münzwurf 0,25; kleiner ist besser)`,
    fc_legend: "Linie: Wahrscheinlichkeit für Ja, jeweils am Vortag geschätzt. Punkte oben und unten: tatsächliches Ergebnis (grün Ja, rot Nein).",
    fc_note: "Statistische Schätzung aus der Vorgeschichte dieses Bahnhofs (die Einstellungen werden bei jedem Update an den bisherigen Ergebnissen neu bestimmt), im Laufe des Tages ergänzt um die bereits angekommenen Züge. Keine Wette, kein Geld, nur Statistik.",
    fc_no_service: "Zurzeit halten hier keine Fernzüge (ICE, IC, EC) (zum Beispiel wegen Bauarbeiten), deshalb gibt es keine Prognose.",
    home_live: (kw, n) => `${kw} · LIVE · Wertungstag ${n} von 7`, home_done: (kw) => `${kw} · abgeschlossen`,
    home_tables: "Ligatabellen", home_tables_sub: "Alle 8 Ligen, ein Klick zur Tabelle",
    home_regional: "+ 5 Regionalbahnhofsligen", home_ranking: "Bundesweite Rangliste", home_top3: "Spitze", home_bottom3: "Schlusslichter",
    home_ranking_sub: (kw) => `Spitze und Schlusslichter aller Ligen, ${kw}`, home_ranking_btn: "Bundesweite Rangliste ansehen",
    home_search: "Finde deinen Bahnhof", home_search_ph: "Bahnhof eingeben, z. B. Nürnberg",
    home_search_sub: (n) => `${n} Bahnhöfe mit regelmäßigem Fernverkehr`, home_popular: "Die größten", home_search_none: "Kein Bahnhof gefunden. Nur Bahnhöfe mit regelmäßigem ICE/IC/EC-Verkehr sind in der Liga.",
    home_week: "Diese Woche", home_leader: "Tabellenführer BBL", home_climber: (d) => `Größter Sprung ${d}`,
    home_climb_txt: (n) => `${n} Plätze nach oben, bundesweit`, home_day: (d) => `Tagessieger bundesweit ${d}`,
    home_how: "So funktioniert's",
    home_steps: [["1", "Jeden Tag Punkte", "Anteil der ICE/IC/EC, die pünktlich ankommen: 0,82 heißt 82 % pünktlich."],
      ["2", "Jede Woche eine Saison", "Montag bis Sonntag, sortiert nach dem Schnitt. Die Tabelle ändert sich jeden Tag."],
      ["3", "Auf- und Abstieg", "Nach jedem Sonntag wechseln Bahnhöfe die Liga, von den Regionalbahnhofsligen bis in die BBL."]],
    home_rules: "Alle Regeln",
    map_title: "Karte", map_intro: "Wie pünktlich sind die Fernzüge in deinem Bundesland, wie stark verspätet, wie oft ausgefallen? Pünktlichkeit hat eine feste Farbskala (rot unter 45 %, grau 45 bis 55 %, grün über 55 %); Verspätungen und Ausfälle werden im Vergleich zu ganz Deutschland eingefärbt.",
    map_period: ["Tag", "Woche (KW)", "4 Wochen"], map_mode: ["Kumuliert", "Einzelner Tag"], map_dots: "Bahnhöfe zeigen",
    map_play: "Abspielen", map_pause: "Pause",
    map_nat: (pct, n) => `Deutschland gesamt: ${pct} % pünktlich (${n} Ankünfte)`,
    map_legend: ["deutlich besser als Deutschland", "ähnlich (± 3 Punkte)", "deutlich schlechter", "keine Daten"],
    map_range: (a, b) => (a === b ? a : `${a} bis ${b}`), map_running: "Der letzte Tag läuft noch.",
    map_tip: (pct, n, d) => `${pct} % pünktlich · ${n} Ankünfte · ${d} Punkte gegenüber Deutschland`,
    map_cols: ["Platz", "Bundesland", "Pünktlich", "Ankünfte", "vs. Deutschland"],
    map_note: "Gezählt werden alle planmäßigen ICE/IC/EC-Ankünfte im Bundesland, auch an Halten, die nicht in der Liga sind. Jeder Zug zählt einmal. Punkte = Prozentpunkte. Kartengrundlage: Natural Earth.",
    rk_title: "Bundesweite Rangliste", rk_intro: "Alle Bahnhöfe aller Ligen in einer Tabelle, sortiert nach dem Schnitt der Woche.",
    rk_cols: ["Platz", "Bahnhof", "Liga", "Bundesland", "Tage", "Schnitt"], rk_all: "Alle Bundesländer", rk_link: "Bundesweite Rangliste",
    rk_freq: (n) => n ? `Nur Bahnhöfe mit mindestens ${n} ICE/IC/EC-Ankünften an einem typischen Tag` : "Alle Bahnhöfe, egal wie viele Züge",
    rk_presets: [["Alle", 0], ["ab 30", 30], ["ab 60", 60], ["Große Knoten ab 100", 100]],
    rk_count: (k, n) => `${k} von ${n} Bahnhöfen`, rk_per_day: "Züge/Tag", rk_nat: "Bundesweit",
    rk_freq_note: "Züge/Tag = typischer Tag (Median der letzten 28 Tage). Mit Filter zeigt „Platz“ den Rang innerhalb der Auswahl.",
    st_rank: (r, n) => `${r}. von ${n} bundesweit`, st_state: (r, n, s) => `${r}. von ${n} in ${s}`,
    st_rank_note: (kw, a) => `Rangliste ${kw} (letzte abgeschlossene Woche), Schnitt ${a}`,
    vol_avg: "ICE/IC/EC-Ankünfte pro Tag (Ø)", vol_busiest: (d) => `meiste Ankünfte, ${d}`,
    wd_title: "Wochentage", wd_note: "Durchschnittlicher Anteil pünktlicher Züge je Wochentag. Grün: bester Tag, rot: schwächster Tag.",
    rec_title: "Rekorde und Serien",
    rec: { best: "Beste Woche", worst: "Schwächste Woche", highest: "Höchste Liga", titles: "Meistertitel",
      moves: "Aufstiege / Abstiege", longest: "Längste Serie ab 0,60", current: "Aktuelle Serie ab 0,60",
      current_short: (d) => `aktuell: ${d}` },
    n_days: (n) => `${n} ${n === 1 ? "Tag" : "Tage"}`, place: (r, l) => `${r}. in der ${l}`,
    st_title: "Bahnhof", st_none: "diese Woche in keiner Liga", st_missing: "Bahnhof nicht gefunden",
    st_error: (m) => `Die Seite konnte nicht geladen werden. Bitte neu laden. (${m})`,
    kpi: ["Ø Anteil pünktlicher Züge pro Tag", "gewertete Tage", "bester Tag", "schlechtester Tag"],
    chart_title: "Anteil pünktlicher Züge pro Tag (letzte 120 Tage)",
    chart_note: "Jeder Balken ist ein Wertungstag: Anteil der ICE/IC/EC-Ankünfte mit weniger als 6 Minuten Verspätung. Grün ab 0,85, grau 0,70 bis 0,85, rot unter 0,70. Dünne Striche an der Grundlinie: nicht gewertet (weniger als 5 Ankünfte).",
    arrivals: "Ankünfte",
    pyr_title: "Ligaverlauf",
    pyr_note: "Jeder Punkt ist eine Saison (KW): je höher, desto besser die Liga und der Platz darin. Grün: aufgestiegen, rot: abgestiegen, gelber Ring: zu Saisonbeginn nachgerückt, hohl: laufende Woche.",
    filled: { spared: "nachgerückt (Abstieg erlassen)", next_best: "nachgerückt (bester Platz der Liga darunter)" },
    fills_title: "Nachrücker zu Saisonbeginn", dropped_title: (n) => `Ausgeschieden: ${n} Bahnhöfe hatten an weniger als der Hälfte der letzten 28 Tage mindestens 5 ICE/IC/EC-Ankünfte`,
    hist_title: "Saisonverlauf", hist_cols: ["Saison", "Liga", "Platz", "Tage", "Schnitt"],
    titles: { "index.html": "Bundesbahnhofsliga · Die Liga der Bahnhöfe", "tables.html": "Tabellen · Bundesbahnhofsliga", "champions.html": "Meister · Bundesbahnhofsliga", "ranking.html": "Rangliste · Bundesbahnhofsliga", "map.html": "Karte · Bundesbahnhofsliga", "stats.html": "Statistik · Bundesbahnhofsliga", "rules.html": "Regeln · Bundesbahnhofsliga", "about.html": "Methodik · Bundesbahnhofsliga" },
    ch_title: "Meisterliste", ch_intro: "Wer stand am Ende der Woche ganz oben? Eine Saison ist eine Kalenderwoche.",
    ch_cols: ["Saison", "Meister", "Schnitt", "Vizemeister"], ch_live: "läuft, führt gerade", ch_promoted: "aufgestiegen",
    ch_record: "Rekordmeister", ch_titles: (n) => `${n} ${n === 1 ? "Titel" : "Titel"}`, ch_none: "Noch keine abgeschlossene Saison.",
    ch_link: "Meisterliste dieser Liga",
  },
  en: {
    nav: ["Home", "Tables", "Ranking", "Map", "Statistics", "Champions", "Rules", "Methodology"],
    home_nat: "Germany: how punctual are long-distance trains?", home_nat_link: "All statistics, also by state",
    ns_title: "Germany at a glance", ns_title_land: (s) => `${s} at a glance`, ns_all: "All of Germany", ns_intro: "How punctual are ICE, IC and EC trains nationwide or in one state? All scheduled long-distance arrivals at all stops, every train counted once.",
    ns_period: ["Day", "Week", "Last 28 days", "All time"],
    ns_kpi: ["arrivals", "on time (< 6 min)", "late (≥ 6 min)", "cancelled", "over 1 h late"],
    ns_cmp: "Periods compared", ns_cmp_rows: ["This week", "Last finished week", "Last 28 days", "All time"],
    ns_cmp_cols: ["Period", "Arrivals", "On time", "6–15", "16–30", "31–60", "1–2 h", "> 2 h", "Canc."],
    ns_note: (a, b) => `Data from ${a} to ${b} · Arrival delay in whole minutes. On time means less than 6 minutes late, as at Deutsche Bahn; cancelled arrivals are counted separately here.`,
    footer: `Fan project, not affiliated with Deutsche Bahn. Data: Deutsche Bahn Timetables API via
      <a href="https://huggingface.co/datasets/piebro/deutsche-bahn-data">piebro/deutsche-bahn-data</a>, CC BY 4.0.
      Rankings describe punctuality as passengers see it at a station; they say nothing about who caused a delay.`,
    updated: (d, g) => `Data through ${d}, built ${g} UTC.`,
    days: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    cols: ["Pos", "Station", "Days", "Points", "Avg", "Form"], col_canc: "Cancelled",
    canc_tip: "Share of cancelled arrivals this week. Cancellations already count as not punctual in the points; this column only shows how many there were.",
    canc_note: "Cancelled: share of cancelled ICE/IC/EC arrivals. They already count as not punctual in the points and are only shown here as well.",
    canc_cards: [(p) => `${p}% cancelled (all time)`, (p) => `${p}% cancelled (last 28 days)`,
      (c, a) => `cancelled this week (${c} of ${a})`, (d, c, a) => `most cancellations: ${d} (${c} of ${a})`],
    canc_day: (c) => `${c} cancelled`,
    mix_title: "On time, late, cancelled", mix_periods: ["This week", "Last 28 days", "All time"],
    mix_all: "All arrivals", mix_dis: "Disruptions only", mix_cats: ["On time (< 6 min)", "Late (≥ 6 min)", "Cancelled"],
    mix_bins: ["6 to 15 min", "16 to 30 min", "31 to 60 min", "1 to 2 h", "over 2 h", "Cancelled"],
    mix_center: ["arrivals", "disruptions"], mix_none: "No data for this period yet.", mix_nodis: "No disruptions in this period.",
    mix_note: (d) => `${d} days. Arrival delay in whole minutes; "disruptions" are all late and cancelled arrivals. Cancelled is also hatched.`,
    map_metric: ["Punctuality", "Cancellations"],
    map_metric_l: "Show:",
    map_fixed: ["over 55% on time (darker = better)", "45 to 55%", "under 45% (darker = worse)"],
    map_metrics: ["On time (under 6 min)", "Late (6 min or more)", "Late 6 to 15 min", "Late 16 to 30 min",
      "Late 31 to 60 min", "Late 1 to 2 h", "Late over 2 h", "Late over 30 min", "Late over 1 h", "Cancelled"],
    map_short: ["On time", "6–15", "16–30", "31–60", "1–2 h", "> 2 h", "Canc."],
    map_nat_m: (lbl, pct, k, n) => `Germany overall, ${lbl}: ${pct}% (${k} of ${n} arrivals)`,
    map_leg_m: (pts) => ["better than Germany", `similar (± ${pts} points)`, "worse than Germany", "no data"],
    map_tip_m: (lbl, pct, k, n, d) => `${lbl}: <b>${pct}%</b> (${k} of ${n}) · ${d} points vs Germany`,
    map_cols_m: ["Pos", "State", "Arrivals", "vs DE"], map_de: "Germany",
    map_nat_c: (pct, c, n) => `Germany overall: ${pct}% cancelled (${c} of ${n} arrivals)`,
    map_tip_c: (pct, c, n, d) => `${pct}% cancelled · ${c} of ${n} arrivals · ${d} points vs Germany`,
    map_legend_c: ["clearly fewer cancellations than Germany", "similar (± 1 point)", "clearly more cancellations", "no data"],
    map_cols_c: ["Pos", "State", "Cancelled", "Arrivals", "vs Germany"],
    called_off: "not scored", new_tag: "NEW", live: "LIVE",
    season_label: "Season (week)", to: "to",
    season_done: "Season finished, promotion and relegation applied.",
    season_live: (n) => `Scoring day ${n} of 7. Promotion and relegation after Sunday.`,
    sub: (n, id, day) => `${n} stations · season ${id} · table after ${day}`,
    matchday: "Scoring day", running: "in progress", pending: "data pending",
    no_data_today: "There is no data for today yet. The data source publishes its files about twice a day (around 2 am and 2 pm German time).",
    view_week: "Week", view_day: "This day only", day_cols: ["Pos", "Station", "Arrivals", "Day points"],
    day_note: (d) => `${d} only: ranked by this single day's points (share of punctual arrivals). On a tie, more arrivals win. Promotion and relegation are decided by the whole week.`,
    leader_top: "Top of the league", leader: "League leader", lantern: "Red lantern", day_winner: (d) => `Day winner ${d}`,
    legend: ["Promotion", "Decider / promotion round", "Relegation",
      "Ranked by average daily points (0 to 1). Grey rows have too few scored days so far."],
    moves_title: "Promotion and relegation",
    first_season: "First season, nothing moved yet.",
    after: (id) => `After season ${id}:`,
    round_title: "Promotion to the 3. BL: the five champions, ranked by average (best 4 go up)",
    round_res: { up: "promoted", stays: "stays (5th of 5)" },
    po_title: "Deciders (Sunday punctuality)",
    tagline: "The Bundesliga of German railway stations, decided by punctual long-distance trains.",
    score_hint: "Points = share of punctual arrivals (less than 6 minutes late). 0.82 means 82% of ICE/IC/EC trains arrived on time.",
    po_up: "goes up", po_stays: "stays up",
    up_into: (l) => `Promoted to the ${l}`, down_from: (l) => `Relegated from the ${l}`,
    load_error: (m) => `Could not load data (${m}).`,
    fc_title: "Forecast for today (live)",
    fc_live: (k, m, n) => `So far ${k} of ${m} due arrivals on time (${Math.round(100 * k / m)}%), about ${n} expected today in total. The forecast is updated with every update.`,
    fc_pre: (p) => `Before the day started: ${p}% Yes.`, fc_waiting: "No data for today yet: forecast from the station's history. The data source publishes around 2 am and 2 pm German time.",
    fc_decided: { yes: "Decided: Yes. The 60% are already certain today.", no: "Decided: No. 60% can no longer be reached today." },
    fc_q: (n, d, t) => `Will at least ${t}% of long-distance trains arrive on time at ${n} on ${d}?`,
    yes: "Yes", no: "No",
    fc_expected: (e, l, h) => `Expected: ${e}% on time (80% range ${l}% to ${h}%)`,
    fc_brier: (b, n) => `Accuracy of the last ${n} forecasts: Brier ${b} (coin flip 0.25; lower is better)`,
    fc_legend: "Line: probability of Yes, as estimated the day before. Dots at top and bottom: actual result (green Yes, red No).",
    fc_note: "A statistical estimate from this station's history (its settings are re-tuned on past results with every update), refined during the day with the trains that have already arrived. No betting, no money, just statistics.",
    fc_no_service: "No long-distance trains (ICE, IC, EC) stop here at the moment (for example because of construction), so there is no forecast.",
    home_live: (kw, n) => `${kw} · LIVE · scoring day ${n} of 7`, home_done: (kw) => `${kw} · finished`,
    home_tables: "League tables", home_tables_sub: "All 8 leagues, one click to the table",
    home_regional: "+ 5 Regionalbahnhofsligen", home_ranking: "National ranking", home_top3: "Top 3", home_bottom3: "Bottom 3",
    home_ranking_sub: (kw) => `Top and bottom of all leagues, ${kw}`, home_ranking_btn: "View national ranking",
    home_search: "Find your station", home_search_ph: "Type a station, e.g. Nürnberg",
    home_search_sub: (n) => `${n} stations with regular long-distance service`, home_popular: "Busiest", home_search_none: "No station found. Only stations with regular ICE/IC/EC service are in the league.",
    home_week: "This week", home_leader: "Top of the BBL", home_climber: (d) => `Biggest climber ${d}`,
    home_climb_txt: (n) => `up ${n} places nationwide`, home_day: (d) => `Day winner nationwide ${d}`,
    home_how: "How it works",
    home_steps: [["1", "Points every day", "The share of ICE/IC/EC trains arriving on time: 0.82 means 82% on time."],
      ["2", "A season every week", "Monday to Sunday, ranked by average. The table changes every day."],
      ["3", "Promotion and relegation", "After every Sunday, stations move between leagues, from the regional leagues up to the BBL."]],
    home_rules: "All rules",
    map_title: "Map", map_intro: "How punctual are long-distance trains in your state, how late, how often cancelled? Punctuality uses a fixed colour scale (red under 45%, grey 45 to 55%, green over 55%); delays and cancellations are coloured compared with Germany as a whole.",
    map_period: ["Day", "Week", "4 weeks"], map_mode: ["Cumulative", "Single day"], map_dots: "Show stations",
    map_play: "Play", map_pause: "Pause",
    map_nat: (pct, n) => `Germany overall: ${pct}% on time (${n} arrivals)`,
    map_legend: ["clearly better than Germany", "similar (± 3 points)", "clearly worse", "no data"],
    map_range: (a, b) => (a === b ? a : `${a} to ${b}`), map_running: "The last day is still in progress.",
    map_tip: (pct, n, d) => `${pct}% on time · ${n} arrivals · ${d} points vs Germany`,
    map_cols: ["Pos", "State", "On time", "Arrivals", "vs Germany"],
    map_note: "All scheduled ICE/IC/EC arrivals in a state count, including stops that are not in the league. Every train counts once. Points = percentage points. Base map: Natural Earth.",
    rk_title: "National ranking", rk_intro: "All stations of all leagues in one table, ranked by the week's average.",
    rk_cols: ["Pos", "Station", "League", "State", "Days", "Avg"], rk_all: "All states", rk_link: "National ranking",
    rk_freq: (n) => n ? `Only stations with at least ${n} ICE/IC/EC arrivals on a typical day` : "All stations, however many trains",
    rk_presets: [["All", 0], ["30+", 30], ["60+", 60], ["Big hubs 100+", 100]],
    rk_count: (k, n) => `${k} of ${n} stations`, rk_per_day: "Trains/day", rk_nat: "Nationwide",
    rk_freq_note: "Trains/day = typical day (median of the last 28 days). With a filter, \"Pos\" is the rank within the selection.",
    st_rank: (r, n) => `${r} of ${n} nationwide`, st_state: (r, n, s) => `${r} of ${n} in ${s}`,
    st_rank_note: (kw, a) => `ranking ${kw} (last finished week), avg ${a}`,
    vol_avg: "ICE/IC/EC arrivals per day (avg)", vol_busiest: (d) => `busiest day, ${d}`,
    wd_title: "Weekdays", wd_note: "Average share of punctual trains per weekday. Green: best day, red: weakest day.",
    rec_title: "Records and streaks",
    rec: { best: "Best week", worst: "Weakest week", highest: "Highest league", titles: "Titles",
      moves: "Promotions / relegations", longest: "Longest streak at 0.60+", current: "Current streak at 0.60+",
      current_short: (d) => `current: ${d}` },
    n_days: (n) => `${n} ${n === 1 ? "day" : "days"}`, place: (r, l) => `${r}. in the ${l}`,
    st_title: "Station", st_none: "not in a league this week", st_missing: "Station not found",
    st_error: (m) => `The page could not be loaded. Please reload. (${m})`,
    kpi: ["average share of punctual trains per day", "scored days", "best day", "worst day"],
    chart_title: "Share of punctual trains per day (last 120 days)",
    chart_note: "Each bar is one scoring day: share of ICE/IC/EC arrivals under 6 minutes late. Green 0.85 or more, grey 0.70 to 0.85, red below 0.70. Thin ticks at the baseline: not scored (fewer than 5 arrivals).",
    arrivals: "arrivals",
    pyr_title: "League journey",
    pyr_note: "Each dot is one season (week): the higher, the better the league and the place in it. Green: promoted, red: relegated, amber ring: moved up to fill a gap, hollow: current week.",
    filled: { spared: "moved up to fill a gap (relegation spared)", next_best: "moved up to fill a gap (best place of the league below)" },
    fills_title: "Filled gaps at the start of the season", dropped_title: (n) => `Dropped out: ${n} stations had at least 5 ICE/IC/EC arrivals on fewer than half of the last 28 days`,
    hist_title: "Season history", hist_cols: ["Season", "League", "Pos", "Days", "Avg"],
    titles: { "index.html": "Bundesbahnhofsliga · The league of railway stations", "tables.html": "Tables · Bundesbahnhofsliga", "champions.html": "Champions · Bundesbahnhofsliga", "ranking.html": "Ranking · Bundesbahnhofsliga", "map.html": "Map · Bundesbahnhofsliga", "stats.html": "Statistics · Bundesbahnhofsliga", "rules.html": "Rules · Bundesbahnhofsliga", "about.html": "Methodology · Bundesbahnhofsliga" },
    ch_title: "Roll of champions", ch_intro: "Who finished the week on top? A season is one calendar week.",
    ch_cols: ["Season", "Champion", "Avg", "Runner-up"], ch_live: "live, currently leading", ch_promoted: "promoted",
    ch_record: "Most titles", ch_titles: (n) => `${n} ${n === 1 ? "title" : "titles"}`, ch_none: "No finished season yet.",
    ch_link: "Champions of this league",
  },
};
const T = STR[LANG];
const dayLabel = (iso) => { const d = new Date(iso + "T12:00:00"); return `${T.days[d.getDay()]} ${d.getDate()}.${d.getMonth() + 1}.`; };
const num = (x, d = 2) => (LANG === "de" ? fmt(x, d).replace(".", ",") : fmt(x, d));

function langLink(l) {
  const p = new URLSearchParams(location.search);
  p.set("lang", l);
  return `?${p.toString()}`;
}

function chrome(active) {
  const pages = ["index.html", "tables.html", "ranking.html", "map.html", "stats.html", "champions.html", "rules.html", "about.html"];
  if (T.titles[active]) document.title = T.titles[active];
  document.body.insertAdjacentHTML("afterbegin", `
    <header class="top"><div class="wrap">
      <img src="assets/logos/bbl.svg" alt="">
      <h1><a href="index.html?lang=${LANG}">Bundesbahnhofsliga</a></h1>
      <nav>${pages.map((h, i) => `<a href="${h}?lang=${LANG}" class="${h === active ? "on" : ""}">${T.nav[i]}</a>`).join("")}
        <span class="lang" role="group" aria-label="Sprache / Language">
          <a href="${langLink("de")}" class="${LANG === "de" ? "on" : ""}" hreflang="de" lang="de">DE</a><a
             href="${langLink("en")}" class="${LANG === "en" ? "on" : ""}" hreflang="en" lang="en">EN</a>
        </span>
      </nav>
    </div></header><div class="stripe"></div>`);
  document.body.insertAdjacentHTML("beforeend", `
    <footer><div class="wrap">${T.footer}
      <span id="updated"></span> · <a href="https://github.com/Awthura/bundesbahnhofsliga">Code</a>
    </div></footer>`);
  // keep the language when following internal links
  document.querySelectorAll('a[href]').forEach((a) => {
    const h = a.getAttribute("href");
    if (/^(index|tables|ranking|map|stats|champions|rules|about|station)\.html/.test(h) && !/[?&]lang=/.test(h)) a.setAttribute("href", h + (h.includes("?") ? "&" : "?") + "lang=" + LANG);
  });
}

// station links built later also carry the language
const stLink = (eva) => `station.html?eva=${encodeURIComponent(eva)}&lang=${LANG}`;

function formChips(form) {
  return `<span class="form">${form.map((p) => {
    if (p == null) return `<i class="x" title="${T.called_off}">–</i>`;
    const c = p >= 0.85 ? "var(--up)" : p >= 0.7 ? "#8c8c8c" : "var(--red)";
    return `<i style="background:${c}" title="${num(p)}">${fmt(p).replace(/^0/, "").replace(/^1\.00$/, "1")}</i>`;
  }).join("")}</span>`;
}

function trendCell(t) {
  if (t == null) return `<span class="trend s">·</span>`;
  if (t > 0) return `<span class="trend u">▲${t}</span>`;
  if (t < 0) return `<span class="trend d">▼${-t}</span>`;
  return `<span class="trend s">=</span>`;
}

function tableHTML(rows, zones, status) {
  const n = rows.length, c = T.cols;
  return `<div class="tablewrap"><table>
    <thead><tr><th>${c[0]}</th><th></th><th>${c[1]}</th><th class="num">${c[2]}</th><th class="num hide-sm">${c[3]}</th>
    <th class="num">${c[4]}</th><th class="num hide-sm" title="${esc(T.canc_tip)}">${T.col_canc}</th><th class="hide-sm">${c[5]}</th></tr></thead><tbody>
    ${rows.map((r, i) => {
      const po = (zones.po_up && i === zones.up) || (zones.po_down && i === n - zones.down - 1);
      const cls = [i < zones.up ? "up" : "", i >= n - zones.down ? "down" : "", po ? "po" : "", r.ranked ? "" : "unranked"].join(" ");
      const tag = status[r.eva] === "new" ? `<span class="tag new">${T.new_tag}</span>` : "";
      return `<tr class="${cls}"><td class="rank">${r.rank}.</td><td>${trendCell(r.trend)}</td>
        <td class="st"><a href="${stLink(r.eva)}">${esc(r.station)}</a>${tag}</td>
        <td class="num">${r.played}</td><td class="num hide-sm">${num(r.points)}</td><td class="num"><b>${num(r.avg, 3)}</b></td>
        <td class="num hide-sm" style="color:var(--muted)">${cancPct(r.canceled || 0, r.arrivals || 0)}</td>
        <td class="hide-sm">${formChips(r.form)}</td></tr>`;
    }).join("")}</tbody></table></div>`;
}

// cancellation rate as "1,2 %" (shown only; cancellations already count as not punctual)
const cancPct = (c, a) => (a ? `${num((100 * c) / a, 1)} %` : "–");

// two donuts: all arrivals (on time / late / cancelled) and the disruptions alone (delay ranges + cancelled)
function donut(parts, centre, label, id) {
  const total = parts.reduce((t, p) => t + p.n, 0), R = 72, r0 = 46, c = 75;
  const pt = (a, rad) => [c + rad * Math.sin(a), c - rad * Math.cos(a)];
  let a = 0, g = `<defs><pattern id="h${id}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
    <rect width="6" height="6" fill="var(--mx-canc)"/><line x1="0" y1="0" x2="0" y2="6" stroke="var(--mx-hatch)" stroke-width="2"/></pattern></defs>`;
  for (const p of parts) {
    if (!p.n) continue;
    const share = p.n / total, fill = p.hatch ? `url(#h${id})` : p.col, tip = `${p.label}: ${p.n.toLocaleString(LANG)} (${num(share * 100, 1)} %)`;
    if (share > 0.9999) {   // a full ring cannot be drawn as one arc
      g += `<path d="M${c},${c - R}A${R},${R} 0 1 1 ${c - 0.01},${c - R}L${c - 0.01},${c - r0}A${r0},${r0} 0 1 0 ${c},${c - r0}Z" fill="${fill}"><title>${esc(tip)}</title></path>`;
      break;
    }
    const b = a + share * 2 * Math.PI, big = b - a > Math.PI ? 1 : 0;
    const [x1, y1] = pt(a, R), [x2, y2] = pt(b, R), [x3, y3] = pt(b, r0), [x4, y4] = pt(a, r0);
    g += `<path d="M${x1},${y1}A${R},${R} 0 ${big} 1 ${x2},${y2}L${x3},${y3}A${r0},${r0} 0 ${big} 0 ${x4},${y4}Z" fill="${fill}"><title>${esc(tip)}</title></path>`;
    a = b;
  }
  g += `<text x="${c}" y="${c + 2}" text-anchor="middle" font-size="20" font-weight="700" fill="var(--ink)">${total.toLocaleString(LANG)}</text>
    <text x="${c}" y="${c + 18}" text-anchor="middle" font-size="11" fill="var(--muted)">${esc(centre)}</text>`;
  const leg = parts.map((p) => `<li><i style="background:${p.hatch ? `repeating-linear-gradient(45deg,var(--mx-canc) 0 3px,var(--mx-hatch) 3px 5px)` : p.col}"></i>
    <span>${esc(p.label)}</span><span class="n">${p.n.toLocaleString(LANG)}</span><span class="p">${total ? num((p.n / total) * 100, 1) : "0"} %</span></li>`).join("");
  return `<div class="mix-card"><svg viewBox="0 0 150 150" role="img" aria-label="${esc(label)}">${g}</svg>
    <div style="flex:1;min-width:0"><h4>${esc(label)}</h4><ul class="mix-leg">${leg}</ul></div></div>`;
}

async function stamp(meta) {
  const u = $("#updated");
  if (u && meta) u.textContent = T.updated(meta.last_day, meta.generated.replace("T", " "));
}

// on phones the tab and day rows scroll sideways: bring the active one into view
function revealActive(container) {
  const el = container && container.querySelector(".on");
  if (el && container.scrollWidth > container.clientWidth) container.scrollLeft = el.offsetLeft - container.offsetLeft - 16;
}

// all leagues' tables after day k merged into one national table (same order as a league table)
function nationalTable(s, k) {
  const rows = [];
  for (const l of s.league_order) for (const r of s.leagues[l].tables[k] || []) rows.push({ ...r, league: l });
  // tie on average: the station with more traffic (ICE/IC/EC arrivals this week) wins
  rows.sort((a, b) => (a.ranked === b.ranked ? 0 : a.ranked ? -1 : 1) || b.avg - a.avg
    || (b.arrivals || 0) - (a.arrivals || 0) || b.points - a.points || a.station.localeCompare(b.station));
  rows.forEach((r, i) => (r.nrank = i + 1));
  return rows;
}

// search: case, accents and "ue/oe/ae/ss" spellings don't matter ("nurnberg" = "Nuernberg" = "Nürnberg")
function fold(t) {
  return String(t).toLowerCase().replace(/ß/g, "ss").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/ae/g, "a").replace(/oe/g, "o").replace(/ue/g, "u").replace(/[^a-z0-9]+/g, " ").trim();
}

// label for a day button: "in progress" only for today (Berlin), "data pending" for a past day not yet complete
const dayButton = (d, i, meta) => `${i + 1} · ${dayLabel(d)}${d === meta.running ? ` <span class="running">· ${T.running}</span>`
  : (meta.pending || []).includes(d) ? ` <span class="running">· ${T.pending}</span>` : ""}`;

// live week: which scoring day it is by the calendar, and a note when today has no data yet
function liveWeek(s, meta) {
  const inWeek = meta.today >= s.start && meta.today <= s.end;
  const n = inWeek ? Math.round((Date.parse(meta.today) - Date.parse(s.start)) / 864e5) + 1 : s.matchdays.length;
  const note = inWeek && !meta.running ? T.no_data_today : "";
  return { n, note };
}

// single-day view: rank by one day's points; the day's arrivals = week-to-date arrivals minus the day before
function dayRows(rows, prevRows) {
  const before = Object.fromEntries((prevRows || []).map((r) => [r.eva, [r.arrivals || 0, r.canceled || 0]]));
  const out = rows.map((r) => ({ ...r, day_points: r.form[r.form.length - 1], day_arrivals: (r.arrivals || 0) - (before[r.eva]?.[0] || 0),
    day_canceled: (r.canceled || 0) - (before[r.eva]?.[1] || 0) }));
  out.sort((a, b) => (a.day_points == null) - (b.day_points == null) || (b.day_points ?? 0) - (a.day_points ?? 0)
    || b.day_arrivals - a.day_arrivals || a.station.localeCompare(b.station));
  return out;
}

function dayTableHTML(rows, leagueOf) {
  const c = T.day_cols;
  return `<div class="tablewrap"><table>
    <thead><tr><th>${c[0]}</th><th>${c[1]}</th>${leagueOf ? "<th></th>" : ""}<th class="num hide-sm">${c[2]}</th><th class="num hide-sm" title="${esc(T.canc_tip)}">${T.col_canc}</th><th class="num">${c[3]}</th></tr></thead><tbody>
    ${rows.map((r, i) => `<tr class="${r.day_points == null ? "unranked" : ""}">
      <td class="rank">${r.day_points == null ? "–" : i + 1 + "."}</td>
      <td class="st"><a href="${stLink(r.eva)}">${esc(r.station)}</a></td>
      ${leagueOf ? `<td><img src="${logo(leagueOf(r))}" alt="" style="width:16px;height:19px;vertical-align:-4px"></td>` : ""}
      <td class="num hide-sm">${r.day_arrivals}</td>
      <td class="num hide-sm" style="color:var(--muted)">${r.day_canceled || 0}</td>
      <td class="num"><b>${r.day_points == null ? T.called_off : num(r.day_points)}</b></td></tr>`).join("")}
    </tbody></table></div>`;
}

function viewToggle(state, rerender) {
  return `<span class="view-toggle">${[["week", T.view_week], ["day", T.view_day]].map(([v, lbl]) =>
    `<button class="${state.view === v ? "on" : ""}" data-view="${v}">${lbl}</button>`).join("")}</span>`;
}
function bindViewToggle(el, state, rerender) {
  el.querySelectorAll("button[data-view]").forEach((b) => (b.onclick = () => {
    state.view = b.dataset.view;
    const p = new URLSearchParams(location.search);
    if (state.view === "day") p.set("view", "day"); else p.delete("view");
    history.replaceState(null, "", "?" + p.toString());
    rerender();
  }));
}
