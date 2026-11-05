'use strict';
/* CAKE — the Place door's left column as data (SPEC_place_microgis §5, 4 Nov 2026). The layers from the sky down to the
   ground, results first and the frame last: McHarg's order turned upside down, so the layer the household lives in comes
   first. Each section names the classes of fabcity-flows 1.0 that live in it and the ceiling those classes carry
   (a planetary boundary, or the material footprint), so the map, the flows log, the inventory and the Index use the same
   words for the same things. Pure: no DOM and no D; doors-placemap.js's LAYERS name their section by `cake: <id>`. */

const CAKE = [
  { id: 'results',      name: 'results',      classes: [],                    ceiling: null },
  { id: 'microclimate', name: 'microclimate', classes: ['electricity'],       ceiling: 'climate' },
  { id: 'flows',        name: 'flows',        classes: ['*'],                 ceiling: 'each class' },
  { id: 'built',        name: 'built',        classes: [],                    ceiling: 'materials' },
  { id: 'animals',      name: 'animals',      classes: ['animal'],            ceiling: 'biosphere' },
  { id: 'plants',       name: 'plants',       classes: ['plant', 'habitat'],  ceiling: 'biosphere, land system' },
  { id: 'soil',         name: 'soil',         classes: ['compost'],           ceiling: 'biogeochemical' },
  { id: 'water',        name: 'water',        classes: ['water'],             ceiling: 'freshwater' },
  { id: 'ground',       name: 'ground',       classes: [],                    ceiling: 'land system' },
  { id: 'frame',        name: 'frame',        classes: [],                    ceiling: null },
];

/* one section per CAKE entry, in its order; a section no layer fills is kept with no rows (the place says what it does
   not know). A row is on or off by the switch, and soon when the layer says it cannot be filled yet. */
const cakeSections = (layers, on) => CAKE.map(s => ({ ...s,
  rows: layers.filter(l => l.cake === s.id).map(l => ({ id: l.id, name: l.name, sub: l.sub, state: l.soon ? 'soon' : on[l.id] ? 'on' : 'off' })) }));

/* the sensors out of doors: the Place map draws the street, and an indoor reading is the house's, not the place's */
const outside = sensors => sensors.filter(s => s.indoor !== true);

if (typeof window !== 'undefined') Object.assign(window, { CAKE, cakeSections, outside });
if (typeof module !== 'undefined') module.exports = { CAKE, cakeSections, outside };
