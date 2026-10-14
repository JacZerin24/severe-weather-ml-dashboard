#!/usr/bin/env node
// Run with: node scripts/check_dashboard.mjs
// Lightweight regression checks for the static, dependency-free dashboard.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const match=html.match(/<script>([\s\S]*?)<\/script>/i);
assert.ok(match,'Dashboard must contain its application script');
const js=match[1];
new vm.Script(js,{filename:'index.html (inline script)'});

function definition(from,to){
  const start=js.indexOf(from),end=js.indexOf(to,start+from.length);
  assert.ok(start>=0 && end>start,`Missing source section: ${from}`);
  return js.slice(start,end);
}
const pad=n=>String(n).padStart(2,'0');
const ymd=d=>`${d.getUTCFullYear()}${pad(d.getUTCMonth()+1)}${pad(d.getUTCDate())}`;
const csu=new Function('pad','ymd',definition('function csuFramesFromLoaded(', 'function csuCard(')+'; return csuFramesFromLoaded;')(pad,ymd);
const today=new Date(Date.UTC(2026,9,14));
const archived='https://schumacher.atmos.colostate.edu/weather/csu_mlp/archive/severe_gefso_2021_day5/2026101300/severe_ml_day5_gefso_101812.png';
const csuDay4=csu(4,archived,today);
assert.equal(csuDay4.length,4,'Day 4 has four eligible trend frames');
assert.ok(csuDay4.some(f=>f.src===archived),'Loaded fallback must remain in its valid-date trend');
assert.match(csuDay4[0].src,/severe_gefso_2021_day4\/2026101400/);
const csuDay1=csu(1,'https://schumacher.atmos.colostate.edu/weather/csu_mlp/archive/severe_gefso_2021_day1/2026101412/severe_ml_day1_all_gefso_101512.png',today);
assert.equal(csuDay1.length,10,'Day 1 spans ten eligible runs');
assert.match(csuDay1[0].src,/2026101412/);


for(const expected of ['function nadocastCwaPanel(', 'function addTrend(',
 'function nsslCard(', 'function spcCard(', 'function build()',
 'stepOlder()', 'stepNewer()', 'retryInFlight', 'setInterval(()=>location.reload(),30*60*1000)',
 'data.trends', 'NADOCast CWA Probabilities', 'NSSL GEFS ML v1.2']){
  assert.ok(js.includes(expected),`Missing required dashboard feature: ${expected}`);
}
assert.ok(!js.includes('api.allorigins.win'), 'Unreliable CONUS proxy must not be used');
assert.ok(!js.includes('nssl_combined_day'), 'Stale NSSL mirrored images must not be used');
console.log('Dashboard regression checks passed (JS syntax, CSU valid dates, CWA trends, source freshness safeguards).');
