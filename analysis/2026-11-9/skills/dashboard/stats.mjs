// Shared counting rules for the interface and the regression checks.
export function selectedSkills(data, view) {
  return data.skills.filter(s => (view.subset === 'all' || s[view.subset]) && (!view.family || s.family === view.family));
}

export function visibleGroups(data, view) {
  const skills = selectedSkills(data, view);
  return view.level === 'family'
    ? data.families.filter(f => skills.some(s => s.family === f.code))
    : skills;
}

export function skillSet(job, view, allowed) {
  return new Set((view.evidence === 'explicit' ? job.explicit : job.skills).filter(s => allowed.has(s)));
}

export function hasGroup(job, code, view, allowed) {
  for (const s of view.evidence === 'explicit' ? job.explicit : job.skills) {
    if (allowed.has(s) && (s === code || s.split('.')[0] === code)) return true;
  }
  return false;
}

export function filterJobs(jobs, filters) {
  return jobs.filter(j => (!filters.industry || (j.industry[0] || 'unknown') === filters.industry)
    && (!filters.occupation || (j.occupation[0] || 'unknown') === filters.occupation)
    && (!filters.province || (filters.province === 'unknown' ? !j.provinces.length : j.provinces.includes(filters.province)))
    && (!filters.employer || j.employer === filters.employer)
    && (!filters.from || j.date.slice(0, 7) >= filters.from)
    && (!filters.to || j.date.slice(0, 7) <= filters.to)
    && (!filters.education || (j.education || 'unavailable') === filters.education)
    && (!filters.entry || j.entry));
}

export function rankGroups(jobs, groups, view, allowed) {
  return groups.map(g => {
    const matches = jobs.filter(j => hasGroup(j, g.code, view, allowed));
    const explicit = matches.filter(j => hasGroup(j, g.code, {...view, evidence: 'explicit'}, allowed)).length;
    return {...g, count: matches.length, explicit, impliedOnly: matches.length - explicit,
      share: jobs.length ? matches.length / jobs.length * 100 : 0};
  }).sort((a, b) => b.count - a.count || a.code.localeCompare(b.code, undefined, {numeric: true}));
}

export function compareGroups(jobs, kind, level, focus, view, allowed) {
  const buckets = new Map();
  for (const job of jobs) {
    const code = job[kind][level-1] || 'unknown';
    if (!buckets.has(code)) buckets.set(code, []);
    buckets.get(code).push(job);
  }
  const overall = jobs.length ? jobs.filter(j => hasGroup(j, focus, view, allowed)).length / jobs.length * 100 : 0;
  return [...buckets].map(([code, group]) => {
    const count = group.filter(j => hasGroup(j, focus, view, allowed)).length;
    const share = count / group.length * 100;
    return {code, n: group.length, count, share, gap: share - overall};
  }).sort((a, b) => b.share - a.share || b.n - a.n);
}

export function provinceStats(jobs, provinces, focus, view, allowed) {
  return Object.entries(provinces).map(([code, [label, region]]) => {
    const group = jobs.filter(j => j.provinces.includes(code));
    const count = group.filter(j => hasGroup(j, focus, view, allowed)).length;
    return {code, label, region, n: group.length, count,
      share: group.length ? count / group.length * 100 : null,
      advertShare: jobs.length ? group.length / jobs.length * 100 : 0};
  });
}

export function regionStats(jobs, focus, view, allowed) {
  return ['Southern', 'Highlands', 'Momase', 'Islands'].map(region => {
    // An advert naming two provinces in one region still counts only once here.
    const group = jobs.filter(j => j.regions.includes(region));
    const count = group.filter(j => hasGroup(j, focus, view, allowed)).length;
    return {code: region, label: region, region, n: group.length, count,
      share: group.length ? count / group.length * 100 : null,
      advertShare: jobs.length ? group.length / jobs.length * 100 : 0};
  });
}

export function companions(jobs, groups, focus, view, allowed, minCount = 10) {
  const withFocus = jobs.filter(j => hasGroup(j, focus, view, allowed));
  return groups.filter(g => g.code !== focus).map(g => {
    const count = withFocus.filter(j => hasGroup(j, g.code, view, allowed)).length;
    const total = jobs.filter(j => hasGroup(j, g.code, view, allowed)).length;
    const conditional = withFocus.length ? count / withFocus.length * 100 : 0;
    const base = jobs.length ? total / jobs.length * 100 : 0;
    return {...g, count, total, n: withFocus.length, conditional, base, lift: base ? conditional/base : 0};
  }).filter(r => r.count >= minCount).sort((a, b) => b.conditional - a.conditional || b.count - a.count);
}

export function monthly(jobs, focus, view, allowed, first, last) {
  const months = new Map();
  let [year, month] = first.split('-').map(Number);
  while (`${year}-${String(month).padStart(2, '0')}` <= last.slice(0, 7)) {
    months.set(`${year}-${String(month).padStart(2, '0')}`, []);
    if (++month === 13) { month = 1; year++; }
  }
  jobs.forEach(j => { const key = j.date.slice(0,7); if (months.has(key)) months.get(key).push(j); });
  return [...months].map(([month, group]) => ({month, n: group.length,
    count: group.filter(j => hasGroup(j, focus, view, allowed)).length}));
}

export function csv(rows) {
  // Quoted text still needs spreadsheet-formula protection when opened in Excel.
  return '\ufeff' + rows.map(row => row.map(v => {
    let text = String(v ?? '');
    if (/^[=+@\-\t\r]/.test(text)) text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
  }).join(',')).join('\r\n');
}
