'use strict';
/* NODE — this node: who runs it and where; what comes in and what goes out, stepped at the pace things arrive
   (motion named after its datum, stepped never tweened, none under reduced motion); the nodes around it; setup;
   the five refusals. The central hexagon with its labelled spokes follows Memotron's graph, drawn in the layer. */
let FLOWOBS = null;
VIEWS.node = function () {
  FLOWOBS && FLOWOBS.disconnect(); CLOCK.off('node-flow');
  const R = D.registry, h = D.health;
  $('#nodehead').innerHTML = `<div class="k">Node · this machine</div>
    <h1 data-learn="1">${esc(R.name)}, in ${esc(R.place)}.</h1>
    <p class="lede mono">planetai-node ${esc(h.version)} · up ${fmt(h.uptime_s / 3600, 1)} h · ${h.ingested.toLocaleString('en')} readings since the restart · cell ${esc(h.cell.id)} · ${esc(h.tz)}</p>`;
  flow(); around(); running();
};

/* What comes in, what goes out (R35's hub, back on Node in R38; the Wall keeps the flow by scale, js/flow.js).
   R38: every link says its own count over the hourly table's last 24 hours (flowData, doors-flow.js); answers come back on a link of
   their own, green; the centre is the node's res-8 cell inside its res-6 parent at true scale, so the cell reads
   against the finest cell that may leave; each square steps at its link's real mean rate, on the Wall's pace
   (--motion-replay-loop: six hours in 30 s), so the two doors run one clock speed. */
async function flow() {
  const F = await flowData(), el = $('#flow'), narrow = el.clientWidth < 700, W = narrow ? 840 : el.clientWidth, H = 500, cx = W / 2, cy = H / 2, R = narrow ? 64 : 96;
  const grp = id => id.startsWith('msh') ? 'mesh' : (D.sensors.find(s => s.sensor_id === id) || {}).kind === 'model' ? 'models' : (D.sensors.find(s => s.sensor_id === id) || {}).local ? 'house' : 'public';
  const n24 = { house: null, public: null, models: null, mesh: null }; for (const [id, n] of Object.entries(F.counts)) n24[grp(id)] = (n24[grp(id)] || 0) + d3.sum(n);
  const loc = D.sensors.filter(s => s.local && s.kind === 'sensor'), pub = D.sensors.filter(s => !s.local && s.kind === 'sensor');
  const heard = pub.filter(s => lastRaw(s.sensor_id, 'pm25') != null).length, models = D.sensors.filter(s => s.kind === 'model').length, c24 = v => v == null ? 'counted with the token' : `${v.toLocaleString('en')} in 24 h`;
  const ret = D.health.reticulum || {}, perDay = ret.announce_s ? Math.round(86400 / ret.announce_s) : null;
  // [title, words, events in 24 h (null: nothing travels), colour]
  const IN = [['Sensors in this house', `${loc.length} · ${c24(n24.house)}`, n24.house, ''], ['Public stations around it', `${heard} of ${pub.length} heard · ${c24(n24.public)}`, n24.public, ''],
    ['Models for this point', `${models} · ${c24(n24.models)}`, n24.models, ''], ['The mesh, by LoRa', n24.mesh == null ? (F.counted ? 'no mesh heard' : 'counted with the token') : `${n24.mesh.toLocaleString('en')} packets in 24 h`, n24.mesh, ''],
    ['Answers, from the household', `${c24(F.answers.length)} · Done, Not now, Doesn’t fit`, F.answers.length, 'green'], ['The satellite', D.earth ? `${D.earth.years.length} years · once a year` : 'not fetched on this node', null, 'sat']];
  const OUT = [['This page, on your network', '0 requests out · when you open it', null, ''], ['Alerts, to a phone', `${c24(F.alerts.length)} · ${D.rho.acted} acted on`, F.alerts.length, 'red'],
    ['Its cell, by radio', ret.announce_s ? `res ${D.geometry.radio.res} · every ${Math.round(ret.announce_s / 60)} min · ${(ret.peers || []).length} heard` : 'no radio on this node', perDay, 'blue'], ['Fab City Index cells', `${new Set(D.index_cells.map(c => c.cell)).size} of 20 · hourly`, 24, 'blue'],
    ['Open export, CC BY 4.0', 'one file a day', 1, ''], ['Hourly means, to a community node', 'none set · nowhere yet', null, '']];
  const xIn = narrow ? 280 : 300, xOut = W - (narrow ? 280 : 340), yAt = (i, n) => 46 + i * ((H - 110) / (n - 1));
  // the centre: the res-6 parent and its 49 res-8 cells, flat and to scale; this node's cell filled. Every hexagon is a real cell.
  /* the node's own answers (js/nodegeo.js): its res-8 cell, the res-6 parent and the parent's 49 children, as rings */
  const NG = D.ngeo, poly = row => ({ type: 'Polygon', coordinates: [llRing(row)] });
  const cellR = NG ? NG.c8.ring : null, parR = NG ? NG.c6.ring : null, cell = NG ? NG.c8.id : D.health.cell.id;
  const pa = NG ? d3.geoPath(d3.geoIdentity().reflectY(true).fitExtent([[cx - R, cy - R], [cx + R, cy + R]], poly(parR))) : null, kids = NG ? NG.c6.children_ll : [];
  const link = d3.linkHorizontal(), paths = [];
  let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" ${narrow ? `style="width:${W}px"` : ''} role="img" aria-label="What comes into this node and what goes out">`;
  IN.forEach(([t, n, e, c], i) => { const y = yAt(i, IN.length), d = link({ source: [xIn + 8, y], target: [cx - R, cy] });
    s += `<path id="fi${i}" d="${d}" class="fl ${e == null ? 'empty' : ''}"/><text x="${xIn}" y="${y - 6}" text-anchor="end" class="ft">${esc(t)}</text><text x="${xIn}" y="${y + 9}" text-anchor="end" class="fn">${esc(n)}</text><circle cx="${xIn + 8}" cy="${y}" r="3" class="fd ${c}"/>`;
    paths.push([`fi${i}`, e, c]); });
  OUT.forEach(([t, n, e, c], i) => { const y = yAt(i, OUT.length), d = link({ source: [cx + R, cy], target: [xOut - 8, y] });
    s += `<path id="fo${i}" d="${d}" class="fl ${e == null ? 'empty' : ''}"/><text x="${xOut}" y="${y - 6}" class="ft">${esc(t)}</text><text x="${xOut}" y="${y + 9}" class="fn">${esc(n)}</text><circle cx="${xOut - 8}" cy="${y}" r="3" class="fd ${e == null ? 'hollow' : c}"/>`;
    paths.push([`fo${i}`, e, c]); });
  const km2 = which => NG ? fmt(NG[which].area_m2 / 1e6, which === 'c8' ? 2 : 0) : '—', tn = (k, v, c) => `<tspan data-num="${k}" data-cmp="${esc(c)}">${v}</tspan>`;   // num(), in SVG
  s += (!NG ? `<text x="${cx}" y="${cy}" text-anchor="middle" class="fn">the cells need the token: unlock below</text>`
    : kids.filter(k => k[0] !== cell).map(k => `<path d="${pa(poly(k))}" class="fgrid"/>`).join('') + `<path d="${pa(poly(parR))}" class="fpar"/><path d="${pa(poly(cellR))}" class="fhex"/>`)
    + `<text x="${cx}" y="${cy - R - 26}" text-anchor="middle" class="fname">${esc(D.registry.name)}</text><text x="${cx}" y="${cy - R - 10}" text-anchor="middle" class="fn">${esc(cell)} · res 8 · ${tn('node.cell.km2', km2('c8'), 'this cell\'s own area')} km²</text>`
    + `<text x="${cx}" y="${cy + R + 18}" text-anchor="middle" class="fn">1 of ${tn('node.cell.n6', NG ? NG.c6.children_n : '—', 'res-8 cells in its res-6 parent, counted by the node')} in its res-6 cell · ${tn('node.par.km2', km2('c6'), 'the parent\'s own area')} km² · dotted: may leave</text>`
    + `<text x="${cx}" y="${cy + R + 34}" text-anchor="middle" class="fn">${D.health.ingested.toLocaleString('en')} readings kept · none leave</text>`
    + `<text x="${cx}" y="${H - 6}" text-anchor="middle" class="fn">raw readings stay here; what leaves is the cell, the means, the Index and the answers</text><g id="dots"></g></svg>`;
  el.innerHTML = s;
  // Stepped, named after its datum: one square per link takes one of eight steps per arrival, at the link's real mean
  // rate over 24 h, compressed to the Wall's pace. One clock, transform only, paused off screen, none under reduced motion.
  if (CLOCK.reduced()) { $('#flownote').textContent = 'Reduced motion: the links hold still and say their counts in words.'; return; }
  const g = el.querySelector('#dots'), STEPS = 8, perH = (parseFloat(css('--motion-replay-loop')) || 30) * 1000 / 6;   // ms for one capture hour
  const links = paths.filter(p => p[1]).map(([id, e, c]) => {
    const path = el.querySelector('#' + id), L = path.getTotalLength(), dot = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    dot.setAttribute('width', 6); dot.setAttribute('height', 6); dot.setAttribute('x', -3); dot.setAttribute('y', -3); dot.setAttribute('class', 'fdot ' + c); g.appendChild(dot);
    const k = Math.floor(Math.random() * STEPS), every = Math.max(84, 24 * perH / e);   /* faster than two clock frames steps every two */
    const put = n => { const p = path.getPointAtLength(L * n / (STEPS - 1)); dot.setAttribute('transform', `translate(${p.x} ${p.y})`); };
    put(k); return { put, k, every, last: 0 };
  });
  const tick = t => { if (view() !== 'node') return CLOCK.off('node-flow'); for (const l of links) if (t - l.last >= l.every) { l.last = t; l.k = (l.k + 1) % STEPS; l.put(l.k); } };
  FLOWOBS = new IntersectionObserver(([e]) => e.isIntersecting ? CLOCK.on('node-flow', tick) : CLOCK.off('node-flow')); FLOWOBS.observe(el);
  $('#flownote').textContent = 'Each square steps once per arrival on its link, at that link’s real rate over the last 24 hours, six hours to 30 s, the Wall’s pace: the house’s readings race, the answers creep, the export takes two minutes. A dashed link carries nothing.';
}

async function around() {
  const land = await geo('world', '/static/world-land-110m.json'), el = $('#world'), W = el.clientWidth || 900, H = Math.round(W * .48);
  // The programme's list on 6 Oct, not something this node heard: its radio has heard no peer yet.
  const N = KNOWN_NODES, NG = D.ngeo;   // js/nodegeo.js
  // the whole-sphere H3 grid at resolution 2, as the landing draws it (planetai web, kit/h3/planet-states-web.svg): under
  // the coast, at half strength; each node lights its own res-2 cell. Edges as lines, so no ring winding can fill the globe.
  /* the planet's res-2 grid and each node's res-2 cell are the node's answers (GET /geo/planet, /geo/cell) */
  const g2 = NG ? NG.planet : [], lit = NG ? NG.lit.map(c => c.ring) : [];
  const pr = d3.geoEqualEarth().fitExtent([[6, 6], [W - 6, H - 6]], { type: 'Sphere' }), path = d3.geoPath(pr);
  let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="The nodes the programme knows" class="geo"><path d="${path({ type: 'Sphere' })}" class="sphere"/>`
    + (g2.length ? `<path d="${path({ type: 'MultiLineString', coordinates: g2.map(llRing) })}" class="h3grid"/>` : '') + `<path d="${path(land)}" class="land"/>`;
  s += lit.map(c => `<path d="${path({ type: 'Polygon', coordinates: [llRing(c).reverse()] })}" class="h3lit"/>`).join('');
  /* an arc from this node to each other node with a point; one label per place, the nodes there by number */
  const me = N.find(x => x.me), far = N.filter(x => !x.me && !x.ring), places = d3.groups(N, x => x.ll.join(','));
  s += far.map(x => `<path d="${path({ type: 'LineString', coordinates: [me.ll, x.ll] })}" class="arc"/>`).join('');
  for (const x of N) { const [px, py] = pr(x.ll); s += `<circle cx="${px}" cy="${py}" r="${x.ring ? 11 : x.me ? 6 : 5}" class="nd ${x.ring ? 'ring' : ''}"/>`; }
  for (const [, xs] of places) { const [px, py] = pr(xs[0].ll), at = xs.find(x => !x.ring) || xs[0];
    s += `<text x="${px + 10}" y="${py + 18}" class="lab">${esc(at.place.split(',').pop().trim())} · ${xs.map(x => x.no ? '#' + x.no : esc(x.n)).join(' and ')}</text>`; }
  s += `</svg>`;
  el.innerHTML = s;
  $('#nodes').innerHTML = N.map(x => `<div class="lrow"><span class="t">#${x.no} ${esc(x.n)}<small>${esc(x.place)}</small></span><span class="s">${esc(x.reads)}</span>`
    + `<span class="c"><span class="state">${x.state}</span> ${x.me ? 'this node' : x.ring ? 'same network' : (NG && NG.dist['node:' + x.n] ? fmt(NG.dist['node:' + x.n].m / 1000, 0) + ' km' : '—')}</span></div>`).join('')
    + `<div class="lrow"><span class="t">A community node above it</span><span class="s">where this node’s hourly means would go, so a city can be built from nodes</span><span class="c x">not set</span></div>`
    + `<p class="fine">The programme’s list on 6 Oct, not something this node heard: its radio has announced its cell every 30 minutes and no peer has answered. State is drawn in weight, never hue: live is a solid 2.5 stroke. #3’s point is not published, so it is a ring around #1 rather than an invented coordinate.</p>`;
}

/* Running, and a light reading of the machine under it (GET /machine, /storage: token-only; the full one is Set up →
   Machine). Meters are ink on a hairline, one per resource, so the state reads at a glance. */
async function running() {
  const h = D.health, mesh = h.mesh && h.mesh.root_topic ? h.mesh : null, ret = h.reticulum;
  const [M, S] = await Promise.all(['machine', 'storage'].map(r => fetch('/' + r, { headers: DOORS_AUTH() }).then(x => x.ok ? x.json() : null).catch(() => null)));
  const meter = (v, T) => T ? `<i class="nm"><b style="width:${Math.min(100, v / T * 100).toFixed(1)}%"></b></i>` : '';
  const gb = b => b == null ? '—' : b >= 1e9 ? `${(b / 1e9).toFixed(1)} GB` : `${Math.round(b / 1e6)} MB`;
  const mem = M && M.memory, used = mem && mem.total_bytes && mem.available_bytes != null ? mem.total_bytes - mem.available_bytes : null, k = S && S.disk;
  const years = d => d == null ? '—' : d >= 730 ? `${Math.round(d / 365)} years` : d >= 60 ? `${Math.round(d / 30)} months` : `${d} days`;
  const hw = M ? [
    ['Processor', `${M.arch} · ${M.cores} cores · load ${M.load ? M.load[0].toFixed(2) : '—'}${meter(M.load ? M.load[0] : 0, M.cores)}`, M.cpu_busy_pct == null ? '—' : `${M.cpu_busy_pct}% busy`],
    ['Memory', `${gb(used)} of ${gb(mem.total_bytes)}${meter(used || 0, mem.total_bytes)}`, `${gb(mem.available_bytes)} free`],
    ...(M.temperatures || []).slice(0, 1).map(t => ['Temperature', t.zone, `${t.celsius} °C`]),
    ...(k ? [['Disk', `${gb(S.database_bytes + S.out_bytes + S.backups.bytes + S.exports_bytes)} this node · ${gb(k.free_bytes)} free of ${gb(k.total_bytes)}${meter(k.used_bytes, k.total_bytes)}`, `${years(S.days_left)} left`]] : []),
  ] : [['The machine', 'its processor, memory and disk are the keeper’s: unlock this screen in Set up', '<a href="#setup/screen">unlock →</a>']];
  $('#running').innerHTML = [['Version', `planetai-node ${h.version} · schema ${h.schema}`, ''], ['Running for', 'since the last restart', `${fmt(h.uptime_s / 3600, 1)} h`],
    ['Readings taken in', h.last_poll ? `${h.polls} polls since the restart, the last at ${h.last_poll.slice(11, 16)} UTC` : 'no poll yet since the restart', h.ingested.toLocaleString('en')],
    ...hw,
    ['Mesh in the house', mesh ? `${mesh.root_topic} · gateway ${mesh.gateway}` : 'no mesh broker set', mesh ? `${mesh.packets} packets` : 'off'],
    ['Radio', ret && ret.announce_s ? `announces its cell every ${ret.announce_s / 60} min` : 'no radio bridge set', ret && ret.ok ? 'on' : 'off'],
    ['This screen', DOORS_TOKEN() ? 'holds a token: it draws the map, the cells and the counts' : `at SHARE_LEVEL=${D.share || 'off'} without a token: the map, the cells and the counts stay on the node`,
      DOORS_TOKEN() ? 'unlocked' : 'locked']]
    .map(([t, s2, c]) => `<div class="lrow"><span class="t">${t}</span><span class="s">${t === 'The machine' || /class="nm"/.test(s2) ? s2.replace(/^([^<]*)/, m => esc(m)) : esc(s2)}</span><span class="c">${/^<a /.test(c) ? c : esc(c)}</span></div>`).join('')
    + `<p class="fine">${M ? 'The machine as the node’s containers see it. ' : ''}<a href="#setup/machine">Set up → Machine</a> has all of it, and how long the disk lasts.</p>`;
}

