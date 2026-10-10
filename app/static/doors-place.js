'use strict';
/* PLACE — the geographic context, as a workbench (OneSoil): pick a layer on the left, read the map, read its facts on
   the right. Every layer is real geometry: H3 cells from the node (GET /geo/*), the coast from Natural Earth 1:10m, the plan from
   OpenStreetMap, the stations at their own coordinates, the satellite frames as photographs. */
const GEO = {};
async function geo(name, url) { return GEO[name] || (GEO[name] = await fetch(url).then(r => r.json())); }
/* Three views of the place: the map (placemap.js, every layer that has a position), and the two that do not —
   the Sentinel frames are photographs not registered to the node's point, and the change is a count, not a shape. */
let PVIEW = 'map', YEAR = 2025, COMPARE = true, PAST = null;   /* From orbit opens as then | now (Tomas, 7 Oct) */
const PVIEWS = [['map', 'Map', 'every layer with a position'], ['orbit', 'From orbit', 'then and now, Sentinel-2'], ['change', 'What changed', 'AlphaEarth, year on year']];
VIEWS.place = function () {
  const h = D.health, area = D.geometry.ladder.find(l => l.res === h.cell.res).own_area_m2 / 1e6;   // the node's own figure for this cell, not the resolution's average
  $('#placehead').innerHTML = `<div class="k">Place · ${said(D.registry.place)}</div>
    <h1 data-learn="1">The ground this node stands on.</h1>
    <p class="lede mono">${esc(h.cell.id)} · res ${h.cell.res} · ${h.cell.edge_m} m edge · ${area.toFixed(2)} km² · ${fmt(D.point[1], 4)}, ${fmt(D.point[0], 4)}</p>
    <nav class="pviews" aria-label="Views of the place">${PVIEWS.map(([id, t, s]) => `<button class="${id === PVIEW ? 'on' : ''}" data-p="${id}"><b>${t}</b><span>${s}</span></button>`).join('')}</nav>`;
  document.querySelectorAll('.pviews button').forEach(b => b.onclick = () => { PVIEW = b.dataset.p; VIEWS.place(); });
  document.querySelector('.bench').dataset.pview = PVIEW;
  if (PVIEW === 'map') placeMap(); else layer();
  reach();
};

/* a fact: its name, its figure, where it is from — and, when it has one, its provenance word as the node draws it */
const facts = (rows, note) => rows.map(([t, v, s, w]) => `<div class="fr"><span>${esc(t)}${s ? `<small class="said">${esc(s)}</small>` : ''}</span><b>${esc(v)}${w ? ' ' + prov(w) : ''}</b></div>`).join('') + (note ? `<p class="fine">${note}</p>` : '');
/* counted in the node's own cell sign: filled for the count, faint for the rest, in the satellite's orange (dashboard.js of20) */
const of20 = v => `<span class="signs">${d3.range(20).map(i => sign('sign-cell', i < Math.round(v * 20) ? 'on sat' : 'off sat')).join('')}</span>`;

async function layer() {
  const el = $('#mapalt'); $('#altbar').innerHTML = ''; el.innerHTML = '';
  const LAYER = PVIEW;
  if (!D.earth || !(D.earth.sentinel || []).length && LAYER === 'orbit') {
    el.innerHTML = `<p class="fine">This node holds no satellite frames yet: <code>planetai run earth frames</code> fetches them.</p>`; $('#altfacts').innerHTML = ''; return;
  }
  if (LAYER === 'orbit') {
    /* Then | now: the latest pass on the right, fixed; the past on the left, stepped through the passes the node
       keeps. Single shows one year at a time. The hectares that changed between the two are the node's own count
       (AlphaEarth, GET /earth), drawn only for a pair it computed. */
    const ys = D.earth.sentinel, NOW = ys[ys.length - 1]; if (!ys.includes(YEAR)) YEAR = NOW;
    if (!ys.includes(PAST) || PAST === NOW) PAST = ys[0];
    const past = ys.filter(y => y !== NOW);
    const ch = (D.earth.changes || []).find(c => c.year_a === PAST && c.year_b === NOW)
      || (D.earth.changes || []).find(c => c.year_a <= PAST + 1 && c.year_b === NOW);
    $('#altbar').innerHTML = COMPARE
      ? `<span class="k">then</span><button id="yp" aria-label="Earlier">‹</button><b class="mono">${PAST}</b><button id="yn" aria-label="Later">›</button><span class="k">· now</span><b class="mono">${NOW}</b>`
        + `<label class="cmp"><input type="checkbox" id="cmp" checked> then and now</label>`
      : `<button id="yp" aria-label="Earlier">‹</button><b class="mono">${YEAR}</b><button id="yn" aria-label="Later">›</button><label class="cmp"><input type="checkbox" id="cmp"> then and now</label>`;
    el.innerHTML = COMPARE
      ? `<div class="pair"><figure><img src="${SAT(PAST)}" alt="Sentinel-2, ${PAST}"><figcaption>then · ${PAST}</figcaption></figure><figure><img src="${SAT(NOW)}" alt="Sentinel-2, ${NOW}"><figcaption>now · ${NOW}</figcaption></figure></div>`
        + (ch ? `<div class="pairnote">${ch.year_a} → ${ch.year_b}: ${num('earth.change.pair', ch.hectares_over_threshold.toFixed(1), `pixels past the change threshold ${ch.threshold}, of ${ch.pixels.toLocaleString('en')}`)} ha changed, ${(ch.share_over_threshold * 100).toFixed(1)} % of the ground, by the node’s AlphaEarth record ${prov('model')}</div>` : '')
      : `<img class="photo" src="${SAT(YEAR)}" alt="Sentinel-2 annual median, ${YEAR}, about 3 km across">`;
    const step = d => { if (COMPARE) PAST = past[Math.max(0, Math.min(past.length - 1, past.indexOf(PAST) + d))]; else YEAR = ys[Math.max(0, Math.min(ys.length - 1, ys.indexOf(YEAR) + d))]; layer(); };
    $('#yp').onclick = () => step(-1); $('#yn').onclick = () => step(1); $('#cmp').onchange = e => { COMPARE = e.target.checked; layer(); };
    $('#altfacts').innerHTML = facts([['Passes kept', ys.join(' · '), 'Sentinel-2 annual medians'], ['Landsat passes', D.earth.landsat.join(' · ')], ['Across', 'about 3 km'], ['Brightness', 'matched across years']],
      `${D.earth.credit.map(esc).join(' ')} Only the structure differs between years. The photograph is not registered to the node’s point, so nothing is drawn over it.`);
  }

  if (LAYER === 'change') {
    const E = D.earth, all = E.changes || [], ch = all.filter(c => c.year_b - c.year_a === 1).sort((a, b) => a.year_a - b.year_a), span = all.find(c => c.year_b - c.year_a > 1);
    const row = (c, t, cls = '') => `<div class="lrow ${cls}"><span class="t">${t}<small>${(c.share_over_threshold * 100).toFixed(2)} % of pixels</small></span>`
      + `<span class="signs">${d3.range(Math.round(c.hectares_over_threshold / 10)).map(() => sign('sign-cell', 'on sat')).join('')}</span><span class="c">${num('earth.change.' + c.year_b, c.hectares_over_threshold.toFixed(1), `pixels that moved more than ${D.earth.change.threshold}`)} ha</span></div>`;
    el.innerHTML = `<div class="chg"><div class="k">Hectares that changed, one square per 10 ha</div>${ch.map(c => row(c, `${c.year_a} → ${c.year_b}`)).join('')}${span ? row(span, `${span.year_a} → ${span.year_b}`, 'span') : ''}</div>`;
    const O = Object.fromEntries(D.observations.filter(o => o.sensor_id === 'ee-point').map(o => [o.metric, o.value]));
    $('#altfacts').innerHTML = `<div class="k">What the ground is made of, within 1 km</div>`
      + [['built', O.built_frac], ['trees', O.tree_frac], ['crops', O.crop_frac], ['water', O.water_frac]].filter(([, v]) => v != null)
        .map(([t, v]) => `<div class="fr col"><span>${t} <small>twentieths of the ground</small></span>${of20(v)}<b>${fmt(v * 100, 0)} % ${prov('model')}</b></div>`).join('')
      + facts([['Vegetation (NDVI median)', fmt(O.ndvi_median, 2)], ['Night lights', fmt(O.night_lights, 1), 'VIIRS radiance'], ['Changed when it moved more than', `${E.change.threshold}`, `AlphaEarth, ${E.change.metres_per_pixel} m pixels, ${E.radius_m * 2 / 1000} km square`]],
        'Orange is what only the satellite knows, and nothing else on this door is orange. Every figure here is a model’s description of the ground, never a reading.');
  }

}

function reach() {
  const R = D.reach || [], max = d3.max(R, r => r.days) || 1, word = { map: 'The satellite', model: 'Models read for this point', sensor: 'The kit in and around this house' };
  $('#reach').innerHTML = R.map(r => `<div class="lrow"><span class="t">${word[r.kind] || r.kind}<small>${r.sources} source${r.sources === 1 ? '' : 's'} · ${r.buckets.toLocaleString('en')} hours</small></span>`
    + `<span class="bar"><i style="width:${Math.max(.5, r.days / max * 100)}%"></i></span><span class="c">${r.days >= 730 ? fmt(r.days / 365.25, 1) + ' yr' : r.days + ' d'}</span></div>`).join('')
    + `<p class="fine">From ${dLabel(dayOf(R[0].oldest))} ${R[0].oldest.slice(0, 4)} for the satellite; the kit started on ${dLabel(dayOf(R[2].oldest))}.</p>`;
  $('#soon').innerHTML = [['Production and trade', 'what this place makes and what it brings in, by category, for the Fab City Index', 'open sources named, no adapter yet'],
    ['Index cells', 'the 20 cells of the Fab City Index for this place, scored where data exists', `${new Set(D.index_cells.map(c => c.cell)).size} of 20 have a value`],
    ['Water and soil', 'the other two things the purpose names, beside air', 'no source yet'], ['Forecast', 'the next day of wind and rain, from BMKG for this village', 'needs this point’s village code']]
    .map(([t, s2, c]) => `<div class="lrow two"><span class="t">${t}</span><span class="s">${s2}<br><span class="soon">${c}</span></span></div>`).join('');
}
