import {selectedSkills, visibleGroups, hasGroup, filterJobs, rankGroups, compareGroups,
  provinceStats, regionStats, companions, monthly, csv, skillSet} from './stats.mjs?v=20261116-2';

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const escape = value => String(value ?? '').replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
const num = value => Number(value).toLocaleString('en-GB');
const pct = value => value == null ? '—' : `${value.toFixed(1)}%`;
const title = text => text ? text[0].toUpperCase() + text.slice(1) : '';
const empty = (heading, message) => `<div class="empty"><strong>${escape(heading)}</strong>${escape(message)}</div>`;
const EDUCATION = {not_stated:'Level not stated', no_qualification_required:'No qualification required', secondary:'Secondary / high school',
  vocational:'Vocational / trade certificate', diploma:'Diploma', bachelor:"Bachelor’s degree", postgraduate:'Postgraduate', other:'Other qualification', unavailable:'Classification unavailable'};
const REGION_COLOURS = {Southern:'#007db7', Momase:'#00b6c9', Highlands:'#e9532b', Islands:'#8dc63f'};
let data, geo, cohort, groups, allowed, ranks, advertRows = [], mapRows = [], detailRequest = 0;
const detailCache = new Map();
const panels = Object.fromEntries(['compare','geo','pairs','time','adverts'].map(key=>[key,{focus:'S2.2',subset:'all',evidence:'all',filters:{}}]));
const state = {
  filters: {industry:'', occupation:'', province:'', employer:'', from:'', to:'', education:'', entry:false},
  view: {level:'category', subset:'all', evidence:'all', family:''}, focus:'S2.2', search:'', allRanks:false,
  compare:'occupation', compareLevel:1, compareMin:20, compareDisplay:'profile', compareAll:false,
  map:'skill', geoDisplay:'bar', geoLevel:'region', province:'PG04', pairOrder:'share', time:'count', advertSearch:'', advertScope:'all', advertSort:'newest', page:0,
};

function option(value, label) { return `<option value="${escape(value)}">${escape(label)}</option>`; }
function labelFor(kind, code, level = 1) { return data.labels[kind][level-1][code] || 'Unclassified / unavailable'; }
function focusLabel(code = state.focus) { return title([...data.skills,...data.families].find(g => g.code === code)?.label || code); }
function countFocus(jobs = cohort, focus = state.focus, view = state.view, codes = allowed) { return jobs.filter(j => hasGroup(j, focus, view, codes)).length; }
function download(name, rows) {
  const url = URL.createObjectURL(new Blob([csv(rows)], {type:'text/csv;charset=utf-8'}));
  const a = document.createElement('a'); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function toast(text) { $('#toast').textContent = text; $('#toast').hidden = false; setTimeout(() => $('#toast').hidden = true, 2800); }
function tooltip(event, text) {
  const box = $('#tooltip'); box.innerHTML = text; box.hidden = false;
  const rect = event.currentTarget.getBoundingClientRect();
  const x = event.clientX || rect.x + rect.width/2;
  const y = event.clientY || rect.y + rect.height/2;
  box.style.left = `${Math.max(10, Math.min(x + 14, innerWidth - box.offsetWidth - 12))}px`;
  box.style.top = `${Math.max(10, Math.min(y + 15, innerHeight - box.offsetHeight - 12))}px`;
}
function bindTooltips(root) {
  root.querySelectorAll('[data-tooltip]').forEach(el => {
    const show = event => tooltip(event, el.dataset.tooltip);
    el.addEventListener('mouseenter', show); el.addEventListener('mousemove', show); el.addEventListener('focus', show);
    el.addEventListener('mouseleave', () => $('#tooltip').hidden = true); el.addEventListener('blur', () => $('#tooltip').hidden = true);
  });
}
function setPressed(attribute, value) { $$(`[${attribute}]`).forEach(el => el.setAttribute('aria-pressed', String(el.getAttribute(attribute) === value))); }
function saveLocation() {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(state.filters)) if (value) params.set(key, String(value));
  for (const [key, value] of Object.entries(state.view)) if (value) params.set(key, value);
  params.set('focus', state.focus);
  for(const [key,value] of Object.entries(panels)) params.set(key,JSON.stringify(value));
  params.set('geoDisplay',state.geoDisplay);params.set('geoLevel',state.geoLevel);params.set('geoMeasure',state.map);
  history.replaceState(null, '', `${location.pathname}?${params}${location.hash}`);
}

function scrollToSection(hash = location.hash) {
  const section = document.getElementById(hash.slice(1));
  if (section) section.scrollIntoView({behavior:'instant', block:'start'});
}

function setupFilters() {
  for (const kind of ['industry','occupation']) {
    const counts = new Map();
    data.jobs.forEach(j => { const k = j[kind][0] || 'unknown'; counts.set(k, (counts.get(k)||0)+1); });
    $(`#${kind}`).innerHTML += [...counts].sort((a,b) => a[0].localeCompare(b[0], undefined, {numeric:true})).map(([code, n]) =>
      option(code, `${code === 'unknown' ? 'Unclassified / unavailable' : code+' · '+labelFor(kind,code)} (${num(n)})`)).join('');
  }
  $('#province').innerHTML += Object.entries(data.provinces).sort((a,b) => a[1][0].localeCompare(b[1][0])).map(([code,[name]]) => option(code,name)).join('') + option('unknown','No province assigned');
  $('#employer').innerHTML += [...new Set(data.jobs.map(j => j.employer))].sort().map(name => option(name,name)).join('');
  $('#education').innerHTML += Object.entries(EDUCATION).map(([code,label]) => option(code,label)).join('');
  $('#family').innerHTML += data.families.map(f => option(f.code,`${f.code} · ${title(f.label)}`)).join('');
  const params = new URLSearchParams(location.search);
  for (const key of Object.keys(state.filters)) {
    const element = $(`#${key}`), value = params.get(key);
    if (value != null) {
      if (key === 'entry') { state.filters[key] = value === 'true'; element.checked = state.filters[key]; }
      else if (element.tagName === 'SELECT') {
        if ([...element.options].some(o => o.value === value)) state.filters[key] = element.value = value;
      } else if (/^\d{4}-(0[1-9]|1[0-2])$/.test(value)) state.filters[key] = element.value = value;
    }
    element.addEventListener('change', () => {state.filters[key] = key === 'entry' ? element.checked : element.value; if(key === 'province' && data.provinces[element.value]) state.province = element.value; state.page = 0; render();});
  }
  for (const key of ['subset','evidence','family']) {
    const el = $(`#${key}`), value = params.get(key);
    if (value && [...el.options].some(o => o.value === value)) state.view[key] = el.value = value;
    el.addEventListener('change', () => {state.view[key] = el.value; state.page = 0; state.allRanks = false; render();});
  }
  if (params.get('level') === 'family') state.view.level = 'family';
  if (params.get('focus')) state.focus = params.get('focus');
  $('#from').min = $('#to').min = data.meta.first.slice(0,7);
  $('#from').max = $('#to').max = data.meta.last.slice(0,7);
}

function sectionContext(key) {
  const p=panels[key];
  const view={subset:p.subset,evidence:p.evidence,family:'',level:p.focus.includes('.')?'category':'family'};
  return {cohort:filterJobs(cohort,p.filters),groups:visibleGroups(data,view),
    allowed:new Set(selectedSkills(data,view).map(s=>s.code)),view,focus:p.focus};
}

function setupPanels() {
  const params=new URLSearchParams(location.search);
  for(const key of Object.keys(panels)) {
    const mount=$(`[data-panel="${key}"]`);
    let saved={};try{saved=JSON.parse(params.get(key)||'{}');}catch{}
    panels[key].focus=[...data.skills,...data.families].some(s=>s.code===saved?.focus)?saved.focus:state.focus;
    panels[key].subset=['all','shortlist','original'].includes(saved?.subset)?saved.subset:'all';
    panels[key].evidence=saved?.evidence==='explicit'?'explicit':'all';
    mount.innerHTML=`<div class="local-primary"><label class="local-skill">Skill or family in focus<select id="${key}-focus"></select></label><label>Evidence<select id="${key}-evidence">${$('#evidence').innerHTML}</select></label><label>Skill selection<select id="${key}-subset">${$('#subset').innerHTML}</select></label></div><details class="local-sample"><summary>Filter this section <span id="${key}-filter-count"></span></summary><div class="filter-grid">${['industry','occupation','province','employer','education'].map(k=>`<label>${title(k)}<select id="${key}-${k}" data-local-filter="${k}">${$('#'+k).innerHTML}</select></label>`).join('')}<label>First seen, from<input type="month" id="${key}-from" data-local-filter="from" min="${data.meta.first.slice(0,7)}" max="${data.meta.last.slice(0,7)}"></label><label>First seen, through<input type="month" id="${key}-to" data-local-filter="to" min="${data.meta.first.slice(0,7)}" max="${data.meta.last.slice(0,7)}"></label><label class="check-label"><input type="checkbox" id="${key}-entry" data-local-filter="entry">Entry, graduate or apprenticeship opportunity</label></div><button class="text-button" id="${key}-clear">Clear this section’s filters</button></details><p class="local-note" id="${key}-sample-note"></p>`;
    for(const field of ['focus','evidence','subset']) $(`#${key}-${field}`).addEventListener('change',e=>{
      panels[key][field]=e.target.value;
      if(key==='adverts')state.page=0;
      renderPanel(key);
    });
    mount.querySelectorAll('[data-local-filter]').forEach(el=>{
      const field=el.dataset.localFilter,value=saved?.filters?.[field];
      if(field==='entry') {el.checked=value===true;panels[key].filters[field]=el.checked;}
      else if(el.tagName==='SELECT' && [...el.options].some(o=>o.value===value)) panels[key].filters[field]=el.value=value;
      else if(['from','to'].includes(field)&&/^\d{4}-(0[1-9]|1[0-2])$/.test(value||''))panels[key].filters[field]=el.value=value;
      el.addEventListener('change',()=>{
        panels[key].filters[field]=field==='entry'?el.checked:el.value;
        if(key==='geo'&&field==='province'&&data.provinces[el.value])state.province=el.value;
        if(key==='adverts')state.page=0;
        renderPanel(key);
      });
    });
    $(`#${key}-clear`).addEventListener('click',()=>{panels[key].filters={};mount.querySelectorAll('[data-local-filter]').forEach(el=>{el.value='';el.checked=false;});state.page=0;renderPanel(key);});
  }
  if(params.get('geoDisplay')==='map')state.geoDisplay='map';
  if(['province','region'].includes(params.get('geoLevel')))state.geoLevel=params.get('geoLevel');
  if(params.get('geoMeasure')==='count')state.map='count';
}

function renderPanelControls(key) {
  const p=panels[key], skills=selectedSkills(data,{...p,family:''});
  const families=data.families.filter(f=>skills.some(s=>s.family===f.code));
  if(![...skills,...families].some(s=>s.code===p.focus))p.focus=skills[0]?.code||'';
  $(`#${key}-focus`).innerHTML=`<optgroup label="${families.length} skill families">${families.map(g=>option(g.code,`${g.code} · ${title(g.label)}`)).join('')}</optgroup>${families.map(f=>`<optgroup label="${escape(f.code+' · '+f.short)}">${skills.filter(s=>s.family===f.code).map(g=>option(g.code,`${g.code} · ${title(g.label)}`)).join('')}</optgroup>`).join('')}`;
  for(const field of ['focus','evidence','subset'])$(`#${key}-${field}`).value=p[field];
  const n=sectionContext(key).cohort.length, count=Object.values(p.filters).filter(Boolean).length;
  $(`#${key}-filter-count`).textContent=count?`(${count} active)`:'';
  $(`#${key}-sample-note`).textContent=`${num(n)} adverts in this section. These controls affect only this section. Main sample filters still apply${cohort.length!==data.jobs.length?` (${num(cohort.length)} adverts)` : ''}.`;
}

function renderPanel(key) {
  $('#tooltip').hidden=true;
  renderPanelControls(key);
  ({compare:renderComparison,geo:renderMap,pairs:renderPairs,time:renderTime,adverts:renderAdverts})[key]();
  saveLocation();
}

function renderIntro() {
  const n = data.jobs.length;
  const all = new Set(data.skills.map(s => s.code));
  const view = {evidence:'all'};
  const families = rankGroups(data.jobs, data.families, view, all);
  $('#hero-count').textContent = num(n);
  $('#hero-bars').innerHTML = families.map(f => `<div class="hero-bar"><span>${escape(f.short)}</span><div class="track"><div class="fill" style="width:${f.share}%"></div></div><span class="value">${f.share.toFixed(0)}%</span></div>`).join('');
  const a = data.meta.audit;
  const refresh=data.meta.classification_refresh;
  $('#method-join').textContent = refresh
    ? `The existing industry, occupation, education and location pipeline has processed all ${num(data.meta.records)} snapshot records. It reused ${num(refresh.reused_unchanged)} unchanged responses and classified ${num(refresh.new_adverts)} new adverts plus ${num(refresh.changed_adverts)} with edited text, using the same model and prompt. ${num(a.matched)} included adverts have usable, matching records. ${num(a.advert_status_disagrees||0)} have conflicting job-advert flags across the two runs, so their industry, occupation and locations are withheld. Unclassified codes in successful responses remain unclassified.`
    : `Industry, occupation, education and work locations come from the earlier classification run. ${num(a.matched)} adverts have matching, usable classifications. ${num(data.meta.adverts-a.matched)} do not. Missing codes can also reflect an unclassified answer rather than an unfinished request.`;
  $('#method-capped').textContent = `${num(a.unrecovered_capped)} included job adverts have a source description that reached the scraper’s original length cap without a matching HTML recovery. The browser flags these. Full available source text appears on inspection, without a dashboard length limit.`;
}

function render() {
  $('#tooltip').hidden = true;
  const availableFamilies = new Set(selectedSkills(data,{...state.view,family:''}).map(s=>s.family));
  [...$('#family').options].forEach(o=>o.disabled=Boolean(o.value && !availableFamilies.has(o.value)));
  if(state.view.family && !availableFamilies.has(state.view.family)) {state.view.family='';$('#family').value='';}
  cohort = filterJobs(data.jobs, state.filters);
  allowed = new Set(selectedSkills(data, state.view).map(s => s.code));
  groups = visibleGroups(data, state.view);
  ranks = rankGroups(cohort, groups, state.view, allowed);
  if (!groups.some(g => g.code === state.focus)) state.focus = ranks[0]?.code || '';
  const active = Object.values(state.filters).filter(Boolean).length;
  $('#cohort-count').textContent = `${num(cohort.length)} adverts selected`;
  $('#cohort-label').textContent = active ? `${active} filter${active>1?'s':''} applied · ${pct(cohort.length/data.jobs.length*100)} of all job adverts` : 'Full sample · 9 non-job notices excluded';
  $('#extra-active').textContent = [state.filters.from,state.filters.to,state.filters.education,state.filters.entry].some(Boolean) ? '(active)' : '';
  $('#filter-note').textContent = state.filters.from && state.filters.to && state.filters.from > state.filters.to
    ? 'The start month is after the end month. Change the date range or reset the filters.'
    : 'Filters apply to all sections below. Percentages use the selected adverts, including adverts with no assigned skill.';
  const selection = state.view.subset === 'shortlist' ? 'Research shortlist: the 47 coloured categories in the supplied ESCO document, all colours combined.'
    : state.view.subset === 'original' ? 'Original study: the 24 categories in the emailed Indeed prompt.' : 'All 74 categories in the S1–S8 codebook.';
  $('#view-note').textContent = `${selection} This changes the skills shown, not the advert denominator. ${state.view.level === 'family' ? 'Each family counts adverts with any included child category, once per advert.' : 'Codes ending in .0 are general categories within a family, not family totals.'}`;
  setPressed('data-level',state.view.level);
  $('#implied-key').hidden = state.view.evidence === 'explicit';
  for(const key of Object.keys(panels)) renderPanelControls(key);
  renderRanks(); renderDetail(); renderComparison(); renderMap(); renderPairs(); renderTime(); renderAdverts(); saveLocation();
}

function renderRanks() {
  const query = state.search.toLowerCase().trim();
  const matching = ranks.filter(g => `${g.code} ${g.label}`.toLowerCase().includes(query));
  const shown = state.allRanks || query || state.view.level === 'family' ? matching : matching.slice(0,15);
  $('#ranking-title').textContent = `Share of ${num(cohort.length)} adverts with each ${state.view.level === 'family' ? 'family' : 'skill'}`;
  $('#ranking').innerHTML = !cohort.length ? empty('No adverts match these filters','Try a wider date range or reset the filters.') : !matching.length ? empty('No matching skills','Try another name or ESCO code.') : shown.map(g =>
    `<button class="rank-row ${g.code === state.focus ? 'selected' : ''}" data-skill="${g.code}" aria-pressed="${g.code === state.focus}" aria-label="${escape(g.label)}, ${pct(g.share)}, ${num(g.count)} adverts"><span class="rank-label">${escape(title(g.label))}<small>${g.code}${g.code.endsWith('.0') ? ' · general category' : ''}</small></span><span class="rank-track"><span class="rank-explicit" style="width:${g.explicit/cohort.length*100}%"></span><span class="rank-implied" style="width:${g.impliedOnly/cohort.length*100}%"></span></span><span class="rank-value">${pct(g.share)}<small>${num(g.count)} adverts</small></span></button>`).join('');
  $$('#ranking [data-skill]').forEach(el => el.addEventListener('click', () => selectSkill(el.dataset.skill)));
  $('#show-all').hidden = state.view.level === 'family' || Boolean(query) || matching.length <= 15 || !cohort.length;
  $('#show-all').textContent = state.allRanks ? 'Show top 15' : `Show all ${matching.length} categories`;
}

function renderDetail() {
  const g = ranks.find(g => g.code === state.focus);
  if (!g) { $('#skill-detail').innerHTML = empty('No skill selected','Change the skill selection.'); return; }
  const family = data.families.find(f => f.code === g.code.split('.')[0]);
  const children = selectedSkills(data,state.view).filter(s => s.family === g.code);
  $('#skill-detail').innerHTML = `<p class="eyebrow">IN FOCUS / ${g.code}</p><h3>${escape(title(g.label))}</h3><p>${escape(family?.short || '')}${state.view.level === 'category' ? ' · '+g.code : ' · family'}</p><strong class="big-share">${cohort.length ? pct(g.share) : '—'}</strong><p>${num(g.count)} of ${num(cohort.length)} selected adverts</p><div class="detail-metrics"><div><strong>${num(g.explicit)}</strong><span>Explicit evidence</span></div><div><strong>${num(g.impliedOnly)}</strong><span>Strongly implied only</span></div></div>${g.description ? `<details open><summary>What this category covers</summary><p>${escape(g.description)}</p></details>` : `<details><summary>${children.length} included categories</summary>${children.map(c=>`<button class="child-link" data-child="${c.code}">${c.code} · ${escape(title(c.label))}</button>`).join('')}</details>`}${g.code.endsWith('.0') ? '<p class="small">This general category is a child of '+family.code+'. Switch to families to see the combined total.</p>' : ''}<button class="outline-button" id="view-evidence">Read matching adverts ↗</button><p class="small">${state.view.level === 'family' ? 'At least one included child skill counts as a match. An explicit child takes precedence in the colour split.' : 'One advert can include several categories. Each percentage has the same advert denominator.'}</p>`;
  $('#view-evidence').addEventListener('click', () => { panels.adverts={focus:state.focus,subset:state.view.subset,evidence:state.view.evidence,filters:{}};renderPanelControls('adverts'); state.advertScope = 'focus'; state.page = 0; $('#advert-scope').value = 'focus'; renderAdverts(); scrollToSection('#adverts'); });
  $$('[data-child]').forEach(el=>el.addEventListener('click',()=>{state.view.level='category';state.focus=el.dataset.child;render();}));
}

function selectSkill(code) {state.focus = code; render();}

function renderComparison() {
  const {cohort,groups,allowed,view,focus}=sectionContext('compare');
  const level = state.compareLevel;
  const rows = compareGroups(cohort,state.compare,level,focus,view,allowed);
  const unknown = rows.find(r=>r.code === 'unknown');
  const known = rows.filter(r=>r.code !== 'unknown');
  const eligible = known.filter(r=>r.n >= state.compareMin);
  const sorted = state.compareDisplay === 'matrix' ? [...eligible].sort((a,b)=>b.n-a.n) : eligible;
  const shown = state.compareAll ? sorted : sorted.slice(0,state.compareDisplay === 'matrix' ? 16 : 20);
  const overall = cohort.length ? countFocus(cohort,focus,view,allowed)/cohort.length*100 : 0;
  $('#compare-note').textContent = `${focusLabel(focus)}. ${num(cohort.length-(unknown?.n||0))} of ${num(cohort.length)} selected adverts have a usable ${state.compare} classification at level ${level}. ${state.compareDisplay === 'matrix' ? 'The matrix compares the included skill families, using this section’s skill selection and evidence settings.' : 'Orange markers show the share across all selected adverts, including unclassified adverts.'}`;
  let content = '';
  if (!shown.length) content = empty('No groups meet this sample size','Lower the minimum advert count or broaden the filters.');
  else if (state.compareDisplay === 'matrix') {
    const families = data.families.filter(f => selectedSkills(data,view).some(s=>s.family === f.code));
    content = `<div class="heatmap-scroll"><table class="heatmap"><caption class="sr-only">Percent of adverts with each skill family by ${state.compare}</caption><thead><tr><th>${state.compare === 'industry' ? 'ISIC industry' : 'ISCO occupation'} / adverts</th>${families.map(f=>`<th scope="col">${f.code}<br>${escape(f.short)}</th>`).join('')}</tr></thead><tbody>${shown.map(row=>{
      const jobs = cohort.filter(j=>j[state.compare][level-1] === row.code);
      return `<tr><th scope="row">${escape(labelFor(state.compare,row.code,level))}<small>${row.code} · n = ${num(row.n)}</small></th>${families.map(f=>{
        const n = jobs.filter(j=>hasGroup(j,f.code,view,allowed)).length, share = n/row.n*100;
        return `<td style="background:${heat(share)};color:${share>=72?'white':'#102b3a'}"><button data-matrix-family="${f.code}" data-tooltip="${escape(`<strong>${escape(f.short)}</strong>${escape(labelFor(state.compare,row.code,level))}<br>${num(n)} / ${num(row.n)} adverts · ${pct(share)}`)}" aria-label="${escape(f.short)}, ${escape(labelFor(state.compare,row.code,level))}, ${pct(share)}">${share.toFixed(0)}%</button></td>`;
      }).join('')}</tr>`;
    }).join('')}</tbody></table></div><p class="small muted">Select a cell to focus on that family. Shading runs from 0% to 100%.</p>`;
  } else content = `<div class="comparison-legend"><span><i class="legend-line"></i>All selected adverts: ${pct(overall)}</span><span>Right column: percentage-point difference</span></div><div class="compare-grid">${shown.map(row=>`<div class="comparison-row ${row.n<20?'low':''}"><span class="comparison-name">${escape(labelFor(state.compare,row.code,level))}<small>${row.code} · ${num(row.count)} of ${num(row.n)} adverts${row.n<20?' · small sample':''}</small></span><span class="comparison-track"><i class="fill" style="width:${row.share}%"></i><i class="baseline" style="left:${overall}%"></i></span><span class="comparison-share">${pct(row.share)}</span><span class="gap ${row.gap>0?'positive':''}">${row.gap>0?'+':''}${row.gap.toFixed(1)} pp</span></div>`).join('')}</div>`;
  if (eligible.length > (state.compareDisplay === 'matrix' ? 16 : 20)) content += `<button id="all-comparisons" class="text-button">${state.compareAll?'Show fewer groups':`Show all ${eligible.length} eligible groups`}</button>`;
  content += `<div class="comparison-unknown">${num(unknown?.n||0)} selected adverts are unclassified or unavailable at this level${unknown?.n ? `; ${pct(unknown.share)} contain the skill in focus` : ''}. ${known.filter(r=>r.n<state.compareMin).length} classified groups fall below the minimum sample size. Labels are joined by classification code, so spelling variants do not create separate groups.</div>`;
  $('#comparison').innerHTML = content;
  $('#all-comparisons')?.addEventListener('click',()=>{state.compareAll=!state.compareAll;renderComparison();});
  $$('[data-matrix-family]').forEach(el=>el.addEventListener('click',()=>{panels.compare.focus=el.dataset.matrixFamily;renderPanel('compare');}));
  bindTooltips($('#comparison'));
}

function heat(p) {
  const a=[237,245,247], b=[0,86,143], t=Math.max(0,Math.min(1,p/100));
  return `rgb(${a.map((v,i)=>Math.round(v+(b[i]-v)*t)).join(',')})`;
}
const project = ([lon,lat]) => [(lon-140.15)*46+12,(-lat-.3)*46];
function pathFor(feature, projection=project) {
  const geom=feature.geometry, polygons=geom.type==='MultiPolygon'?geom.coordinates:[geom.coordinates];
  return polygons.map(poly=>poly.map(ring=>ring.map((p,i)=>`${i?'L':'M'}${projection(p).map(x=>x.toFixed(1)).join(',')}`).join('')+'Z').join('')).join('');
}
function countColour(n) {
  const colours=['#e0e7e9','#d5eaf0','#abd3e2','#78b7d0','#4296bb','#087bac','#004b83'];
  const index=n===0?0:n<25?1:n<100?2:n<250?3:n<500?4:n<1000?5:6;
  return colours[index];
}
function mapFill(r) { return state.map === 'count' ? countColour(r.n) : r.n < 20 ? 'url(#small-sample)' : heat(r.share); }
function renderMap() {
  const {cohort,groups,allowed,view,focus}=sectionContext('geo');
  $('#tooltip').hidden = true;
  const isMap=state.geoDisplay==='map';
  const level=isMap?'province':state.geoLevel;
  $('#map-layout').hidden=!isMap;
  $('#geo-bars').hidden=isMap;
  $('#geo-level').value=level;
  $('#geo-level').disabled=isMap;
  setPressed('data-geo-display',state.geoDisplay);
  setPressed('data-map',state.map);
  mapRows = provinceStats(cohort,data.provinces,focus,view,allowed);
  const rows=level==='region'?regionStats(cohort,focus,view,allowed):mapRows;
  const byCode = Object.fromEntries(mapRows.map(r=>[r.code,r]));
  const locationField=level==='region'?'regions':'provinces';
  const mapped = cohort.filter(j=>j[locationField].length).length;
  $('#map-subtitle').textContent = state.map === 'count'
    ? `${num(mapped)} of ${num(cohort.length)} adverts have an assigned ${level}. Counts can overlap where adverts name several locations.`
    : `${focusLabel(focus)}. Percentage of adverts within each ${level}; n is the total number of adverts in that ${level}.${isMap?' Provinces with fewer than 20 adverts are hatched.':' Small samples (n < 20) are marked.'}`;
  const maximum=state.map==='count'?Math.max(1,...rows.map(r=>r.n)):100;
  const sorted=[...rows].sort((a,b)=>state.map==='count'?b.n-a.n:(b.share??-1)-(a.share??-1)||b.n-a.n);
  $('#geo-bars').innerHTML=cohort.length?`<div class="geo-chart-heading"><h3>${state.map==='skill'?escape(focusLabel(focus)):'Adverts by '+level}</h3><span>${state.map==='skill'?'Percent of adverts · 0–100%':'Number of adverts'}</span></div><div class="geo-bar-chart ${level==='province'?'province-bars':''}">${sorted.map(r=>`<div class="geo-bar-row ${r.n>0&&r.n<20?'small-sample':''}" data-area="${r.code}" data-n="${r.n}" data-count="${r.count}"><span class="geo-bar-label">${escape(r.label)} <small>(n = ${num(r.n)})</small>${r.n>0&&r.n<20?'<em>Small sample</em>':''}</span><div class="geo-bar-track"><div style="width:${(state.map==='skill'?r.share||0:r.n)/maximum*100}%;background:${REGION_COLOURS[r.region]}"></div></div><span class="geo-bar-value">${state.map==='skill'?pct(r.share):num(r.n)}<small>${state.map==='skill'?`${num(r.count)} with skill`:pct(r.advertShare)+' of sample'}</small></span></div>`).join('')}</div><p class="chart-note">Each advert counts once per ${level}, even when it names several places within that ${level}. An advert can count in more than one ${level}. Adverts without an assigned ${level} are shown in the coverage figures below.</p>`:empty('No adverts match this section’s filters','Clear the section filters or widen the main sample.');
  const shapes = (features, projection) => features.map(f=>{
    const r=byCode[f.properties.code];
    const tip=`<strong>${escape(r.label)}</strong>${num(r.n)} adverts · ${pct(r.advertShare)} of selection<br>${num(r.count)} with skill in focus${r.n?' · '+pct(r.share):''}${r.n<20?'<br>Fewer than 20 adverts':''}`;
    return `<path d="${pathFor(f,projection)}" class="province-shape ${r.code===state.province?'selected':''}" fill="${mapFill(r)}" fill-rule="evenodd" tabindex="0" role="button" aria-label="${escape(r.label)}, ${r.n} adverts" data-province="${r.code}" data-tooltip="${escape(tip)}"/>`;
  }).join('');
  const labels = [
    ['PG01',142,-7.8,142,-7.8],['PG02',144.9,-8.2,144.9,-8.2],['PG03',147.8,-8.1,147.6,-9],
    ['PG04',146.5,-10.6,147.18,-9.47],['PG05',153.1,-10.9,150.6,-10.2],['PG06',150.8,-8.9,148.4,-8.9],
    ['PG12',148.7,-6.9,146.9,-6.6],['PG13',145.7,-3.4,145.2,-4.8],['PG14',143.2,-3,143.3,-4.1],
    ['PG15',141.1,-2.3,141.7,-3.8],['PG16',147.1,-1.3,147,-2.1],['PG17',152.4,-2.4,151.7,-3.2],
    ['PG18',154.3,-4.2,152,-4.8],['PG19',151.2,-7,150,-5.7],['PG20',157.7,-6.1,155.3,-6.1],
  ];
  const labelSvg=labels.map(([code,x,y,ax,ay])=>{
    const [px,py]=project([x,y]),[qx,qy]=project([ax,ay]),r=byCode[code];
    const name=code==='PG04'?'NCD / Port Moresby':code==='PG20'?'Bougainville':r.label;
    const value=state.map==='count'?num(r.n):r.n>=20?pct(r.share):'n < 20';
    return `<path class="map-line" d="M${qx},${qy} L${px},${py-5}"/><text x="${px}" y="${py}" class="map-label" text-anchor="middle">${escape(name)}<tspan class="map-label-num" x="${px}" dy="13">${value}</tspan></text>`;
  }).join('');
  const ncd=project([147.18,-9.47]);
  const highlandFeatures=geo.features.filter(f=>data.provinces[f.properties.code][1]==='Highlands');
  const insetProjection=([lon,lat])=>[(lon-142.1)*65+25,(-lat-4.6)*65+432];
  const insetLabels=[['PG21',142.8,-5.7],['PG08',143.45,-5.15],['PG09',144.35,-5.55],['PG22',144.72,-5.95],['PG10',145.03,-6.35],['PG11',145.65,-6.15],['PG07',143.45,-6.35]];
  $('#map').innerHTML=`<defs><pattern id="small-sample" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="#e3ecef"/><path d="M0 6L6 0" stroke="#b8cbd4" stroke-width="1"/></pattern></defs><text x="710" y="350" class="map-ocean">SOLOMON SEA</text><text x="440" y="535" class="map-ocean">CORAL SEA</text>${shapes(geo.features,project)}${labelSvg}<circle class="map-circle ${state.province==='PG04'?'selected':''}" cx="${ncd[0]}" cy="${ncd[1]}" r="4" data-province="PG04" role="button" tabindex="0" aria-label="Select National Capital District"/><path class="map-line" d="M112 227 L65 405" stroke-dasharray="3 4"/><text x="32" y="417" class="map-inset-title">HIGHLANDS / ENLARGED</text>${shapes(highlandFeatures,insetProjection)}${insetLabels.map(([code,x,y])=>{const [px,py]=insetProjection([x,y]);const name=byCode[code].label.replace(' Highlands',' H.');return `<text class="map-label small" x="${px}" y="${py}" text-anchor="middle">${escape(name)}</text>`;}).join('')}`;
  $('#map-legend').innerHTML = state.map === 'count'
    ? `<span>Adverts</span>${[[0,'0'],[1,'1–24'],[25,'25–99'],[100,'100–249'],[250,'250–499'],[500,'500–999'],[1000,'1,000+']].map(([n,label])=>`<span class="legend-scale"><i style="background:${countColour(n)}"></i>${label}</span>`).join('')}`
    : `<span>Share with skill</span>${[0,20,40,60,80,100].map(p=>`<span class="legend-scale"><i style="background:${heat(p)}"></i>${p}%</span>`).join('')}<span> / Hatched: n &lt; 20</span>`;
  $$('#map [data-province]').forEach(el=>{
    const select=()=>{state.province=el.dataset.province;renderMap();};
    el.addEventListener('click',select);el.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();select();}});
  });
  bindTooltips($('#map'));
  const unknown=cohort.filter(j=>!j[locationField].length);
  const unmatched=unknown.filter(j=>j.join!=='matched').length;
  $('#map-accounting').innerHTML=`<div><strong>${num(mapped)}</strong>adverts with at least one assigned ${level}</div><div><strong>${num(unknown.length)}</strong>without a ${level}: ${num(unmatched)} lack a usable classification, ${num(unknown.length-unmatched)} have no assigned ${level}</div><div><strong>${num(cohort.filter(j=>j[locationField].length>1).length)}</strong>adverts span several ${level}s and appear in each. ${num(cohort.filter(j=>j.nationwide).length)} flag PNG-wide scope.</div>`;
  $('.province-table summary').textContent=`View all ${rows.length} ${level}s as a table`;
  $('#province-table').innerHTML=`<table><thead><tr><th>${title(level)}</th><th>Adverts (n)</th><th>% of sample</th><th>With focus skill</th><th>% within ${level}</th></tr></thead><tbody>${[...rows].sort((a,b)=>b.n-a.n).map(r=>`<tr><td>${level==='province'?`<button data-table-province="${r.code}">${escape(r.label)}</button>`:escape(r.label)}</td><td>${num(r.n)}</td><td>${pct(r.advertShare)}</td><td>${num(r.count)}</td><td>${pct(r.share)}${r.n<20?' *':''}</td></tr>`).join('')}</tbody></table><p class="small muted">* Fewer than 20 adverts. Location shares can add to more than 100%.</p>`;
  $$('[data-table-province]').forEach(el=>el.addEventListener('click',()=>{state.province=el.dataset.tableProvince;state.geoDisplay='map';renderPanel('geo');}));
  renderProvinceDetail();
}

function renderProvinceDetail() {
  const {cohort,groups,allowed,view,focus}=sectionContext('geo');
  const r=mapRows.find(r=>r.code===state.province);
  const local=cohort.filter(j=>j.provinces.includes(r.code));
  const top=rankGroups(local,groups,view,allowed).filter(g=>g.count).slice(0,3);
  $('#province-detail').innerHTML=`<p class="eyebrow">PROVINCE PROFILE</p><h3>${escape(r.label)}</h3><span class="region"><i class="swatch" style="background:${REGION_COLOURS[r.region]}"></i> ${r.region}</span><strong class="province-count">${num(r.n)}</strong><p>${pct(r.advertShare)} of selected adverts</p><div class="province-skill"><strong>${pct(r.share)}</strong>${escape(focusLabel(focus))}<p>${num(r.count)} of ${num(r.n)} province adverts${r.n<20?'<br>Small sample. Interpret with care.':''}</p></div><div class="mini-rank">${top.map(g=>`<div><span>${escape(title(g.label))}</span><span>${pct(g.share)}</span></div>`).join('')}</div><button class="text-button" id="filter-province">${state.filters.province===r.code?'Clear province filter':'Filter to this province'} ↗</button>`;
  $('#filter-province').textContent=panels.geo.filters.province===r.code?'Clear section’s province filter':'Filter this section to '+r.label;
  $('#filter-province').addEventListener('click',()=>{panels.geo.filters.province=panels.geo.filters.province===r.code?'':r.code;$('#geo-province').value=panels.geo.filters.province;renderPanel('geo');});
}

function renderPairs() {
  const {cohort,groups,allowed,view,focus}=sectionContext('pairs');
  const rows=companions(cohort,groups,focus,view,allowed);
  if(state.pairOrder==='lift') rows.sort((a,b)=>b.lift-a.lift||b.count-a.count);
  const n=countFocus(cohort,focus,view,allowed);
  $('#pair-focus').textContent = `In focus: ${focusLabel(focus)}`;
  $('#pair-note').textContent = `${num(n)} selected adverts include this ${view.level}. Bars show the companion’s share among those adverts. The dark marker shows its share across all ${num(cohort.length)} selected adverts. The right column shows relative frequency.`;
  $('#pairs').innerHTML=rows.length?rows.slice(0,10).map(r=>`<div class="pair-row"><button class="pair-label" data-pair="${r.code}">${escape(title(r.label))}<small>${r.code} · ${num(r.count)} adverts together</small></button><div class="pair-track"><div class="pair-fill" style="width:${r.conditional}%"></div><i class="pair-base" style="left:${r.base}%"></i></div><strong>${pct(r.conditional)}</strong><span class="pair-lift">${r.lift.toFixed(1)}×</span></div>`).join(''):empty('Too few shared adverts','No companion meets the minimum of 10 adverts under these settings.');
  $$('[data-pair]').forEach(el=>el.addEventListener('click',()=>{panels.pairs.focus=el.dataset.pair;renderPanel('pairs');}));
}

function renderTime() {
  const {cohort,groups,allowed,view,focus}=sectionContext('time');
  const from=[state.filters.from,panels.time.filters.from,data.meta.first.slice(0,7)].filter(Boolean).sort().at(-1);
  const to=[state.filters.to,panels.time.filters.to,data.meta.last.slice(0,7)].filter(Boolean).sort()[0];
  const rows=monthly(cohort,focus,view,allowed,from,to);
  const W=1170,H=290,left=48,right=15,top=25,bottom=49,inner=H-top-bottom;
  const maximum=state.time==='count'?Math.max(50,Math.ceil(Math.max(0,...rows.map(r=>r.n))/100)*100):100;
  const step=(W-left-right)/Math.max(1,rows.length),bar=Math.min(48,step*.6);
  const y=v=>H-bottom-v/maximum*inner;
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Monthly ${state.time==='count'?'advert counts':'skill prevalence'}"><title>Monthly ${state.time==='count'?'advert counts':escape(focusLabel(focus))}</title>`;
  for(let i=0;i<=4;i++){const value=maximum*i/4;svg+=`<line class="time-grid" x1="${left}" x2="${W-right}" y1="${y(value)}" y2="${y(value)}"/><text class="time-axis" x="${left-10}" y="${y(value)+4}" text-anchor="end">${Math.round(value)}${state.time==='skill'?'%':''}</text>`;}
  let line='';
  rows.forEach((r,i)=>{
    const x=left+step*(i+.5), share=r.n?r.count/r.n*100:null;
    const partial=['2025-10','2026-11'].includes(r.month), gap=r.month==='2026-09';
    const note=partial?'Partial month':gap?'Scraper paused 1–19 September':'';
    const value=state.time==='count'?r.n:share;
    const tip=`<strong>${r.month}</strong>${num(r.n)} adverts first seen<br>${num(r.count)} with skill in focus${r.n?' · '+pct(share):''}${note?'<br>'+note:''}`;
    if(state.time==='count') svg+=`<rect class="time-bar ${partial?'partial':''} ${gap?'gap-month':''}" x="${x-bar/2}" y="${y(value)}" width="${bar}" height="${Math.max(0,y(0)-y(value))}" tabindex="0" data-tooltip="${escape(tip)}" aria-label="${r.month}: ${r.n} adverts"/><text class="time-axis" x="${x}" y="${y(value)-8}" text-anchor="middle">${num(value)}</text>`;
    else if(share!==null) {line+=`${i&&rows[i-1].n?'L':'M'}${x},${y(share)} `;svg+=`<circle class="time-point" cx="${x}" cy="${y(share)}" r="4.5" tabindex="0" data-tooltip="${escape(tip)}" aria-label="${r.month}: ${pct(share)}, ${r.count} of ${r.n} adverts"/>`;}
    const date=new Date(r.month+'-15T12:00:00Z');
    svg+=`<text class="time-axis" x="${x}" y="${H-bottom+22}" text-anchor="middle">${date.toLocaleDateString('en-GB',{month:'short',timeZone:'UTC'})}${partial?'*':gap?'†':''}<tspan x="${x}" dy="14">${r.month.slice(0,4)}</tspan></text>`;
  });
  if(line)svg+=`<path class="time-line" d="${line}" pointer-events="none"/>`;
  svg+='</svg>';
  $('#timeline').innerHTML = rows.length && cohort.length ? svg : empty('No monthly observations','Adjust the current filters.');
  $('#time-note').textContent = state.time==='count'?`Observed adverts by month first seen. Total under current filters: ${num(cohort.length)}.`:`${focusLabel(focus)}. Each month uses its own advert count as the denominator. Changes can reflect the mix of adverts and employers.`;
  bindTooltips($('#timeline'));
}

function renderAdverts() {
  const {cohort,groups,allowed,view,focus}=sectionContext('adverts');
  const query=state.advertSearch.trim().toLowerCase();
  advertRows=cohort.filter(j=>(!query||`${j.id} ${j.title} ${j.employer}`.toLowerCase().includes(query))
    &&(state.advertScope!=='focus'||hasGroup(j,focus,view,allowed))
    &&(state.advertScope!=='empty'||skillSet(j,view,allowed).size===0)
    &&(state.advertScope!=='capped'||j.capped)
    &&(state.advertScope!=='unmatched'||j.join!=='matched'));
  advertRows.sort((a,b)=>state.advertSort==='skills' ? skillSet(b,view,allowed).size-skillSet(a,view,allowed).size || b.date.localeCompare(a.date) : state.advertSort==='oldest' ? a.date.localeCompare(b.date)||Number(a.id)-Number(b.id) : b.date.localeCompare(a.date)||Number(b.id)-Number(a.id));
  const pages=Math.max(1,Math.ceil(advertRows.length/12));
  state.page=Math.min(state.page,pages-1);
  const slice=advertRows.slice(state.page*12,(state.page+1)*12);
  $('#advert-count').textContent=`${num(advertRows.length)} adverts${state.advertScope==='focus'?' with '+focusLabel(focus):''}`;
  $('#advert-rows').innerHTML=slice.length?slice.map(j=>`<tr data-job="${j.id}"><td><button class="advert-title" data-open-job="${j.id}">${escape(j.title)}</button><span class="advert-id">#${j.id}${j.capped?' · source length flag':''}${j.join!=='matched'?' · classification unavailable':''}</span></td><td>${escape(j.employer)}</td><td>${j.date}</td><td><span class="skill-count">${skillSet(j,view,allowed).size}</span></td><td class="row-arrow" aria-hidden="true">↗</td></tr>`).join(''):'<tr><td colspan="5">'+empty('No adverts match','Try another search or change the browser selection.')+'</td></tr>';
  $('#page-label').textContent=`Page ${state.page+1} of ${pages}`;
  $('#prev-page').disabled=state.page===0;$('#next-page').disabled=state.page>=pages-1;
  $$('[data-job]').forEach(el=>el.addEventListener('click',()=>openAdvert(el.dataset.job)));
}

function formatDescription(raw) {
  // Repair HTML-induced inline breaks while retaining paragraphs and list items.
  return raw.replace(/\r/g,'').split(/\n\s*\n/).map(block=>
    block.split(/\n(?=\s*[-•]\s*\S)/).map(line=>line.replace(/\s+/g,' ').trim()).join('\n')
  ).filter(Boolean).join('\n\n');
}

async function openAdvert(id) {
  const {view,allowed}=sectionContext('adverts');
  const job=data.jobs.find(j=>j.id===id), request=++detailRequest;
  $('#dialog-id').textContent=`ADVERT #${id}`;
  $('#dialog-content').innerHTML='<div class="dialog-heading"><h2 id="dialog-title">Loading advert…</h2></div>';
  if(!$('#advert-dialog').open)$('#advert-dialog').showModal();
  try {
    if(!detailCache.has(job.detail)) {
      const response=await fetch(`data/details/${job.detail}.json`);
      if(!response.ok)throw new Error(`Unable to load saved advert (${response.status})`);
      detailCache.set(job.detail,await response.json());
    }
    if(request!==detailRequest)return;
    const detail=detailCache.get(job.detail)[id];
    const shown=skillSet(job,view,allowed);
    const safeUrl=/^https:\/\/www\.pngworkforce\.com\//.test(detail.url)?detail.url:null;
    $('#dialog-content').innerHTML=`<div class="dialog-heading"><h2 id="dialog-title">${escape(job.title)}</h2><p class="dialog-sub">${escape(job.employer)} · First seen ${job.date} · ${escape(detail.location||'Location not stated')}</p><div class="dialog-actions">${safeUrl?`<a href="${escape(safeUrl)}" target="_blank" rel="noopener">Original advert ↗</a>`:''}<button class="text-button" id="copy-id">Copy job ID</button><button class="text-button" id="download-advert">Download text ↓</button></div>${job.capped?'<p class="notice">The source description reached the scraper’s original length cap. All available text is shown here, but the original posting may have been longer.</p>':''}${job.join!=='matched'?'<p class="notice">Industry, occupation and location classifications are unavailable for this version of the advert.</p>':''}</div><div class="dialog-grid"><div class="source-text"><h3>Full available advert text</h3><p>${escape(formatDescription(detail.description))}</p></div><div class="evidence-list"><h3>${detail.skills.length} assigned categories <span class="muted small">/ ${shown.size} under current settings</span></h3><p class="small muted">Faded entries are outside the current skill or evidence selection. Quotes use the run’s whitespace and punctuation normalisation.</p>${detail.skills.length?detail.skills.map(s=>`<article class="evidence-item ${shown.has(s.code)?'':'outside-view'}"><h4><small>${s.code}</small>${escape(title(data.skills.find(g=>g.code===s.code).label))}</h4><span class="evidence-tag">${s.evidence_basis==='explicit'?'Explicit':'Strongly implied'}</span><blockquote>${escape(s.quote)}</blockquote><p>${escape(s.motivation)}</p></article>`).join(''):'<p>No skill category was assigned to this advert.</p>'}${detail.classification_summary?`<details><summary class="small">Classification notes</summary><p class="small muted">${escape(detail.classification_summary)}</p><p class="small muted">Province evidence: ${escape(detail.location_evidence.join(' / ')||'None')}</p></details>`:''}</div></div>`;
    $('#copy-id').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(id);toast('Job ID copied');}catch{toast(`Job ID: ${id}`);}});
    $('#download-advert').addEventListener('click',()=>{
      const url=URL.createObjectURL(new Blob([`${job.title}\n${job.employer}\nJob ID: ${id}\n\n${detail.description}`],{type:'text/plain;charset=utf-8'}));
      const a=document.createElement('a');a.href=url;a.download=`advert-${id}.txt`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
  } catch(error) {if(request===detailRequest)$('#dialog-content').innerHTML=empty('Advert could not load',error.message);}
}

function reset() {
  for(const key of Object.keys(state.filters)){state.filters[key]=key==='entry'?false:'';if(key==='entry')$('#entry').checked=false;else $(`#${key}`).value='';}
  state.page=0;render();
}

function events() {
  $('#sign-out').hidden=location.protocol!=='https:';
  $$('a[href^="#"]').forEach(link=>link.addEventListener('click',event=>{
    const hash=link.getAttribute('href');
    if(!document.getElementById(hash.slice(1)))return;
    event.preventDefault();
    if(location.hash!==hash)history.pushState(null,'',hash);
    scrollToSection(hash);
  }));
  window.addEventListener('hashchange',()=>scrollToSection());
  $('#reset').addEventListener('click',reset);
  $$('[data-level]').forEach(el=>el.addEventListener('click',()=>{state.view.level=el.dataset.level;state.allRanks=false;state.search='';$('#skill-search').value='';if(state.view.level==='family')state.focus=state.focus.split('.')[0];render();}));
  $('#skill-search').addEventListener('input',e=>{state.search=e.target.value;renderRanks();});
  $('#show-all').addEventListener('click',()=>{state.allRanks=!state.allRanks;renderRanks();});
  $$('[data-compare]').forEach(el=>el.addEventListener('click',()=>{state.compare=el.dataset.compare;state.compareAll=false;setPressed('data-compare',state.compare);renderComparison();}));
  $('#compare-level').addEventListener('change',e=>{state.compareLevel=Number(e.target.value);state.compareAll=false;renderComparison();});
  $('#compare-min').addEventListener('change',e=>{state.compareMin=Number(e.target.value);renderComparison();});
  $('#compare-display').addEventListener('change',e=>{state.compareDisplay=e.target.value;state.compareAll=false;renderComparison();});
  $$('[data-map]').forEach(el=>el.addEventListener('click',()=>{state.map=el.dataset.map;renderPanel('geo');}));
  $$('[data-geo-display]').forEach(el=>el.addEventListener('click',()=>{state.geoDisplay=el.dataset.geoDisplay;renderPanel('geo');}));
  $('#geo-level').addEventListener('change',e=>{state.geoLevel=e.target.value;renderPanel('geo');});
  $('#pair-order').addEventListener('change',e=>{state.pairOrder=e.target.value;renderPairs();});
  $$('[data-time]').forEach(el=>el.addEventListener('click',()=>{state.time=el.dataset.time;setPressed('data-time',state.time);renderTime();}));
  $('#advert-search').addEventListener('input',e=>{state.advertSearch=e.target.value;state.page=0;renderAdverts();});
  $('#advert-scope').addEventListener('change',e=>{state.advertScope=e.target.value;state.page=0;renderAdverts();});
  $('#advert-sort').addEventListener('change',e=>{state.advertSort=e.target.value;state.page=0;renderAdverts();});
  $('#prev-page').addEventListener('click',()=>{state.page--;renderAdverts();});
  $('#next-page').addEventListener('click',()=>{state.page++;renderAdverts();});
  $('#close-dialog').addEventListener('click',()=>$('#advert-dialog').close());
  $('#advert-dialog').addEventListener('click',e=>{if(e.target===$('#advert-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
  $('#export-skills').addEventListener('click',()=>download('png-skill-prevalence.csv',[
    ['code','label','adverts_with_skill','denominator_adverts','percent','explicit_adverts','strongly_implied_only_adverts','hierarchy','skill_selection','evidence','filters'],
    ...ranks.map(r=>[r.code,r.label,r.count,cohort.length,r.share.toFixed(6),r.explicit,r.impliedOnly,state.view.level,state.view.subset,state.view.evidence,JSON.stringify(state.filters)])]));
  $('#export-adverts').addEventListener('click',()=>{const {view,allowed}=sectionContext('adverts');download('png-selected-adverts.csv',[
    ['job_id','title','employer','first_seen','industry_1digit','occupation_1digit','provinces','skills_under_current_settings','skills_all_assigned','source_length_flag','classification_join','skill_selection','evidence'],
    ...advertRows.map(j=>[j.id,j.title,j.employer,j.date,j.industry[0]?labelFor('industry',j.industry[0]):'',j.occupation[0]?labelFor('occupation',j.occupation[0]):'',j.provinces.map(p=>data.provinces[p][0]).join('; '),[...skillSet(j,view,allowed)].join('; '),j.skills.join('; '),j.capped,j.join,view.subset,view.evidence])]);});
  document.addEventListener('keydown',e=>{if(e.key==='Escape')$('#tooltip').hidden=true;});
  const observer=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){$$('.masthead nav a').forEach(a=>a.classList.toggle('active',a.hash==='#'+e.target.id));}},{rootMargin:'-15% 0px -65% 0px'});
  for(const id of ['explore','compare','geography','adverts','methods'])observer.observe($('#'+id));
}

try {
  const responses=await Promise.all([fetch('data/dashboard.json'),fetch('data/provinces.json')]);
  if(responses.some(r=>!r.ok))throw new Error('The local data files are missing. Run build_data.py in the dashboard folder.');
  [data,geo]=await Promise.all(responses.map(r=>r.json()));
  setupFilters();setupPanels();renderIntro();events();render();$('#loading').hidden=true;
  // Charts and filters add height after the browser's initial fragment scroll.
  // Align the requested section only once the populated layout is visible.
  requestAnimationFrame(()=>scrollToSection());
  // Test hooks expose computed research state only; no API credentials or model calls.
  window.dashboard={get state(){return state;},get cohort(){return cohort;},get ranks(){return ranks;},get data(){return data;},get panels(){return panels;},sectionContext};
} catch(error) {
  console.error(error);
  $('#loading p').textContent=`Could not load the dashboard. ${location.protocol==='file:'?'Start the local server with python3 serve.py, then open http://127.0.0.1:8765.':error.message}`;
}
