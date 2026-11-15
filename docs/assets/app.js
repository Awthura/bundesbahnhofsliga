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
    nav: ["Home", "Tabellen", "Rangliste", "Meister", "Regeln", "Methodik"],
    footer: `Fanprojekt, nicht mit der Deutschen Bahn verbunden. Daten: Deutsche Bahn Timetables API über
      <a href="https://huggingface.co/datasets/piebro/deutsche-bahn-data">piebro/deutsche-bahn-data</a>, CC BY 4.0.
      Die Tabellen zeigen die Pünktlichkeit, wie Fahrgäste sie am Bahnhof erleben; über die Ursache einer Verspätung sagen sie nichts.`,
    updated: (d, g) => `Daten bis ${d}, erstellt ${g} UTC.`,
    days: ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"],
    cols: ["Platz", "Bahnhof", "Tage", "Punkte", "Schnitt", "Form"],
    called_off: "nicht gewertet", new_tag: "NEU", live: "LIVE",
    season_label: "Saison (KW)", to: "bis",
    season_done: "Saison beendet, Auf- und Abstieg vollzogen.",
    season_live: (n) => `Wertungstag ${n} von 7. Auf- und Abstieg nach dem Sonntag.`,
    sub: (n, id, day) => `${n} Bahnhöfe · Saison ${id} · Tabelle nach ${day}`,
    matchday: "Wertungstag",
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
    fc_title: "Prognose für morgen",
    fc_q: (n, d, t) => `Kommen am ${d} mindestens ${t} % der Fernzüge in ${n} pünktlich an?`,
    yes: "Ja", no: "Nein",
    fc_expected: (e, l, h) => `Erwartet: ${e} % pünktlich (80-%-Bereich ${l} bis ${h} %)`,
    fc_brier: (b, n) => `Treffsicherheit der letzten ${n} Prognosen: Brier ${b} (Münzwurf 0,25; kleiner ist besser)`,
    fc_legend: "Linie: Wahrscheinlichkeit für Ja, jeweils am Vortag geschätzt. Punkte oben und unten: tatsächliches Ergebnis (grün Ja, rot Nein).",
    fc_note: "Statistische Schätzung aus den letzten 8 Wochen dieses Bahnhofs; jüngere Tage und der gleiche Wochentag zählen mehr. Keine Wette, kein Geld, nur Statistik.",
    fc_no_service: "Zurzeit halten hier keine Fernzüge (ICE, IC, EC) (zum Beispiel wegen Bauarbeiten), deshalb gibt es keine Prognose.",
    home_live: (kw, n) => `${kw} · LIVE · Wertungstag ${n} von 7`, home_done: (kw) => `${kw} · abgeschlossen`,
    home_tables: "Ligatabellen", home_tables_sub: "Alle 8 Ligen, ein Klick zur Tabelle",
    home_regional: "+ 5 Regionalbahnhofsligen", home_ranking: "Bundesweite Rangliste",
    home_ranking_sub: (kw) => `Die besten Bahnhöfe aller Ligen, ${kw}`, home_ranking_btn: "Bundesweite Rangliste ansehen",
    home_search: "Finde deinen Bahnhof", home_search_ph: "Bahnhof eingeben, z. B. Nürnberg",
    home_search_sub: (n) => `${n} Bahnhöfe mit regelmäßigem Fernverkehr`, home_popular: "Die größten", home_search_none: "Kein Bahnhof gefunden. Nur Bahnhöfe mit regelmäßigem ICE/IC/EC-Verkehr sind in der Liga.",
    home_week: "Diese Woche", home_leader: "Tabellenführer BBL", home_climber: (d) => `Größter Sprung ${d}`,
    home_climb_txt: (n) => `${n} Plätze nach oben, bundesweit`, home_day: (d) => `Tagessieger bundesweit ${d}`,
    home_how: "So funktioniert's",
    home_steps: [["1", "Jeden Tag Punkte", "Anteil der ICE/IC/EC, die pünktlich ankommen: 0,82 heißt 82 % pünktlich."],
      ["2", "Jede Woche eine Saison", "Montag bis Sonntag, sortiert nach dem Schnitt. Die Tabelle ändert sich jeden Tag."],
      ["3", "Auf- und Abstieg", "Nach jedem Sonntag wechseln Bahnhöfe die Liga, von den Regionalbahnhofsligen bis in die BBL."]],
    home_rules: "Alle Regeln",
    rk_title: "Bundesweite Rangliste", rk_intro: "Alle Bahnhöfe aller Ligen in einer Tabelle, sortiert nach dem Schnitt der Woche.",
    rk_cols: ["Platz", "Bahnhof", "Liga", "Bundesland", "Tage", "Schnitt"], rk_all: "Alle Bundesländer", rk_link: "Bundesweite Rangliste",
    rk_freq: (n) => n ? `Nur Bahnhöfe mit mindestens ${n} ICE/IC/EC-Ankünften an einem typischen Tag` : "Alle Bahnhöfe, egal wie viele Züge",
    rk_presets: [["Alle", 0], ["ab 30", 30], ["ab 60", 60], ["Große Knoten ab 100", 100]],
    rk_count: (k, n) => `${k} von ${n} Bahnhöfen`, rk_per_day: "Züge/Tag", rk_nat: "Bundesweit",
    rk_freq_note: "Züge/Tag = typischer Tag (Median der letzten 28 Tage). Mit Filter zeigt „Platz“ den Rang innerhalb der Auswahl.",
    st_rank: (r, n) => `${r}. von ${n} bundesweit`, st_state: (r, n, s) => `${r}. von ${n} in ${s}`,
    st_rank_note: (kw, a) => `Rangliste ${kw} (letzte abgeschlossene Woche), Schnitt ${a}`,
    vol_avg: "ICE/IC/EC-Ankünfte pro Tag (Ø)", vol_busiest: (d) => `meiste Ankünfte, ${d}`,
    wd_title: "Wochentage", wd_note: "Durchschnittliche Tagespunkte je Wochentag. Grün: bester Tag, rot: schwächster Tag.",
    rec_title: "Rekorde und Serien",
    rec: { best: "Beste Woche", worst: "Schwächste Woche", highest: "Höchste Liga", titles: "Meistertitel",
      moves: "Aufstiege / Abstiege", longest: "Längste Serie ab 0,60", current: "Aktuelle Serie ab 0,60" },
    n_days: (n) => `${n} ${n === 1 ? "Tag" : "Tage"}`, place: (r, l) => `${r}. in der ${l}`,
    st_title: "Bahnhof", st_none: "diese Woche in keiner Liga", st_missing: "Bahnhof nicht gefunden",
    st_error: (m) => `Die Seite konnte nicht geladen werden. Bitte neu laden. (${m})`,
    kpi: ["Durchschnitt Tagespunkte", "gewertete Tage", "bester Tag", "schlechtester Tag"],
    chart_title: "Tagespunkte (letzte 120 Tage)",
    chart_note: "Jeder Balken ist ein Wertungstag: Anteil der ICE/IC/EC-Ankünfte mit weniger als 6 Minuten Verspätung. Grün ab 0,85, grau 0,70 bis 0,85, rot unter 0,70. Dünne Striche an der Grundlinie: nicht gewertet (weniger als 5 Ankünfte).",
    arrivals: "Ankünfte",
    pyr_title: "Ligaverlauf",
    pyr_note: "Jeder Punkt ist eine Saison (KW): je höher, desto besser die Liga und der Platz darin. Grün: aufgestiegen, rot: abgestiegen, gelber Ring: zu Saisonbeginn nachgerückt, hohl: laufende Woche.",
    filled: { spared: "nachgerückt (Abstieg erlassen)", next_best: "nachgerückt (bester Platz der Liga darunter)" },
    fills_title: "Nachrücker zu Saisonbeginn", dropped_title: (n) => `Ausgeschieden: ${n} Bahnhöfe hatten an weniger als der Hälfte der letzten 28 Tage mindestens 5 ICE/IC/EC-Ankünfte`,
    hist_title: "Saisonverlauf", hist_cols: ["Saison", "Liga", "Platz", "Tage", "Schnitt"],
    titles: { "index.html": "Bundesbahnhofsliga · Die Liga der Bahnhöfe", "tables.html": "Tabellen · Bundesbahnhofsliga", "champions.html": "Meister · Bundesbahnhofsliga", "ranking.html": "Rangliste · Bundesbahnhofsliga", "rules.html": "Regeln · Bundesbahnhofsliga", "about.html": "Methodik · Bundesbahnhofsliga" },
    ch_title: "Meisterliste", ch_intro: "Wer stand am Ende der Woche ganz oben? Eine Saison ist eine Kalenderwoche.",
    ch_cols: ["Saison", "Meister", "Schnitt", "Vizemeister"], ch_live: "läuft, führt gerade", ch_promoted: "aufgestiegen",
    ch_record: "Rekordmeister", ch_titles: (n) => `${n} ${n === 1 ? "Titel" : "Titel"}`, ch_none: "Noch keine abgeschlossene Saison.",
    ch_link: "Meisterliste dieser Liga",
  },
  en: {
    nav: ["Home", "Tables", "Ranking", "Champions", "Rules", "Methodology"],
    footer: `Fan project, not affiliated with Deutsche Bahn. Data: Deutsche Bahn Timetables API via
      <a href="https://huggingface.co/datasets/piebro/deutsche-bahn-data">piebro/deutsche-bahn-data</a>, CC BY 4.0.
      Rankings describe punctuality as passengers see it at a station; they say nothing about who caused a delay.`,
    updated: (d, g) => `Data through ${d}, built ${g} UTC.`,
    days: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    cols: ["Pos", "Station", "Days", "Points", "Avg", "Form"],
    called_off: "not scored", new_tag: "NEW", live: "LIVE",
    season_label: "Season (week)", to: "to",
    season_done: "Season finished, promotion and relegation applied.",
    season_live: (n) => `Scoring day ${n} of 7. Promotion and relegation after Sunday.`,
    sub: (n, id, day) => `${n} stations · season ${id} · table after ${day}`,
    matchday: "Scoring day",
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
    fc_title: "Forecast for tomorrow",
    fc_q: (n, d, t) => `Will at least ${t}% of long-distance trains arrive on time at ${n} on ${d}?`,
    yes: "Yes", no: "No",
    fc_expected: (e, l, h) => `Expected: ${e}% on time (80% range ${l}% to ${h}%)`,
    fc_brier: (b, n) => `Accuracy of the last ${n} forecasts: Brier ${b} (coin flip 0.25; lower is better)`,
    fc_legend: "Line: probability of Yes, as estimated the day before. Dots at top and bottom: actual result (green Yes, red No).",
    fc_note: "A statistical estimate from this station's last 8 weeks; recent days and the same weekday count more. No betting, no money, just statistics.",
    fc_no_service: "No long-distance trains (ICE, IC, EC) stop here at the moment (for example because of construction), so there is no forecast.",
    home_live: (kw, n) => `${kw} · LIVE · scoring day ${n} of 7`, home_done: (kw) => `${kw} · finished`,
    home_tables: "League tables", home_tables_sub: "All 8 leagues, one click to the table",
    home_regional: "+ 5 Regionalbahnhofsligen", home_ranking: "National ranking",
    home_ranking_sub: (kw) => `The best stations of all leagues, ${kw}`, home_ranking_btn: "View national ranking",
    home_search: "Find your station", home_search_ph: "Type a station, e.g. Nürnberg",
    home_search_sub: (n) => `${n} stations with regular long-distance service`, home_popular: "Busiest", home_search_none: "No station found. Only stations with regular ICE/IC/EC service are in the league.",
    home_week: "This week", home_leader: "Top of the BBL", home_climber: (d) => `Biggest climber ${d}`,
    home_climb_txt: (n) => `up ${n} places nationwide`, home_day: (d) => `Day winner nationwide ${d}`,
    home_how: "How it works",
    home_steps: [["1", "Points every day", "The share of ICE/IC/EC trains arriving on time: 0.82 means 82% on time."],
      ["2", "A season every week", "Monday to Sunday, ranked by average. The table changes every day."],
      ["3", "Promotion and relegation", "After every Sunday, stations move between leagues, from the regional leagues up to the BBL."]],
    home_rules: "All rules",
    rk_title: "National ranking", rk_intro: "All stations of all leagues in one table, ranked by the week's average.",
    rk_cols: ["Pos", "Station", "League", "State", "Days", "Avg"], rk_all: "All states", rk_link: "National ranking",
    rk_freq: (n) => n ? `Only stations with at least ${n} ICE/IC/EC arrivals on a typical day` : "All stations, however many trains",
    rk_presets: [["All", 0], ["30+", 30], ["60+", 60], ["Big hubs 100+", 100]],
    rk_count: (k, n) => `${k} of ${n} stations`, rk_per_day: "Trains/day", rk_nat: "Nationwide",
    rk_freq_note: "Trains/day = typical day (median of the last 28 days). With a filter, \"Pos\" is the rank within the selection.",
    st_rank: (r, n) => `${r} of ${n} nationwide`, st_state: (r, n, s) => `${r} of ${n} in ${s}`,
    st_rank_note: (kw, a) => `ranking ${kw} (last finished week), avg ${a}`,
    vol_avg: "ICE/IC/EC arrivals per day (avg)", vol_busiest: (d) => `busiest day, ${d}`,
    wd_title: "Weekdays", wd_note: "Average daily points per weekday. Green: best day, red: weakest day.",
    rec_title: "Records and streaks",
    rec: { best: "Best week", worst: "Weakest week", highest: "Highest league", titles: "Titles",
      moves: "Promotions / relegations", longest: "Longest streak at 0.60+", current: "Current streak at 0.60+" },
    n_days: (n) => `${n} ${n === 1 ? "day" : "days"}`, place: (r, l) => `${r}. in the ${l}`,
    st_title: "Station", st_none: "not in a league this week", st_missing: "Station not found",
    st_error: (m) => `The page could not be loaded. Please reload. (${m})`,
    kpi: ["average daily points", "scored days", "best day", "worst day"],
    chart_title: "Daily points (last 120 days)",
    chart_note: "Each bar is one scoring day: share of ICE/IC/EC arrivals under 6 minutes late. Green 0.85 or more, grey 0.70 to 0.85, red below 0.70. Thin ticks at the baseline: not scored (fewer than 5 arrivals).",
    arrivals: "arrivals",
    pyr_title: "League journey",
    pyr_note: "Each dot is one season (week): the higher, the better the league and the place in it. Green: promoted, red: relegated, amber ring: moved up to fill a gap, hollow: current week.",
    filled: { spared: "moved up to fill a gap (relegation spared)", next_best: "moved up to fill a gap (best place of the league below)" },
    fills_title: "Filled gaps at the start of the season", dropped_title: (n) => `Dropped out: ${n} stations had at least 5 ICE/IC/EC arrivals on fewer than half of the last 28 days`,
    hist_title: "Season history", hist_cols: ["Season", "League", "Pos", "Days", "Avg"],
    titles: { "index.html": "Bundesbahnhofsliga · The league of railway stations", "tables.html": "Tables · Bundesbahnhofsliga", "champions.html": "Champions · Bundesbahnhofsliga", "ranking.html": "Ranking · Bundesbahnhofsliga", "rules.html": "Rules · Bundesbahnhofsliga", "about.html": "Methodology · Bundesbahnhofsliga" },
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
  const pages = ["index.html", "tables.html", "ranking.html", "champions.html", "rules.html", "about.html"];
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
    if (/^(index|tables|ranking|champions|rules|about|station)\.html/.test(h) && !/[?&]lang=/.test(h)) a.setAttribute("href", h + (h.includes("?") ? "&" : "?") + "lang=" + LANG);
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
    <th class="num">${c[4]}</th><th class="hide-sm">${c[5]}</th></tr></thead><tbody>
    ${rows.map((r, i) => {
      const po = (zones.po_up && i === zones.up) || (zones.po_down && i === n - zones.down - 1);
      const cls = [i < zones.up ? "up" : "", i >= n - zones.down ? "down" : "", po ? "po" : "", r.ranked ? "" : "unranked"].join(" ");
      const tag = status[r.eva] === "new" ? `<span class="tag new">${T.new_tag}</span>` : "";
      return `<tr class="${cls}"><td class="rank">${r.rank}.</td><td>${trendCell(r.trend)}</td>
        <td class="st"><a href="${stLink(r.eva)}">${esc(r.station)}</a>${tag}</td>
        <td class="num">${r.played}</td><td class="num hide-sm">${num(r.points)}</td><td class="num"><b>${num(r.avg, 3)}</b></td>
        <td class="hide-sm">${formChips(r.form)}</td></tr>`;
    }).join("")}</tbody></table></div>`;
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
  rows.sort((a, b) => (a.ranked === b.ranked ? 0 : a.ranked ? -1 : 1) || b.avg - a.avg || b.points - a.points || a.station.localeCompare(b.station));
  rows.forEach((r, i) => (r.nrank = i + 1));
  return rows;
}

// search: case, accents and "ue/oe/ae/ss" spellings don't matter ("nurnberg" = "Nuernberg" = "Nürnberg")
function fold(t) {
  return String(t).toLowerCase().replace(/ß/g, "ss").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/ae/g, "a").replace(/oe/g, "o").replace(/ue/g, "u").replace(/[^a-z0-9]+/g, " ").trim();
}
