/* NSSL GEFS ML v1.2 interactive cards.
 * Images are transparent probabilities; the viewer layers geographic basemaps separately.
 * Date-based URLs were obtained from the actual Chrome Network request.
 */
const NSSL_ROOT='https://apps.nssl.noaa.gov/s2s-severe/';
const NSSL_VIEWER=NSSL_ROOT+'forecast_gefs_ml.html';
const NSSL_MAX_DAY=15;
const NSSL_HISTORY=8;
const NSSL_BASEMAP_LINES=NSSL_ROOT+'images/static_overlays/basemap_lcc.png';
const NSSL_BASEMAP_GREY=NSSL_ROOT+'images/static_underlays/basemap_greys_underlay_lcc.png';
const nsslProbeCache=new Map();

function nsslUtcDay(date,offset=0){
  const value=new Date(Date.UTC(date.getUTCFullYear(),date.getUTCMonth(),date.getUTCDate()));
  value.setUTCDate(value.getUTCDate()+offset);
  return value;
}
function nsslImageUrl(date,lead){
  return NSSL_ROOT+'images/forecast/'+ymd(date)+'/daily_ml2-2severe24_day'+lead+'.png';
}
// This is a d(prog)/dt comparison for the *same valid calendar day*.
function nsslFrames(day,reference){
  const frames=[];
  for(let offset=0;offset<NSSL_HISTORY&&day+offset<=NSSL_MAX_DAY;offset++){
    const init=nsslUtcDay(reference,-offset),lead=day+offset;
    const valid=nsslUtcDay(init,lead-1);
    frames.push({
      src:nsslImageUrl(init,lead),init:ymd(init),valid:ymd(valid),lead,
      label:'Init '+ymd(init)+' 00Z · Day '+lead+' · Valid '+ymd(valid)
    });
  }
  return frames;
}
function nsslProbe(url){
  if(nsslProbeCache.has(url))return nsslProbeCache.get(url);
  const promise=new Promise(resolve=>{
    const img=new Image();
    const timer=setTimeout(()=>{img.onload=null;img.onerror=null;resolve(null);},12000);
    img.onload=()=>{
      clearTimeout(timer);
      resolve(img.naturalWidth>=100&&img.naturalHeight>=100?
        {width:img.naturalWidth,height:img.naturalHeight}:null);
    };
    img.onerror=()=>{clearTimeout(timer);resolve(null);};
    img.src=url;
  });
  nsslProbeCache.set(url,promise);
  return promise;
}
// The official viewer serves geography separately from dated forecast shading.
// Use the real Lambert-Conformal map layers, not directory guesses.
// If the optional grey underlay is unavailable, retain geographic outlines.
function nsslCard(day){
  const c=card(day===1?
    '<a href="'+NSSL_VIEWER+'" target="_blank" rel="noopener">NSSL GEFS ML v1.2</a>':
    'NSSL GEFS ML v1.2');
  const map=document.createElement('div');
  map.className='nssl-map';
  map.tabIndex=0;
  map.setAttribute('role','button');
  map.setAttribute('aria-label','Enlarge NSSL severe probability map');
  const underlay=document.createElement('img');
  underlay.alt='';underlay.loading='lazy';
  const shading=document.createElement('img');
  shading.alt='';shading.className='nssl-shading';
  shading.loading='lazy';
  const outlines=document.createElement('img');
  outlines.alt='';outlines.className='nssl-lines';outlines.loading='lazy';
  const empty=document.createElement('div');empty.className='nssl-empty';
  empty.textContent='Checking recent 00Z NSSL forecast cycles…';
  map.append(underlay,shading,outlines,empty);
  const label=document.createElement('div');label.className='label';
  const status=document.createElement('div');status.className='status-detail';
  const mapAlert=document.createElement('div');mapAlert.className='nssl-basemap-alert';
  const legend=document.createElement('div');legend.className='nssl-legend';
  legend.setAttribute('aria-label','Severe probability color scale');
  const ticks=document.createElement('div');ticks.className='nssl-legend-labels';
  ['2%','5%','10%','15%','30%','45%','60%+'].forEach(value=>{
    const span=document.createElement('span');span.textContent=value;ticks.append(span);
  });
  const source=document.createElement('div');source.className='nssl-help';
  const link=document.createElement('a');link.href=NSSL_VIEWER;
  link.target='_blank';link.rel='noopener';
  link.textContent='Official NSSL v1.2 viewer ↗';
  source.append(link);
  c.append(map,legend,ticks,label,status,mapAlert,source);
  const frames=nsslFrames(day,new Date());
  let index=-1,loading=false;
  const controls=document.createElement('div'),prev=document.createElement('button'),
        next=document.createElement('button'),tag=document.createElement('span');
  controls.className='trend';tag.className='trend-label';
  prev.type=next.type='button';
  prev.textContent='◀ Prev';next.textContent='Next ▶';
  prev.title='Older 00Z initialization, same valid date';
  next.title='Newer 00Z initialization, same valid date';
  c.insertBefore(controls,source);
  controls.append(prev,tag,next);
  function updateControls(){
    prev.disabled=loading||index<0||index>=frames.length-1;
    next.disabled=loading||index<=0;
    tag.textContent=index<0?'Checking…':'Trend '+(index+1)+' / '+frames.length;
  }
  function showFrame(frame,dimensions,i){
    index=i;
    shading.src=frame.src;
    shading.alt='NSSL severe probability initialized '+frame.init+
      ' 00Z valid '+frame.valid+' (Day '+frame.lead+')';
    map.style.setProperty('--nssl-ratio',String(dimensions.width/dimensions.height));
    map.style.aspectRatio=dimensions.width+' / '+dimensions.height;
    empty.hidden=true;
    label.textContent=frame.label;
    status.textContent='NSSL severe probability v1.2'+
      (i>0?' · Earlier initialization, latest file unavailable':'');
    updateControls();
  }
  async function seek(start,direction){
    if(loading)return;
    loading=true;updateControls();
    let found=false;
    for(let i=start;i>=0&&i<frames.length;i+=direction){
      const size=await nsslProbe(frames[i].src);
      if(!c.isConnected)return;
      if(size){showFrame(frames[i],size,i);found=true;break;}
    }
    if(!found&&index<0){
      empty.hidden=false;
      empty.textContent='NSSL imagery could not be loaded by this browser. Open the official viewer.';
      status.textContent='No current or recent 00Z map verified; outdated EAX mirror not used.';
    }else if(!found){
      status.textContent='No additional available forecast cycles in that direction.';
    }
    loading=false;updateControls();
  }
  prev.onclick=()=>seek(index+1,1);
  next.onclick=()=>seek(index-1,-1);
  trendState.set(shading,{
    stepOlder(){if(index>=0&&!loading)seek(index+1,1);},
    stepNewer(){if(index>0&&!loading)seek(index-1,-1);}
  });
  updateControls();
  // Overlay path confirmed from NSSL's original forecast viewer.
  // Boundaries are deliberately composited above the shaded probability PNG.
  nsslProbe(NSSL_BASEMAP_LINES).then(size=>{
    if(!c.isConnected)return;
    if(size){
      outlines.src=NSSL_BASEMAP_LINES;
      mapAlert.textContent='';
    }else{
      mapAlert.textContent='NSSL geographic outlines could not be loaded. Open the official viewer for geographic context.';
    }
  });
  // This is a separate *underlay*, not the outline image.
  nsslProbe(NSSL_BASEMAP_GREY).then(size=>{
    if(!c.isConnected)return;
    if(size)underlay.src=NSSL_BASEMAP_GREY;
    // Keep the outline overlay usable even when the grey land/sea raster fails.
  });
  seek(0,1);
  function toggleZoom(){
    const zoomed=map.classList.contains('zoomed');
    document.querySelectorAll('img.zoomed,.nssl-map.zoomed')
      .forEach(el=>el.classList.remove('zoomed'));
    map.classList.toggle('zoomed',!zoomed);
    document.body.classList.toggle('zoom-active',!zoomed);
    if(!zoomed)map.focus();
  }
  map.onclick=toggleZoom;
  map.onkeydown=event=>{
    if((event.key==='Enter'||event.key===' ')&&!event.repeat){
      event.preventDefault();toggleZoom();
    }
  };
  return c;
}
