/* Curated research links, ordered for forecast-desk use.
 * These are external research resources, not a claim of operational status.
 */
const GUIDANCE_RESOURCES=[
  {
    title:'Convective hazard forecasting',
    context:'Medium-range and short-range model guidance',
    items:[
      {name:'StormNet',lab:'StormNet / OpenSnow',tag:'0–14 days / external viewer',
       about:'AI guidance for lightning, hail, damaging wind and tornado risk, with radar overlays. Open the live map; integrated data requires licensed API access.',
       url:'https://stormnet.ai/stormnet'},
      {name:'NCAR AI-NWP Convective Hazards',lab:'NSF NCAR',tag:'Day 1–8 / research',
       about:'Pangu, FengWu and WeatherNext-based convective-hazard probabilities, with run selection and GEFS comparisons.',
       url:'https://www2.mmm.ucar.edu/projects/ncar_ensemble/ainwp/index.php'},
      {name:'HRRR Neural-Network Hazards',lab:'NSF NCAR',tag:'CAM / severe',
       about:'Neural-network and updraft-helicity probabilities for tornado, hail and severe wind from HRRR guidance.',
       url:'https://www2.mmm.ucar.edu/projects/ncar_ensemble/camviewer/'},
      {name:'HRRRCast',lab:'NOAA GSL',tag:'AI / regional NWP',
       about:'Experimental HRRR-trained AI guidance, including high-resolution deterministic and ensemble output.',
       url:'https://gsl.noaa.gov/hrrrcast/'}
    ]
  },
  {
    title:'Storm-scale and nowcasting',
    context:'Short-fuse hazards and probability guidance',
    items:[
      {name:'ProbSevere v3',lab:'NOAA / CIMSS',tag:'Radar + satellite / ML',
       about:'Experimental real-time storm-object probabilities for severe thunderstorms and individual hazards.',
       url:'https://cimss.ssec.wisc.edu/severe_conv/psv3.html'},
      {name:'LightningCast',lab:'NOAA / CIMSS',tag:'GOES / 0–60 min',
       about:'Satellite-based machine-learning probabilities of lightning occurrence within the next hour.',
       url:'https://cimss.ssec.wisc.edu/severe_conv/pltg.html'},
      {name:'Cloud-based WoFS',lab:'NOAA NSSL',tag:'Storm-scale / ML severe',
       about:'Convection-resolving ensemble and machine-learning severe-hazard objects; availability and access vary.',
       url:'https://cbwofs.nssl.noaa.gov/'},
      {name:'Probabilistic Hazard Information',lab:'NOAA NSSL',tag:'PHI / limited access',
       about:'Storm-motion and hazard probability guidance built from ProbSevere, TORP and ProbLightning research.',
       url:'https://phi.nssl.noaa.gov/'}
    ]
  },
  {
    title:'Supporting guidance and workbenches',
    context:'Related predictors, visualization and research',
    items:[
      {name:'DESI Ensemble Viewer',lab:'NOAA GSL',tag:'Visualization',
       about:'Compare ensemble scenarios, parameters and probabilities, including experimental NOAA model output.',
       url:'https://gsl.noaa.gov/desi/'},
      {name:'CSU-MLP: Excessive Rainfall',lab:'Colorado State',tag:'Flash flood / ML',
       about:'Random-forest probabilities for excessive rainfall and convective hazards, alongside outlook guidance.',
       url:'https://schumacher.atmos.colostate.edu/hilla/csu_mlp/index.php'},
      {name:'WeatherNext / Weather Lab',lab:'Google DeepMind',tag:'Global AI / context',
       about:'Experimental AI global forecast guidance and large-scale environmental context, not a severe-hazard outlook.',
       url:'https://deepmind.google/science/weathernext/'}
    ]
  }
];
function buildResourceIndex(){
  const section=document.createElement('section');
  section.className='resources-section';
  section.id='resources';
  section.setAttribute('aria-labelledby','resource-title');
  const all=GUIDANCE_RESOURCES.flatMap(g=>g.items);
  const top=document.createElement('div');top.className='resources-top';
  const left=document.createElement('div');
  const eyebrow=document.createElement('p');eyebrow.className='resources-kicker';
  eyebrow.textContent='Reference desk / External guidance';
  const title=document.createElement('h2');title.id='resource-title';
  title.textContent='Additional AI & ML resources';
  const intro=document.createElement('p');intro.className='resources-intro';
  intro.textContent='Research products worth keeping in the forecast workflow. Links open at their original sources; product availability and access vary.';
  left.append(eyebrow,title,intro);
  const count=document.createElement('span');count.className='resources-count';
  count.textContent=all.length+' selected references';
  top.append(left,count);
  section.append(top);
  GUIDANCE_RESOURCES.forEach(group=>{
    const wrap=document.createElement('div');wrap.className='resource-group';
    const head=document.createElement('div');head.className='resource-group-heading';
    const name=document.createElement('h3');name.textContent=group.title;
    const context=document.createElement('p');context.textContent=group.context;
    head.append(name,context);
    const grid=document.createElement('div');grid.className='resource-grid';
    group.items.forEach(item=>{
      const anchor=document.createElement('a');
      anchor.className='resource-entry';
      anchor.href=item.url;
      anchor.target='_blank';
      anchor.rel='noopener noreferrer';
      anchor.setAttribute('aria-label','Open '+item.name+' at '+item.lab+' in a new tab');
      const meta=document.createElement('span');meta.className='resource-meta';
      meta.textContent=item.lab+'  /  '+item.tag;
      const heading=document.createElement('h4');heading.textContent=item.name;
      const description=document.createElement('p');description.textContent=item.about;
      const action=document.createElement('div');action.className='resource-action';
      const text=document.createElement('span');text.textContent='Visit resource';
      const arrow=document.createElement('span');arrow.textContent='↗';arrow.setAttribute('aria-hidden','true');
      action.append(text,arrow);
      anchor.append(meta,heading,description,action);
      grid.append(anchor);
    });
    wrap.append(head,grid);
    section.append(wrap);
  });
  const footer=document.createElement('div');footer.className='resource-footer';
  const disclaimer=document.createElement('span');
  disclaimer.textContent='Experimental and third-party products supplement official NWS/SPC guidance; they do not replace watches or warnings.';
  const curation=document.createElement('span');
  curation.textContent='Curated for meteorological operations · Links reviewed October 2026';
  footer.append(disclaimer,curation);
  section.append(footer);
  return section;
}
