const state = {
  jobs: [], section: '可报名', favorites: new Set(JSON.parse(localStorage.getItem('gss_favorites') || '[]')),
  progress: JSON.parse(localStorage.getItem('gss_progress') || '{}'), visibleLimit: 60
};
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const dateLabel = (value) => value ? value.slice(0, 10) : '未提取';

async function loadData() {
  try {
    const response = await fetch(`data/jobs.json?v=${Date.now()}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.jobs = data.jobs || [];
    if (!state.jobs.some(job => job.section === '可报名') && state.jobs.some(job => job.section === '趋势参考')) {
      state.section = '趋势参考';
      document.querySelectorAll('.tab').forEach(tab => tab.classList.toggle('active', tab.dataset.section === state.section));
    }
    $('updated').textContent = data.generated_at ? `数据更新：${new Date(data.generated_at).toLocaleString('zh-CN')}` : '尚未运行采集';
    renderHealth(data.source_runs || []);
    populateFilters();
    render();
  } catch (error) {
    $('updated').textContent = '岗位库读取失败';
    $('empty').hidden = false;
    $('empty').querySelector('span').textContent = `请稍后重试：${error.message}`;
  }
}

function populateFilters() {
  const cities = [...new Set(state.jobs.map(j => j.city).filter(Boolean))].sort();
  const categories = [...new Set(state.jobs.map(j => j.category).filter(Boolean))].sort();
  $('city').insertAdjacentHTML('beforeend', cities.map(v => `<option>${esc(v)}</option>`).join(''));
  $('category').insertAdjacentHTML('beforeend', categories.map(v => `<option>${esc(v)}</option>`).join(''));
}

function filteredJobs() {
  const query = $('search').value.trim().toLowerCase();
  const city = $('city').value, category = $('category').value, level = $('level').value, progress = $('progress').value;
  let jobs = state.jobs.filter(job => {
    const sectionOk = state.section === '收藏' ? state.favorites.has(job.id) : job.section === state.section;
    const text = [job.title, job.organization, job.position, job.majors, job.summary, job.source_name, job.source_file].join(' ').toLowerCase();
    return sectionOk && (!query || text.includes(query)) && (!city || job.city === city) &&
      (!category || job.category === category) && (!level || job.match?.level === level) &&
      (!progress || (state.progress[job.id] || '未处理') === progress);
  });
  const sort = $('sort').value;
  jobs.sort((a, b) => sort === 'date' ? String(b.published_at).localeCompare(String(a.published_at)) :
    sort === 'deadline' ? String(a.deadline || '9999').localeCompare(String(b.deadline || '9999')) :
    (b.match?.score || 0) - (a.match?.score || 0));
  return jobs;
}

function render() {
  const jobs = filteredJobs();
  const visibleJobs = jobs.slice(0, state.visibleLimit);
  $('jobList').replaceChildren(...visibleJobs.map(renderCard));
  $('loadMore').hidden = visibleJobs.length >= jobs.length;
  $('loadMore').textContent = `加载更多岗位（还有 ${Math.max(0, jobs.length - visibleJobs.length)} 条）`;
  $('empty').hidden = jobs.length > 0;
  $('resultCount').textContent = `${jobs.length} 个岗位`;
  $('totalCount').textContent = state.jobs.length;
  $('availableCount').textContent = state.jobs.filter(j => j.section === '可报名').length;
  $('uncertainCount').textContent = state.jobs.filter(j => j.section === '身份待核实').length;
  $('highCount').textContent = state.jobs.filter(j => j.match?.level === '高把握').length;
  $('favoriteCount').textContent = state.favorites.size;
}

function renderCard(job) {
  const node = $('jobTemplate').content.firstElementChild.cloneNode(true);
  const level = job.match?.level || '待确认';
  const levelClass = level === '高把握' ? 'high' : level === '不符合' ? 'blocked' : 'pending';
  const scoreLabel = job.section === '趋势参考' ? `相关 ${job.match?.score || 0}` : `${job.match?.score || 0}分`;
  node.querySelector('.badges').innerHTML = `<span class="badge ${levelClass}">${esc(level)} · ${scoreLabel}</span><span class="badge">${esc(job.category)}</span><span class="badge">${esc(job.city)}</span>`;
  node.querySelector('h3').textContent = job.position || job.title;
  node.querySelector('.org').textContent = job.organization || job.title;
  node.querySelector('.job-meta').innerHTML = `<span>学历：${esc(job.education || '待查')}</span><span>专业：${esc(job.majors || '见附件')}</span><span>发布：${dateLabel(job.published_at)}</span><span>截止：${dateLabel(job.deadline)}</span>`;
  node.querySelector('.summary').textContent = job.summary || '请查看官方公告和职位表附件。';
  const notes = [...(job.match?.blockers || []), ...(job.match?.warnings || []), ...(job.match?.reasons || [])];
  node.querySelector('.match-explain').innerHTML = notes.length ? `<ul>${notes.slice(0, 5).map(v => `<li>${esc(v)}</li>`).join('')}</ul>` : '当前未发现明显限制条件，报名前仍需核对官方职位表。';
  const sourceParts = [job.source_name || '来源名称待补充'];
  if (job.source_file) sourceParts.push(`文件：${job.source_file}`);
  if (job.source_sheet) sourceParts.push(`工作表：${job.source_sheet}`);
  if (job.source_row) sourceParts.push(`第${job.source_row}行`);
  if (job.source_code) sourceParts.push(`代码：${job.source_code}`);
  node.querySelector('.source-detail').innerHTML = `<strong>来源</strong><span>${sourceParts.map(esc).join(' · ')}</span>`;
  const favorite = node.querySelector('.favorite');
  favorite.textContent = state.favorites.has(job.id) ? '★' : '☆';
  favorite.addEventListener('click', () => toggleFavorite(job.id));
  const progress = node.querySelector('.progress-select');
  progress.value = state.progress[job.id] || '未处理';
  progress.addEventListener('change', event => setProgress(job.id, event.target.value));
  const link = node.querySelector('.official-link');
  if (job.source_url) {
    link.href = job.source_url;
    link.textContent = '查看官方来源';
  } else {
    link.removeAttribute('href');
    link.classList.add('disabled');
    link.textContent = '官方链接待补充';
  }
  return node;
}

function toggleFavorite(id) {
  state.favorites.has(id) ? state.favorites.delete(id) : state.favorites.add(id);
  localStorage.setItem('gss_favorites', JSON.stringify([...state.favorites]));
  render();
}
function setProgress(id, value) { state.progress[id] = value; localStorage.setItem('gss_progress', JSON.stringify(state.progress)); render(); }
function renderHealth(runs) {
  $('sourceHealth').innerHTML = runs.length ? runs.map(run => `<div class="source-row"><span class="${run.ok ? 'ok' : 'fail'}">${run.ok ? '正常' : '失败'}</span><span>${esc(run.source)} · ${run.found || 0} 条 ${run.error ? `· ${esc(run.error)}` : ''}</span></div>`).join('') : '<p>尚未运行在线采集。</p>';
}

document.querySelectorAll('.tab').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(tab => tab.classList.toggle('active', tab === button));
  state.section = button.dataset.section; state.visibleLimit = 60; render();
}));
['search','city','category','level','progress','sort'].forEach(id => $(id).addEventListener(id === 'search' ? 'input' : 'change', () => { state.visibleLimit = 60; render(); }));
$('resetFilters').addEventListener('click', () => { ['search','city','category','level','progress'].forEach(id => $(id).value = ''); $('sort').value = 'score'; render(); });
$('loadMore').addEventListener('click', () => { state.visibleLimit += 60; render(); });
loadData();
