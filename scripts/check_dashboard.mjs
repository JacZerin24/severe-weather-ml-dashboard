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
const nssl=readFileSync(new URL('../nssl-v12.js',import.meta.url),'utf8');
assert.match(html,/src="nssl-v12\\.js"/);
new vm.Script(nssl,{filename:'nssl-v12.js'});

const nsslHelpers=nssl.slice(nssl.indexOf('function nsslUtcDay('), nssl.indexOf('function nsslProbe('));
const nsslFns=new Function('ymd',nsslHelpers+';return {nsslFrames,nsslImageUrl};')(ymdForTest);
function ymdForTest(d){
  return `${d.getUTCFullYear()}${String(d.getUTCMonth()+1).padStart(2,'0')}${String(d.getUTCDate()).padStart(2,'0')}`;
}
const initDate=new Date(Date.UTC(2026,9,14));
const fixedDay1=nsslFns.nsslFrames(1,initDate);
assert.equal(fixedDay1.length,8);
assert.match(fixedDay1[0].src,/20261014\\/daily_ml2-2severe24_day1\\.png/);
assert.match(fixedDay1[1].src,/20261013\\/daily_ml2-2severe24_day2\\.png/);
assert.ok(fixedDay1.every(frame=>frame.valid==='20261014'));
const fixedDay7=nsslFns.nsslFrames(7,initDate);
assert.equal(fixedDay7.length,8);
assert.match(fixedDay7[7].src,/daily_ml2-2severe24_day14\\.png/);
assert.ok(fixedDay7.every(frame=>frame.valid==='20261020'));


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
 'function spcCard(', 'function build()',
 'stepOlder()', 'stepNewer()', 'retryInFlight', 'setInterval(()=>location.reload(),30*60*1000)',
 'data.trends', 'NADOCast CWA Probabilities']){
  assert.ok(js.includes(expected),`Missing required dashboard feature: ${expected}`);
}
assert.ok(!js.includes('api.allorigins.win'), 'Unreliable CONUS proxy must not be used');
assert.ok(!js.includes('nssl_combined_day')&&!nssl.includes('nssl_combined_day'), 'Stale NSSL mirrored images must not be used');
assert.match(nssl,/function nsslCard\(/);
assert.match(nssl,/basemap_greys_underlay_lcc\.png/);
assert.match(nssl,/daily_ml2-2severe24_day/);
console.log('Dashboard regression checks passed (NSSL URLs, fixed valid dates, map layers, CSU/CWA trends).');
