/* ========================================================
   MOCK STREAM — timer, progress loop, log streaming
   ======================================================== */
(function(){
  /* Page transitions + loading overlay */
  function v2InjectOverlay(){
    if(document.getElementById('v2-transition-overlay')) return;
    const o = document.createElement('div');
    o.id = 'v2-transition-overlay';
    o.innerHTML = '<div class="v2-loader"><div class="v2-loader-ring"></div><div class="v2-loader-ring inner"></div><div class="v2-loader-mark">P</div></div><div class="v2-loader-text">carregando<span class="v2-loader-dots"><span></span><span></span><span></span></span></div>';
    document.body.appendChild(o);
  }
  v2InjectOverlay();
  if(window.V2Utils && window.V2Utils.renderDashboardLink) window.V2Utils.renderDashboardLink();
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

  const pad = (n, w = 2) => String(n).padStart(w,'0');
  const fmtTime = ms => {
    const s = Math.floor(ms/1000), m = Math.floor(s/60);
    return `${pad(m)}:${pad(s%60)}.${pad(ms%1000,3)}`;
  };

  // Timer state — goes from 4231ms → 9800ms then loops back
  let elapsed = 4231;
  const startReal = performance.now() - elapsed;

  const elTimerLive = document.getElementById('timer-live');
  const elKpiTimer  = document.getElementById('kpi-timer');
  const elMetaElap  = document.getElementById('meta-elapsed');
  const elStepLive  = document.getElementById('step-live');
  const elProgFill  = document.getElementById('prog-fill');
  const elProgPct   = document.getElementById('prog-pct');
  const elKpiPct    = document.getElementById('kpi-pct');
  const elKpiPctSub = document.getElementById('kpi-pct-sub');
  const elProgCount = document.getElementById('prog-count');
  const elProgTotal = document.getElementById('prog-total');
  const elKpiSteps  = document.getElementById('kpi-steps');
  const elFootStep  = document.getElementById('footer-step');
  const elRunStatus = document.querySelector('.run-status .txt');
  const elLogCount  = document.getElementById('log-count');

  const loopStart = 4231, loopEnd = 9800;
  const phaseTotal = 35;
  let lastPct = -1, lastFaseCount = -1;

  // ETAPA 5: flag que desativa o mock quando run real é detectada
  let realRunDetected = false;
  let lastSeenLogCount = 0;
  // Interpolação: última elapsed conhecida + quando foi amostrada
  let lastPolledElapsedMs = 0;
  let lastPollAtPerf = 0;
  let smoothRafId = null;

  // Histórico de steps: cache de label + status por número de step (1-indexed),
  // pra reconstruir a lista dinamicamente baseada no total real do progress.json
  const STEP_HISTORY = {};
  let lastRenderedTotal = 0;
  let runIsFinished = false;

  /* Aplica meta da run (Run ID, pipe, flow hero, breadcrumb) a partir do sessionStorage */
  (function applyRunMeta(){
    let meta;
    try { meta = JSON.parse(sessionStorage.getItem('v2-run-meta') || 'null'); } catch(e){ meta = null; }
    if(!meta) return;

    // Breadcrumb
    const bcCurrent = document.querySelector('.crumbs .current');
    if(bcCurrent) bcCurrent.textContent = 'run_' + meta.runId + ' · em execução';
    const bcParent = document.querySelectorAll('.crumbs a');
    if(bcParent[1]){
      const parentLabel = meta.mode === 'cross' ? 'Cross Env' :
                          meta.mode === 'snapshot' ? 'Snapshot' :
                          meta.mode === 'batch' ? 'Batch' :
                          meta.mode === 'ipaas' ? 'iPaaS' : 'Single Env';
      bcParent[1].textContent = parentLabel;
    }

    // Run ID
    const runHash = document.querySelector('.runid-hash');
    if(runHash) runHash.textContent = meta.runId;
    const runSuffix = document.querySelector('.runid-suffix');
    if(runSuffix) runSuffix.textContent = meta.startedAtLabel;
    const runBlock = document.querySelector('.meta-block.runid');
    if(runBlock) runBlock.setAttribute('data-tip', meta.runIdFull + ' · ' + meta.startedAt);

    // Pipe name
    const pipeMetaValue = document.querySelector('.meta-block .meta-value.muted');
    if(pipeMetaValue && meta.pipeSrc){
      const dimSpan = pipeMetaValue.querySelector('.meta-value.dim');
      const dimText = dimSpan ? ' · ' + dimSpan.textContent.replace('· ', '') : '';
      pipeMetaValue.textContent = '';
      pipeMetaValue.appendChild(document.createTextNode(meta.pipeSrc + ' '));
      if(dimSpan){
        const newDim = document.createElement('span');
        newDim.className = 'meta-value dim';
        newDim.textContent = '· preset ' + (meta.config || '');
        pipeMetaValue.appendChild(newDim);
      }
    }

    // Flow hero env-names
    const envNames = document.querySelectorAll('.meta-flow-hero .env-name');
    if(envNames[0] && meta.envLabel) envNames[0].textContent = meta.envLabel;
    if(envNames[1] && meta.envLabel) envNames[1].textContent = meta.envLabel;
    // Se modo cross-env, origem/destino são diferentes
    if(meta.mode === 'cross' && meta.config && window.V2Utils){
      const m = window.V2Utils.parseCrossConfigMeta(meta.config);
      if(envNames[0] && m.srcEnvId) envNames[0].textContent = m.srcEnvId;
      if(envNames[1] && m.dstEnvId) envNames[1].textContent = m.dstEnvId;
    }
  })();

  function flash(el){
    el.classList.remove('flash');
    void el.offsetWidth;
    el.classList.add('flash');
  }

  function tickTimer(){
    if(realRunDetected) return;  // mock desativa quando run real detectada
    const now = performance.now();
    let e = (now - startReal);
    // loop window: 4231 .. 9800 then back to 4231
    const span = loopEnd - loopStart;
    const mod = ((e - loopStart) % span + span) % span;
    elapsed = loopStart + mod;

    const str = fmtTime(Math.floor(elapsed));
    elTimerLive.textContent = str;
    elKpiTimer.textContent  = str;
    elMetaElap.textContent  = str;

    // step-live — seconds within CT03
    const ct03 = ((elapsed - 3400) / 1000).toFixed(3);
    elStepLive.textContent = `${ct03}s`;

    // progress 42% -> 64% across the loop
    const pct = 42 + ((elapsed - loopStart) / span) * 22;
    const pctInt = Math.floor(pct);
    elProgFill.style.width = pct.toFixed(2) + '%';
    if (pctInt !== lastPct){
      elProgPct.textContent = pctInt + '%';
      elKpiPct.textContent  = pctInt + '%';
      elRunStatus.textContent = `RUNNING · ${pctInt}%`;
      flash(elKpiPct);
      lastPct = pctInt;
    }
    const elapsedSec = (elapsed/1000).toFixed(1);
    elKpiPctSub.textContent = `${elapsedSec}s / ~9.8s estimado`;

    // fases processadas: 3 → 22
    const fase = Math.min(phaseTotal, Math.max(3, Math.floor(3 + ((elapsed - loopStart) / span) * 19)));
    if (fase !== lastFaseCount){
      elProgCount.textContent = fase;
      lastFaseCount = fase;
    }

    requestAnimationFrame(tickTimer);
  }
  requestAnimationFrame(tickTimer);

  /* -------- LOG STREAM -------- */
  const log = document.getElementById('log-stream');
  const seedLogs = [
    ['09:38:12.418','INFO','Iniciando run <span class="tk">run_4f82a1cb</span> · cross-env validation'],
    ['09:38:12.420','INFO','Carregando configuração <span class="tk">validator.config.yml</span>'],
    ['09:38:12.512','INFO','Conectando em <span class="tk">fourd-sandbox</span> · API v2'],
    ['09:38:12.704','OK  ','Token OAuth válido · scope=<span class="dim">pipe:read</span>'],
    ['09:38:12.891','INFO','Conectando em <span class="tk">fourd-staging</span> · API v2'],
    ['09:38:13.043','OK  ','Token OAuth válido · scope=<span class="dim">pipe:read</span>'],
    ['09:38:13.112','INFO','CT01 · Validar estrutura do pipe'],
    ['09:38:13.215','INFO','Executando query <span class="tk">pipe_structure.graphql</span>'],
    ['09:38:13.648','INFO','Recebidos <span class="tk">14</span> phases, <span class="tk">87</span> fields (origem)'],
    ['09:38:13.821','INFO','Recebidos <span class="tk">14</span> phases, <span class="tk">89</span> fields (destino)'],
    ['09:38:14.102','WARN','Schema drift: +2 fields adicionados em destino'],
    ['09:38:14.396','OK  ','CT01 finalizado · 1.284s · 0 erros estruturais'],
    ['09:38:14.412','INFO','CT02 · Comparar fases e ordenação'],
    ['09:38:14.588','INFO','Ordenando phases por <span class="tk">created_at</span>'],
    ['09:38:14.912','INFO','Diff detectado: fase <span class="tk">Em Andamento</span> · ordenação alterada (pos 4 → 5)'],
    ['09:38:15.204','INFO','Diff detectado: fase <span class="tk">Liquidação</span> · renomeada para <span class="tk">Liquidação FX</span>'],
    ['09:38:15.841','WARN','Fase <span class="tk">Aprovação Credito</span> existe em origem mas não em destino'],
    ['09:38:16.221','INFO','Resolvendo field IDs para labels humanas'],
    ['09:38:16.528','OK  ','CT02 finalizado · 2.116s · 3 divergências'],
    ['09:38:16.534','INFO','CT03 · Comparar campos (labels, tipos, obrigatoriedade)'],
    ['09:38:16.612','INFO','Carregando <span class="tk">field_specs.graphql</span>'],
    ['09:38:16.889','INFO','Comparando fase <span class="tk">Início</span> · 12 fields'],
    ['09:38:17.102','INFO','Comparando fase <span class="tk">Triagem</span> · 8 fields'],
    ['09:38:17.254','WARN','Field <span class="tk">canal_confirmacao</span> · opção <span class="dim">"SMS"</span> adicionada em destino'],
    ['09:38:17.388','INFO','Comparando fase <span class="tk">Análise de Risco</span> · 15 fields'],
    ['09:38:17.601','ERR ','Field <span class="tk">cnpj_contraparte</span> · tipo divergente: <span class="dim">short_text</span> (origem) vs <span class="dim">cnpj</span> (destino)'],
    ['09:38:17.712','INFO','Comparando fase <span class="tk">Em Andamento</span> · 18 fields'],
    ['09:38:17.895','INFO','Field <span class="tk">taxa_spread</span> · obrigatoriedade alterada (false → true)'],
    ['09:38:18.042','INFO','Comparando fase <span class="tk">Aprovação</span> · 9 fields'],
    ['09:38:18.214','INFO','Field <span class="tk">aprovador_secundario</span> · label alterada'],
    ['09:38:18.398','INFO','Comparando fase <span class="tk">Registro B3</span> · 11 fields'],
    ['09:38:18.512','INFO','Diff detectado: <span class="tk">numero_contrato_b3</span> · padrão regex alterado'],
    ['09:38:18.689','INFO','Batch 1/3 processado · 73 fields comparados'],
    ['09:38:18.801','INFO','Carregando batch 2/3 · start token <span class="tk">eyJwaGFzZSI6N30=</span>'],
    ['09:38:18.924','INFO','Comparando fase <span class="tk">Liquidação FX</span> · 16 fields'],
    ['09:38:19.043','INFO','Field <span class="tk">conta_corrente_destino</span> · validação adicional'],
    ['09:38:19.162','INFO','Field <span class="tk">canal_confirmacao</span> adicionou 1 opção (<span class="dim">"SMS"</span>)'],
    ['09:38:19.284','INFO','Comparando fase <span class="tk">Pós-Liquidação</span> · 7 fields'],
    ['09:38:19.412','INFO','Processando automations do batch · <span class="tk">auto_liq_notif_1923</span>'],
    ['09:38:19.528','INFO','Progresso CT03 · <span class="tk">3 / 35</span> fases processadas'],
    ['09:38:19.612','INFO','Checkpoint salvo em <span class="tk">.checkpoints/run_4f82a1cb_ct03.json</span>'],
    ['09:38:19.801','INFO','Aguardando resposta API destino · <span class="tk">field_specs.graphql</span>'],
  ];

  // render seed
  seedLogs.forEach(l => log.appendChild(makeLine(l[0], l[1], l[2])));
  // add cursor placeholder at end
  const cursorLine = document.createElement('div');
  cursorLine.className = 'logline info';
  cursorLine.innerHTML = `<span class="ts">09:38:19.812</span><span class="lv">INFO</span><span class="msg"><span class="cursor"></span></span>`;
  log.appendChild(cursorLine);
  log.scrollTop = log.scrollHeight;

  function makeLine(ts, lv, msg){
    const div = document.createElement('div');
    const cls = lv.trim().toLowerCase();
    div.className = 'logline ' + (cls === 'ok' ? 'ok' : cls === 'warn' ? 'warn' : cls === 'err' ? 'err' : 'info');
    div.innerHTML = `<span class="ts">${ts}</span><span class="lv">${lv}</span><span class="msg">${msg}</span>`;
    return div;
  }

  // streaming new lines every ~400ms
  const streamLines = [
    ['INFO','Comparando fase <span class="tk">Cancelamento</span> · 5 fields'],
    ['INFO','Field <span class="tk">motivo_cancelamento</span> · opção adicionada'],
    ['INFO','Batch 2/3 processado · 68 fields comparados'],
    ['INFO','Carregando batch 3/3 · start token <span class="tk">eyJwaGFzZSI6MTB9</span>'],
    ['INFO','Comparando fase <span class="tk">Retomada</span> · 6 fields'],
    ['WARN','Field <span class="tk">data_retomada</span> · formato de data alterado (<span class="dim">ISO8601 → BRT</span>)'],
    ['INFO','Comparando fase <span class="tk">Encerramento</span> · 4 fields'],
    ['INFO','Todos os 35 fields do batch 3 carregados'],
    ['INFO','Normalizando labels para comparação case-insensitive'],
    ['OK  ','Subtask · label diff map construído · 217 entries'],
    ['INFO','Preparando próximo step · CT04 <span class="tk">compare_automations.robot</span>'],
  ];
  let streamIdx = 0;
  let lineCount = seedLogs.length;
  // Mantemos o handle pra poder clearInterval quando a run real for detectada
  // (pollStatus seta realRunDetected=true) ou quando a tela for descarregada.
  // Antes ficava rodando infinitamente, queimando CPU mesmo apos early-return.
  const mockStreamHandle = setInterval(() => {
    if(realRunDetected){
      clearInterval(mockStreamHandle);
      return;
    }
    if (log.children.length > 80){
      // trim oldest
      for (let i = 0; i < 20; i++) log.removeChild(log.firstChild);
    }
    const item = streamLines[streamIdx % streamLines.length];
    streamIdx++;
    const nowMs = Math.floor(elapsed);
    const ts = `09:38:${pad(19 + Math.floor(nowMs/1000 - 4))}.${pad(nowMs%1000,3)}`;
    const line = makeLine(ts, item[0], item[1]);
    // insert before cursor line
    log.insertBefore(line, cursorLine);
    lineCount++;
    elLogCount.textContent = lineCount;
    log.scrollTop = log.scrollHeight;
  }, 420);
  window.addEventListener('beforeunload', () => clearInterval(mockStreamHandle), { once: true });

  /* -------- CANCEL POPOVER -------- */
  const btnCancel = document.getElementById('btn-cancel');
  const pop = document.getElementById('cancel-pop');
  const noBtn = document.getElementById('cancel-no');
  const yesBtn = document.getElementById('cancel-yes');

  btnCancel.addEventListener('click', (e) => {
    e.stopPropagation();
    pop.classList.toggle('open');
  });
  noBtn.addEventListener('click', (e) => { e.stopPropagation(); pop.classList.remove('open'); });
  yesBtn.addEventListener('click', async (e) => {
    e.stopPropagation();
    pop.classList.remove('open');
    // Cancel real: chama o backend pra matar o subprocess do Robot.
    // AbortSignal.timeout evita travar a UI se o backend nao responder; o
    // usuario ainda pode navegar via redirect no catch.
    try {
      const cancelOpts = { method: 'POST' };
      try { cancelOpts.signal = AbortSignal.timeout(8000); } catch(_){ /* browsers antigos */ }
      const res = await (window.V2Utils ? window.V2Utils.apiFetch : fetch)('/api/run/cancel', cancelOpts);
      const body = await res.json().catch(() => ({}));
      console.log('[v2] cancel:', res.status, body);
      if(res.ok){
        // Dá um instante pro polling capturar o estado finished+cancelled antes de navegar
        setTimeout(() => {
          try { navigateTo(getConfigUrl()); } catch(_){ navigateTo('/v2/configuracao'); }
        }, 400);
      } else {
        alert('Não foi possível cancelar: ' + (body.error || 'HTTP ' + res.status));
      }
    } catch(err){
      console.warn('[v2] cancel falhou, voltando pra config:', err.message);
      try { navigateTo(getConfigUrl()); } catch(_){ navigateTo('/v2/configuracao'); }
    }
  });
  document.addEventListener('click', (e) => {
    if (!pop.contains(e.target) && e.target !== btnCancel) pop.classList.remove('open');
  });

  /* -------- Chip filters (visual only) -------- */
  document.querySelectorAll('.logpane .chip').forEach(c => {
    c.addEventListener('click', () => {
      document.querySelectorAll('.logpane .chip').forEach(x => x.classList.remove('active'));
      c.classList.add('active');
      const f = c.dataset.filter;
      log.querySelectorAll('.logline').forEach(l => {
        if (f === 'all' || !f) l.style.display = '';
        else l.style.display = l.classList.contains(f) ? '' : 'none';
      });
    });
  });

  /* ============================================================
     ETAPA 5: POLLING /api/status — run real substitui o mock
     ============================================================ */

  // Contador de falhas consecutivas pra backoff exponencial + cap.
  // Antes pollStatus se auto-agendava forever em erro de rede sem backoff
  // (sempre 500ms) nem limite, mantendo a tela viva ate o backend voltar.
  let _pollFailures = 0;
  const _POLL_BASE_MS = 500;
  const _POLL_MAX_MS = 10000;
  const _POLL_FAIL_CAP = 20;
  let _pollStopped = false;

  async function pollStatus(){
    if(_pollStopped) return;
    try {
      const res = await (window.V2Utils ? window.V2Utils.apiFetch : fetch)('/api/status');
      if(!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      _pollFailures = 0;  // sucesso reseta o backoff

      const hasRun = data.running || data.elapsed != null || data.finished;

      if(hasRun && !realRunDetected){
        realRunDetected = true;
        console.log('[v2] run real detectada, desativando mock');
        log.innerHTML = '';
        const cursorEl = document.createElement('div');
        cursorEl.className = 'logline info';
        cursorEl.id = 'cursor-live';
        cursorEl.innerHTML = '<span class="ts">--:--:--.---</span><span class="lv">INFO</span><span class="msg"><span class="cursor"></span></span>';
        log.appendChild(cursorEl);
        lastSeenLogCount = 0;

        // Limpa lista de steps mock (CT01-CT07 hardcoded). renderStepsList vai recriar
        // dinamicamente baseado no total real do progress.json.
        const stepsListEl = document.getElementById('steps-list');
        if(stepsListEl) stepsListEl.innerHTML = '<div style="padding:20px;color:var(--muted);font-size:12px;text-align:center">Aguardando primeiro step…</div>';
        lastRenderedTotal = 0;
        if(elKpiSteps) elKpiSteps.innerHTML = '0<span style="font-size:14px;color:var(--muted);margin-left:4px">/ —</span>';

        // Se o backend retornou run_id real, atualiza o hash do Run ID
        // (substitui o gerado client-side pelo sessionStorage)
        if(data.run_id){
          const runHash = document.querySelector('.runid-hash');
          if(runHash) runHash.textContent = data.run_id;
          const bcCurrent = document.querySelector('.crumbs .current');
          if(bcCurrent) bcCurrent.textContent = 'run_' + data.run_id + ' · em execução';
        }
      }

      if(hasRun) applyRealStatus(data);

      if(data.finished){
        console.log('[v2] run finalizada, exit_code=' + data.exit_code + ' · elapsed_final=' + data.elapsed_final);
        runIsFinished = true;
        if(smoothRafId){ cancelAnimationFrame(smoothRafId); smoothRafId = null; }

        // Congela timer no valor final vindo do backend (mais preciso que interpolação)
        if(data.elapsed_final != null){
          const finalMs = Math.floor(data.elapsed_final * 1000);
          const str = fmtTime(finalMs);
          if(elTimerLive) elTimerLive.textContent = str;
          if(elKpiTimer)  elKpiTimer.textContent  = str;
          if(elMetaElap)  elMetaElap.textContent  = str;
          // Atualiza sessionStorage pra Resultados usar
          try {
            const meta = JSON.parse(sessionStorage.getItem('v2-run-meta') || '{}');
            meta.elapsedFinal = data.elapsed_final;
            meta.elapsedFinalLabel = str;
            sessionStorage.setItem('v2-run-meta', JSON.stringify(meta));
          } catch(e){}
        }

        const success = data.exit_code === 0;
        elRunStatus.textContent = success ? 'DONE · 100%' : 'FAILED · exit=' + data.exit_code;
        setTimeout(() => { navigateTo('/v2/resultados'); }, 2200);
        return;
      }
    } catch(e) {
      _pollFailures++;
      console.warn('[v2] poll falhou (' + _pollFailures + '/' + _POLL_FAIL_CAP + '):', e.message);
      if(_pollFailures >= _POLL_FAIL_CAP){
        _pollStopped = true;
        console.error('[v2] poll desistiu apos ' + _POLL_FAIL_CAP + ' falhas consecutivas');
        if(elRunStatus) elRunStatus.textContent = 'CONEXAO PERDIDA';
        return;
      }
    }
    // Backoff exponencial em erro: 500ms, 1s, 2s, 4s, ate _POLL_MAX_MS.
    // Em sucesso (_pollFailures=0), volta ao baseline de 500ms.
    const delay = Math.min(_POLL_BASE_MS * Math.pow(2, _pollFailures), _POLL_MAX_MS);
    setTimeout(pollStatus, delay);
  }
  window.addEventListener('beforeunload', () => { _pollStopped = true; }, { once: true });

  /* Renderiza a lista de steps na sidebar esquerda baseada no progress.json.
     Reconstroi os N slots (total) com status done/running/pending. */
  function renderStepsList(currentStep, total, currentLabel){
    const listEl = document.getElementById('steps-list');
    if(!listEl) return;

    // Só re-renderiza estrutura completa se o total mudou (evita flicker)
    const structureChanged = total !== lastRenderedTotal;
    if(structureChanged){
      const slots = [];
      for(let i = 1; i <= total; i++){
        slots.push(buildStepNode(i, total));
      }
      listEl.innerHTML = '';
      slots.forEach(node => listEl.appendChild(node));
      lastRenderedTotal = total;
    }

    // Atualiza estado de cada slot (done/running/pending) e label
    for(let i = 1; i <= total; i++){
      const row = listEl.querySelector('[data-step="' + i + '"]');
      if(!row) continue;
      let status, label;
      if(i < currentStep){
        status = 'done';
        label = (STEP_HISTORY[i] && STEP_HISTORY[i].label) || 'Concluído';
      } else if(i === currentStep){
        status = (currentLabel && /done|conclu|salvo|ok/i.test(currentLabel)) ? 'done' : 'running';
        label = currentLabel || (STEP_HISTORY[i] && STEP_HISTORY[i].label) || 'Em execução';
      } else {
        status = 'pending';
        label = 'Aguardando';
      }
      row.classList.remove('done', 'running', 'pending');
      row.classList.add(status);
      const ind = row.querySelector('.step-ind');
      if(ind) ind.innerHTML = stepIndicatorSvg(status);
      const nameEl = row.querySelector('.step-name');
      if(nameEl){
        nameEl.textContent = label.length > 60 ? label.slice(0, 57) + '...' : label;
        nameEl.title = label;
      }
      const timeEl = row.querySelector('.step-time');
      if(timeEl){
        if(status === 'done') timeEl.textContent = '✓';
        else if(status === 'running') timeEl.textContent = '...';
        else timeEl.textContent = '—';
      }
    }
  }

  function buildStepNode(idx, total){
    const div = document.createElement('div');
    div.className = 'step pending';
    div.dataset.step = String(idx);
    div.innerHTML = ''
      + '<div class="step-ind">' + stepIndicatorSvg('pending') + '</div>'
      + '<div class="step-body">'
      +   '<span class="step-code">' + String(idx) + '/' + String(total) + '</span>'
      +   '<span class="step-name">Aguardando</span>'
      + '</div>'
      + '<span class="step-time">—</span>';
    return div;
  }

  function stepIndicatorSvg(status){
    if(status === 'done'){
      return '<svg class="ind-done" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M7.5 12.5l3 3 6-6.5"/></svg>';
    }
    if(status === 'running'){
      return '<svg class="ind-running" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path class="arc" d="M12 3 a9 9 0 0 1 6.36 2.64" fill="none"/></svg>';
    }
    return '<svg class="ind-pending" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/></svg>';
  }

  function tickSmoothTimer(){
    if(runIsFinished){ smoothRafId = null; return; }
    const now = performance.now();
    const extrapolated = lastPolledElapsedMs + (now - lastPollAtPerf);
    const str = fmtTime(Math.floor(extrapolated));
    if(elTimerLive) elTimerLive.textContent = str;
    if(elKpiTimer)  elKpiTimer.textContent  = str;
    if(elMetaElap)  elMetaElap.textContent  = str;

    // Cursor do log: timestamp vivo pra mostrar que stream tá ativo
    const cursorTs = document.querySelector('#cursor-live .ts');
    if(cursorTs){
      const d = new Date();
      const hh = String(d.getHours()).padStart(2, '0');
      const mm = String(d.getMinutes()).padStart(2, '0');
      const ss = String(d.getSeconds()).padStart(2, '0');
      const ms = String(d.getMilliseconds()).padStart(3, '0');
      cursorTs.textContent = hh + ':' + mm + ':' + ss + '.' + ms;
      cursorTs.style.color = 'var(--accent)';
    }

    smoothRafId = requestAnimationFrame(tickSmoothTimer);
  }

  function applyRealStatus(data){
    const elapsedMs = Math.floor((data.elapsed || 0) * 1000);

    // Sincroniza base pra interpolação RAF
    lastPolledElapsedMs = elapsedMs;
    lastPollAtPerf = performance.now();

    // Atualiza imediatamente (será refinado pelo RAF entre polls)
    const str = fmtTime(elapsedMs);
    elTimerLive.textContent = str;
    elKpiTimer.textContent  = str;
    elMetaElap.textContent  = str;

    // Dispara o loop de interpolação se ainda não rodando e run ativa
    if(!runIsFinished && !smoothRafId){
      smoothRafId = requestAnimationFrame(tickSmoothTimer);
    }

    const prog = data.progress || {};
    // Estrutura real do progress.json: {step, total, label, status}
    // Aliases tolerantes caso backend mude: prog.current ou prog.step
    const step = Number.isFinite(prog.step) ? prog.step
              : Number.isFinite(prog.current) ? prog.current : 0;
    const total = Number.isFinite(prog.total) ? prog.total : 0;

    if(total > 0){
      const pct = Math.max(0, Math.min(100, Math.floor((step / total) * 100)));
      elProgFill.style.width = pct + '%';
      const cur = parseInt(String(elProgPct.textContent).replace('%',''), 10);
      if(cur !== pct){
        elProgPct.textContent = pct + '%';
        elKpiPct.textContent  = pct + '%';
        elRunStatus.textContent = (data.finished ? 'DONE · ' : 'RUNNING · ') + pct + '%';
        flash(elKpiPct);
      }
      // Atualiza contadores de fases no centro (prog-count de step, prog-total)
      const pc = document.getElementById('prog-count');
      const pt = document.getElementById('prog-total');
      if(pc) pc.textContent = step;
      if(pt) pt.textContent = total;
      // Atualiza KPI de steps "X / 7"
      if(elKpiSteps){
        elKpiSteps.innerHTML = step + '<span style="font-size:14px;color:var(--muted);margin-left:4px">/ ' + total + '</span>';
      }
      if(elFootStep) elFootStep.textContent = step;
      // KPI sub: tempo decorrido real
      if(elKpiPctSub){
        const secs = (elapsedMs / 1000).toFixed(1);
        elKpiPctSub.textContent = secs + 's · step ' + step + '/' + total;
      }
    }

    // Label atual do progresso (ex "Extraindo automações Destino...")
    if(prog.label){
      const codeEl = document.getElementById('prog-code');
      if(codeEl) codeEl.textContent = prog.label.length > 50 ? prog.label.slice(0, 47) + '...' : prog.label;
    }

    // Atualiza lista dinâmica de steps (substitui mock CT01-CT07 hardcoded)
    if(total > 0){
      // Atualiza histórico do step atual
      if(step > 0){
        const stepStatus = (prog.status === 'done') ? 'done' : 'running';
        STEP_HISTORY[step] = { label: prog.label || ('Step ' + step), status: stepStatus };
      }
      renderStepsList(step, total, prog.label || '');
    }

    const logs = data.logs || [];
    if(logs.length > lastSeenLogCount){
      const cursorEl = document.getElementById('cursor-live');
      const newLogs = logs.slice(lastSeenLogCount);
      newLogs.forEach(line => {
        const div = renderRealLogLine(line);
        if(cursorEl && cursorEl.parentNode) log.insertBefore(div, cursorEl);
        else log.appendChild(div);
      });
      lastSeenLogCount = logs.length;
      if(elLogCount) elLogCount.textContent = logs.length;
      log.scrollTop = log.scrollHeight;
    }
  }

  function renderRealLogLine(line){
    let ts = '', lvl = 'INFO', msg = line;
    const m1 = line.match(/^(\d{2}:\d{2}:\d{2}\.\d+)\s+(INFO|WARN|ERROR|ERR|OK|DEBUG|PASS|FAIL|TRACE)\s+(.*)$/i);
    if(m1){ ts = m1[1]; lvl = m1[2].toUpperCase(); msg = m1[3]; }
    else {
      const m2 = line.match(/^(INFO|WARN|ERROR|ERR|OK|DEBUG|PASS|FAIL|TRACE):?\s+(.*)$/i);
      if(m2){ lvl = m2[1].toUpperCase(); msg = m2[2]; }
    }
    const cls = (lvl === 'ERROR' || lvl === 'ERR' || lvl === 'FAIL') ? 'err'
              : (lvl === 'WARN') ? 'warn'
              : (lvl === 'OK' || lvl === 'PASS') ? 'ok' : 'info';
    const lvlDisplay = lvl === 'ERROR' ? 'ERR ' : (lvl.length === 3 ? lvl + ' ' : lvl.slice(0, 4));
    const escape = s => String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
    const div = document.createElement('div');
    div.className = 'logline ' + cls;
    div.innerHTML = '<span class="ts">' + escape(ts) + '</span>'
                  + '<span class="lv">' + escape(lvlDisplay) + '</span>'
                  + '<span class="msg">' + escape(msg) + '</span>';
    return div;
  }

  pollStatus();

  /* URL de configuração preservando mode/sub do run em curso */
  function getConfigUrl(opts){
    opts = opts || {};
    let meta;
    try { meta = JSON.parse(sessionStorage.getItem('v2-run-meta') || 'null'); } catch(e){ meta = null; }
    if(!meta || !meta.mode) return '/v2/configuracao';
    if(opts.level === 'root') return '/v2/configuracao';
    const params = new URLSearchParams();
    params.set('mode', meta.mode);
    if(meta.mode === 'snapshot' && meta.snapshotSub) params.set('sub', meta.snapshotSub);
    if(meta.config) params.set('config', meta.config);
    return '/v2/configuracao?' + params.toString();
  }

  /* Wire topbar: breadcrumbs e icon-btns levam à Configuração preservando o modo */
  const crumbAnchors = document.querySelectorAll('.crumbs a');
  crumbAnchors.forEach((a, idx) => {
    const isRoot = idx === 0;
    a.addEventListener('click', (e) => { e.preventDefault(); navigateTo(getConfigUrl({ level: isRoot ? 'root' : 'mode' })); });
  });
  document.querySelectorAll('.topbar .top-right .icon-btn').forEach(btn => {
    btn.addEventListener('click', () => { navigateTo(getConfigUrl()); });
  });

})();
