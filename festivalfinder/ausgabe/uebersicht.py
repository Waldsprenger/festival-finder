"""Eine durchsuchbare HTML-Übersicht des ganzen Bestands.

Nicht die Webseite, sondern das Arbeitsblatt dazu: eine Tabelle mit allen
Festivals, ihren Quellen und ihren Lineups. Für den Blick von außen auf das,
was der Lauf zusammengetragen hat.
"""

import html
from collections import Counter

from ..kern.festival import Festival
from ..kern.zeit import deutsch
from ..pfade import DATA, schreib_text
from ..quellen import BAUPLAN

ZIEL = DATA / "uebersicht.html"


def esc(v) -> str:
    return html.escape(str(v or ""))


def kuerzel() -> dict[str, str]:
    """Zwei Buchstaben je Quelle — eindeutig, auch bei zwölf.

    Die meisten Namen beginnen mit „festival"; die ersten beiden Buchstaben
    ergäben also achtmal „FE". Genommen wird deshalb der erste Buchstabe plus
    der erste, der die Kürzel unterscheidet.
    """
    raus: dict[str, str] = {}
    for bauart in BAUPLAN:
        name = bauart.name
        rest = name[len("festival"):] if name.startswith("festival") else name[1:]
        kurz = (name[0] + (rest[0] if rest else name[1])).upper()
        i = 1
        while kurz in raus.values() and i < len(rest):
            kurz = (name[0] + rest[i]).upper()
            i += 1
        raus[name] = kurz
    return raus


def zeile(i: int, f: Festival, kurz: dict[str, str]) -> str:
    lineup = f.lineup
    anfang = ", ".join(lineup[:8])
    rest = ", ".join(lineup[8:])

    termin = deutsch(f.von)
    if f.bis and f.bis != f.von:
        termin += " – " + deutsch(f.bis)
    if not termin:
        termin = f'<span class="sub">{esc(f.hinweis or "Termin offen")}</span>'
    termin = (f'{esc(f.jahr)}<div class="sub">{termin}</div>' if not f.von
              else f'{termin}<div class="sub">{esc(f.jahr)}</div>')

    weblink = (f'<a href="{esc(f.webseite)}" target="_blank" rel="noopener">Website</a>'
               if f.webseite else "–")
    quellen = " ".join(
        f'<a class="src" href="{esc(u)}" target="_blank" rel="noopener">'
        f'{kurz.get(q, q[:2].upper())}</a>' for q, u in f.quellen.items())
    mehrfach = " multi" if len(f.quellen) > 1 else ""
    mehr = (f'<span class="rest" id="r{i}" hidden>, {esc(rest)}</span>'
            f'<button class="more" data-t="r{i}">+{len(lineup) - 8}</button>') if rest else ""
    flagge = '<span class="flag">Abgesagt</span> ' if f.abgesagt else ""
    suche = esc(" ".join([f.name, f.stadt, f.land, *lineup]).lower())

    return f"""<tr class="row{mehrfach}{' cancelled' if f.abgesagt else ''}" data-search="{suche}">
<td class="nm">{flagge}{esc(f.name)}<div class="sub">{esc(f.genre[:60])}</div></td>
<td class="dt">{termin}</td>
<td>{esc(f.location or f.stadt)}</td>
<td class="pr">{esc(f.preis) or '–'}</td>
<td>{weblink}</td>
<td class="lu"><span class="cnt">{len(lineup)}</span> {esc(anfang)}{mehr}</td>
<td class="sr">{quellen}</td></tr>"""


STIL = """
:root { color-scheme: light dark; --bg:#fff; --fg:#16181d; --mut:#6b7280;
  --line:#e5e7eb; --acc:#2563eb; --chip:#f3f4f6; }
@media (prefers-color-scheme: dark) { :root { --bg:#0f1115; --fg:#e8eaed;
  --mut:#9aa1ab; --line:#272b33; --acc:#7aa2f7; --chip:#1b1f27; } }
* { box-sizing:border-box; }
body { margin:0; padding:1.5rem; background:var(--bg); color:var(--fg);
  font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif; }
h1 { font-size:1.5rem; margin:0 0 .25rem; }
.meta { color:var(--mut); margin-bottom:1rem; }
.bar { display:flex; gap:.5rem; flex-wrap:wrap; align-items:center;
  margin-bottom:1rem; position:sticky; top:0; background:var(--bg);
  padding:.5rem 0; z-index:5; }
input[type=search] { flex:1; min-width:240px; padding:.55rem .7rem;
  border:1px solid var(--line); border-radius:8px; background:var(--chip);
  color:var(--fg); font-size:14px; }
button { padding:.4rem .7rem; border:1px solid var(--line); border-radius:6px;
  background:var(--chip); color:var(--fg); cursor:pointer; font-size:13px; }
button.on { border-color:var(--acc); color:var(--acc); }
.wrap { overflow-x:auto; border:1px solid var(--line); border-radius:10px; }
table { border-collapse:collapse; width:100%; min-width:1000px; }
th,td { padding:.55rem .7rem; border-bottom:1px solid var(--line);
  vertical-align:top; text-align:left; }
th { position:sticky; top:56px; background:var(--bg); font-size:12px;
  text-transform:uppercase; letter-spacing:.04em; color:var(--mut); z-index:4; }
.nm { font-weight:600; min-width:180px; }
.sub { font-weight:400; font-size:12px; color:var(--mut); }
.dt { white-space:nowrap; font-variant-numeric:tabular-nums; }
.pr { white-space:nowrap; }
.lu { font-size:13px; color:var(--fg); max-width:520px; }
.cnt { display:inline-block; min-width:1.6em; padding:0 .35em; margin-right:.4em;
  border-radius:5px; background:var(--chip); color:var(--mut); font-size:11px;
  text-align:center; }
.more { margin-left:.4em; padding:0 .35em; font-size:11px; }
a { color:var(--acc); }
.src { display:inline-block; padding:.1em .35em; margin-right:.2em;
  border-radius:4px; background:var(--chip); font-size:11px; text-decoration:none; }
.tags { display:flex; flex-wrap:wrap; gap:.35rem; margin:.5rem 0 1.25rem; }
.tag { background:var(--chip); border-radius:999px; padding:.2rem .6rem; font-size:12px; }
.tag b { color:var(--acc); }
tr.cancelled .nm { text-decoration:line-through; }
.flag { display:inline-block; background:#c62828; color:#fff; font-size:10px;
  font-weight:700; letter-spacing:.08em; text-transform:uppercase;
  padding:.05em .35em; border-radius:3px; margin-right:.35em;
  text-decoration:none; vertical-align:middle; }
"""

SKRIPT = """
const rows = [...document.querySelectorAll('#tb tr')];
const q = document.getElementById('q'), n = document.getElementById('n');
const fl = document.getElementById('fl'), fm = document.getElementById('fm');
let nurLineup = false, nurMehrfach = false;
function anwenden() {
  const term = q.value.trim().toLowerCase();
  let sichtbar = 0;
  for (const r of rows) {
    let ok = !term || r.dataset.search.includes(term);
    if (ok && nurLineup) ok = r.querySelector('.cnt').textContent !== '0';
    if (ok && nurMehrfach) ok = r.classList.contains('multi');
    r.hidden = !ok;
    if (ok) sichtbar++;
  }
  n.textContent = sichtbar + ' Treffer';
}
q.addEventListener('input', anwenden);
fl.addEventListener('click', () => { nurLineup = !nurLineup; fl.classList.toggle('on', nurLineup); anwenden(); });
fm.addEventListener('click', () => { nurMehrfach = !nurMehrfach; fm.classList.toggle('on', nurMehrfach); anwenden(); });
document.addEventListener('click', e => {
  const b = e.target.closest('.more'); if (!b) return;
  const s = document.getElementById(b.dataset.t);
  s.hidden = !s.hidden; b.textContent = s.hidden ? b.textContent : '−';
});
anwenden();
"""


def bauen(festivals: list[Festival]) -> dict:
    kurz = kuerzel()
    haeufig: Counter[str] = Counter()
    for f in festivals:
        haeufig.update(f.lineup)
    geteilt = [(b, c) for b, c in haeufig.most_common(40) if c > 1]

    zeilen = "".join(zeile(i, f, kurz) for i, f in enumerate(festivals))
    mit_lineup = sum(1 for f in festivals if f.lineup)
    mehrfach = sum(1 for f in festivals if len(f.quellen) > 1)
    tags = "".join(f'<span class="tag">{esc(b)} <b>{c}×</b></span>' for b, c in geteilt)

    doc = f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Festival-Übersicht weltweit</title>
<style>{STIL}</style></head><body>
<h1>Festival-Übersicht weltweit</h1>
<div class="meta">{len(festivals)} Festivals · {mit_lineup} mit Lineup ·
{mehrfach} aus mehreren Quellen · {len(haeufig)} normalisierte Acts ·
{len(BAUPLAN)} Quellen</div>

<div class="tags">{tags}</div>

<div class="bar">
  <input type="search" id="q" placeholder="Festival, Ort, Land oder Band suchen …">
  <button id="fl">nur mit Lineup</button>
  <button id="fm">nur Doppeltreffer</button>
  <span class="meta" id="n"></span>
</div>

<div class="wrap"><table>
<thead><tr><th>Festival</th><th>Datum</th><th>Ort</th><th>Preis</th><th>Web</th>
<th>Lineup</th><th>Quelle</th></tr></thead>
<tbody id="tb">
{zeilen}
</tbody></table></div>

<script>{SKRIPT}</script>
</body></html>"""

    schreib_text(ZIEL, doc)
    return {"mb": ZIEL.stat().st_size / 1e6, "festivals": len(festivals),
            "acts": len(haeufig)}
