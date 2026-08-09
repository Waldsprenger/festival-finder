"""Erzeugt aus data/festivals.json eine durchsuchbare HTML-Uebersicht."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "festivals.json"
OUTF = BASE / "data" / "uebersicht.html"


def esc(v: str) -> str:
    return html.escape(v or "")


def main() -> None:
    festivals = json.loads(DATA.read_text(encoding="utf-8"))

    band_count: Counter[str] = Counter()
    for f in festivals:
        band_count.update(f["lineup"])
    shared = [(b, c) for b, c in band_count.most_common(40) if c > 1]

    rows = []
    for i, f in enumerate(festivals):
        lineup = f["lineup"]
        preview = ", ".join(lineup[:8])
        rest = ", ".join(lineup[8:])
        date = f["date_from"]
        if f["date_to"] and f["date_to"] != f["date_from"]:
            date += " – " + f["date_to"]
        if not date:
            date = f'<span class="sub">{esc(f.get("note") or "Termin offen")}</span>'
        date = f'{esc(f["year"])}<div class="sub">{date}</div>' if not f["date_from"] \
            else f'{date}<div class="sub">{esc(f["year"])}</div>'
        web = f["website"]
        weblink = f'<a href="{esc(web)}" target="_blank" rel="noopener">Website</a>' if web else "–"
        srcs = " ".join(
            f'<a class="src" href="{esc(u)}" target="_blank" rel="noopener">{esc(s[:2].upper())}</a>'
            for s, u in f["sources"].items())
        multi = " multi" if len(f["sources"]) > 1 else ""
        more = (f'<span class="rest" id="r{i}" hidden>, {esc(rest)}</span>'
                f'<button class="more" data-t="r{i}">+{len(lineup) - 8}</button>') if rest else ""
        rows.append(f"""<tr class="row{multi}" data-search="{esc((f['name'] + ' ' + f['city'] + ' ' + f['country'] + ' ' + ' '.join(lineup)).lower())}">
<td class="nm">{esc(f['name'])}<div class="sub">{esc(f['genre'][:60])}</div></td>
<td class="dt">{date}</td>
<td>{esc(f['location'] or f['city'])}</td>
<td class="pr">{esc(f['price']) or '–'}</td>
<td>{weblink}</td>
<td class="lu"><span class="cnt">{len(lineup)}</span> {esc(preview)}{more}</td>
<td class="sr">{srcs}</td></tr>""")

    with_lineup = sum(1 for f in festivals if f["lineup"])
    both = sum(1 for f in festivals if len(f["sources"]) > 1)

    doc = f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Festival-Übersicht Europa</title>
<style>
:root {{ color-scheme: light dark; --bg:#fff; --fg:#16181d; --mut:#6b7280; --line:#e5e7eb; --acc:#2563eb; --chip:#f3f4f6; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0f1115; --fg:#e8eaed; --mut:#9aa1ab; --line:#272b33; --acc:#7aa2f7; --chip:#1b1f27; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:1.5rem; background:var(--bg); color:var(--fg);
  font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif; }}
h1 {{ font-size:1.5rem; margin:0 0 .25rem; }}
.meta {{ color:var(--mut); margin-bottom:1rem; }}
.bar {{ display:flex; gap:.5rem; flex-wrap:wrap; align-items:center; margin-bottom:1rem;
  position:sticky; top:0; background:var(--bg); padding:.5rem 0; z-index:5; }}
input[type=search] {{ flex:1; min-width:240px; padding:.55rem .7rem; border:1px solid var(--line);
  border-radius:8px; background:var(--chip); color:var(--fg); font-size:14px; }}
button {{ padding:.4rem .7rem; border:1px solid var(--line); border-radius:6px;
  background:var(--chip); color:var(--fg); cursor:pointer; font-size:13px; }}
button.on {{ border-color:var(--acc); color:var(--acc); }}
.wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:10px; }}
table {{ border-collapse:collapse; width:100%; min-width:1000px; }}
th,td {{ padding:.55rem .7rem; border-bottom:1px solid var(--line); vertical-align:top; text-align:left; }}
th {{ position:sticky; top:56px; background:var(--bg); font-size:12px; text-transform:uppercase;
  letter-spacing:.04em; color:var(--mut); z-index:4; }}
.nm {{ font-weight:600; min-width:180px; }}
.sub {{ font-weight:400; font-size:12px; color:var(--mut); }}
.dt {{ white-space:nowrap; font-variant-numeric:tabular-nums; }}
.pr {{ white-space:nowrap; }}
.lu {{ font-size:13px; color:var(--fg); max-width:520px; }}
.cnt {{ display:inline-block; min-width:1.6em; padding:0 .35em; margin-right:.4em; border-radius:5px;
  background:var(--chip); color:var(--mut); font-size:11px; text-align:center; }}
.more {{ margin-left:.4em; padding:0 .35em; font-size:11px; }}
a {{ color:var(--acc); }}
.src {{ display:inline-block; padding:.1em .35em; margin-right:.2em; border-radius:4px;
  background:var(--chip); font-size:11px; text-decoration:none; }}
.tags {{ display:flex; flex-wrap:wrap; gap:.35rem; margin:.5rem 0 1.25rem; }}
.tag {{ background:var(--chip); border-radius:999px; padding:.2rem .6rem; font-size:12px; }}
.tag b {{ color:var(--acc); }}
</style></head><body>
<h1>Festival-Übersicht Europa</h1>
<div class="meta">{len(festivals)} Festivals · {with_lineup} mit Lineup · {both} in beiden Quellen ·
{len(band_count)} normalisierte Acts · Quellen: festivalticker.de, festivalsunited.com</div>

<div class="tags">{''.join(f'<span class="tag">{esc(b)} <b>{c}×</b></span>' for b, c in shared)}</div>

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
{''.join(rows)}
</tbody></table></div>

<script>
const rows = [...document.querySelectorAll('#tb tr')];
const q = document.getElementById('q'), n = document.getElementById('n');
const fl = document.getElementById('fl'), fm = document.getElementById('fm');
let onlyLineup = false, onlyMulti = false;
function apply() {{
  const term = q.value.trim().toLowerCase();
  let shown = 0;
  for (const r of rows) {{
    let ok = !term || r.dataset.search.includes(term);
    if (ok && onlyLineup) ok = r.querySelector('.cnt').textContent !== '0';
    if (ok && onlyMulti) ok = r.classList.contains('multi');
    r.hidden = !ok;
    if (ok) shown++;
  }}
  n.textContent = shown + ' Treffer';
}}
q.addEventListener('input', apply);
fl.addEventListener('click', () => {{ onlyLineup = !onlyLineup; fl.classList.toggle('on', onlyLineup); apply(); }});
fm.addEventListener('click', () => {{ onlyMulti = !onlyMulti; fm.classList.toggle('on', onlyMulti); apply(); }});
document.addEventListener('click', e => {{
  const b = e.target.closest('.more'); if (!b) return;
  const s = document.getElementById(b.dataset.t);
  s.hidden = !s.hidden; b.textContent = s.hidden ? b.textContent : '−';
}});
apply();
</script>
</body></html>"""

    OUTF.write_text(doc, encoding="utf-8")
    print(f"{OUTF}  ({OUTF.stat().st_size / 1e6:.1f} MB, {len(festivals)} Festivals)")


if __name__ == "__main__":
    main()
