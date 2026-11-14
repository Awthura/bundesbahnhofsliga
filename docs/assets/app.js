// Bundesbahnhofsliga: tiny static frontend, no build step.
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const getJSON = (p) => fetch(p, { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(p); return r.json(); });
const fmt = (x, d = 2) => (x == null ? "-" : Number(x).toFixed(d));
const DAYS = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
const dayLabel = (iso) => { const d = new Date(iso + "T12:00:00"); return `${DAYS[d.getDay()]} ${d.getDate()}.${d.getMonth() + 1}.`; };
const logo = (lid) => `assets/logos/liga-${lid}.svg`;

function chrome(active) {
  const nav = [["index.html", "Tabellen"], ["rules.html", "Regeln"], ["about.html", "Methodik"]];
  document.body.insertAdjacentHTML("afterbegin", `
    <header class="top"><div class="wrap">
      <img src="assets/logos/bbl.svg" alt="">
      <h1><a href="index.html">Bundesbahnhofsliga</a></h1>
      <nav>${nav.map(([h, t]) => `<a href="${h}" class="${h === active ? "on" : ""}">${t}</a>`).join("")}</nav>
    </div></header><div class="stripe"></div>`);
  document.body.insertAdjacentHTML("beforeend", `
    <footer><div class="wrap">
      Fan project, not affiliated with Deutsche Bahn. Data: Deutsche Bahn Timetables API via
      <a href="https://huggingface.co/datasets/piebro/deutsche-bahn-data">piebro/deutsche-bahn-data</a>, CC BY 4.0.
      Rankings describe punctuality as passengers see it at a station; they say nothing about who caused a delay.
      <span id="updated"></span> · <a href="https://github.com/Awthura/bundesbahnhofsliga">Code</a>
    </div></footer>`);
}

function formChips(form) {
  return `<span class="form">${form.map((p) => {
    if (p == null) return `<i class="x" title="abgesagt">–</i>`;
    const c = p >= 0.85 ? "var(--up)" : p >= 0.7 ? "#8c8c8c" : "var(--red)";
    return `<i style="background:${c}" title="${fmt(p)}">${fmt(p).replace(/^0/, "").replace(/^1\.00$/, "1")}</i>`;
  }).join("")}</span>`;
}

function trendCell(t) {
  if (t == null) return `<span class="trend s">·</span>`;
  if (t > 0) return `<span class="trend u">▲${t}</span>`;
  if (t < 0) return `<span class="trend d">▼${-t}</span>`;
  return `<span class="trend s">=</span>`;
}

function tableHTML(rows, zones, status) {
  const n = rows.length;
  return `<div class="tablewrap"><table>
    <thead><tr><th>Platz</th><th></th><th>Bahnhof</th><th class="num">Spiele</th><th class="num">Punkte</th>
    <th class="num">Schnitt</th><th class="hide-sm">Form</th></tr></thead><tbody>
    ${rows.map((r, i) => {
      const po = (zones.po_up && i === zones.up) || (zones.po_down && i === n - zones.down - 1);
      const cls = [i < zones.up ? "up" : "", i >= n - zones.down ? "down" : "", po ? "po" : "", r.ranked ? "" : "unranked"].join(" ");
      const tag = status[r.eva] === "new" ? `<span class="tag new">NEU</span>` : "";
      return `<tr class="${cls}"><td class="rank">${r.rank}.</td><td>${trendCell(r.trend)}</td>
        <td class="st"><a href="station.html?eva=${r.eva}">${esc(r.station)}</a>${tag}</td>
        <td class="num">${r.played}</td><td class="num">${fmt(r.points)}</td><td class="num"><b>${fmt(r.avg, 3)}</b></td>
        <td class="hide-sm">${formChips(r.form)}</td></tr>`;
    }).join("")}</tbody></table></div>`;
}

async function stamp(meta) {
  const u = $("#updated");
  if (u && meta) u.textContent = `Data through ${meta.last_day}, built ${meta.generated.replace("T", " ")} UTC.`;
}
