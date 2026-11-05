'use strict';
/* NODEGEO — every cell and every distance the flow, the Wall and Node draw, asked of the node once, at load
   (GET /geo/*). The page computes no H3 and no distance: rings come as [id, lat, lng, …] or as [id, metres, bearing, …]
   from the node, stations as {m, deg} from the node. /geo/* is token-only at every SHARE_LEVEL (together they place
   the node): without the token D.ngeo is null and each drawing says what it is not drawing. */

/* The nodes the programme lists: registry.json on main, as the node read it (GET /nodes, open at every share level;
   docs/SPEC_hello.md). Another node's point comes to one decimal (about 10 km): its owner published it, not this page. */
let KNOWN_NODES = [];

/* a cells_ll row as a closed [lng, lat] ring (GeoJSON order), and a polar row as [[metres, bearing], …]: reorders only */
const llRing = row => { const r = []; for (let i = 1; i < row.length; i += 2) r.push([row[i + 1], row[i]]); r.push(r[0]); return r; };
const polarRing = row => { const r = []; for (let i = 1; i < row.length; i += 2) r.push([row[i], row[i + 1]]); return r; };

/* Which of the list is this node, by its own name; a node not on the list is added as itself, not listed yet. Its
   own point is the one /health gives this screen. A listed node with no point is not drawn. */
async function knownNodes(D) {
  D.listed = await fetch('/nodes').then(r => r.ok ? r.json() : null).catch(() => null);
  KNOWN_NODES = ((D.listed && D.listed.nodes) || []).filter(x => x.ll)
    .map(x => ({ n: x.name, place: x.place || '', ll: x.ll, listed: true, reads: [x.scale, x.since && 'since ' + x.since].filter(Boolean).join(' · ') }));
  let me = KNOWN_NODES.find(x => x.n === D.health.node);
  if (!me) KNOWN_NODES.push(me = { n: D.health.node, place: D.health.city || '', listed: false, reads: 'not listed yet: planetai hello' });
  me.me = true; me.ll = D.point;
}

async function nodeGeo(D) {
  const ask = p => doorsFetch('/' + p).then(r => r.ok ? r.json() : Promise.reject(new Error(`GET /${p.split('?')[0]} answered ${r.status}`)));
  const [lon, lat] = D.point, here = r => `geo/cell?lat=${lat}&lon=${lon}&res=${r}`;
  // one path from the node through every point a drawing places by distance: stations, the sea model, other nodes
  const pts = D.sensors.filter(s => s.lat != null).map(s => ({ id: s.sensor_id, ll: [s.lon, s.lat] }))
    .concat(KNOWN_NODES.filter(x => !x.me).map(x => ({ id: 'node:' + x.n, ll: x.ll })));
  const [c8, c6, c3, m, planet, ...lit] = await Promise.all([
    ask(here(8) + '&polar=true'), ask(here(6) + '&children=8&polar=true'), ask(here(3) + '&children=8'),
    ask(`geo/measure?from_node=true&each=true&path=${pts.map(p => p.ll.map(v => v.toFixed(6)).join(',')).join(';')}`),
    ask('geo/planet?res=2'),
    ...[...new Set(KNOWN_NODES.map(x => x.ll.join(',')))].map(k => { const [x, y] = k.split(','); return ask(`geo/cell?lat=${y}&lon=${x}&res=2`); })]);
  return { c8, c6, c3, planet: planet.cells_ll, lit: [...new Map(lit.map(c => [c.id, c])).values()],
    dist: Object.fromEntries(pts.map((p, i) => [p.id, m.each[i]])) };
}
