/* ============================================================
   MVP HONESTO (decisão D parcial): controles que ainda viram fachada.
   Single/Cross/Snapshot/Batch: pipes JÁ respeitados via --variable (A+ done).
   Categorias: ainda fachada (filtro granular no backlog).
   ============================================================ */
function applyMvpHonestMode(){
  // Single-env: pipe-flow agora é honesto (backend recebe pipe_*_uuid via payload).
  // Mantém apenas o card informativo do preset (token + scope vem dele).
  const singlePane = document.querySelector('.mode-pane[data-pane="single"]');
  if(singlePane){
    injectPresetInfoCard(singlePane);
  }

  // A+ done: categorias agora são respeitadas pelo Robot via --variable CATEGORIES_FILTER.
  // Mantém os blocos cat-grid visíveis (eles já existem no HTML e têm handlers).
}

function injectPresetInfoCard(singlePane){
  if(singlePane.querySelector('.mvp-preset-card')) return;

  // Card 1: Preset selecionado
  const card = document.createElement('div');
  card.className = 'block mvp-preset-card';
  card.innerHTML = `
    <div class="block-head">
      <div class="block-title">Preset selecionado</div>
      <div class="block-hint">backend executa cenário fixo deste preset</div>
    </div>
    <div style="padding:14px 16px;border:1px solid rgba(201,168,76,.22);border-radius:10px;background:rgba(201,168,76,.04)">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
        <div style="width:36px;height:36px;border-radius:8px;background:rgba(201,168,76,.12);display:flex;align-items:center;justify-content:center;color:var(--accent)">
          <svg style="width:18px;height:18px;stroke-width:2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        </div>
        <div style="flex:1;min-width:0">
          <div id="preset-card-name" style="font-size:14px;font-weight:600;color:var(--ink)">—</div>
          <div id="preset-card-sub" style="font-size:11.5px;color:var(--muted);font-family:var(--mono);margin-top:2px">config/<span id="preset-card-file">—</span>.robot</div>
        </div>
      </div>
      <div id="preset-card-pipes" style="font-size:11.5px;color:var(--ink-2);font-family:var(--mono);padding-top:10px;border-top:1px solid rgba(255,255,255,.05)"></div>
    </div>
  `;

  // Card 2: Validações incluídas (as 7 categorias como informação)
  const validationsCard = document.createElement('div');
  validationsCard.className = 'block mvp-validations-card';
  validationsCard.innerHTML = `
    <div class="block-head">
      <div class="block-title">Validações incluídas</div>
      <div class="block-hint">7 categorias executadas em toda run</div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
      <div style="padding:10px 12px;border:1px solid var(--line-2);border-radius:6px;background:rgba(212,168,75,.04);display:flex;align-items:center;gap:10px">
        <span style="width:8px;height:8px;border-radius:2px;background:#d4a84b;flex-shrink:0"></span>
        <div style="flex:1">
          <div style="font-size:12px;color:var(--ink);font-weight:500">Start Form</div>
          <div style="font-size:10.5px;color:var(--muted)">Formulário inicial do pipe</div>
        </div>
      </div>
      <div style="padding:10px 12px;border:1px solid var(--line-2);border-radius:6px;background:rgba(224,101,101,.04);display:flex;align-items:center;gap:10px">
        <span style="width:8px;height:8px;border-radius:2px;background:#e06565;flex-shrink:0"></span>
        <div style="flex:1">
          <div style="font-size:12px;color:var(--ink);font-weight:500">Fases & Campos</div>
          <div style="font-size:10.5px;color:var(--muted)">Estrutura, tipos, obrigatoriedade</div>
        </div>
      </div>
      <div style="padding:10px 12px;border:1px solid var(--line-2);border-radius:6px;background:rgba(108,169,217,.04);display:flex;align-items:center;gap:10px">
        <span style="width:8px;height:8px;border-radius:2px;background:#6ca9d9;flex-shrink:0"></span>
        <div style="flex:1">
          <div style="font-size:12px;color:var(--ink);font-weight:500">Labels</div>
          <div style="font-size:10.5px;color:var(--muted)">Nomes e cores de labels</div>
        </div>
      </div>
      <div style="padding:10px 12px;border:1px solid var(--line-2);border-radius:6px;background:rgba(217,138,92,.04);display:flex;align-items:center;gap:10px">
        <span style="width:8px;height:8px;border-radius:2px;background:#d98a5c;flex-shrink:0"></span>
        <div style="flex:1">
          <div style="font-size:12px;color:var(--ink);font-weight:500">Automação · Status</div>
          <div style="font-size:10.5px;color:var(--muted)">Active/inactive, action, event</div>
        </div>
      </div>
      <div style="padding:10px 12px;border:1px solid var(--line-2);border-radius:6px;background:rgba(166,140,217,.04);display:flex;align-items:center;gap:10px">
        <span style="width:8px;height:8px;border-radius:2px;background:#a68cd9;flex-shrink:0"></span>
        <div style="flex:1">
          <div style="font-size:12px;color:var(--ink);font-weight:500">Automação · Fase Destino</div>
          <div style="font-size:10.5px;color:var(--muted)">Roteamento entre fases</div>
        </div>
      </div>
      <div style="padding:10px 12px;border:1px solid var(--line-2);border-radius:6px;background:rgba(108,194,108,.04);display:flex;align-items:center;gap:10px">
        <span style="width:8px;height:8px;border-radius:2px;background:#6cc26c;flex-shrink:0"></span>
        <div style="flex:1">
          <div style="font-size:12px;color:var(--ink);font-weight:500">Automação · HTTP</div>
          <div style="font-size:10.5px;color:var(--muted)">URL, method, body, headers</div>
        </div>
      </div>
      <div style="padding:10px 12px;border:1px solid var(--line-2);border-radius:6px;background:rgba(217,124,168,.04);display:flex;align-items:center;gap:10px;grid-column:1 / -1">
        <span style="width:8px;height:8px;border-radius:2px;background:#d97ca8;flex-shrink:0"></span>
        <div style="flex:1">
          <div style="font-size:12px;color:var(--ink);font-weight:500">Automação · Condition</div>
          <div style="font-size:10.5px;color:var(--muted)">Lógica condicional (operator + value legível)</div>
        </div>
      </div>
    </div>
  `;

  // Ordem desejada: Ambiente, Preset, Pipes, Validações.
  // Preset card vai depois do primeiro block (Ambiente).
  // Validations card vai depois do block "Pipes".
  const firstBlock = singlePane.querySelector('.block');
  if(firstBlock && firstBlock.nextSibling){
    firstBlock.parentNode.insertBefore(card, firstBlock.nextSibling);
  } else if(firstBlock){
    singlePane.appendChild(card);
  } else {
    singlePane.appendChild(card);
  }

  const blocks = Array.from(singlePane.querySelectorAll('.block'));
  const pipesBlock = blocks.find(b => {
    const t = b.querySelector('.block-title');
    return t && t.textContent.trim() === 'Pipes';
  });
  if(pipesBlock){
    if(pipesBlock.nextSibling){
      pipesBlock.parentNode.insertBefore(validationsCard, pipesBlock.nextSibling);
    } else {
      pipesBlock.parentNode.appendChild(validationsCard);
    }
  } else {
    singlePane.appendChild(validationsCard);
  }
}

function updatePresetInfoCard(){
  const nameEl = document.getElementById('preset-card-name');
  const fileEl = document.getElementById('preset-card-file');
  const pipesEl = document.getElementById('preset-card-pipes');
  if(!nameEl || !ENVS_DATA) return;

  const env = (ENVS_DATA.pipefy || []).find(e => e.id === state.single.env);
  if(!env){
    nameEl.textContent = state.single.env || '—';
    if(fileEl) fileEl.textContent = state.single.env || '—';
    if(pipesEl) pipesEl.textContent = '';
    return;
  }
  nameEl.textContent = env.name;
  if(fileEl) fileEl.textContent = env.id;
  if(pipesEl){
    const pipes = env.pipes || [];
    if(pipes.length >= 2){
      pipesEl.innerHTML = '<span style="color:var(--muted)">pipes:</span> ' +
        pipes.slice(0, 2).map(p => '<b style="color:var(--ink)">' + escapeHtmlInline(p.name) + '</b>').join(' <span style="color:var(--accent)">→</span> ');
    } else if(pipes.length === 1){
      pipesEl.innerHTML = '<span style="color:var(--muted)">pipe:</span> <b style="color:var(--ink)">' + escapeHtmlInline(pipes[0].name) + '</b>';
    } else {
      pipesEl.textContent = 'nenhum pipe configurado';
    }
  }
}

/* ============================================================ PAGE TRANSITIONS */
function v2InjectOverlay(){
  if(document.getElementById('v2-transition-overlay')) return;
  const o = document.createElement('div');
  o.id = 'v2-transition-overlay';
  o.innerHTML = '<div class="v2-loader"><div class="v2-loader-ring"></div><div class="v2-loader-ring inner"></div><div class="v2-loader-mark">P</div></div><div class="v2-loader-text">carregando<span class="v2-loader-dots"><span></span><span></span><span></span></span></div>';
  document.body.appendChild(o);
}
v2InjectOverlay();
if(sessionStorage.getItem('v2-in-transit') === '1'){
  sessionStorage.removeItem('v2-in-transit');
  document.body.classList.add('v2-arriving');
  setTimeout(() => { document.body.classList.remove('v2-arriving'); }, 280);
}
function navigateTo(url){
  sessionStorage.setItem('v2-in-transit', '1');
  document.body.classList.add('v2-leaving');
  setTimeout(() => { window.location.href = url; }, 320);
}

/* ============================================================ STATE */
const state = {
  mode: 'single',
  single: {
    env: 'fourd-sandbox',
    src: 'mesa_credito_pf_origem',
    dst: 'mesa_credito_pf_copia',
    cats: ['SF','FA','LB','AS','AD','AH','AC'],
  },
  cross: {
    config: null,      // 'cross_<src>_x_<dst>' | 'cross_<env>_selfcheck' | null
    cats: ['SF','FA','LB','AS','AD','AH','AC'],
    // A+: pipes origem/destino dinâmicos (override do .robot via --variable)
    pipe_origem_uuid: '',
    pipe_destino_uuid: '',
    pipe_origem_repo_id: '',
    pipe_destino_repo_id: '',
    pipe_origem_name: '',
    pipe_destino_name: '',
  },
  snapshot: {
    sub: 'gerar',      // 'gerar' | 'comparar'
    env: '',           // env_id válido (ex: 'fourd_hmg'). Preenchido via populateSnapEnvDropdown
    pipe: '',          // nome do pipe origem do env selecionado
    pipe_uuid: '',
    pipe_repo_id: '',
    label: '',         // auto-gerado a partir do pipe/env; vira custom se usuário edita
    labelEdited: false,
    baseline: '',
    // Modo comparar: pipe live escolhido pra comparar contra o baseline (vai como --variable PIPE_DESTINO_*)
    compare_env: '',
    compare_pipe: '',
    compare_pipe_uuid: '',
    compare_pipe_repo_id: '',
  },
  batch: {
    sel: ['b1','b2'],
    cats: ['SF','FA','LB','AS','AD','AH','AC'],
  },
  ipaas: {
    env: 'ipaas-fourd',
    type: 'descoberta',
    cats: ['IF','IT','IS'],
  },
  healthcheck: {},
};

/* ============================================================ MODE NAV */
const MODE_META = {
  single:   { ico:'i-git-compare', title:'Validação em ambiente único',  desc:'Compare dois pipes dentro do mesmo ambiente', beta:false },
  cross:    { ico:'i-layers',      title:'Validação entre ambientes',    desc:'Compare pipes entre HMG e PRD ou outros ambientes', beta:false },
  snapshot: { ico:'i-camera',      title:'Snapshot e baseline',          desc:'Congele a estrutura atual ou compare vs baseline', beta:false },
  batch:    { ico:'i-package',     title:'Validação em lote',            desc:'Execute múltiplos pipes na mesma run', beta:false },
  ipaas:    { ico:'i-plug',        title:'Integração iPaaS',             desc:'Valide flows do Activepieces (Pipefy Integrations)', beta:true },
  healthcheck: { ico:'i-check',     title:'Health Check',                  desc:'Diagnóstico rápido de todas as camadas', beta:false },
};

const content = document.getElementById('content');
const contentInner = document.getElementById('content-inner');
const shIco = document.getElementById('sh-ico');
const shTitle = document.getElementById('sh-title');
const shDesc = document.getElementById('sh-desc');

function setMode(mode){
  if(mode === state.mode) return;
  // out
  content.classList.add('anim-out');
  setTimeout(()=>{
    state.mode = mode;
    content.setAttribute('data-mode', mode);
    document.querySelectorAll('.nav-item').forEach(n=>n.classList.toggle('active', n.dataset.mode === mode));
    document.querySelectorAll('.mode-pane').forEach(p=>p.classList.toggle('active', p.dataset.pane === mode));
    // subhead
    const m = MODE_META[mode];
    shIco.innerHTML = `<svg><use href="#${m.ico}"/></svg>`;
    shTitle.innerHTML = m.title + (m.beta ? ' <span class="beta">BETA</span>' : '');
    shDesc.textContent = m.desc;
    // in
    content.classList.remove('anim-out');
    content.classList.add('anim-in');
    requestAnimationFrame(()=>{
      content.classList.remove('anim-in');
      updateFooter();
    });
  }, 120);
}

document.querySelectorAll('.nav-item').forEach(btn=>{
  btn.addEventListener('click', ()=> setMode(btn.dataset.mode));
});

/* ============================================================ DROPDOWNS */
document.querySelectorAll('.dropdown').forEach(dd=>{
  const btn = dd.querySelector('[data-dd-trigger]');
  const menu = dd.querySelector('.dd-menu');
  if(!btn || !menu) return;
  btn.addEventListener('click', (e)=>{
    e.stopPropagation();
    const isOpen = menu.classList.contains('open');
    document.querySelectorAll('.dd-menu.open').forEach(m=>{
      m.classList.remove('open');
      m.parentElement.querySelector('.dd-btn')?.classList.remove('open');
    });
    if(!isOpen){
      menu.classList.add('open');
      btn.classList.add('open');
    }
  });
  menu.querySelectorAll('.dd-opt').forEach(opt=>{
    opt.addEventListener('click', (e)=>{
      e.stopPropagation();
      menu.querySelectorAll('.dd-opt').forEach(o=>o.classList.remove('sel'));
      opt.classList.add('sel');
      // update display
      const value = opt.querySelector('.opt-name').textContent;
      const valueEl = btn.querySelector('.dd-value');
      if(valueEl){
        // preserve muted prefix if any
        const muted = valueEl.querySelector('.muted');
        if(muted){
          valueEl.innerHTML = '';
          valueEl.appendChild(muted);
          valueEl.appendChild(document.createTextNode(value.split(' / ').pop()));
        } else {
          valueEl.textContent = value;
        }
      }
      // state updates based on dropdown key
      const key = dd.dataset.dd;
      if(key === 'env-single') state.single.env = opt.dataset.val || value;
      if(key === 'pipe-src')   state.single.src = opt.dataset.val || value;
      if(key === 'pipe-dst')   state.single.dst = opt.dataset.val || value;
      if(key === 'snap-baseline'){
        state.snapshot.baseline = value.replace(/\.json$/,'');
        if(typeof updateSnapBaselinePreview === 'function') updateSnapBaselinePreview();
      }
      if(key === 'ipaas-env')  state.ipaas.env = opt.dataset.val || value;
      menu.classList.remove('open');
      btn.classList.remove('open');
      updateFooter();
    });
  });
});
document.addEventListener('click', ()=>{
  document.querySelectorAll('.dd-menu.open').forEach(m=>{
    m.classList.remove('open');
    m.parentElement.querySelector('.dd-btn')?.classList.remove('open');
  });
});

/* ============================================================ CATEGORIES */
document.querySelectorAll('[data-cat-grid]').forEach(grid=>{
  const gridName = grid.dataset.catGrid;
  grid.querySelectorAll('.facet').forEach(f=>{
    f.addEventListener('click', ()=>{
      f.classList.toggle('active');
      syncCatState(gridName);
    });
  });
});
document.querySelectorAll('[data-cat-action]').forEach(btn=>{
  btn.addEventListener('click', ()=>{
    const action = btn.dataset.catAction;
    const gridName = btn.dataset.grid;
    const grid = document.querySelector(`[data-cat-grid="${gridName}"]`);
    grid.querySelectorAll('.facet').forEach(f=>{
      if(action === 'all') f.classList.add('active');
      if(action === 'none') f.classList.remove('active');
      if(action === 'invert') f.classList.toggle('active');
    });
    syncCatState(gridName);
  });
});
function syncCatState(gridName){
  const grid = document.querySelector(`[data-cat-grid="${gridName}"]`);
  const active = [...grid.querySelectorAll('.facet.active')].map(f=>f.dataset.cat);
  if(gridName === 'single') state.single.cats = active;
  if(gridName === 'cross')  state.cross.cats  = active;
  if(gridName === 'batch')  state.batch.cats  = active;
  // counters
  const count = active.length;
  if(gridName === 'single') document.getElementById('cat-count-s').textContent = count;
  if(gridName === 'cross')  document.getElementById('cat-count-c').textContent = count;
  if(gridName === 'batch')  document.getElementById('batch-count-cats').textContent = `${count * state.batch.sel.length} categorias total`;
  updateFooter();
}

/* ============================================================ CROSS cards */
document.querySelectorAll('.cross-card').forEach(card=>{
  card.addEventListener('click', ()=>{
    const v = card.dataset.cross;
    if(state.cross.config === v){
      state.cross.config = null;
      card.classList.remove('sel');
    } else {
      state.cross.config = v;
      document.querySelectorAll('.cross-card').forEach(c=>c.classList.toggle('sel', c === card));
    }
    updateFooter();
  });
});

/* ============================================================ SNAPSHOT subtabs */
document.querySelectorAll('.subtab').forEach(tab=>{
  tab.addEventListener('click', ()=>{
    const target = tab.dataset.subtab;
    if(state.snapshot.sub === target) return;
    const currentPane = document.querySelector(`.snap-pane.active`);
    const nextPane = document.querySelector(`.snap-pane[data-snap="${target}"]`);
    currentPane.classList.add('out');
    setTimeout(()=>{
      document.querySelectorAll('.subtab').forEach(t=>t.classList.toggle('active', t === tab));
      document.querySelectorAll('.snap-pane').forEach(p=>p.classList.remove('active','out','in'));
      nextPane.classList.add('active','in');
      requestAnimationFrame(()=>{
        nextPane.classList.remove('in');
        state.snapshot.sub = target;
        updateFooter();
      });
    }, 80);
  });
});

/* Snap label input: marca como editado manualmente pra não sobrescrever no auto-gen */
document.getElementById('snap-label').addEventListener('input', (e)=>{
  state.snapshot.label = e.target.value;
  state.snapshot.labelEdited = true;
  updateFooter();
});

/* Computa label sugerido a partir do pipe + env selecionados no snap-env */
function computeSuggestedSnapLabel(){
  const pipeSlug = slugify(state.snapshot.pipe || '');
  const envId = state.snapshot.env || '';
  if(!pipeSlug) return '';
  return envId ? (pipeSlug + '_' + envId) : pipeSlug;
}

function applySuggestedLabel(){
  const suggested = computeSuggestedSnapLabel();
  if(!suggested) return;
  state.snapshot.label = suggested;
  const input = document.getElementById('snap-label');
  if(input){
    input.value = suggested;
    console.log('[v2] label auto-preenchido:', suggested);
  }
}

/* Atualiza preview do snapshot gerar com dados reais do env+pipe selecionado */
function updateSnapGerarPreview(){
  const snapGerarPane = document.querySelector('.snap-pane[data-snap="gerar"]');
  if(!snapGerarPane) return;
  const spGrid = snapGerarPane.querySelector('.snap-preview .sp-grid');
  const spName = snapGerarPane.querySelector('.snap-preview .sp-name');
  const spDate = snapGerarPane.querySelector('.snap-preview .sp-date');

  if(spName) spName.textContent = state.snapshot.pipe || '—';
  if(spDate){
    const now = new Date();
    const dd = String(now.getDate()).padStart(2, '0');
    const mm = String(now.getMonth() + 1).padStart(2, '0');
    const yy = now.getFullYear();
    const hh = String(now.getHours()).padStart(2, '0');
    const mi = String(now.getMinutes()).padStart(2, '0');
    const envName = (ENVS_DATA && (ENVS_DATA.pipefy || []).find(e => e.id === state.snapshot.env) || {}).name || state.snapshot.env || '—';
    spDate.textContent = 'será salvo agora · ' + envName + ' · ' + dd + '/' + mm + '/' + yy + ' ' + hh + ':' + mi;
  }
  if(spGrid){
    spGrid.innerHTML = '<span><b>' + (state.snapshot.pipe_repo_id || '—') + '</b> repo</span>'
                    + '<span><b>' + String(state.snapshot.pipe_uuid || '').slice(0, 8) + '</b> uuid</span>'
                    + '<span style="color:var(--muted)" title="stats não expostos pelo backend"><b>—</b> fases</span>'
                    + '<span style="color:var(--muted)"><b>—</b> campos</span>';
  }

  // Atualiza dd-env badge do snap-env dropdown com contador de auto (se disponível)
  const dd = document.querySelector('.dropdown[data-dd="snap-env"]');
  if(dd){
    const badge = dd.querySelector('.dd-env');
    if(badge) badge.textContent = state.snapshot.pipe_repo_id ? ('repo ' + state.snapshot.pipe_repo_id) : '—';
  }
}

function populateSnapEnvDropdown(){
  const dd = document.querySelector('.dropdown[data-dd="snap-env"]');
  if(!dd || !ENVS_DATA) return;
  const menuInner = dd.querySelector('.dd-menu-inner');
  if(!menuInner) return;

  // Gera uma opção por (env, pipe) pra permitir snapshot de qualquer pipe de qualquer env
  const envs = (ENVS_DATA.pipefy || []);
  const items = [];
  envs.forEach(env => {
    (env.pipes || []).forEach(pipe => {
      items.push({
        env_id: env.id,
        env_name: env.name,
        pipe_name: pipe.name,
        pipe_uuid: pipe.uuid || '',
        pipe_repo_id: pipe.repo_id || '',
        has_token: env.has_token === true,
      });
    });
  });

  if(items.length === 0){
    menuInner.innerHTML = '<div style="padding:12px 16px;color:var(--muted);font-size:11.5px">Nenhum ambiente com pipes configurados.</div>';
    return;
  }

  // Pré-seleção: primeiro item com has_token=true, senão o primeiro
  const defaultItem = items.find(i => i.has_token) || items[0];
  if(!state.snapshot.env){
    state.snapshot.env = defaultItem.env_id;
    state.snapshot.pipe = defaultItem.pipe_name;
    state.snapshot.pipe_uuid = defaultItem.pipe_uuid;
    state.snapshot.pipe_repo_id = defaultItem.pipe_repo_id;
    if(!state.snapshot.labelEdited) applySuggestedLabel();
  }

  menuInner.innerHTML = items.map(it => {
    const isSel = it.env_id === state.snapshot.env && it.pipe_name === state.snapshot.pipe;
    const envTag = it.env_id.includes('prd') ? 'prd' : it.env_id.includes('stg') ? 'stg' : it.env_id.includes('dev') ? 'dev' : 'hmg';
    const tokenFlag = it.has_token ? '' : ' · <span style="color:var(--yellow)">sem token</span>';
    return '<button class="dd-opt' + (isSel ? ' sel' : '') + '"'
         + ' data-env-id="' + it.env_id + '"'
         + ' data-pipe-name="' + escapeHtmlInline(it.pipe_name) + '"'
         + ' data-pipe-uuid="' + it.pipe_uuid + '"'
         + ' data-pipe-repo="' + it.pipe_repo_id + '"'
         + ' data-has-token="' + (it.has_token ? '1' : '0') + '">'
         +   '<span class="env-tag">' + envTag + '</span>'
         +   '<span class="opt-name">' + escapeHtmlInline(it.env_name + ' / ' + it.pipe_name) + '</span>'
         +   '<span class="opt-sub">repo ' + (it.pipe_repo_id || '—') + tokenFlag + '</span>'
         + '</button>';
  }).join('');

  // Atualiza value do botão
  const valueEl = dd.querySelector('.dd-value');
  const envName = (envs.find(e => e.id === state.snapshot.env) || {}).name || state.snapshot.env;
  if(valueEl){
    valueEl.innerHTML = '<span class="muted">' + escapeHtmlInline(envName) + ' / </span>' + escapeHtmlInline(state.snapshot.pipe || '—');
  }

  // Event delegation pros clicks
  if(!menuInner.dataset.snapEnvWired){
    menuInner.dataset.snapEnvWired = '1';
    menuInner.addEventListener('click', (e) => {
      const opt = e.target.closest('.dd-opt');
      if(!opt) return;
      menuInner.querySelectorAll('.dd-opt').forEach(o => o.classList.remove('sel'));
      opt.classList.add('sel');
      state.snapshot.env = opt.dataset.envId;
      state.snapshot.pipe = opt.dataset.pipeName;
      state.snapshot.pipe_uuid = opt.dataset.pipeUuid;
      state.snapshot.pipe_repo_id = opt.dataset.pipeRepo;
      // Atualiza value do botão
      const envLabel = (envs.find(e => e.id === state.snapshot.env) || {}).name || state.snapshot.env;
      if(valueEl){
        valueEl.innerHTML = '<span class="muted">' + escapeHtmlInline(envLabel) + ' / </span>' + escapeHtmlInline(state.snapshot.pipe);
      }
      // Auto-label se o usuário não editou manualmente
      if(!state.snapshot.labelEdited) applySuggestedLabel();
      updateSnapGerarPreview();
      updateFooter();
      // Fecha menu
      dd.querySelector('.dd-menu').classList.remove('open');
      dd.querySelector('[data-dd-trigger]').classList.remove('open');
    });
  }

  updateSnapGerarPreview();
}

/* ============================================================ BATCH rows */
document.querySelectorAll('.batch-row').forEach(row=>{
  row.addEventListener('click', ()=>{
    const id = row.dataset.batch;
    const idx = state.batch.sel.indexOf(id);
    if(idx >= 0){ state.batch.sel.splice(idx,1); row.classList.remove('sel'); }
    else { state.batch.sel.push(id); row.classList.add('sel'); }
    document.getElementById('batch-count-sel').textContent = state.batch.sel.length;
    syncCatState('batch');
  });
});
document.querySelectorAll('[data-batch-action]').forEach(btn=>{
  btn.addEventListener('click', ()=>{
    const action = btn.dataset.batchAction;
    document.querySelectorAll('.batch-row').forEach(row=>{
      if(action === 'all'){ row.classList.add('sel'); if(!state.batch.sel.includes(row.dataset.batch)) state.batch.sel.push(row.dataset.batch); }
      if(action === 'none'){ row.classList.remove('sel'); }
    });
    if(action === 'none') state.batch.sel = [];
    document.getElementById('batch-count-sel').textContent = state.batch.sel.length;
    syncCatState('batch');
  });
});

/* ============================================================ IPAAS radio */
document.querySelectorAll('[data-radio="ipaas-type"] .radio-card').forEach(rc=>{
  rc.addEventListener('click', ()=>{
    document.querySelectorAll('[data-radio="ipaas-type"] .radio-card').forEach(c=>c.classList.remove('sel'));
    rc.classList.add('sel');
    state.ipaas.type = rc.dataset.val;
    updateFooter();
  });
});

/* ============================================================ PW toggle */
const pwInput = document.getElementById('pw-input');
const pwToggle = document.getElementById('pw-toggle');
if(pwToggle){
  pwToggle.addEventListener('click', ()=>{
    const masked = pwInput.classList.contains('masked');
    if(masked){
      pwInput.classList.remove('masked');
      pwInput.type = 'text';
      pwToggle.innerHTML = '<svg><use href="#i-eye-off"/></svg>';
    } else {
      pwInput.classList.add('masked');
      pwInput.type = 'password';
      pwToggle.innerHTML = '<svg><use href="#i-eye"/></svg>';
    }
  });
}

/* ============================================================ FOOTER (summary + run btn) */
const summary = document.getElementById('summary');
const btnRun  = document.getElementById('btn-run');
const runLabel = document.getElementById('run-label');
const auxLink = document.getElementById('aux-link');

/* Botão "Gerenciar" do footer abre o modal de ambientes (mesmo destino da engrenagem) */
if(auxLink){
  auxLink.addEventListener('click', (e) => {
    e.preventDefault();
    if(typeof openModal === 'function') openModal();
  });
  auxLink.style.cursor = 'pointer';
}

function buildSummary(parts, typeLabel){
  const bits = [`<span class="sum-type">${typeLabel}</span>`];
  parts.forEach((p,i)=>{
    bits.push('<span class="sum-sep">·</span>');
    bits.push(`<span class="sum-part${p.muted ? ' muted' : ''}">${p.text}</span>`);
  });
  summary.innerHTML = bits.join('');
}

const CROSS_NAMES = {
  cross_fourd_hmg_selfcheck:'cross_fourd_hmg_selfcheck',
  cross_fourd_hmg_x_fourd_stg:'cross_fourd_hmg_x_fourd_stg',
  cross_fourd_hmg_x_fourd_prd:'cross_fourd_hmg_x_fourd_prd',
};

const PIPE_NAMES = {
  mesa_credito_pf_origem:'Mesa Crédito PF (Origem)',
  mesa_credito_pf_copia:'Mesa Crédito PF (Cópia)',
};

function updateFooter(){
  const m = state.mode;
  let disabled = false;
  let label = 'Executar validação';
  let auxText = '';

  if(m === 'single'){
    // MVP honesto (decisão D): não lista categorias nem pipes individuais
    // porque backend não aceita esses parâmetros. Mostra só o preset.
    buildSummary([
      { text: 'preset: ' + state.single.env, muted: false },
      { text: '7 categorias · todas validadas', muted: true },
    ], 'SINGLE_ENV');
  }

  if(m === 'cross'){
    if(!state.cross.config){
      buildSummary([{ text:'nenhuma configuração selecionada', muted:true }], 'CROSS_ENV');
      disabled = true;
      label = 'Selecione uma configuração';
    } else {
      // Fix E: checa has_token de AMBOS ambientes (origem e destino) antes de habilitar.
      // Substitui hardcode anterior que só bloqueava IDs específicos.
      const tokenCheck = getCrossTokenStatus(state.cross.config);
      buildSummary([
        { text: CROSS_NAMES[state.cross.config] || state.cross.config },
        { text: '7 categorias · todas validadas', muted:true },
      ], 'CROSS_ENV');
      if(!tokenCheck.ok){
        disabled = true;
        if(tokenCheck.labels.length === 1){
          label = 'Credenciais pendentes: ' + tokenCheck.labels[0];
        } else {
          label = 'Credenciais pendentes em ' + tokenCheck.labels.length + ' ambientes';
        }
        auxText = 'Gerenciar';
      }
    }
  }

  if(m === 'snapshot'){
    if(state.snapshot.sub === 'gerar'){
      if(!state.snapshot.label.trim() || !state.snapshot.pipe){
        buildSummary([{ text:'faltam label e pipe', muted:true }], 'SNAPSHOT');
        disabled = true;
        label = 'Selecione pipe e label';
      } else {
        buildSummary([
          { text:'gerar baseline' },
          { text: state.snapshot.env },
          { text: state.snapshot.pipe },
          { text: state.snapshot.label, muted:true },
        ], 'SNAPSHOT');
        label = 'Gerar baseline';
      }
    } else {
      if(!state.snapshot.baseline){
        buildSummary([{ text:'nenhum baseline escolhido', muted:true }], 'SNAPSHOT');
        disabled = true;
        label = 'Selecione um baseline';
      } else {
        buildSummary([
          { text:'comparar vs' },
          { text: state.snapshot.baseline },
        ], 'SNAPSHOT');
        label = 'Comparar vs baseline';
      }
    }
  }

  if(m === 'batch'){
    const n = state.batch.sel.length;
    buildSummary([
      { text: `${n} pipe${n===1?'':'s'} selecionado${n===1?'':'s'}` },
      { text: '7 categorias · todas validadas', muted:true },
    ], 'BATCH');
    if(n === 0){ disabled = true; label = 'Selecione ao menos 1 pipe'; }
    else { label = `Executar validação · ${n} pipe${n===1?'':'s'}`; }
  }

  if(m === 'ipaas'){
    if(state.ipaas.env === 'ipaas-fourd-prd'){
      buildSummary([{ text:'ipaas-fourd-prd — sem credenciais', muted:true }], 'IPAAS');
      disabled = true;
      label = 'Credenciais Activepieces pendentes';
      auxText = 'Gerenciar';
    } else if(!state.ipaas.type){
      buildSummary([{ text:'nenhum tipo selecionado', muted:true }], 'IPAAS');
      disabled = true;
      label = 'Selecione tipo de validação';
    } else {
      buildSummary([
        { text: state.ipaas.type },
        { text: state.ipaas.env },
      ], 'IPAAS');
      label = 'Executar validação iPaaS';
    }
  }

  if(m === 'healthcheck'){
    const envName = (ENVS_DATA && (ENVS_DATA.pipefy || []).find(e => e.id === state.single.env) || {}).name || state.single.env || '—';
    buildSummary([
      { text: 'diagnóstico em ' + envName },
      { text: '9 verificações', muted: true },
    ], 'HEALTHCHECK');
    label = 'Executar Health Check';
    // Atualiza o display do env-alvo na tela
    const hcEnvDisplay = document.getElementById('hc-env-display');
    if(hcEnvDisplay) hcEnvDisplay.textContent = envName + ' (preset: ' + (state.single.env || '—') + ')';
  }

  runLabel.textContent = label;
  btnRun.disabled = disabled;
  if(disabled) btnRun.setAttribute('disabled',''); else btnRun.removeAttribute('disabled');
  if(auxText){ auxLink.style.display = 'inline-flex'; auxLink.textContent = auxText; }
  else { auxLink.style.display = 'none'; }
}

/* ============================================================ MODAL (manage envs) */
const modal = document.getElementById('modal-envs');
let lastFocus = null;

function openModal(){
  lastFocus = document.activeElement;
  // Re-render do modal antes de abrir, garantindo que reflete o vault atual
  if(typeof populateEnvModal === 'function') populateEnvModal();
  modal.classList.add('open');
  // focus first focusable inside
  setTimeout(()=>{
    const f = modal.querySelector('button, input, [tabindex]');
    if(f) f.focus();
  }, 50);
}
function closeModal(){
  modal.classList.remove('open');
  if(lastFocus) lastFocus.focus();
}

document.getElementById('btn-settings').addEventListener('click', openModal);
document.getElementById('link-manage').addEventListener('click', (e)=>{ e.preventDefault(); openModal(); });
document.getElementById('link-manage-2')?.addEventListener('click', (e)=>{ e.preventDefault(); openModal(); });
document.getElementById('modal-close').addEventListener('click', closeModal);
document.getElementById('modal-cancel').addEventListener('click', closeModal);
modal.addEventListener('click', (e)=>{ if(e.target === modal) closeModal(); });

document.querySelectorAll('.modal-tab').forEach(t=>{
  t.addEventListener('click', ()=>{
    document.querySelectorAll('.modal-tab').forEach(x=>x.classList.toggle('active', x === t));
  });
});

/* Focus trap + keyboard */
document.addEventListener('keydown', (e)=>{
  if(e.key === 'Escape'){
    if(modal.classList.contains('open')){ e.preventDefault(); closeModal(); return; }
    // close any dropdown
    document.querySelectorAll('.dd-menu.open').forEach(m=>{
      m.classList.remove('open');
      m.parentElement.querySelector('.dd-btn')?.classList.remove('open');
    });
  }
  if(e.key === 'Enter' && !modal.classList.contains('open') &&
     !['INPUT','TEXTAREA'].includes(document.activeElement.tagName)){
    if(!btnRun.disabled){
      e.preventDefault();
      runPulse();
    }
  }
  if(e.key === 'Tab' && modal.classList.contains('open')){
    const focusables = [...modal.querySelectorAll('button, input, [tabindex]:not([tabindex="-1"])')].filter(el => !el.disabled && el.offsetParent !== null);
    if(focusables.length === 0) return;
    const first = focusables[0];
    const last  = focusables[focusables.length - 1];
    if(e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
    else if(!e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
  }
});

function runPulse(){
  btnRun.style.transition = 'transform .1s';
  btnRun.style.transform = 'translateY(0) scale(.98)';
  setTimeout(()=>{
    btnRun.style.transform = '';
    btnRun.style.transition = '';
  }, 100);
}
btnRun.addEventListener('click', ()=>{ if(!btnRun.disabled) runPulse(); });

/* init */
updateFooter();

/* ============================================================
   API WIRE-UP — credenciais sao client-side (localStorage do navegador).
   Backend nunca persiste tokens; cada /api/run leva credenciais no body.
   ============================================================ */

let ENVS_DATA = null;

/** Recarrega ENVS_DATA a partir do vault (localStorage + sessionStorage).
 *  Estrutura igual ao antigo /api/v2/environments: { pipefy: [...], ipaas: [...] }
 *  com has_token mas sem token efetivo. */
function loadEnvironmentsFromVault(){
  if(!window.V2Utils){
    ENVS_DATA = { pipefy: [], ipaas: [] };
    return;
  }
  const sanitized = window.V2Utils.vaultSanitized();
  ENVS_DATA = {
    pipefy: sanitized.filter(e => (e.type || 'pipefy') === 'pipefy'),
    ipaas: sanitized.filter(e => e.type === 'ipaas'),
  };
}

async function loadEnvironments(){
  loadEnvironmentsFromVault();
  populateSingleEnvDropdown();
  populatePipeDropdowns();
  if(typeof populateSnapEnvDropdown === 'function') populateSnapEnvDropdown();
  if(typeof renderConnectedBadge === 'function') renderConnectedBadge();
  if(typeof maybeShowOnboardingModal === 'function') maybeShowOnboardingModal();
}

/* Busca env completo do vault (com token) — usado no momento de editar */
function fetchFullEnv(type, id){
  if(!window.V2Utils) return null;
  const env = window.V2Utils.vaultGet(id);
  if(!env) return null;
  if(type && (env.type || 'pipefy') !== type) return null;
  return env;
}

/* apiFetch vem de V2Utils.apiFetch (definido em v2_utils.js).
   Wrapper local pra fallback quando V2Utils não carregou ainda. */
function apiFetch(url, options){
  if(window.V2Utils && window.V2Utils.apiFetch){
    return window.V2Utils.apiFetch(url, options);
  }
  return fetch(url, options);
}

function slugify(s){
  return (s || '').toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '');
}

function attachOptClickToNew(dd){
  const btn = dd.querySelector('[data-dd-trigger]');
  const menu = dd.querySelector('.dd-menu');
  if(!btn || !menu) return;
  menu.querySelectorAll('.dd-opt').forEach(opt=>{
    if(opt.dataset.wired === '1') return;
    opt.dataset.wired = '1';
    opt.addEventListener('click', (e)=>{
      e.stopPropagation();
      menu.querySelectorAll('.dd-opt').forEach(o=>o.classList.remove('sel'));
      opt.classList.add('sel');
      const value = opt.querySelector('.opt-name').textContent;
      const valueEl = btn.querySelector('.dd-value');
      if(valueEl){
        const muted = valueEl.querySelector('.muted');
        if(muted){
          valueEl.innerHTML = '';
          valueEl.appendChild(muted);
          valueEl.appendChild(document.createTextNode(value.split(' / ').pop()));
        } else {
          valueEl.textContent = value;
        }
      }
      const key = dd.dataset.dd;
      if(key === 'env-single'){
        state.single.env = opt.dataset.val || value;
        populatePipeDropdowns();
        if(typeof updatePresetInfoCard === 'function') updatePresetInfoCard();
        // Re-renderiza batch list filtrando pelos pipes do novo env
        if(typeof renderBatchList === 'function') renderBatchList();
      }
      if(key === 'pipe-src'){
        state.single.src = opt.dataset.val || value;
        if(typeof updatePipeStats === 'function') updatePipeStats();
      }
      if(key === 'pipe-dst'){
        state.single.dst = opt.dataset.val || value;
        if(typeof updatePipeStats === 'function') updatePipeStats();
      }
      if(key === 'snap-baseline'){
        state.snapshot.baseline = value.replace(/\.json$/,'');
        if(typeof updateSnapBaselinePreview === 'function') updateSnapBaselinePreview();
      }
      if(key === 'ipaas-env') state.ipaas.env = opt.dataset.val || value;
      menu.classList.remove('open');
      btn.classList.remove('open');
      updateFooter();
    });
  });
}

function populateSingleEnvDropdown(){
  const dd = document.querySelector('.dropdown[data-dd="env-single"]');
  if(!dd || !ENVS_DATA) return;
  const menuInner = dd.querySelector('.dd-menu-inner');
  const envs = ENVS_DATA.pipefy || [];
  if(envs.length === 0) return;

  const currentEnv = envs.find(e => e.id === state.single.env) || envs[0];
  state.single.env = currentEnv.id;

  menuInner.innerHTML = envs.map(env => {
    const isSel = env.id === state.single.env;
    const hasToken = env.has_token !== undefined ? env.has_token : (env.token && !env.token.startsWith('<') && env.token.length > 10);
    const authTag = env.auth_mode === 'cookie' ? 'Cookie' : 'Bearer';
    const pending = !hasToken;
    return `<button class="dd-opt${isSel ? ' sel' : ''}" data-val="${escapeHtmlInline(env.id)}">`
         + `<span class="env-tag${pending ? ' pending' : ''}">${pending ? 'Pendente' : authTag}</span>`
         + `<span class="opt-name">${escapeHtmlInline(env.name)}</span>`
         + `<span class="opt-sub">${(env.pipes || []).length} pipes</span>`
         + `</button>`;
  }).join('');

  const valueEl = dd.querySelector('.dd-value');
  if(valueEl){
    const muted = valueEl.querySelector('.muted');
    if(muted){
      valueEl.innerHTML = '';
      valueEl.appendChild(muted);
      valueEl.appendChild(document.createTextNode(currentEnv.name));
    } else {
      valueEl.textContent = currentEnv.name;
    }
  }
  attachOptClickToNew(dd);
}

function updatePipeStats(){
  // Substitui as estatísticas hardcoded (14 fases / 87 campos / 35 automações)
  // por info real que temos do environments.json (repo_id) e marca o resto como indisponível
  document.querySelectorAll('.pipe-card .pc-stats').forEach((stats, i) => {
    const isOrigem = i === 0;
    const pipeKey = isOrigem ? state.single.src : state.single.dst;
    const env = (ENVS_DATA && ENVS_DATA.pipefy || []).find(e => e.id === state.single.env);
    const pipe = env && (env.pipes || []).find(p => slugify(p.name) === pipeKey);
    if(pipe){
      stats.innerHTML = '<span><b>' + (pipe.repo_id || '?') + '</b> repo</span>'
                     + '<span><b>' + (pipe.uuid || '').slice(0, 8) + '</b> uuid</span>'
                     + '<span style="color:var(--muted)" title="Requer chamada prévia ao Pipefy pra calcular"><b>—</b> stats</span>';
    } else {
      stats.innerHTML = '<span style="color:var(--muted)">pipe não encontrado</span>';
    }
  });

  // Snap-gerar preview é responsabilidade exclusiva de updateSnapGerarPreview(),
  // que é disparada pelo handler do dropdown snap-env dedicado.
}

function populatePipeDropdowns(){
  if(!ENVS_DATA) return;
  const env = (ENVS_DATA.pipefy || []).find(e => e.id === state.single.env);
  const pipes = (env && env.pipes) || [];

  ['pipe-src', 'pipe-dst'].forEach((key, idx) => {
    const dd = document.querySelector(`.dropdown[data-dd="${key}"]`);
    if(!dd) return;
    const menuInner = dd.querySelector('.dd-menu-inner');
    if(pipes.length === 0){
      menuInner.innerHTML = `<div style="padding:12px 16px;color:var(--muted);font-size:11.5px">Nenhum pipe configurado nesse ambiente</div>`;
      return;
    }
    const currentKey = key === 'pipe-src' ? state.single.src : state.single.dst;
    const currentPipe = pipes.find(p => slugify(p.name) === currentKey) || pipes[idx] || pipes[0];
    const newKey = slugify(currentPipe.name);
    if(key === 'pipe-src') state.single.src = newKey;
    if(key === 'pipe-dst') state.single.dst = newKey;

    menuInner.innerHTML = pipes.map(p => {
      const pk = slugify(p.name);
      const isSel = pk === newKey;
      return `<button class="dd-opt${isSel ? ' sel' : ''}" data-val="${escapeHtmlInline(pk)}" data-uuid="${escapeHtmlInline(p.uuid || '')}" data-repo="${escapeHtmlInline(p.repo_id || '')}" title="${escapeHtmlInline(p.name)}">`
           + `<span class="opt-name">${escapeHtmlInline(p.name)}</span>`
           + `<span class="opt-sub">repo ${escapeHtmlInline(p.repo_id || '')}</span>`
           + `</button>`;
    }).join('');

    const valueEl = dd.querySelector('.dd-value');
    if(valueEl){
      const muted = valueEl.querySelector('.muted');
      if(muted){
        valueEl.innerHTML = '';
        valueEl.appendChild(muted);
        valueEl.appendChild(document.createTextNode(currentPipe.name));
      } else {
        valueEl.textContent = currentPipe.name;
      }
      // Tooltip nativo pro nome completo se truncar
      valueEl.setAttribute('title', currentPipe.name);
    }
    attachOptClickToNew(dd);
  });

  // Atualiza o mapa de nomes pro footer exibir nomes reais
  pipes.forEach(p => { PIPE_NAMES[slugify(p.name)] = p.name; });

  // Atualiza stats dos pipe-cards (repo_id, uuid, marca fases/campos como indisponível)
  updatePipeStats();

  updateFooter();
}

/* ------------------------------------------------------------
   3B: CROSS-ENV CARDS — agora lê do localStorage (cross configs sao
   composições virtuais de 2 envs do vault, persistidas client-side).
   ------------------------------------------------------------ */
const CROSS_CONFIGS_KEY = 'pv-cross-configs-v1';

function _readCrossConfigs(){
  try {
    const raw = localStorage.getItem(CROSS_CONFIGS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch(_) { return []; }
}

function _saveCrossConfigs(list){
  try { localStorage.setItem(CROSS_CONFIGS_KEY, JSON.stringify(list || [])); } catch(_) {}
}

async function loadConfigs(){
  try {
    // Cross configs vivem no localStorage. Backend nao serve mais.
    const data = { cross: _readCrossConfigs(), single: [] };
    populateCrossCards(data.cross || []);
  } catch(e) {
    console.warn('[v2] loadConfigs falhou:', e.message);
  }
}

/* Parse id do cross config (cross_<src>_x_<dst> ou cross_<x>_selfcheck) pra extrair env_ids. */
function parseCrossConfigMeta(id){
  const clean = id.replace(/^cross_/, '');
  const selfMatch = clean.match(/^(.+)_selfcheck$/i);
  if(selfMatch){
    const envId = selfMatch[1];
    return { src: envId, dst: envId, srcEnvId: envId, dstEnvId: envId, status: 'ok', hint: '0 diffs esperados' };
  }
  const crossMatch = clean.match(/^(.+?)_x_(.+)$/);
  if(crossMatch){
    return { src: crossMatch[1], dst: crossMatch[2], srcEnvId: crossMatch[1], dstEnvId: crossMatch[2], status: 'typical', hint: 'validação cruzada' };
  }
  return { src: clean || 'origem', dst: clean || 'destino', srcEnvId: null, dstEnvId: null, status: 'typical', hint: 'validação cruzada' };
}

/* Fix E: consulta ENVS_DATA pra descobrir se os 2 ambientes de um cross têm token.
   Retorna { ok: bool, missing: [env_id,...], labels: [label,...] }. */
function getCrossTokenStatus(crossId){
  const meta = parseCrossConfigMeta(crossId);
  if(!ENVS_DATA || !meta.srcEnvId || !meta.dstEnvId){
    return { ok: true, missing: [], labels: [] };  // sem info, não bloqueia
  }
  const pipefyList = ENVS_DATA.pipefy || [];
  const findEnv = id => pipefyList.find(e => e.id === id);
  const srcEnv = findEnv(meta.srcEnvId);
  const dstEnv = findEnv(meta.dstEnvId);
  const missing = [];
  const labels = [];
  if(!srcEnv || srcEnv.has_token !== true){
    missing.push(meta.srcEnvId);
    labels.push((srcEnv && srcEnv.name) || meta.srcEnvId);
  }
  if(meta.dstEnvId !== meta.srcEnvId && (!dstEnv || dstEnv.has_token !== true)){
    missing.push(meta.dstEnvId);
    labels.push((dstEnv && dstEnv.name) || meta.dstEnvId);
  }
  return { ok: missing.length === 0, missing: missing, labels: labels };
}

function _wireCrossAddBtn(){
  const addBtn = document.querySelector('.cross-add');
  if(addBtn && addBtn.dataset.wired !== '1'){
    addBtn.dataset.wired = '1';
    addBtn.addEventListener('click', (e) => {
      e.preventDefault();
      showCrossAddDialog();
    });
  }
}

function populateCrossCards(crossList){
  const list = document.querySelector('.cross-list');
  if(!list){ _wireCrossAddBtn(); return; }
  if(crossList.length === 0){
    list.innerHTML = `<div style="padding:16px;color:var(--muted);font-size:12px">Nenhuma configuração cross-env encontrada. Clique em <b style="color:var(--ink-2)">Criar nova configuração cross-env</b> abaixo.</div>`;
    _wireCrossAddBtn();
    return;
  }
  list.innerHTML = crossList.map(cfg => {
    const meta = parseCrossConfigMeta(cfg.id);
    const displayName = cfg.label || cfg.id;
    return `<button class="cross-card" data-cross="${escapeHtmlInline(cfg.id)}" title="${escapeHtmlInline(cfg.id)}">`
         + `<div class="cc-name"><span>${escapeHtmlInline(displayName)}</span><span style="font-family:var(--mono);font-size:10px;color:var(--muted);margin-left:6px;font-weight:400">${escapeHtmlInline(cfg.id)}</span></div>`
         + `<div class="cc-status ${meta.status}"><span class="d"></span>${meta.hint}</div>`
         + `<div class="cc-flow">`
         + `  <span class="env-pill">${meta.src}</span>`
         + `  <span class="arrow"><svg><use href="#i-arrow-right"/></svg></span>`
         + `  <span class="env-pill dest">${meta.dst}</span>`
         + `</div>`
         + `</button>`;
  }).join('');
  // Reatacha handlers dos cards novos
  list.querySelectorAll('.cross-card').forEach(card => {
    card.addEventListener('click', () => {
      const v = card.dataset.cross;
      if(state.cross.config === v){
        state.cross.config = null;
        card.classList.remove('sel');
        hideCrossPipesBlock();
      } else {
        state.cross.config = v;
        list.querySelectorAll('.cross-card').forEach(c => c.classList.toggle('sel', c === card));
        populateCrossPipeDropdowns(v);
      }
      updateFooter();
    });
  });

  // Wire do botão "Criar nova configuração cross-env"
  _wireCrossAddBtn();
}

function hideCrossPipesBlock(){
  const block = document.getElementById('cross-pipes-block');
  if(block) block.style.display = 'none';
  const preview = document.getElementById('cross-pipe-preview-block');
  if(preview) preview.style.display = 'none';
}

/* Popula os 2 dropdowns (cross-pipe-src, cross-pipe-dst) baseado no cross selecionado.
   Lê env_ids via parseCrossConfigMeta + lista de pipes via ENVS_DATA.
   Default: primeiro pipe de cada env. */
function populateCrossPipeDropdowns(crossId){
  const block = document.getElementById('cross-pipes-block');
  if(!block || !ENVS_DATA){
    if(block) block.style.display = 'none';
    return;
  }
  const meta = parseCrossConfigMeta(crossId);
  if(!meta.srcEnvId || !meta.dstEnvId){
    block.style.display = 'none';
    return;
  }
  block.style.display = '';

  // Reset state pipes ao mudar de cross (defaults serão repopulados em populateOneCrossPipeDropdown)
  state.cross.pipe_origem_uuid = '';
  state.cross.pipe_origem_repo_id = '';
  state.cross.pipe_origem_name = '';
  state.cross.pipe_destino_uuid = '';
  state.cross.pipe_destino_repo_id = '';
  state.cross.pipe_destino_name = '';

  const envs = ENVS_DATA.pipefy || [];
  const srcEnv = envs.find(e => e.id === meta.srcEnvId);
  const dstEnv = envs.find(e => e.id === meta.dstEnvId);

  populateOneCrossPipeDropdown('cross-pipe-src', srcEnv, 'origem');
  populateOneCrossPipeDropdown('cross-pipe-dst', dstEnv, 'destino');
  updateCrossPipePreview();
}

/* Atualiza o card visual read-only de pipes cross-env. Lê de state.cross e
   pinta nome do pipe, env e repo/uuid em cada card. Idempotente. */
function updateCrossPipePreview(){
  const block = document.getElementById('cross-pipe-preview-block');
  if(!block) return;
  const block2 = document.getElementById('cross-pipes-block');
  // Só mostra se o cross-pipes-block estiver visível (cross-card selecionado)
  if(!block2 || block2.style.display === 'none'){
    block.style.display = 'none';
    return;
  }
  block.style.display = '';

  const meta = (typeof parseCrossConfigMeta === 'function' && state.cross.config)
    ? parseCrossConfigMeta(state.cross.config) : { srcEnvId: null, dstEnvId: null };
  const envs = (ENVS_DATA && ENVS_DATA.pipefy) || [];
  const srcEnv = envs.find(e => e.id === meta.srcEnvId);
  const dstEnv = envs.find(e => e.id === meta.dstEnvId);

  function paint(role){
    const isOrig = role === 'origem';
    const stateKey = isOrig ? 'pipe_origem' : 'pipe_destino';
    const env = isOrig ? srcEnv : dstEnv;
    const nameEl = document.getElementById('cross-preview-' + (isOrig ? 'src' : 'dst') + '-name');
    const envEl = document.getElementById('cross-preview-' + (isOrig ? 'src' : 'dst') + '-env');
    const statsEl = document.getElementById('cross-preview-' + (isOrig ? 'src' : 'dst') + '-stats');
    const pipeName = state.cross[stateKey + '_name'] || '—';
    const pipeUuid = state.cross[stateKey + '_uuid'] || '';
    const pipeRepo = state.cross[stateKey + '_repo_id'] || '';
    if(nameEl) nameEl.textContent = pipeName;
    if(envEl) envEl.textContent = (env && env.name) || (env && env.id) || '—';
    if(statsEl){
      statsEl.innerHTML = '<span><b>' + (pipeRepo || '—') + '</b> repo</span>'
                       + '<span><b>' + (pipeUuid ? pipeUuid.slice(0, 8) : '—') + '</b> uuid</span>'
                       + '<span style="color:var(--muted)" title="Requer chamada prévia ao Pipefy pra calcular"><b>—</b> stats</span>';
    }
  }
  paint('origem');
  paint('destino');
}

function populateOneCrossPipeDropdown(ddKey, env, role){
  const dd = document.querySelector('.dropdown[data-dd="' + ddKey + '"]');
  if(!dd) return;
  const valueEl = dd.querySelector('.dd-value');
  const badge = dd.querySelector('.dd-env');
  const menuInner = dd.querySelector('.dd-menu-inner');

  if(!env || !env.pipes || env.pipes.length === 0){
    if(menuInner) menuInner.innerHTML = '<div style="padding:12px 16px;color:var(--muted);font-size:11.5px">Nenhum pipe configurado neste ambiente.</div>';
    if(valueEl) valueEl.innerHTML = '<span class="muted">— / </span>—';
    if(badge) badge.textContent = '—';
    return;
  }

  // Default: primeiro pipe do env
  const stateKey = role === 'origem' ? 'pipe_origem' : 'pipe_destino';
  if(!state.cross[stateKey + '_uuid']){
    const def = env.pipes[0];
    state.cross[stateKey + '_name'] = def.name;
    state.cross[stateKey + '_uuid'] = def.uuid || '';
    state.cross[stateKey + '_repo_id'] = def.repo_id || '';
  }

  if(menuInner){
    menuInner.innerHTML = env.pipes.map(p => {
      const isSel = p.name === state.cross[stateKey + '_name'];
      return '<button class="dd-opt' + (isSel ? ' sel' : '') + '"'
           + ' data-pipe-name="' + escapeHtmlInline(p.name) + '"'
           + ' data-pipe-uuid="' + (p.uuid || '') + '"'
           + ' data-pipe-repo="' + (p.repo_id || '') + '">'
           +   '<span class="opt-name">' + escapeHtmlInline(p.name) + '</span>'
           +   '<span class="opt-sub">repo ' + (p.repo_id || '—') + '</span>'
           + '</button>';
    }).join('');
  }
  if(valueEl){
    valueEl.innerHTML = '<span class="muted">' + escapeHtmlInline(env.name) + ' / </span>' + escapeHtmlInline(state.cross[stateKey + '_name'] || '—');
  }
  if(badge) badge.textContent = 'repo ' + (state.cross[stateKey + '_repo_id'] || '—');

  // Event delegation idempotente
  if(menuInner && !menuInner.dataset.crossPipeWired){
    menuInner.dataset.crossPipeWired = '1';
    menuInner.addEventListener('click', (e) => {
      const opt = e.target.closest('.dd-opt');
      if(!opt) return;
      menuInner.querySelectorAll('.dd-opt').forEach(o => o.classList.remove('sel'));
      opt.classList.add('sel');
      state.cross[stateKey + '_name'] = opt.dataset.pipeName;
      state.cross[stateKey + '_uuid'] = opt.dataset.pipeUuid;
      state.cross[stateKey + '_repo_id'] = opt.dataset.pipeRepo;
      if(valueEl){
        valueEl.innerHTML = '<span class="muted">' + escapeHtmlInline(env.name) + ' / </span>' + escapeHtmlInline(state.cross[stateKey + '_name']);
      }
      if(badge) badge.textContent = 'repo ' + (state.cross[stateKey + '_repo_id'] || '—');
      dd.querySelector('.dd-menu').classList.remove('open');
      dd.querySelector('[data-dd-trigger]').classList.remove('open');
      updateFooter();
      if(typeof updateCrossPipePreview === 'function') updateCrossPipePreview();
    });
  }
}

function showCrossAddDialog(){
  const existing = document.getElementById('cross-add-dialog');
  if(existing) existing.remove();

  const backdrop = document.createElement('div');
  backdrop.id = 'cross-add-dialog';
  backdrop.style.cssText = 'position:fixed;inset:0;background:rgba(11,15,26,.72);backdrop-filter:blur(4px);z-index:100;display:flex;align-items:center;justify-content:center;opacity:0;transition:opacity .2s';

  const envs = (ENVS_DATA && ENVS_DATA.pipefy) || [];
  const envOpts = envs.map(e => `<option value="${e.id}">${escapeHtmlInline(e.name)} (${e.id})${e.has_token ? '' : ' · sem token'}</option>`).join('');

  const modal = document.createElement('div');
  modal.style.cssText = 'width:520px;max-width:92vw;background:var(--bg-1);border:1px solid var(--line-2);border-radius:12px;padding:20px 22px;box-shadow:0 24px 60px rgba(0,0,0,.6);transform:scale(0.96);transition:transform .22s';
  modal.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
      <div style="font-size:14px;font-weight:500;color:var(--ink);letter-spacing:-.01em">Criar configuração cross-env</div>
      <button id="cross-add-close" style="background:none;border:none;color:var(--muted);cursor:pointer;padding:4px;border-radius:4px;display:flex;align-items:center;justify-content:center">
        <svg style="width:16px;height:16px;stroke-width:1.75" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
      </button>
    </div>
    <div style="font-size:12px;color:var(--muted);line-height:1.55;margin-bottom:14px">Cross config combina dois ambientes do seu vault. As credenciais de cada um vão no body do <code style="font-family:var(--mono);color:var(--accent);font-size:11px">/api/run</code> só na hora de executar.</div>

    <label style="display:block;font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">ID</label>
    <input type="text" id="cross-add-id" placeholder="ex: hmg_x_stg" style="width:100%;padding:9px 12px;background:rgba(255,255,255,.02);border:1px solid var(--line-2);border-radius:6px;color:var(--ink);font-family:var(--mono);font-size:12.5px;margin-bottom:12px">

    <label style="display:block;font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Ambiente origem</label>
    <select id="cross-add-src" style="width:100%;padding:9px 12px;background:rgba(255,255,255,.02);border:1px solid var(--line-2);border-radius:6px;color:var(--ink);font-size:12.5px;margin-bottom:12px">
      <option value="">— selecione —</option>${envOpts}
    </select>

    <label style="display:block;font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Ambiente destino</label>
    <select id="cross-add-dst" style="width:100%;padding:9px 12px;background:rgba(255,255,255,.02);border:1px solid var(--line-2);border-radius:6px;color:var(--ink);font-size:12.5px;margin-bottom:14px">
      <option value="">— selecione —</option>${envOpts}
    </select>

    <div id="cross-add-error" style="display:none;font-size:11.5px;color:#d9534f;background:rgba(217,83,79,.08);border:1px solid rgba(217,83,79,.25);border-radius:6px;padding:8px 10px;margin-bottom:12px"></div>

    <div style="display:flex;gap:8px;justify-content:flex-end">
      <button id="cross-add-cancel" style="padding:8px 14px;border-radius:6px;background:rgba(255,255,255,.04);border:1px solid var(--line-2);color:var(--ink-2);font-size:12.5px;cursor:pointer">Cancelar</button>
      <button id="cross-add-create" style="padding:8px 16px;border-radius:6px;background:var(--accent);color:#0b0f1a;border:none;font-weight:600;font-size:12.5px;cursor:pointer">Criar</button>
    </div>
  `;
  backdrop.appendChild(modal);
  document.body.appendChild(backdrop);

  requestAnimationFrame(() => {
    backdrop.style.opacity = '1';
    modal.style.transform = 'scale(1)';
  });

  function close(){
    backdrop.style.opacity = '0';
    modal.style.transform = 'scale(0.96)';
    setTimeout(() => backdrop.remove(), 220);
  }

  function showError(msg){
    const el = document.getElementById('cross-add-error');
    if(el){ el.textContent = msg; el.style.display = ''; }
  }

  document.getElementById('cross-add-close').addEventListener('click', close);
  document.getElementById('cross-add-cancel').addEventListener('click', close);
  backdrop.addEventListener('click', (e) => { if(e.target === backdrop) close(); });

  document.getElementById('cross-add-create').addEventListener('click', () => {
    const id = document.getElementById('cross-add-id').value.trim();
    const src = document.getElementById('cross-add-src').value;
    const dst = document.getElementById('cross-add-dst').value;
    if(!id){ showError('ID é obrigatório'); return; }
    if(!src){ showError('Selecione o ambiente origem'); return; }
    if(!dst){ showError('Selecione o ambiente destino'); return; }
    const safe = id.replace(/[^a-zA-Z0-9_-]+/g, '_').replace(/^_|_$/g, '');
    if(!safe){ showError('ID inválido'); return; }
    const fileId = safe.startsWith('cross_') ? safe : 'cross_' + safe;
    const list = _readCrossConfigs();
    if(list.some(c => c.id === fileId)){
      showError('Já existe ' + fileId);
      return;
    }
    list.push({
      id: fileId,
      label: fileId.replace(/^cross_/, '').replace(/_/g, ' '),
      src_env_id: src,
      dst_env_id: dst,
    });
    _saveCrossConfigs(list);
    console.log('[v2] cross criado client-side:', fileId);
    close();
    if(typeof loadConfigs === 'function') loadConfigs();
  });

  const escHandler = (e) => {
    if(e.key === 'Escape'){ close(); document.removeEventListener('keydown', escHandler); }
  };
  document.addEventListener('keydown', escHandler);
}

/* ------------------------------------------------------------
   3C: SNAPSHOT BASELINE DROPDOWN — fetch /api/snapshots
   ------------------------------------------------------------ */
async function loadSnapshots(){
  try {
    const res = await apiFetch('/api/snapshots');
    if(!res.ok) throw new Error('HTTP ' + res.status);
    const snaps = await res.json();
    populateSnapshotDropdown(snaps);
  } catch(e) {
    console.warn('[v2] /api/snapshots falhou:', e.message);
  }
}

function fmtTimestamp(ts){
  if(!ts) return '';
  try {
    const str = String(ts).trim();
    // Detecta se timestamp tem indicador de TZ. Se não, parse como LOCAL (não UTC).
    const hasTz = /(Z|[+-]\d{2}:?\d{2})$/.test(str);
    let d;
    if(hasTz){
      d = new Date(str);
    } else {
      // Parse manual: "YYYY-MM-DDTHH:MM:SS[.fff]" como timezone local
      const m = str.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?/);
      if(m){
        d = new Date(+m[1], +m[2]-1, +m[3], +m[4], +m[5], +m[6], m[7] ? Math.floor(+('0.' + m[7]) * 1000) : 0);
      } else {
        d = new Date(str);
      }
    }
    if(isNaN(d.getTime())) return str.slice(0, 16);

    const diffMs = Date.now() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if(diffMin < 0) return 'agora mesmo';
    if(diffMin < 1) return 'agora mesmo';
    if(diffMin < 60) return diffMin + ' min atrás';
    const diffHr = Math.floor(diffMin / 60);
    if(diffHr < 48) return diffHr + ' h atrás';
    const diffDay = Math.floor(diffHr / 24);
    return diffDay + ' dias atrás';
  } catch(_){
    return String(ts).slice(0, 16);
  }
}

let SNAPSHOTS_CACHE = [];

function updateSnapBaselinePreview(){
  // Encontra o snapshot selecionado (primeiro .sel ou primeiro da lista)
  const dd = document.querySelector('.dropdown[data-dd="snap-baseline"]');
  if(!dd) return;
  const sel = dd.querySelector('.dd-opt.sel');
  const selFile = sel ? sel.dataset.val : '';
  const selSnap = SNAPSHOTS_CACHE.find(s => s.file === selFile) || SNAPSHOTS_CACHE[0];
  if(!selSnap) return;

  // Atualiza a pílula dd-env com tempo real
  const ddEnv = dd.querySelector('.dd-env');
  if(ddEnv) ddEnv.textContent = fmtTimestamp(selSnap.timestamp);

  // Atualiza o Preview do baseline
  const panes = document.querySelectorAll('.snap-pane[data-snap="comparar"] .snap-preview');
  const preview = panes[0];
  if(preview){
    const spName = preview.querySelector('.sp-name');
    const spDate = preview.querySelector('.sp-date');
    const spGrid = preview.querySelector('.sp-grid');
    if(spName) spName.textContent = selSnap.name;
    if(spDate){
      const ago = fmtTimestamp(selSnap.timestamp);
      spDate.textContent = 'gerado ' + (ago === 'agora mesmo' ? 'agora' : ago) + ' · ' + (selSnap.pipe_name || '—');
    }
    if(spGrid){
      spGrid.innerHTML = '<span><b>' + (selSnap.automacoes || '—') + '</b> automações</span>'
                      + '<span><b>' + (selSnap.size_kb ? selSnap.size_kb.toFixed(1) + ' KB' : '—') + '</b> tamanho</span>'
                      + '<span title="stats de fases/campos não são expostos pelo backend"><b>—</b> fases/campos</span>'
                      + '<span><b>' + escapeHtmlInline(String(selSnap.pipe_name || '')) + '</b></span>';
    }
  }

  // Snap-current: lista todos os pipes de todos envs (via ENVS_DATA), permite escolher
  // qual pipe LIVE comparar contra o baseline. Pré-seleciona o pipe que casa com pipe_name
  // do baseline. Backend recebe pipe_uuid/repo_id via --variable PIPE_DESTINO_*.
  populateSnapCurrentDropdown(selSnap);
}

function populateSnapCurrentDropdown(selSnap){
  const dd = document.querySelector('.dropdown[data-dd="snap-current"]');
  if(!dd || !ENVS_DATA) return;
  const valueEl = dd.querySelector('.dd-value');
  const badge = dd.querySelector('.dd-env');
  const menuInner = dd.querySelector('.dd-menu-inner');
  if(!menuInner) return;

  const envs = ENVS_DATA.pipefy || [];
  const items = [];
  envs.forEach(env => {
    (env.pipes || []).forEach(pipe => {
      items.push({
        env_id: env.id,
        env_name: env.name,
        pipe_name: pipe.name,
        pipe_uuid: pipe.uuid || '',
        pipe_repo_id: pipe.repo_id || '',
        has_token: env.has_token === true,
      });
    });
  });

  if(items.length === 0){
    menuInner.innerHTML = '<div style="padding:12px 16px;color:var(--muted);font-size:11.5px">Nenhum ambiente com pipes configurados.</div>';
    return;
  }

  // Pré-seleção: tenta achar pipe com nome igual ao do baseline. Senão, primeiro com token.
  const baselineName = (selSnap && selSnap.pipe_name) || '';
  let defaultItem = items.find(i => i.has_token && i.pipe_name === baselineName);
  if(!defaultItem) defaultItem = items.find(i => i.pipe_name === baselineName);
  if(!defaultItem) defaultItem = items.find(i => i.has_token) || items[0];

  // Atualiza state apenas se ainda não tem seleção válida ou se mudou o baseline
  if(!state.snapshot.compare_pipe_uuid || state.snapshot.compare_pipe !== baselineName){
    state.snapshot.compare_env = defaultItem.env_id;
    state.snapshot.compare_pipe = defaultItem.pipe_name;
    state.snapshot.compare_pipe_uuid = defaultItem.pipe_uuid;
    state.snapshot.compare_pipe_repo_id = defaultItem.pipe_repo_id;
  }

  menuInner.innerHTML = items.map(it => {
    const isSel = it.env_id === state.snapshot.compare_env && it.pipe_name === state.snapshot.compare_pipe;
    const envTag = it.env_id.includes('prd') ? 'prd' : it.env_id.includes('stg') ? 'stg' : it.env_id.includes('dev') ? 'dev' : 'hmg';
    const matchTag = it.pipe_name === baselineName ? '<span style="color:var(--green);margin-left:6px">· mesmo</span>' : '<span style="color:var(--yellow);margin-left:6px">· pipe diferente</span>';
    const tokenFlag = it.has_token ? '' : ' · <span style="color:var(--yellow)">sem token</span>';
    return '<button class="dd-opt' + (isSel ? ' sel' : '') + '"'
         + ' data-env-id="' + it.env_id + '"'
         + ' data-pipe-name="' + escapeHtmlInline(it.pipe_name) + '"'
         + ' data-pipe-uuid="' + it.pipe_uuid + '"'
         + ' data-pipe-repo="' + it.pipe_repo_id + '"'
         + ' data-has-token="' + (it.has_token ? '1' : '0') + '">'
         +   '<span class="env-tag">' + envTag + '</span>'
         +   '<span class="opt-name">' + escapeHtmlInline(it.env_name + ' / ' + it.pipe_name) + matchTag + '</span>'
         +   '<span class="opt-sub">repo ' + (it.pipe_repo_id || '—') + tokenFlag + '</span>'
         + '</button>';
  }).join('');

  // Atualiza value/badge do botão
  const envName = (envs.find(e => e.id === state.snapshot.compare_env) || {}).name || state.snapshot.compare_env;
  if(valueEl){
    valueEl.innerHTML = '<span class="muted">' + escapeHtmlInline(envName) + ' / </span>' + escapeHtmlInline(state.snapshot.compare_pipe || '—');
  }
  if(badge){
    const isMatch = state.snapshot.compare_pipe === baselineName;
    badge.textContent = isMatch ? 'mesmo pipe do baseline' : 'pipe diferente';
    badge.style.color = isMatch ? 'var(--green)' : 'var(--yellow)';
  }

  // Event delegation pros clicks (idempotente via flag)
  if(!menuInner.dataset.snapCurrentWired){
    menuInner.dataset.snapCurrentWired = '1';
    menuInner.addEventListener('click', (e) => {
      const opt = e.target.closest('.dd-opt');
      if(!opt) return;
      menuInner.querySelectorAll('.dd-opt').forEach(o => o.classList.remove('sel'));
      opt.classList.add('sel');
      state.snapshot.compare_env = opt.dataset.envId;
      state.snapshot.compare_pipe = opt.dataset.pipeName;
      state.snapshot.compare_pipe_uuid = opt.dataset.pipeUuid;
      state.snapshot.compare_pipe_repo_id = opt.dataset.pipeRepo;
      // Atualiza value/badge
      const envLabel = (envs.find(e => e.id === state.snapshot.compare_env) || {}).name || state.snapshot.compare_env;
      if(valueEl){
        valueEl.innerHTML = '<span class="muted">' + escapeHtmlInline(envLabel) + ' / </span>' + escapeHtmlInline(state.snapshot.compare_pipe);
      }
      if(badge){
        const isMatch = state.snapshot.compare_pipe === baselineName;
        badge.textContent = isMatch ? 'mesmo pipe do baseline' : 'pipe diferente';
        badge.style.color = isMatch ? 'var(--green)' : 'var(--yellow)';
      }
      dd.querySelector('.dd-menu').classList.remove('open');
      dd.querySelector('[data-dd-trigger]').classList.remove('open');
      updateFooter();
    });
  }
}

function escapeHtmlInline(s){
  return String(s || '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

function populateSnapshotDropdown(snaps){
  SNAPSHOTS_CACHE = snaps || [];
  const dd = document.querySelector('.dropdown[data-dd="snap-baseline"]');
  if(!dd) return;
  const menuInner = dd.querySelector('.dd-menu-inner');
  if(!menuInner) return;
  // Atualiza contador dinâmico no block-hint
  const countEl = document.getElementById('snap-count-hint');
  if(countEl) countEl.textContent = String((snaps || []).filter(s => !s.is_ipaas).length);
  if(snaps.length === 0){
    menuInner.innerHTML = `<div style="padding:12px 16px;color:var(--muted);font-size:11.5px">Nenhum snapshot disponível. Gere um na sub-aba acima.</div>`;
    return;
  }
  // Filtra snapshots Pipefy (não iPaaS) pra este dropdown
  const pipefySnaps = snaps.filter(s => !s.is_ipaas);
  const list = pipefySnaps.length > 0 ? pipefySnaps : snaps;
  menuInner.innerHTML = list.map((s, i) => {
    const isSel = i === 0; // primeiro selecionado por default
    const ago = fmtTimestamp(s.timestamp);
    const short = s.name.replace(/\.json$/, '');
    return `<button class="dd-opt${isSel ? ' sel' : ''}" data-val="${s.file}" data-pipe="${s.pipe_name || ''}">`
         + `<span class="opt-name">${short}</span>`
         + `<span class="opt-sub">${ago} · ${s.automacoes} auto${s.size_kb ? ' · ' + s.size_kb + 'KB' : ''}</span>`
         + `</button>`;
  }).join('');
  if(list.length > 0){
    state.snapshot.baseline = list[0].name.replace(/\.json$/, '');
    const valueEl = dd.querySelector('.dd-value');
    if(valueEl){
      const muted = valueEl.querySelector('.muted');
      if(muted){
        valueEl.innerHTML = '';
        valueEl.appendChild(muted);
        valueEl.appendChild(document.createTextNode(list[0].name.replace(/\.json$/, '')));
      } else {
        valueEl.textContent = list[0].name.replace(/\.json$/, '');
      }
    }
  }
  attachOptClickToNew(dd);
  // Event delegation redundante: garante que seleção de baseline sempre dispare preview update,
  // mesmo se attachOptClickToNew tiver estado inconsistente entre re-renders
  if(!menuInner.dataset.delegationWired){
    menuInner.dataset.delegationWired = '1';
    menuInner.addEventListener('click', (e) => {
      const opt = e.target.closest('.dd-opt');
      if(!opt) return;
      menuInner.querySelectorAll('.dd-opt').forEach(o => o.classList.remove('sel'));
      opt.classList.add('sel');
      const file = opt.dataset.val || '';
      const name = (opt.querySelector('.opt-name') || {}).textContent || '';
      state.snapshot.baseline = name.replace(/\.json$/, '');
      console.log('[v2] baseline selecionado:', file, '→ atualizando preview');
      updateSnapBaselinePreview();
      updateFooter();
    });
  }
  updateSnapBaselinePreview();
}

/* ------------------------------------------------------------
   3D: IPAAS ENV DROPDOWN — usa ENVS_DATA.ipaas já carregado
   ------------------------------------------------------------ */
function populateIpaasEnvDropdown(){
  const dd = document.querySelector('.dropdown[data-dd="ipaas-env"]');
  if(!dd || !ENVS_DATA) return;
  const menuInner = dd.querySelector('.dd-menu-inner');
  if(!menuInner) return;
  const ipaasList = ENVS_DATA.ipaas || [];

  // Atualiza o callout de alerta baseado em ambientes pendentes
  const callout = document.querySelector('.mode-pane[data-pane="ipaas"] .callout');
  if(callout){
    const pending = ipaasList.filter(e => !(e.has_token !== undefined ? e.has_token : (e.token && e.token.length > 10)));
    const calloutText = callout.querySelector('div');
    if(pending.length === 0){
      // Nenhum pendente: esconde o callout (ou mostra mensagem positiva)
      callout.style.display = 'none';
    } else {
      callout.style.display = '';
      if(calloutText){
        const pendingNames = pending.map(e => '<b>' + e.id + '</b>').join(', ');
        calloutText.innerHTML = 'Validação iPaaS requer credenciais Activepieces. ' + pendingNames + ' ainda não configurado — abra <a href="#" class="link-manage-cta" style="color:var(--accent);text-decoration:none">Gerenciar ambientes</a> para adicionar.';
        // Wire o link dinâmico
        const cta = calloutText.querySelector('.link-manage-cta');
        if(cta){
          cta.addEventListener('click', (e) => {
            e.preventDefault();
            const modalTrigger = document.getElementById('link-manage');
            if(modalTrigger) modalTrigger.click();
          });
        }
      }
    }
  }

  if(ipaasList.length === 0){
    menuInner.innerHTML = `<div style="padding:12px 16px;color:var(--muted);font-size:11.5px">Nenhum ambiente iPaaS configurado</div>`;
    return;
  }
  const currentEnv = ipaasList.find(e => e.id === state.ipaas.env) || ipaasList[0];
  state.ipaas.env = currentEnv.id;
  menuInner.innerHTML = ipaasList.map(env => {
    const isSel = env.id === state.ipaas.env;
    const hasToken = env.has_token !== undefined ? env.has_token : (env.token && !env.token.startsWith('<') && env.token.length > 10);
    const authType = hasToken ? 'JWT' : 'não configurado';
    const tagClass = hasToken ? '' : 'pending';
    const tagStyle = hasToken ? 'background:rgba(108,194,108,.08);border-color:rgba(108,194,108,.22);color:var(--green)' : '';
    const tagText = hasToken ? 'ok' : 'Pendente';
    return `<button class="dd-opt${isSel ? ' sel' : ''}" data-val="${env.id}">`
         + `<span class="env-tag ${tagClass}" style="${tagStyle}">${tagText}</span>`
         + `<span class="opt-name">${env.name}</span>`
         + `<span class="opt-sub">${authType}</span>`
         + `</button>`;
  }).join('');
  const valueEl = dd.querySelector('.dd-value');
  if(valueEl){
    const muted = valueEl.querySelector('.muted');
    if(muted){
      valueEl.innerHTML = '';
      valueEl.appendChild(muted);
      valueEl.appendChild(document.createTextNode(currentEnv.name));
    } else {
      valueEl.textContent = currentEnv.name;
    }
  }
  attachOptClickToNew(dd);
}

/* ------------------------------------------------------------
   3E: BATCH LIST — fetch /api/batch
   ------------------------------------------------------------ */
let BATCH_CACHE = [];

async function loadBatch(){
  try {
    const res = await apiFetch('/api/batch');
    if(!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    BATCH_CACHE = data.pipes || [];
    renderBatchList();
  } catch(e) {
    console.warn('[v2] /api/batch falhou:', e.message);
  }
}

/* Renderiza lista de batch filtrada pelo env ativo (state.single.env).
   Pipes com env_id diferente são ocultos, porque rodariam com token errado → PERMISSION_DENIED. */
function renderBatchList(){
  const list = document.querySelector('.batch-list');
  if(!list) return;
  const activeEnv = state.single.env || '';
  const pipes = BATCH_CACHE.filter(p => !activeEnv || !p.env_id || p.env_id === activeEnv);

  // Atualiza hint informativo no topo (qual env está filtrando)
  const bar = document.querySelector('.batch-bar .bar-count');
  const envData = (ENVS_DATA && ENVS_DATA.pipefy || []).find(e => e.id === activeEnv);
  const envLabel = envData ? envData.name : activeEnv;
  const countCats = document.getElementById('batch-count-cats');
  if(countCats) countCats.textContent = 'ambiente: ' + (envLabel || '—');

  if(pipes.length === 0){
    const msg = BATCH_CACHE.length === 0
      ? 'Nenhum pipe configurado. Edite <code style="font-family:var(--mono);color:var(--ink-2)">config/batch_pipes.json</code>.'
      : 'Nenhum pipe do ambiente <b>' + (envLabel || activeEnv) + '</b> em <code style="font-family:var(--mono);color:var(--ink-2)">batch_pipes.json</code>. Troque o ambiente em Single-env ou adicione pipes.';
    list.innerHTML = '<div style="padding:16px;color:var(--muted);font-size:12px">' + msg + '</div>';
    document.getElementById('batch-count-sel').textContent = '0';
    const countSelEl = document.getElementById('batch-count-sel');
    if(countSelEl && countSelEl.parentElement){
      const sibs = countSelEl.parentElement.querySelectorAll('b');
      if(sibs.length >= 2) sibs[1].textContent = '0';
    }
    state.batch.sel = [];
    return;
  }

  // Inicia com todos selecionados por default
  state.batch.sel = pipes.map((_, i) => 'b' + (i + 1));
  list.innerHTML = pipes.map((p, i) => {
    const id = 'b' + (i + 1);
    const srcEnv = p.uuid_origem === p.uuid_destino ? 'mesmo ambiente' : (p.env_origem || 'origem');
    const dstEnv = p.uuid_origem === p.uuid_destino ? 'mesmo ambiente' : (p.env_destino || 'destino');
    const statusClass = p.uuid_origem === p.uuid_destino ? 'ok' : 'pending';
    const statusText = p.uuid_origem === p.uuid_destino ? 'self-check' : 'pendente';
    return `<button class="batch-row sel" data-batch="${id}" data-uuid-origem="${p.uuid_origem}" data-uuid-destino="${p.uuid_destino}">`
         + `<span class="check"></span>`
         + `<span class="br-flow">`
         + `  <span class="env-pill">${srcEnv}</span>`
         + `  <span class="arrow"><svg><use href="#i-arrow-right"/></svg></span>`
         + `  <span class="env-pill dest">${dstEnv}</span>`
         + `  <span class="pipe-name">${p.nome}</span>`
         + `</span>`
         + `<span class="br-count"><b>${p.repo_origem || '?'}</b> repo</span>`
         + `<span class="br-status ${statusClass}"><span class="d"></span>${statusText}</span>`
         + `</button>`;
  }).join('');

  document.getElementById('batch-count-sel').textContent = pipes.length;
  const countSelEl = document.getElementById('batch-count-sel');
  if(countSelEl && countSelEl.parentElement){
    const sibs = countSelEl.parentElement.querySelectorAll('b');
    if(sibs.length >= 2) sibs[1].textContent = pipes.length;
  }

  // Reatacha handlers
  list.querySelectorAll('.batch-row').forEach(row => {
    row.addEventListener('click', () => {
      const id = row.dataset.batch;
      const idx = state.batch.sel.indexOf(id);
      if(idx >= 0){ state.batch.sel.splice(idx, 1); row.classList.remove('sel'); }
      else { state.batch.sel.push(id); row.classList.add('sel'); }
      document.getElementById('batch-count-sel').textContent = state.batch.sel.length;
      syncCatState('batch');
    });
  });
  syncCatState('batch');
}

// Legacy alias: mantém compatibilidade se algum outro lugar chama populateBatchList
function populateBatchList(pipes){
  BATCH_CACHE = pipes || BATCH_CACHE;
  renderBatchList();
}

/* ------------------------------------------------------------
   3F: MODAL GERENCIAR AMBIENTES — render dinâmico da lista
   (Edit/Delete wire-up ficam para próxima iteração)
   ------------------------------------------------------------ */
function populateEnvModal(){
  if(!ENVS_DATA) return;
  const pipefyPane = document.querySelector('.mpane[data-mpane="pipefy"]');
  const pipefyList = ENVS_DATA.pipefy || [];
  const ipaasList = ENVS_DATA.ipaas || [];

  // Atualiza contadores nas tabs
  const pipefyTab = document.querySelector('.modal-tab[data-mtab="pipefy"] .c');
  const ipaasTab = document.querySelector('.modal-tab[data-mtab="ipaas"] .c');
  if(pipefyTab) pipefyTab.textContent = pipefyList.length;
  if(ipaasTab) ipaasTab.textContent = ipaasList.length;

  if(pipefyPane){
    pipefyPane.innerHTML = pipefyList.map(env => {
      const initials = (env.name || '??').split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
      const authLabel = env.auth_mode === 'cookie' ? 'Cookie+CSRF' : 'Bearer';
      // Prefere has_token do endpoint sanitizado; fallback pra checagem do token se presente
      const hasToken = env.has_token !== undefined ? env.has_token : (env.token && !env.token.startsWith('<') && env.token.length > 10);
      return `<div class="env-row" data-env-id="${env.id}">`
           + `<div class="env-mark">${initials}</div>`
           + `<div class="env-info">`
           + `  <div class="env-name">${env.name}</div>`
           + `  <div class="env-url">${env.base_url || ''} · ${authLabel}</div>`
           + `</div>`
           + `<div class="env-auth${hasToken ? '' : ' pending'}">${(env.pipes || []).length} pipes</div>`
           + `<div class="env-actions">`
           + `  <button class="icon-btn" data-tip="Editar" data-env-action="edit"><svg><use href="#i-edit"/></svg></button>`
           + `  <button class="icon-btn danger" data-tip="Remover" data-env-action="delete"><svg><use href="#i-trash"/></svg></button>`
           + `</div>`
           + `</div>`;
    }).join('');
    // Wire up remove button (vault local)
    pipefyPane.querySelectorAll('[data-env-action="delete"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const row = btn.closest('.env-row');
        const envId = row?.dataset.envId;
        if(!envId) return;
        if(!confirm(`Remover ambiente "${envId}"? Isto não pode ser desfeito.`)) return;
        if(window.V2Utils){
          window.V2Utils.vaultRemove(envId);
          console.log(`[v2] ambiente ${envId} removido do vault`);
          loadEnvironments();
          populateEnvModal();
        }
      });
    });
  }

  // iPaaS pane (criar se não existir)
  let ipaasPane = document.querySelector('.mpane[data-mpane="ipaas"]');
  if(!ipaasPane){
    ipaasPane = document.createElement('div');
    ipaasPane.className = 'mpane';
    ipaasPane.setAttribute('data-mpane', 'ipaas');
    document.querySelector('.modal-body')?.appendChild(ipaasPane);
  }
  ipaasPane.innerHTML = ipaasList.map(env => {
    const initials = (env.name || '??').split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
    const hasToken = env.has_token !== undefined ? env.has_token : (env.token && !env.token.startsWith('<') && env.token.length > 10);
    return `<div class="env-row" data-env-id="${env.id}">`
         + `<div class="env-mark">${initials}</div>`
         + `<div class="env-info">`
         + `  <div class="env-name">${env.name}</div>`
         + `  <div class="env-url">${env.base_url || ''} · ${hasToken ? 'JWT' : 'não configurado'}</div>`
         + `</div>`
         + `<div class="env-auth${hasToken ? '' : ' pending'}">${env.desc || ''}</div>`
         + `<div class="env-actions">`
         + `  <button class="icon-btn" data-tip="Editar" data-env-action="edit"><svg><use href="#i-edit"/></svg></button>`
         + `  <button class="icon-btn danger" data-tip="Remover" data-env-action="delete-ipaas"><svg><use href="#i-trash"/></svg></button>`
         + `</div>`
         + `</div>`;
  }).join('');
  ipaasPane.querySelectorAll('[data-env-action="delete-ipaas"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const row = btn.closest('.env-row');
      const envId = row?.dataset.envId;
      if(!envId) return;
      if(!confirm(`Remover ambiente iPaaS "${envId}"?`)) return;
      if(window.V2Utils){
        window.V2Utils.vaultRemove(envId);
        loadEnvironments();
        populateEnvModal();
      }
    });
  });

  // Wire up modal tab switch (se ainda não wired)
  document.querySelectorAll('.modal-tab').forEach(tab => {
    if(tab.dataset.wired === '1') return;
    tab.dataset.wired = '1';
    tab.addEventListener('click', () => {
      const target = tab.dataset.mtab;
      document.querySelectorAll('.modal-tab').forEach(t => t.classList.toggle('active', t === tab));
      // Esconde/mostra panes via style direto pra garantir (caso CSS não tenha .mpane { display: none })
      document.querySelectorAll('.mpane').forEach(p => {
        const isTarget = p.dataset.mpane === target;
        p.classList.toggle('active', isTarget);
        p.style.display = isTarget ? '' : 'none';
      });
    });
  });

  // Garante estado inicial: só a tab ativa visível
  const activeTab = document.querySelector('.modal-tab.active');
  const activeTarget = activeTab ? activeTab.dataset.mtab : 'pipefy';
  document.querySelectorAll('.mpane').forEach(p => {
    p.style.display = p.dataset.mpane === activeTarget ? '' : 'none';
  });
}

/* ------------------------------------------------------------
   KICK-OFF — carrega tudo que depende de API
   ------------------------------------------------------------ */
// MVP honesto: esconde controles deceptivos ANTES de popular (evita flash)
applyMvpHonestMode();

loadEnvironments().then(() => {
  populateIpaasEnvDropdown();
  populateEnvModal();
  updatePresetInfoCard();
  applyUrlParamsIfAny();
});
loadConfigs().then(() => applyUrlParamsIfAny());
loadSnapshots();
loadBatch();

/* Restaura modo/sub a partir da URL (ex: ?mode=snapshot&sub=comparar&config=fourd_hmg)
   Chamado depois de loadEnvironments e loadConfigs pra garantir que selects existem. */
function applyUrlParamsIfAny(){
  try {
    const params = new URLSearchParams(window.location.search);
    const mode = params.get('mode');
    const sub = params.get('sub');
    const config = params.get('config');

    if(mode && mode !== state.mode){
      // Troca imediata sem animação (diferente do setMode que tem setTimeout)
      state.mode = mode;
      const container = document.getElementById('content') || document.querySelector('[data-mode]');
      if(container) container.setAttribute('data-mode', mode);
      document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.mode === mode));
      document.querySelectorAll('.mode-pane').forEach(p => p.classList.toggle('active', p.dataset.pane === mode));
      const m = MODE_META[mode];
      if(m){
        if(shIco) shIco.innerHTML = '<svg><use href="#' + m.ico + '"/></svg>';
        if(shTitle) shTitle.innerHTML = m.title + (m.beta ? ' <span class="beta">BETA</span>' : '');
        if(shDesc) shDesc.textContent = m.desc;
      }
    }

    if(mode === 'snapshot' && sub && sub !== state.snapshot.sub){
      state.snapshot.sub = sub;
      document.querySelectorAll('.subtab').forEach(t => t.classList.toggle('active', t.dataset.subtab === sub));
      document.querySelectorAll('.snap-pane').forEach(p => p.classList.remove('active', 'out', 'in'));
      const targetPane = document.querySelector('.snap-pane[data-snap="' + sub + '"]');
      if(targetPane) targetPane.classList.add('active');
    }

    if(mode === 'cross' && config){
      state.cross.config = config;
      document.querySelectorAll('.cross-card').forEach(c => c.classList.toggle('sel', c.dataset.cross === config));
    }

    // Atualiza o breadcrumb current pra refletir o modo ativo
    if(mode){
      const bcCurrent = document.querySelector('.crumbs .current');
      if(bcCurrent){
        const modeNames = {
          single: 'Single Env',
          cross: 'Cross Env',
          snapshot: sub === 'comparar' ? 'Snapshot · Comparar' : 'Snapshot · Gerar',
          batch: 'Batch',
          ipaas: 'iPaaS',
          healthcheck: 'Health Check',
        };
        bcCurrent.textContent = modeNames[mode] || 'Nova execução';
      }
    }

    if(mode && typeof updateFooter === 'function') updateFooter();
  } catch(e){
    console.warn('[v2] applyUrlParamsIfAny falhou:', e.message);
  }
}

/* Breadcrumb + header icons: tornar clicáveis ou remover dead links */
document.querySelectorAll('.crumbs a').forEach(a => {
  a.addEventListener('click', (e) => {
    e.preventDefault();
    // Já está na home de configuração, scroll pro topo
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
});

/* Header icons: Documentação → /v2/docs (manual completo), Ajuda → /v2/help (FAQ + atalhos) */
(function wireHeaderIcons(){
  document.querySelectorAll('.topbar .icon-btn, header .icon-btn').forEach(btn => {
    if(btn.dataset.wiredHeader === '1') return;
    btn.dataset.wiredHeader = '1';
    const tip = btn.getAttribute('data-tip') || '';
    btn.addEventListener('click', (e) => {
      if(tip.includes('Documentação') || tip.includes('Book')){
        e.preventDefault();
        window.open('/v2/docs', '_blank');
      } else if(tip.includes('Ajuda') || tip.includes('Help')){
        e.preventDefault();
        window.open('/v2/help', '_blank');
      }
    });
  });
})();

function showTopToast(msg){
  const existing = document.getElementById('v2-toast');
  if(existing) existing.remove();
  const t = document.createElement('div');
  t.id = 'v2-toast';
  t.textContent = msg;
  t.style.cssText = 'position:fixed;top:60px;left:50%;transform:translateX(-50%);padding:10px 18px;border-radius:8px;background:rgba(11,15,26,.95);border:1px solid var(--accent);color:var(--ink);font-size:12px;font-weight:500;font-family:var(--sans);z-index:9998;box-shadow:0 8px 24px rgba(0,0,0,.4);opacity:0;transition:opacity .2s';
  document.body.appendChild(t);
  requestAnimationFrame(() => { t.style.opacity = '1'; });
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 220); }, 3200);
}

/* ============================================================
   ETAPA 4: BOTÃO EXECUTAR — POST /api/run e navega pra Execução
   ============================================================ */

/* Resolve um pipe (uuid + repo_id) a partir do slug + env_id consultando ENVS_DATA. */
function resolvePipe(envId, pipeSlug){
  if(!ENVS_DATA) return null;
  const env = (ENVS_DATA.pipefy || []).find(e => e.id === envId);
  if(!env) return null;
  const pipe = (env.pipes || []).find(p => slugify(p.name) === pipeSlug);
  return pipe || null;
}

function buildRunPayload(){
  const m = state.mode;
  const VU = window.V2Utils;
  if(!VU) return null;

  if(m === 'single'){
    const orig = resolvePipe(state.single.env, state.single.src);
    const dest = resolvePipe(state.single.env, state.single.dst);
    const base = {
      config: state.single.env,
      test: 'CT01*',
      pipe_origem_uuid: (orig && orig.uuid) || '',
      pipe_destino_uuid: (dest && dest.uuid) || '',
      pipe_origem_repo_id: (orig && orig.repo_id) || '',
      pipe_destino_repo_id: (dest && dest.repo_id) || '',
      categories: Array.isArray(state.single.cats) ? state.single.cats : [],
    };
    return VU.buildRunPayload('single', { src: state.single.env }, base);
  }

  if(m === 'cross'){
    if(!state.cross.config) return null;
    const meta = VU.parseCrossConfigMeta(state.cross.config);
    // Permite override pelos campos do cross-config salvo (que tem src_env_id/dst_env_id)
    const cross = _readCrossConfigs().find(c => c.id === state.cross.config);
    const srcId = (cross && cross.src_env_id) || meta.srcEnvId;
    const dstId = (cross && cross.dst_env_id) || meta.dstEnvId;
    const base = {
      config: state.cross.config,
      test: 'CT-CROSS*',
      pipe_origem_uuid: state.cross.pipe_origem_uuid || '',
      pipe_destino_uuid: state.cross.pipe_destino_uuid || '',
      pipe_origem_repo_id: state.cross.pipe_origem_repo_id || '',
      pipe_destino_repo_id: state.cross.pipe_destino_repo_id || '',
      categories: Array.isArray(state.cross.cats) ? state.cross.cats : [],
    };
    return VU.buildRunPayload('cross', { src: srcId, dst: dstId }, base);
  }

  if(m === 'snapshot'){
    if(state.snapshot.sub === 'gerar'){
      if(!state.snapshot.label || state.snapshot.label.trim() === '') return null;
      const envId = state.snapshot.env || state.single.env;
      const base = {
        config: envId,
        snapshot_mode: 'create',
        label: state.snapshot.label.trim(),
        pipe_uuid: state.snapshot.pipe_uuid || '',
        pipe_repo_id: state.snapshot.pipe_repo_id || '',
        test: 'CT05*',
      };
      return VU.buildRunPayload('snapshot', { src: envId }, base);
    } else {
      const sel = document.querySelector('.dropdown[data-dd="snap-baseline"] .dd-opt.sel');
      const file = (sel && sel.dataset.val) || `snapshots/${state.snapshot.baseline}.json`;
      if(!state.snapshot.baseline) return null;
      const envId = state.snapshot.compare_env || state.snapshot.env || state.single.env;
      const base = {
        config: envId,
        snapshot_mode: 'compare',
        file: file,
        pipe_uuid: state.snapshot.compare_pipe_uuid || '',
        pipe_repo_id: state.snapshot.compare_pipe_repo_id || '',
        test: 'CT06*',
      };
      return VU.buildRunPayload('snapshot', { src: envId }, base);
    }
  }

  if(m === 'batch'){
    if(!state.batch.sel || state.batch.sel.length === 0) return null;
    const list = document.querySelector('.batch-list');
    const selectedUuids = [];
    if(list){
      list.querySelectorAll('.batch-row.sel').forEach(row => {
        const uuid = row.dataset.uuidOrigem;
        if(uuid) selectedUuids.push(uuid);
      });
    }
    const envId = state.single.env;
    const base = {
      config: envId,
      test: 'CT-BATCH*',
      batch_env: envId,
      pipes_selected: selectedUuids,
      categories: Array.isArray(state.batch.cats) ? state.batch.cats : [],
    };
    return VU.buildRunPayload('batch', { src: envId }, base);
  }

  if(m === 'ipaas'){
    const typeMap = {
      'descoberta': 'CT-IPAAS-01*',
      'gerar':      'CT-IPAAS-03*',
      'comparar':   'CT-IPAAS-04*',
    };
    const base = {
      ipaas_config: state.ipaas.env,
      test: typeMap[state.ipaas.type] || 'CT-IPAAS-01*',
      categories: Array.isArray(state.ipaas.cats) ? state.ipaas.cats : [],
    };
    return VU.buildRunPayload('ipaas', { ipaas: state.ipaas.env }, base);
  }

  if(m === 'healthcheck'){
    const base = { config: state.single.env, test: 'HC*' };
    // Inclui credenciais Pipefy se houver env selecionado
    return VU.buildRunPayload('healthcheck', { src: state.single.env }, base);
  }

  return null;
}

function buildRunMeta(){
  // Snapshot das escolhas do usuário pra que Execução e Resultados mostrem info correta
  const m = state.mode;
  const runId = Date.now().toString(36).slice(-8);
  const startedAt = new Date();
  const hhmm = String(startedAt.getHours()).padStart(2, '0') + ':' + String(startedAt.getMinutes()).padStart(2, '0');
  const tzSuffix = hhmm + ' BRT';

  let envLabel = '';
  let pipeSrc = '';
  let pipeDst = '';
  let configLabel = '';
  let modeLabel = m.toUpperCase();

  if(m === 'single'){
    const env = (ENVS_DATA && ENVS_DATA.pipefy || []).find(e => e.id === state.single.env);
    envLabel = env ? env.name : state.single.env;
    pipeSrc = PIPE_NAMES[state.single.src] || state.single.src;
    pipeDst = PIPE_NAMES[state.single.dst] || state.single.dst;
    configLabel = envLabel + ' · ' + pipeSrc + ' → ' + pipeDst;
  }
  if(m === 'cross'){
    envLabel = 'Cross Env';
    configLabel = state.cross.config || '';
    modeLabel = 'CROSS_ENV';
  }
  if(m === 'snapshot'){
    envLabel = state.snapshot.sub === 'gerar' ? 'Snapshot · gerar' : 'Snapshot · comparar';
    configLabel = state.snapshot.sub === 'gerar' ? state.snapshot.label : state.snapshot.baseline;
    modeLabel = 'SNAPSHOT';
    // Fornece src/dst pra tela de Resultados separar origem (baseline) de destino (live)
    if(state.snapshot.sub === 'comparar'){
      pipeSrc = 'Baseline · ' + (state.snapshot.baseline || '');
      pipeDst = 'Live · ' + (state.snapshot.pipe || 'pipe atual');
    } else {
      pipeSrc = state.snapshot.pipe || '';
      pipeDst = 'Baseline salvo';
    }
  }
  if(m === 'batch'){
    envLabel = 'Batch';
    configLabel = state.batch.sel.length + ' pipes';
    modeLabel = 'BATCH';
  }
  if(m === 'ipaas'){
    envLabel = 'iPaaS';
    configLabel = state.ipaas.type;
    modeLabel = 'IPAAS';
  }

  return {
    mode: m,
    modeLabel: modeLabel,
    config: state[m] && state[m].env || state[m] && state[m].config || state.single.env,
    runId: runId,
    runIdFull: 'run_' + runId + '_' + startedAt.toISOString().replace(/[:.]/g, '').slice(0, 15),
    startedAt: startedAt.toISOString(),
    startedAtLabel: tzSuffix,
    envLabel: envLabel,
    pipeSrc: pipeSrc,
    pipeDst: pipeDst,
    configLabel: configLabel,
    categories: (state[m] && state[m].cats) || [],
    // Preserva sub-estado pra navegação de volta (ex: /v2/configuracao?mode=snapshot&sub=comparar)
    snapshotSub: m === 'snapshot' ? state.snapshot.sub : undefined,
    snapshotBaseline: m === 'snapshot' ? state.snapshot.baseline : undefined,
  };
}

async function executeRun(){
  if(btnRun.disabled) return;

  const payload = buildRunPayload();
  if(!payload){
    console.warn('[v2] payload inválido, abortando');
    return;
  }

  // Salva meta no sessionStorage pra Execução e Resultados exibirem dados corretos
  try {
    sessionStorage.setItem('v2-run-meta', JSON.stringify(buildRunMeta()));
  } catch(e) {
    console.warn('[v2] sessionStorage falhou:', e.message);
  }

  const originalHTML = btnRun.innerHTML;
  btnRun.disabled = true;
  btnRun.style.opacity = '.75';
  btnRun.innerHTML = '<span>Iniciando...</span>';

  try {
    const res = await apiFetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if(res.status === 409){
      const body = await res.json().catch(() => ({}));
      alert(body.error || 'Já existe uma validação em execução. Aguarde o fim ou acesse /v2/execucao.');
      btnRun.disabled = false;
      btnRun.style.opacity = '';
      btnRun.innerHTML = originalHTML;
      return;
    }

    if(res.status === 400){
      const body = await res.json().catch(() => ({}));
      alert('Credenciais inválidas: ' + (body.error || 'configure um ambiente em Gerenciar Ambientes.'));
      btnRun.disabled = false;
      btnRun.style.opacity = '';
      btnRun.innerHTML = originalHTML;
      return;
    }

    if(!res.ok) throw new Error('HTTP ' + res.status);

    const body = await res.json();
    console.log('[v2] /api/run iniciou:', body);

    // Fix #3: substitui run_id client-side pelo real do backend ANTES de navegar
    // pra Execução/Resultados sincronizarem o mesmo identificador no breadcrumb.
    if(body.run_id){
      try {
        const meta = JSON.parse(sessionStorage.getItem('v2-run-meta') || '{}');
        meta.runId = body.run_id;
        meta.runIdFull = 'run_' + body.run_id + '_' + (meta.startedAt || new Date().toISOString()).replace(/[:.]/g, '').slice(0, 15);
        sessionStorage.setItem('v2-run-meta', JSON.stringify(meta));
      } catch(e){ console.warn('[v2] sync run_id falhou:', e.message); }
    }

    setTimeout(() => { navigateTo('/v2/execucao'); }, 300);
  } catch(e) {
    console.error('[v2] falha ao iniciar:', e);
    alert('Falha ao iniciar validação: ' + e.message);
    btnRun.disabled = false;
    btnRun.style.opacity = '';
    btnRun.innerHTML = originalHTML;
  }
}

/* Adiciona listener NOVO que faz a ação real, sem mexer no runPulse existente */
btnRun.addEventListener('click', () => {
  if(btnRun.disabled) return;
  setTimeout(executeRun, 120);
});

/* ============================================================
   POLISH: Modal Gerenciar Ambientes — EDITAR + ADICIONAR + SALVAR
   ============================================================ */

function renderEnvForm(env, type, isNew){
  env = env || {};
  const fields = type === 'pipefy' ? [
    { key: 'id',          label: 'ID (slug)', type: 'text', required: true, disabled: !isNew },
    { key: 'name',        label: 'Nome',       type: 'text', required: true },
    { key: 'desc',        label: 'Descrição',  type: 'text' },
    { key: 'base_url',    label: 'URL base',   type: 'text', required: true, placeholder: 'https://api.pipefy.com/graphql' },
    { key: 'auth_mode',   label: 'Modo de auth', type: 'select', required: true, options: ['bearer', 'cookie'] },
    { key: 'token',       label: 'Token (Bearer ... ou valor cru)', type: 'password', required: true },
    { key: 'session_cookie', label: 'Session cookie (se cookie mode)', type: 'text', default: 'NONE' },
    { key: 'csrf_token',  label: 'CSRF token (se cookie mode)', type: 'text', default: 'NONE' },
    { key: 'org_id',      label: 'Organization ID', type: 'text' },
    { key: 'verify_ssl',  label: 'Verify SSL', type: 'bool' },
  ] : [
    { key: 'id',          label: 'ID (slug)', type: 'text', required: true, disabled: !isNew },
    { key: 'name',        label: 'Nome', type: 'text', required: true },
    { key: 'desc',        label: 'Descrição', type: 'text' },
    { key: 'base_url',    label: 'URL base', type: 'text', required: true, placeholder: 'https://ipaas.pipefy.com/api/v1' },
    { key: 'token',       label: 'Token Bearer JWT', type: 'password', required: true },
    { key: 'project_id',  label: 'Project ID', type: 'text' },
    { key: 'verify_ssl',  label: 'Verify SSL', type: 'bool' },
  ];

  const rows = fields.map(f => {
    const val = env[f.key] != null ? env[f.key] : (f.default !== undefined ? f.default : '');
    if(f.type === 'bool'){
      return `<div class="field" style="margin:0">
        <div class="field-lbl">${f.label.toUpperCase()}</div>
        <label style="display:inline-flex;align-items:center;gap:8px;font-size:12px;color:var(--ink-2);cursor:pointer">
          <input type="checkbox" data-env-key="${f.key}" ${val ? 'checked' : ''} style="accent-color:var(--accent);width:14px;height:14px">
          ${val ? 'Habilitado' : 'Desabilitado'}
        </label>
      </div>`;
    }
    if(f.type === 'select'){
      return `<div class="field" style="margin:0">
        <div class="field-lbl">${f.label.toUpperCase()}${f.required ? ' *' : ''}</div>
        <select data-env-key="${f.key}" class="input" style="background:rgba(255,255,255,.02);color:var(--ink);border:1px solid var(--line-2);border-radius:5px;padding:8px 10px;font-family:var(--sans);font-size:12px">
          ${f.options.map(o => `<option value="${o}"${o === val ? ' selected' : ''}>${o}</option>`).join('')}
        </select>
      </div>`;
    }
    if(f.type === 'password'){
      return `<div class="field" style="margin:0;grid-column:1 / -1">
        <div class="field-lbl">${f.label.toUpperCase()}${f.required ? ' *' : ''}</div>
        <div class="password-wrap">
          <input class="input masked" type="password" data-env-key="${f.key}" value="${String(val).replace(/"/g, '&quot;')}" ${f.placeholder ? `placeholder="${f.placeholder}"` : ''}>
          <button type="button" class="pw-toggle" data-env-pw-toggle><svg><use href="#i-eye"/></svg></button>
        </div>
      </div>`;
    }
    return `<div class="field" style="margin:0${f.key === 'base_url' || f.key === 'desc' ? ';grid-column:1 / -1' : ''}">
      <div class="field-lbl">${f.label.toUpperCase()}${f.required ? ' *' : ''}</div>
      <input class="input" type="text" data-env-key="${f.key}" value="${String(val).replace(/"/g, '&quot;')}" ${f.disabled ? 'disabled' : ''} ${f.placeholder ? `placeholder="${f.placeholder}"` : ''}>
    </div>`;
  }).join('');

  // Seletor de tipo explícito (só quando isNew, pra evitar confusão com #37)
  const typeSelector = isNew ? `
    <div style="margin-bottom:14px;padding:10px 12px;border-radius:8px;background:rgba(201,168,76,.05);border:1px solid rgba(201,168,76,.2)">
      <div style="font-size:10px;color:var(--muted);letter-spacing:.06em;text-transform:uppercase;font-weight:600;margin-bottom:6px">TIPO DE AMBIENTE *</div>
      <div style="display:flex;gap:8px">
        <label style="flex:1;display:flex;align-items:center;gap:6px;padding:7px 10px;border-radius:5px;border:1px solid ${type==='pipefy' ? 'var(--accent)' : 'var(--line-2)'};background:${type==='pipefy' ? 'rgba(201,168,76,.12)' : 'transparent'};cursor:pointer;font-size:12px;color:${type==='pipefy' ? 'var(--accent)' : 'var(--ink-2)'};font-weight:500">
          <input type="radio" name="env-type-select" value="pipefy" ${type==='pipefy' ? 'checked' : ''} style="accent-color:var(--accent)">
          Pipefy
        </label>
        <label style="flex:1;display:flex;align-items:center;gap:6px;padding:7px 10px;border-radius:5px;border:1px solid ${type==='ipaas' ? 'var(--accent)' : 'var(--line-2)'};background:${type==='ipaas' ? 'rgba(201,168,76,.12)' : 'transparent'};cursor:pointer;font-size:12px;color:${type==='ipaas' ? 'var(--accent)' : 'var(--ink-2)'};font-weight:500">
          <input type="radio" name="env-type-select" value="ipaas" ${type==='ipaas' ? 'checked' : ''} style="accent-color:var(--accent)">
          iPaaS
        </label>
      </div>
    </div>
  ` : '';

  const rememberDefault = env.remember !== false;
  const rememberCheckbox = `
    <div style="margin-top:12px;padding:10px 12px;border-radius:8px;background:rgba(255,255,255,.02);border:1px solid var(--line-2)">
      <label style="display:flex;align-items:center;gap:10px;font-size:12px;color:var(--ink-2);cursor:pointer">
        <input type="checkbox" data-env-key="_remember" ${rememberDefault ? 'checked' : ''} style="accent-color:var(--accent);width:14px;height:14px">
        <span>
          <b style="color:var(--ink)">Lembrar nesta máquina</b>
          <span style="display:block;font-size:11px;color:var(--muted);margin-top:2px">
            Marcado: token salvo em localStorage. Desmarcado: só nesta sessão (sessionStorage).
          </span>
        </span>
      </label>
    </div>`;

  return `<div class="env-edit-form" data-env-type="${type}" data-env-original-id="${env.id || ''}" data-is-new="${isNew ? '1' : '0'}" style="padding:16px;border:1px solid var(--line-2);border-radius:10px;background:var(--bg-1);margin-bottom:10px">
    <div style="font-size:11px;color:var(--muted);letter-spacing:.06em;text-transform:uppercase;font-weight:600;margin-bottom:12px">
      ${isNew ? 'Novo ambiente' : 'Editar ' + (env.name || env.id)} · <span class="form-type-label">${type}</span>
    </div>
    ${typeSelector}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      ${rows}
    </div>
    ${rememberCheckbox}
    ${type === 'pipefy' ? `
      <div class="env-discover-block" style="margin-top:12px;padding:10px 12px;border-radius:8px;background:rgba(201,168,76,.04);border:1px solid rgba(201,168,76,.18)">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
          <div style="font-size:12px;color:var(--ink-2)">
            <b style="color:var(--ink)">Pipes</b>
            <span class="env-pipes-count" style="color:var(--muted);margin-left:4px">${(env.pipes||[]).length} cadastrado${(env.pipes||[]).length===1?'':'s'}</span>
          </div>
          <button type="button" data-env-action="discover-pipes" style="padding:6px 12px;border-radius:6px;background:transparent;border:1px solid var(--accent);color:var(--accent);font-size:11.5px;font-weight:500;cursor:pointer">Buscar pipes da org</button>
        </div>
        <div class="env-discover-status" style="margin-top:8px;font-size:11.5px;color:var(--muted);display:none"></div>
      </div>` : ''}
    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
      <button class="ghost" data-env-action="form-cancel" style="padding:7px 14px;border-radius:6px;border:1px solid var(--line-2);background:none;color:var(--ink-2);font-size:12px;cursor:pointer">Cancelar</button>
      <button class="primary" data-env-action="form-save" style="padding:7px 16px;border-radius:6px;background:var(--accent);color:#0b0f1a;border:none;font-weight:600;font-size:12px;cursor:pointer">Salvar</button>
    </div>
  </div>`;
}

function wireFormInsideModal(formEl){
  // Password toggle
  formEl.querySelectorAll('[data-env-pw-toggle]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const input = btn.parentElement.querySelector('input');
      if(input.type === 'password'){ input.type = 'text'; btn.innerHTML = '<svg><use href="#i-eye-off"/></svg>'; }
      else { input.type = 'password'; btn.innerHTML = '<svg><use href="#i-eye"/></svg>'; }
    });
  });

  // Radio de tipo (pipefy/ipaas) — re-renderiza o form com o tipo selecionado
  formEl.querySelectorAll('input[name="env-type-select"]').forEach(radio => {
    radio.addEventListener('change', () => {
      const newType = radio.value;
      const isNew = formEl.dataset.isNew === '1';
      if(!isNew) return; // só troca de tipo em form de novo
      // Preserva valores atuais que são comuns
      const current = {};
      formEl.querySelectorAll('[data-env-key]').forEach(el => {
        current[el.dataset.envKey] = el.type === 'checkbox' ? el.checked : el.value;
      });
      // Substitui o form por um novo com o tipo escolhido
      const parent = formEl.parentElement;
      const newForm = document.createElement('div');
      newForm.innerHTML = renderEnvForm(current, newType, true).trim();
      const replacement = newForm.firstChild;
      parent.replaceChild(replacement, formEl);
      wireFormInsideModal(replacement);
    });
  });

  // Cancel
  formEl.querySelector('[data-env-action="form-cancel"]').addEventListener('click', () => {
    formEl.remove();
  });

  // Discover pipes (botão isolado no form Pipefy)
  const discoverBtn = formEl.querySelector('[data-env-action="discover-pipes"]');
  if(discoverBtn){
    discoverBtn.addEventListener('click', async () => {
      const statusEl = formEl.querySelector('.env-discover-status');
      const countEl = formEl.querySelector('.env-pipes-count');
      const setStatus = (msg, color) => {
        if(!statusEl) return;
        statusEl.style.display = '';
        statusEl.style.color = color || 'var(--muted)';
        statusEl.textContent = msg;
      };
      const get = k => {
        const el = formEl.querySelector(`[data-env-key="${k}"]`);
        return el ? (el.type === 'checkbox' ? el.checked : el.value) : '';
      };
      const token = get('token');
      const baseUrl = get('base_url');
      const orgId = get('org_id');
      const verifySsl = get('verify_ssl');
      if(!token || !baseUrl){ setStatus('Preencha token e URL base antes', '#d9534f'); return; }
      if(!orgId){ setStatus('Preencha o Org ID antes', '#d9534f'); return; }

      const original = discoverBtn.textContent;
      discoverBtn.disabled = true;
      discoverBtn.textContent = 'Buscando...';
      setStatus('Consultando Pipefy GraphQL...', 'var(--muted)');
      try {
        const res = await apiFetch('/api/discover-pipes', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({
            token: token, base_url: baseUrl, org_id: orgId, verify_ssl: !!verifySsl,
          }),
        });
        const body = await res.json().catch(() => ({}));
        if(!res.ok){
          setStatus('Erro: ' + (body.error || ('HTTP ' + res.status)), '#d9534f');
          return;
        }
        // Salva os pipes encontrados num data attr no form pra serem persistidos no save
        formEl.dataset.discoveredPipes = JSON.stringify(body.pipes || []);
        if(countEl) countEl.textContent = (body.count || 0) + ' encontrado' + (body.count === 1 ? '' : 's');
        setStatus(`OK: ${body.count} pipe(s) na org ${body.org_name || orgId}. Clique Salvar pra aplicar.`, '#6fd17a');
      } catch(err){
        setStatus('Falha de rede: ' + err.message, '#d9534f');
      } finally {
        discoverBtn.disabled = false;
        discoverBtn.textContent = original;
      }
    });
  }

  // Save
  formEl.querySelector('[data-env-action="form-save"]').addEventListener('click', async () => {
    const type = formEl.dataset.envType;
    const isNew = formEl.dataset.isNew === '1';
    const originalId = formEl.dataset.envOriginalId;
    const env = {};
    formEl.querySelectorAll('[data-env-key]').forEach(el => {
      const k = el.dataset.envKey;
      if(el.type === 'checkbox') env[k] = el.checked;
      else env[k] = el.value;
    });

    // Validações mínimas
    if(!env.id || !env.name || !env.base_url || !env.token){
      alert('Preencha ao menos: ID, Nome, URL base e Token.');
      return;
    }
    if(!/^[a-z0-9_-]+$/i.test(env.id)){
      alert('ID deve conter apenas letras, números, _ ou -.');
      return;
    }

    // Preserva pipes existentes se for edit de Pipefy (busca do vault não-sanitizado)
    if(!isNew && type === 'pipefy' && window.V2Utils){
      const existing = window.V2Utils.vaultGet(originalId);
      if(existing && existing.pipes) env.pipes = existing.pipes;
    }
    // Se o user clicou Buscar pipes, sobrescreve com os recém-descobertos
    if(type === 'pipefy' && formEl.dataset.discoveredPipes){
      try { env.pipes = JSON.parse(formEl.dataset.discoveredPipes); } catch(_) {}
    }

    const saveBtn = formEl.querySelector('[data-env-action="form-save"]');
    const originalLabel = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Salvando...';
    saveBtn.style.opacity = '.6';

    try {
      // Salva no vault local. type='pipefy'|'ipaas'.
      const remember = env._remember !== false;
      const toSave = Object.assign({ type: type, remember: remember }, env);
      delete toSave._remember;
      if(window.V2Utils){
        window.V2Utils.vaultSave(toSave);
      }
      console.log('[v2] ambiente ' + env.id + ' salvo no vault (' + (remember ? 'persistente' : 'sessao') + ')');
      await loadEnvironments();
      populateEnvModal();
      if(typeof populateIpaasEnvDropdown === 'function') populateIpaasEnvDropdown();
      populateSingleEnvDropdown();
      populatePipeDropdowns();
    } catch(e) {
      alert('Falha ao salvar: ' + e.message);
      saveBtn.disabled = false;
      saveBtn.textContent = originalLabel;
      saveBtn.style.opacity = '';
    }
  });
}

// Hook edit/add handlers após cada populateEnvModal
const _origPopulateEnvModal = populateEnvModal;
populateEnvModal = function(){
  _origPopulateEnvModal();

  // Edit buttons — fetch full env (with token) antes de abrir form
  document.querySelectorAll('.mpane [data-env-action="edit"]').forEach(btn => {
    if(btn.dataset.wiredEdit === '1') return;
    btn.dataset.wiredEdit = '1';
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const row = btn.closest('.env-row');
      const envId = row && row.dataset.envId;
      const pane = btn.closest('.mpane');
      const type = pane && pane.dataset.mpane;
      if(!envId || !type) return;
      if(row.nextElementSibling && row.nextElementSibling.classList.contains('env-edit-form')) return;

      const env = fetchFullEnv(type, envId);
      if(!env){ alert('Ambiente não encontrado no vault'); return; }
      row.insertAdjacentHTML('afterend', renderEnvForm(env, type, false));
      wireFormInsideModal(row.nextElementSibling);
    });
  });

  // Add button
  const addBtn = document.querySelector('.add-btn');
  if(addBtn && addBtn.dataset.wiredAdd !== '1'){
    addBtn.dataset.wiredAdd = '1';
    addBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();

      // Fecha qualquer dropdown aberto no app
      document.querySelectorAll('.dd-menu.open').forEach(m => {
        m.classList.remove('open');
        const ddBtn = m.parentElement && m.parentElement.querySelector('.dd-btn');
        if(ddBtn) ddBtn.classList.remove('open');
      });

      const activeTab = document.querySelector('.modal-tab.active');
      const type = activeTab ? activeTab.dataset.mtab : 'pipefy';
      const pane = document.querySelector(`.mpane[data-mpane="${type}"]`);
      if(!pane) return;

      // Garante que o pane correto está visível
      document.querySelectorAll('.mpane').forEach(p => p.classList.toggle('active', p === pane));

      // Se já tem form de novo no topo, foca nele
      let existing = pane.querySelector('.env-edit-form[data-is-new="1"]');
      if(!existing){
        pane.insertAdjacentHTML('afterbegin', renderEnvForm({}, type, true));
        existing = pane.querySelector('.env-edit-form[data-is-new="1"]');
        wireFormInsideModal(existing);
      }

      // Scroll o modal-body pra mostrar o form (ele está no topo do pane, modal-body é scrollable)
      const modalBody = document.querySelector('.modal-body');
      if(modalBody){
        modalBody.scrollTop = 0;
      }
      // Também faz scrollIntoView pra garantir em layouts diferentes
      requestAnimationFrame(() => {
        existing.scrollIntoView({ behavior: 'smooth', block: 'start' });
        // Foca o primeiro input habilitado
        setTimeout(() => {
          const firstInput = existing.querySelector('input:not([disabled]), select:not([disabled])');
          if(firstInput) firstInput.focus();
        }, 200);
      });
    });
  }
};

/* ============================================================
   ONBOARDING + BADGE "Conectado" no header
   ============================================================ */

function _activeEnvName(){
  if(!ENVS_DATA) return '';
  const list = ENVS_DATA.pipefy || [];
  if(!list.length) return '';
  const current = list.find(e => e.id === state.single.env);
  return (current && current.name) || (list[0] && list[0].name) || '';
}

function renderConnectedBadge(){
  const topRight = document.querySelector('.topbar .top-right');
  if(!topRight) return;
  let badge = document.getElementById('v2-connected-badge');
  const total = (ENVS_DATA && ENVS_DATA.pipefy ? ENVS_DATA.pipefy.length : 0)
              + (ENVS_DATA && ENVS_DATA.ipaas ? ENVS_DATA.ipaas.length : 0);
  if(!badge){
    badge = document.createElement('div');
    badge.id = 'v2-connected-badge';
    badge.style.cssText = 'display:flex;align-items:center;gap:6px;padding:5px 10px;border-radius:14px;font-size:11.5px;font-weight:500;cursor:pointer;border:1px solid var(--line-2);transition:background .12s';
    badge.title = 'Trocar ambientes';
    badge.addEventListener('click', () => {
      if(typeof openModal === 'function') openModal();
    });
    topRight.insertBefore(badge, topRight.firstChild);
  }
  if(total === 0){
    badge.style.color = 'var(--muted)';
    badge.style.background = 'rgba(255,255,255,.02)';
    badge.innerHTML = '<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--muted)"></span><span>Sem ambiente</span>';
  } else {
    const name = _activeEnvName() || 'Ambiente';
    badge.style.color = 'var(--ink-2)';
    badge.style.background = 'rgba(108,194,108,.08)';
    badge.style.borderColor = 'rgba(108,194,108,.22)';
    badge.innerHTML = '<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#6fd17a"></span><span>' + escapeHtmlInline(name) + '</span><span style="color:var(--muted);margin-left:4px">(' + total + ')</span>';
  }
}

var _onboardingShown = false;

function maybeShowOnboardingModal(){
  if(_onboardingShown) return;
  if(!ENVS_DATA) return;
  const total = (ENVS_DATA.pipefy || []).length + (ENVS_DATA.ipaas || []).length;
  if(total > 0) return;
  _onboardingShown = true;
  showOnboardingModal();
}

function showOnboardingModal(){
  if(document.getElementById('pv-onboarding')) return;
  const back = document.createElement('div');
  back.id = 'pv-onboarding';
  back.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(4px);z-index:9999;display:flex;align-items:center;justify-content:center;padding:20px';
  back.innerHTML = `
    <div style="max-width:520px;width:100%;background:var(--bg-1);border:1px solid var(--line-2);border-radius:14px;padding:28px 28px 22px;box-shadow:0 20px 60px rgba(0,0,0,.6)">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
        <div style="width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#c9a84c,#8a6f1e);display:flex;align-items:center;justify-content:center;color:#0b0f1a;font-weight:700;font-size:16px">P</div>
        <div>
          <div style="font-size:15px;font-weight:600;color:var(--ink);letter-spacing:-.01em">Configure seu primeiro ambiente</div>
          <div style="font-size:11.5px;color:var(--muted);margin-top:2px">Cole seu Bearer do Pipefy. Token fica só no seu navegador.</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px">
        <div class="field" style="margin:0;grid-column:1 / -1">
          <div class="field-lbl">NOME *</div>
          <input class="input" id="pv-on-name" type="text" placeholder="ex: meu-sandbox" value="meu-sandbox">
        </div>
        <div class="field" style="margin:0;grid-column:1 / -1">
          <div class="field-lbl">URL BASE *</div>
          <input class="input" id="pv-on-baseurl" type="text" value="https://api.pipefy.com/graphql">
        </div>
        <div class="field" style="margin:0">
          <div class="field-lbl">ORG ID</div>
          <input class="input" id="pv-on-org" type="text" placeholder="opcional">
        </div>
        <div class="field" style="margin:0">
          <div class="field-lbl">VERIFY SSL</div>
          <label style="display:inline-flex;align-items:center;gap:8px;font-size:12px;color:var(--ink-2);cursor:pointer;padding-top:5px">
            <input type="checkbox" id="pv-on-verify" style="accent-color:var(--accent);width:14px;height:14px">
            Habilitado
          </label>
        </div>
        <div class="field" style="margin:0;grid-column:1 / -1">
          <div class="field-lbl">BEARER TOKEN *</div>
          <input class="input" id="pv-on-token" type="password" placeholder="cole aqui (com ou sem prefixo Bearer)">
        </div>
      </div>
      <label style="display:flex;align-items:center;gap:10px;font-size:12px;color:var(--ink-2);cursor:pointer;margin-top:14px;padding:10px 12px;border-radius:8px;background:rgba(255,255,255,.02);border:1px solid var(--line-2)">
        <input type="checkbox" id="pv-on-remember" checked style="accent-color:var(--accent);width:14px;height:14px">
        <span>
          <b style="color:var(--ink)">Lembrar nesta máquina</b>
          <span style="display:block;font-size:11px;color:var(--muted);margin-top:2px">Marcado: localStorage. Desmarcado: só nesta sessão.</span>
        </span>
      </label>
      <div id="pv-on-err" style="display:none;font-size:11.5px;color:#d9534f;background:rgba(217,83,79,.08);border:1px solid rgba(217,83,79,.25);border-radius:6px;padding:8px 10px;margin-top:12px"></div>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:18px">
        <button id="pv-on-skip" class="ghost" style="padding:8px 16px;border-radius:6px;border:1px solid var(--line-2);background:none;color:var(--muted);font-size:12px;cursor:pointer">Pular por agora</button>
        <button id="pv-on-save" class="primary" style="padding:8px 18px;border-radius:6px;background:var(--accent);color:#0b0f1a;border:none;font-weight:600;font-size:12px;cursor:pointer">Conectar</button>
      </div>
    </div>`;
  document.body.appendChild(back);

  function err(m){
    const e = document.getElementById('pv-on-err');
    if(e){ e.textContent = m; e.style.display = ''; }
  }
  function close(){ back.remove(); }

  document.getElementById('pv-on-skip').addEventListener('click', close);
  document.getElementById('pv-on-save').addEventListener('click', () => {
    const name = document.getElementById('pv-on-name').value.trim();
    const baseUrl = document.getElementById('pv-on-baseurl').value.trim();
    const token = document.getElementById('pv-on-token').value.trim();
    const orgId = document.getElementById('pv-on-org').value.trim();
    const verify = document.getElementById('pv-on-verify').checked;
    const remember = document.getElementById('pv-on-remember').checked;
    if(!name || !baseUrl || !token){
      err('Nome, URL base e token são obrigatórios.');
      return;
    }
    if(!window.V2Utils){ err('V2Utils não disponível'); return; }
    const slug = window.V2Utils.slugify(name);
    if(!slug){ err('Nome inválido'); return; }
    window.V2Utils.vaultSave({
      id: slug,
      name: name,
      type: 'pipefy',
      base_url: baseUrl,
      org_id: orgId,
      auth_mode: 'bearer',
      verify_ssl: verify,
      token: token,
      session_cookie: 'NONE',
      csrf_token: 'NONE',
      pipes: [],
      remember: remember,
    });
    close();
    state.single.env = slug;
    loadEnvironments().then(() => {
      if(typeof populateEnvModal === 'function') populateEnvModal();
      if(typeof updatePresetInfoCard === 'function') updatePresetInfoCard();
    });
  });
}
