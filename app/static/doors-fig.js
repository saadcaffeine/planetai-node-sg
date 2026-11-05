'use strict';
/* The day, large, and the week under it on the same x (R33). One function for Now and the Wall.
   o: { el: <svg>, issue, big: bool (wall scale), pick: i => void (moves the moment), week: false (the day alone: a phone
   draws the week as rows it can press, doors-now.js weekRows) } */
function dayWeek(o) {
  const k = o.issue, it = D.issues[k], svg = d3.select(o.el), uid = o.el.id;
  const W = o.el.parentNode.clientWidth, narrow = W < 560, B = o.big ? 1.6 : 1;
  const m = { l: narrow ? 46 : 74 * B, r: narrow ? 52 : 64 * B, t: 40 * B }, H1 = narrow ? 190 : (o.h1 || 220), rowH = narrow ? 13 : 15 * B, gap = 34 * B;
  const iw = W - m.l - m.r, nD = o.week === false ? 0 : D.dates.length, H = m.t + H1 + (nD ? gap + nD * rowH : 0) + 26;
  svg.attr('viewBox', `0 0 ${W} ${H}`).attr('width', W).attr('height', H).selectAll('*').remove();
  svg.attr('aria-label', `${it.name || k}, hour by hour${nD ? ', and the last seven days' : ''}`);   /* the figure's own name; the sentence describes it */
  const date = dayOf(D.buckets[S.i]);
  const x = d3.scaleLinear([0, 24], [m.l, m.l + iw]);
  const idx = h => D.at[date + '|' + h];
  const dists = ['room', 'yard', 'ring'].filter(dk => (it.series || {})[dk]);
  /* a node that reads this issue at no distance sends distance: null and every band null (a model-only node,
     a fresh install): the day draws with no line, instead of the throw sending the page to the locked screen */
  const sd = (it.series || {})[it.hero_distance] || [];
  const dayVals = []; for (let h = 0; h < 24; h++) for (const dk of dists) { const j = idx(h); if (j != null && it.series[dk][j] != null) dayVals.push(it.series[dk][j]); }
  const usual = it.usual || [];
  // A scale a spike cannot flatten: the top is the larger of the line, the usual and the day's 95th percentile.
  const q95 = d3.quantile([...dayVals].sort(d3.ascending), 0.95) ?? 0;
  const top = Math.max(it.line ?? 0, d3.max(usual, u => u[1]) ?? 0, q95) * 1.12;
  const lo = k === 'heat' ? Math.floor(Math.min(d3.min(dayVals) ?? 0, d3.min(usual, u => u[0]) ?? 0) - 1) : 0;
  const y = d3.scaleLinear([lo, top], [m.t + H1, m.t]).nice(4);
  const g = svg.append('g');
  const defs = svg.append('defs');
  defs.append('pattern').attr('id', 'hatch-' + uid).attr('patternUnits', 'userSpaceOnUse').attr('width', 6).attr('height', 6).attr('patternTransform', 'rotate(45)')
    .append('line').attr('x1', 0).attr('y1', 0).attr('x2', 0).attr('y2', 6).attr('stroke', 'currentColor').attr('stroke-width', 1).attr('opacity', .28);
  svg.style('color', getComputedStyle(document.body).color);
  // y grid and values on the right (Apple Weather)
  for (const t of y.ticks(4)) {
    g.append('line').attr('x1', m.l).attr('x2', m.l + iw).attr('y1', y(t)).attr('y2', y(t)).attr('stroke', 'var(--hair)');
    g.append('text').attr('x', m.l + iw + 8).attr('y', y(t) + 4).text(fmt(t, t % 1 ? 1 : 0));
  }
  // hours not yet come: hatched, said once
  const nowH = date === dayOf(D.buckets[D.now]) ? hourOf(D.buckets[D.now]) + 1 : 24;
  if (nowH < 24) {
    g.append('rect').attr('x', x(nowH)).attr('y', m.t).attr('width', x(24) - x(nowH)).attr('height', H1).attr('fill', `url(#hatch-${uid})`);
    g.append('text').attr('x', x(nowH) + 6).attr('y', m.t + 12).text('not yet');
  }
  // the usual band, median to p90 of the last 14 days at each hour
  if (usual.length) {
    g.append('path').attr('fill', 'currentColor').attr('opacity', .08)
      .attr('d', d3.area().x((u, h) => x(h + .5)).y0(u => y(Math.max(lo, u[0]))).y1(u => y(Math.min(y.domain()[1], u[1]))).curve(d3.curveStep)(usual));
  }
  // the line: red, dashed (.linep), labelled in ink (lineLab: "WHO 15" for the air)
  if (it.line != null) {
    g.append('line').attr('class', 'linep').attr('x1', m.l).attr('x2', m.l + iw).attr('y1', y(it.line)).attr('y2', y(it.line));
    if (narrow) g.append('text').attr('class', 'lab').attr('x', m.l + 4).attr('y', y(it.line) - 5).text(lineLab(it));
    else g.append('text').attr('class', 'lab').attr('x', m.l - 8).attr('y', y(it.line) + 4).attr('text-anchor', 'end').text(lineLab(it));
  }
  // events: a bar from open to clear across the top, its answer a ring. The labels take lanes: each is
  // measured, kept inside the frame's right edge, and a label that would land on one already written
  // steps a row up (two spikes an hour apart used to print through each other). Lanes that fit above
  // the chart are m.t's own; beyond them the label overlaps as it did before — said, never dropped.
  const labLane = [], laneMax = Math.max(1, Math.floor((m.t - 14) / 13));
  const evs = [];
  for (const e of D.events.filter(e => e.issue === k)) {
    const a = dayOf(e.opened_at) === date ? hourOf(e.opened_at) + (+loc(e.opened_at).slice(14, 16)) / 60 : (dayOf(e.opened_at) < date ? 0 : null);
    if (a == null) continue;
    const zEnd = e.cleared_at ? (dayOf(e.cleared_at) === date ? hourOf(e.cleared_at) + (+e.cleared_at.slice(14, 16)) / 60 : (dayOf(e.cleared_at) > date ? 24 : null)) : nowH;
    if (zEnd == null || zEnd < a) continue;
    evs.push({ e, a, zEnd });
  }
  evs.sort((p, q) => p.a - q.a);
  for (const { e, a, zEnd } of evs) {
    g.append('rect').attr('x', x(a)).attr('y', m.t - 14).attr('width', Math.max(2, x(zEnd) - x(a))).attr('height', 4).attr('fill', 'currentColor');
    const t = g.append('text').attr('class', 'lab').text(`${e.kind} ${hhmm(e.opened_at)}`);
    const tw = (t.node().getComputedTextLength ? t.node().getComputedTextLength() : 0) || 0;
    let tx = x(a), lane = 0;
    if (tx + tw > m.l + iw) tx = Math.max(m.l, m.l + iw - tw);
    while (lane < labLane.length && labLane[lane] > tx - 6 && lane < laneMax) lane++;
    t.attr('x', tx).attr('y', m.t - 18 - lane * 13);
    labLane[lane] = Math.max(labLane[lane] || 0, tx + tw);
    if (e.answer && dayOf(e.answer.ts) === date) {
      const ah = hourOf(e.answer.ts) + (+e.answer.ts.slice(14, 16)) / 60;
      g.append('circle').attr('cx', x(ah)).attr('cy', m.t - 12).attr('r', 5).attr('fill', 'var(--ground)')
        .attr('stroke', e.answer.stage === 'acted' ? 'var(--rings)' : 'currentColor').attr('stroke-width', 2);
    }
  }
  // every distance: the house heavy, the others thin and dashed; a hole is a hole; labelled at the right end
  const STY = { room: [2.5, null], yard: [1.25, '5 3'], ring: [1.25, '1.5 3'] }, ends = [];
  for (const dk of dists) {
    const pts = d3.range(24).map(h => { const j = idx(h); return j == null ? null : [h + .5, it.series[dk][j]]; });
    g.append('path').attr('fill', 'none').attr('stroke', 'currentColor').attr('stroke-width', STY[dk][0]).attr('stroke-dasharray', STY[dk][1])
      .attr('opacity', dk === 'room' ? 1 : .7)
      .attr('d', d3.line().defined(p => p && p[1] != null).x(p => x(p[0])).y(p => y(Math.min(p[1], y.domain()[1]))).curve(d3.curveMonotoneX)(pts));
    const last = pts.filter(p => p && p[1] != null).pop();
    if (last) ends.push({ dk, x: x(last[0]) + 8, y: y(Math.min(last[1], y.domain()[1])) + 4 });
    // a reading above the scale is clipped and printed, never allowed to flatten the day
    pts.forEach(p => { if (p && p[1] != null && p[1] > y.domain()[1]) {
      g.append('text').attr('class', 'lab').attr('x', x(p[0]) + 9).attr('y', m.t + 12).text(`↑ ${fmt(p[1], it.dp)}`); } });
  }
  ends.sort((a, b) => a.y - b.y).forEach((e, n, A) => { if (n && e.y - A[n - 1].y < 12) e.y = A[n - 1].y + 12; });
  if (!narrow) ends.forEach(e => g.append('text').attr('class', e.dk === 'room' ? 'lab' : '').attr('x', e.x).attr('y', e.y).text(D.labels[e.dk]));
  // the hours over the line: red ticks along the floor (the mark carries the red, the words stay ink)
  for (let h = 0; h < 24; h++) { const j = idx(h); const v = j == null ? null : sd[j];
    if (it.line != null && v != null && v > it.line) g.append('rect').attr('x', x(h) + 1).attr('y', m.t + H1 - 6).attr('width', x(h + 1) - x(h) - 2).attr('height', 6).attr('fill', 'var(--signal-worse)'); }
  // high and low of the house, labelled on the line (Apple Weather)
  const hv = d3.range(24).map(h => { const j = idx(h); return j == null ? null : sd[j]; });
  const hiH = d3.maxIndex(hv.map(v => v ?? -Infinity)), loH = d3.minIndex(hv.map(v => v ?? Infinity));
  for (const [h, w] of [[hiH, 'H'], [loH, 'L']]) if (hv[h] != null && hv[h] <= y.domain()[1]) {
    g.append('text').attr('class', 'lab').attr('x', x(h + .5)).attr('y', y(hv[h]) + (w === 'H' ? -8 : 16)).attr('text-anchor', 'middle').text(`${w} ${fmt(hv[h], it.dp)}`); }
  // the hour axis is the scrubber's track
  for (let h = 0; h <= 24; h += narrow ? 6 : 3) g.append('text').attr('x', x(h)).attr('y', m.t + H1 + 16).attr('text-anchor', 'middle').text(String(h % 24).padStart(2, '0'));

  // ---- the week: one row a day on the same x, the cursor's day outlined ----
  const y0 = m.t + H1 + gap, shade = d3.scaleLinear([lo, top], [.08, .9]).clamp(true);
  if (nD) D.dates.forEach((dt, r) => {
    const yy = y0 + r * rowH, pd = (it.per_day || []).find(p => p.date === dt);
    g.append('text').attr('class', dt === date ? 'lab' : '').attr('x', m.l - 8).attr('y', yy + rowH - 3).attr('text-anchor', 'end').text(narrow ? dt.slice(8) : dLabel(dt).replace(',', ''));
    for (let h = 0; h < 24; h++) {
      const j = D.at[dt + '|' + h]; if (j == null) continue;
      const v = sd[j], over = it.line != null && v != null && v > it.line;
      g.append('rect').attr('x', x(h) + 1).attr('y', yy + 1).attr('width', x(h + 1) - x(h) - 2).attr('height', rowH - 2)
        .attr('fill', v == null ? `url(#hatch-${uid})` : 'currentColor').attr('opacity', v == null ? 1 : over ? .9 : shade(v))
        .style('cursor', 'pointer').on('click', () => o.pick && o.pick(j));
      /* over the line: an ink cell with a red tick on top, never a red fill (the layer) */
      if (over) g.append('rect').attr('x', x(h) + 1).attr('y', yy + 1).attr('width', x(h + 1) - x(h) - 2).attr('height', 2.5).attr('fill', 'var(--signal-worse)').attr('pointer-events', 'none');
    }
    g.append('text').attr('x', m.l + iw + 8).attr('y', yy + rowH - 3).attr('class', pd && pd.over ? 'lab' : '').text(pd ? (pd.over ? `${pd.over} h` : '0') : '');
    if (dt === date) g.append('rect').attr('x', m.l).attr('y', yy).attr('width', iw).attr('height', rowH).attr('fill', 'none').attr('stroke', 'currentColor').attr('stroke-width', 1.5);
  });
  if (nD) g.append('text').attr('x', m.l + iw + 8).attr('y', y0 - 6).text('over');
  // ---- the cursor: one hour, through the day and the week ----
  const ch = hourOf(D.buckets[S.i]) + .5, cv = val(k, it.hero_distance, S.i);
  g.append('line').attr('x1', x(ch)).attr('x2', x(ch)).attr('y1', m.t - 4).attr('y2', nD ? y0 + nD * rowH + 4 : m.t + H1).attr('stroke', 'var(--cells)').attr('stroke-width', 1.5);
  if (cv != null) g.append('circle').attr('cx', x(ch)).attr('cy', y(Math.min(cv, y.domain()[1]))).attr('r', 5).attr('fill', 'var(--ground)').attr('stroke', 'var(--cells)').attr('stroke-width', 2);
  g.append('circle').attr('cx', x(ch)).attr('cy', m.t + H1 + 4).attr('r', 7).attr('fill', 'var(--cells)');
  /* said in sentence case under the drawing: the day, what is drawn, how to move through it */
  o.head && (o.head.innerHTML = `${esc(dLabel(date))}: the house heavy, the street and the ring dashed${nD ? ', the week below' : ''}. Drag across the day, or focus it and use the arrow keys.`);
  o.scale && (o.scale.innerHTML = it.line != null ? `Scale to <span class="mono">${fmt(y.domain()[1], 0)}</span> ${said(it.unit)}.` : '');
  svg.selectAll('text').style('font-size', o.big ? '17px' : null);
  if (!o.pick) return;
  // scrub: press and drag inside the day; it moves the moment, never only a tooltip
  const toI = ev => { const [px] = d3.pointer(ev, svg.node()); const h = Math.max(0, Math.min(23, Math.floor(x.invert(px)))); const j = D.at[date + '|' + h]; return j; };
  let drag = false;
  svg.on('pointerdown', ev => { const [, py] = d3.pointer(ev, svg.node()); if (py > m.t + H1 + 22) return; drag = true; svg.node().setPointerCapture(ev.pointerId); const j = toI(ev); if (j != null) o.pick(j); })
     .on('pointermove', ev => { if (!drag) return; const j = toI(ev); if (j != null && j !== S.i) o.pick(j); })
     .on('pointerup pointercancel', () => { drag = false; });
}
