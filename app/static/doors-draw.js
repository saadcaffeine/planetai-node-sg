'use strict';
/* DRAW — the Place drawing's pure half (SPEC_place_microgis, 4 Nov 2026): the geodesic math on a sphere, the state of a
   drawing in progress, and the figure the readout shows. A point is [lon, lat]; a drawing is {kind, pts} and every
   function returns a new one, so the screen can keep each state it has been in and Backspace is one step back. The
   numbers here are what the screen shows while somebody draws; the stored ones are PostGIS's, from geom::geography
   (they differ by a fraction of a percent, and the server's win). Pure: no DOM and no D; doors-place.js wires it up. */

const EARTH_R = 6371008.8;                       // metres, the mean radius PostGIS's sphere uses
const rad = d => d * Math.PI / 180;

/* the great-circle distance between two points (haversine), metres */
const legM = ([x1, y1], [x2, y2]) => {
  const a = Math.sin(rad(y2 - y1) / 2) ** 2 + Math.cos(rad(y1)) * Math.cos(rad(y2)) * Math.sin(rad(x2 - x1) / 2) ** 2;
  return 2 * EARTH_R * Math.asin(Math.min(1, Math.sqrt(a)));
};
const lengthM = c => c.reduce((m, p, i) => i ? m + legM(c[i - 1], p) : 0, 0);
/* a ring closed or left open measures the same: the closing leg is added when the last point is not the first */
const perimeterM = r => r.length < 2 ? 0 : lengthM(r) + (r[0][0] === r[r.length - 1][0] && r[0][1] === r[r.length - 1][1] ? 0 : legM(r[r.length - 1], r[0]));
/* the spherical ring formula: R²/2 · Σ (λ2 − λ1)(2 + sin φ1 + sin φ2), edge by edge, the closing edge included.
   ponytail: no wrap at the antimeridian (a lot that straddles ±180° reads wrong); a place on this node never does. */
const areaM2 = r => {
  if (r.length < 3) return 0;
  let s = 0;
  for (let i = 0; i < r.length; i++) {
    const [x1, y1] = r[i], [x2, y2] = r[(i + 1) % r.length];
    s += rad(x2 - x1) * (2 + Math.sin(rad(y1)) + Math.sin(rad(y2)));
  }
  return Math.abs(s) * EARTH_R * EARTH_R / 2;
};

const fmtLen = m => Math.round(m) >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`;
const fmtArea = m2 => m2 >= 10000 ? `${Number((m2 / 10000).toFixed(1))} ha` : `${Math.round(m2)} m² · ${(m2 / 10000).toFixed(2)} ha`;

/* the state: points as they are pressed, and what each kind needs before it is a thing */
const NEED = { marker: 1, note: 1, line: 2, area: 3 };
const drawState = kind => ({ kind, pts: [] });
const addPt = (s, pt) => ({ ...s, pts: [...s.pts, pt] });
const backPt = s => ({ ...s, pts: s.pts.slice(0, -1) });
const canFinish = s => s.pts.length >= NEED[s.kind];
/* a GeoJSON Feature, or null while the shape is not one yet; an area's ring is closed, the caller's props win */
const toFeature = (s, props) => {
  if (!canFinish(s)) return null;
  const geometry = s.kind === 'line' ? { type: 'LineString', coordinates: s.pts.map(p => [...p]) }
    : s.kind === 'area' ? { type: 'Polygon', coordinates: [[...s.pts, s.pts[0]].map(p => [...p])] }
    : { type: 'Point', coordinates: [...s.pts[0]] };
  return { type: 'Feature', geometry, properties: { kind: s.kind, ...props } };
};

/* what the readout says while drawing: the figure large, its unit small, and one line of what to do next. `hover` is the
   point under the pointer, counted as the shape's next point without being added. The hints are the mockup's READ. */
const HINT = {
  marker: 'Press the map to drop it. Enter drops one at the centre.',
  line: 'Press to add a point, double-press or Enter to finish. Backspace takes one back.',
  area: 'Press to add a corner, press the first one or Enter to close.',
  note: 'A note sits on the map and travels with the map when it is downloaded.',
};
const figure = (s, hover) => {
  const hint = HINT[s.kind] || '', pts = hover ? [...s.pts, hover] : s.pts, none = { value: '', unit: '', hint };
  if (s.kind === 'marker') {
    const p = hover || s.pts[s.pts.length - 1];
    return p ? { value: [p[1], p[0]].map(v => v.toFixed(4).replace('-', '−')).join(', '), unit: '', hint } : none;
  }
  if (s.kind === 'line' && pts.length >= 2) {
    const m = lengthM(pts), n = pts.length - 1;
    return { value: m >= 1000 ? (m / 1000).toFixed(2) : m.toFixed(1), unit: `${m >= 1000 ? 'km' : 'm'} · ${n} segment${n > 1 ? 's' : ''}`, hint };
  }
  if (s.kind === 'area' && pts.length >= 3) {
    const a = areaM2(pts), round = `${fmtLen(perimeterM(pts))} round`;
    return a >= 10000 ? { value: String(Number((a / 10000).toFixed(1))), unit: `ha · ${round}`, hint }
      : { value: String(Math.round(a)), unit: `m² · ${(a / 10000).toFixed(2)} ha · ${round}`, hint };
  }
  return none;
};

/* the drawing keys, in the order the screen's left edge lists them */
const KEYS = [['select', 'V'], ['marker', 'M'], ['line', 'L'], ['area', 'A'], ['note', 'N'], ['image', 'I']];

const DRAW = { lengthM, areaM2, perimeterM, fmtLen, fmtArea, drawState, addPt, backPt, canFinish, toFeature, figure, KEYS };
if (typeof window !== 'undefined') Object.assign(window, DRAW);
if (typeof module !== 'undefined') module.exports = DRAW;
