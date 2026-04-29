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

    const segs = document.querySelectorAll('.stacked-seg');
    const pop = document.getElementById('stacked-pop');
    const bar = document.getElementById('stacked-bar');
    const barsEl = document.getElementById('pop-bars');
    const swatch = document.getElementById('pop-swatch');
    const totalCount = 93;

    function update(seg){
      const d = seg.dataset;
      const color = getComputedStyle(seg).backgroundColor;
      const count = parseInt(d.count,10);
      const err = parseInt(d.err,10), warn = parseInt(d.warn,10), info = parseInt(d.info,10);

      swatch.textContent = d.cat;
      swatch.style.background = color;
      document.getElementById('pop-cat').textContent = d.name;
      document.getElementById('pop-sub').innerHTML = 'tag · ' + d.cat + ' · ' + d.count + ' divergência' + (count>1?'s':'');
      document.getElementById('pop-num').textContent = d.count;
      document.getElementById('pop-pct').textContent = d.pct + '% do total';
      document.getElementById('pop-axis').textContent = '0 → ' + d.count;
      document.getElementById('pop-v-err').textContent = err;
      document.getElementById('pop-v-warn').textContent = warn;
      document.getElementById('pop-v-info').textContent = info;
      const tot = Math.max(1, err+warn+info);
      document.getElementById('pop-bar-err').style.setProperty('--w',(err/tot*100).toFixed(0)+'%');
      document.getElementById('pop-bar-warn').style.setProperty('--w',(warn/tot*100).toFixed(0)+'%');
      document.getElementById('pop-bar-info').style.setProperty('--w',(info/tot*100).toFixed(0)+'%');

      const trend = d.trend.split(',').map(Number);
      const mx = Math.max(...trend,1);
      barsEl.innerHTML = trend.map((v,i)=>{
        const h = (v/mx*100).toFixed(0);
        const cur = i===trend.length-1 ? 'current' : '';
        return '<div class="pop-bar '+cur+'" style="height:'+h+'%;color:'+color+'"></div>';
      }).join('');

      pop.style.color = color;

      // position: center above segment, clamped to viewport
      const segRect = seg.getBoundingClientRect();
      const barRect = bar.getBoundingClientRect();
      let cx = (segRect.left + segRect.right)/2 - barRect.left + 20; // account for .stacked padding 20px? no, offsetParent is .stacked
      // pop is inside .stacked which has padding 0 20px; getBoundingClientRect gives us what we want via offset against .stacked
      const stackedRect = document.getElementById('stacked-section').getBoundingClientRect();
      cx = (segRect.left + segRect.right)/2 - stackedRect.left;
      const w = 340, half = w/2;
      const minL = 12, maxL = stackedRect.width - 12;
      if (cx - half < minL) cx = minL + half;
      if (cx + half > maxL) cx = maxL - half;
      pop.style.left = cx + 'px';
    }

    segs.forEach(seg => {
      seg.addEventListener('mouseenter', () => update(seg));
    });

    /* ============================================================
       ETAPA 6: FETCH /api/results — substitui mock pelos dados reais
       ============================================================ */

    function categorizeDivergence(s){
      const m = s.match(/^\[([^\]]+)\]/);
      if(!m) return { cat: 'FA', name: 'Fases & Campos' };
      const tipo = m[1].toUpperCase();
      if(tipo.includes('START') && tipo.includes('FORM')) return { cat: 'SF', name: 'Start Form' };
      if(tipo.startsWith('LABEL') || tipo === 'LB') return { cat: 'LB', name: 'Labels' };
      if(tipo.startsWith('AUTOMACAO')){
        if(tipo.includes('FASE')) return { cat: 'AD', name: 'Automação · Fase Destino' };
        if(tipo.includes('HTTP') || tipo.includes('URL')) return { cat: 'AH', name: 'Automação · HTTP' };
        if(tipo.includes('CONDITION')) return { cat: 'AC', name: 'Automação · Condition' };
        return { cat: 'AS', name: 'Automação · Status' };
      }
      return { cat: 'FA', name: 'Fases & Campos' };
    }

    function severityOf(s){
      // Info: mudanças cosméticas que não afetam comportamento
      if(/\bcor\b|help_text|ordem\b|\s+color\s*=|ICONE|ICON/i.test(s)) return 'info';
      // Warn: mudanças aditivas ou reversíveis
      if(/CAMPO\s+EXTRA|AUTOMACAO\s+ADICIONAD|OPCAO\s+ADIC|OPCOES\s+ADIC|LABEL\s+(ADICION|EXTRA|NOVA|RENOMEAD)|FASE\s+EXTRA|FASE\s+RENOMEAD|LABEL\s+REMOVID/i.test(s)) return 'warn';
      // Err: mudanças que quebram ou têm impacto estrutural
      if(/AUSENTE|DIFERENTE|REMOVID|STATUS|FASE_DESTINO|CONDITION|TRIGGER|HTTP|URL|ACTION|EVENT\b|REQUIRED|TIPO\s+CAMPO/i.test(s)) return 'err';
      return 'info';
    }

    const CAT_META = [
      { key: 'FA', name: 'Fases & Campos',           color: '#e06565' },
      { key: 'AD', name: 'Auto · Fase Destino',      color: '#a68cd9' },
      { key: 'AS', name: 'Auto · Status',            color: '#d98a5c' },
      { key: 'AH', name: 'Auto · HTTP',              color: '#6cc26c' },
      { key: 'AC', name: 'Auto · Condition',         color: '#d97ca8' },
      { key: 'LB', name: 'Labels',                   color: '#6ca9d9' },
      { key: 'SF', name: 'Start Form',               color: '#d4a84b' },
    ];

    function renderSidebarDonut(byCat, total){
      const sidebar = document.querySelector('.pane-left');
      if(!sidebar) return;

      // Remove donut anterior se existir (re-render)
      const existingWrap = document.getElementById('sidebar-donut-wrap');
      if(existingWrap) existingWrap.remove();
      // Também remove a section antiga (caso ainda exista de builds anteriores)
      const existingSection = document.getElementById('sidebar-donut-section');
      if(existingSection) existingSection.remove();

      if(total === 0) return;

      // Encontra a seção "Categoria" pra injetar o donut dentro dela
      const categoriaSection = Array.from(document.querySelectorAll('.filter-section')).find(s => {
        const t = s.querySelector('.filter-title');
        return t && t.textContent.trim() === 'Categoria';
      });
      if(!categoriaSection) return;

      // Ordena categorias por count, filtra as com > 0
      const segments = CAT_META
        .map(m => ({ ...m, count: byCat[m.key] || 0 }))
        .filter(s => s.count > 0)
        .sort((a, b) => b.count - a.count);

      const R = 52;
      const CIRC = 2 * Math.PI * R;
      let offset = 0;
      const svgSegs = segments.map(s => {
        const len = (s.count / total) * CIRC;
        const gap = CIRC - len;
        const thisOffset = offset;
        offset += len;
        return `<circle cx="68" cy="68" r="${R}" fill="none" stroke="${s.color}" stroke-width="12" stroke-dasharray="${len.toFixed(2)} ${gap.toFixed(2)}" stroke-dashoffset="${(-thisOffset).toFixed(2)}" transform="rotate(-90 68 68)" class="donut-seg" data-cat="${s.key}" style="cursor:pointer;transition:stroke-width .18s,opacity .18s"><title>${s.name}: ${s.count}</title></circle>`;
      }).join('');

      const wrap = document.createElement('div');
      wrap.id = 'sidebar-donut-wrap';
      wrap.style.cssText = 'display:flex;justify-content:center;padding:6px 0 14px;margin-bottom:4px';
      wrap.innerHTML = `
        <svg width="136" height="136" viewBox="0 0 136 136">
          <circle cx="68" cy="68" r="${R}" fill="none" stroke="rgba(255,255,255,.04)" stroke-width="12"/>
          ${svgSegs}
          <text x="68" y="66" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="22" font-weight="500" fill="var(--ink)" style="letter-spacing:-.02em">${total}</text>
          <text x="68" y="83" text-anchor="middle" font-family="DM Sans, sans-serif" font-size="9" fill="var(--muted)" style="letter-spacing:.06em;text-transform:uppercase">divergências</text>
        </svg>
      `;

      // Insere DENTRO da Categoria, logo depois do .filter-head (antes da lista de facets)
      const filterHead = categoriaSection.querySelector('.filter-head');
      if(filterHead) filterHead.insertAdjacentElement('afterend', wrap);
      else categoriaSection.insertBefore(wrap, categoriaSection.firstChild);

      const section = wrap; // pra compatibilidade com o código abaixo que referencia "section"

      // Anima entrada: stroke-dashoffset animated
      requestAnimationFrame(() => {
        section.querySelectorAll('.donut-seg').forEach((seg, i) => {
          const finalOffset = seg.getAttribute('stroke-dashoffset');
          seg.setAttribute('stroke-dashoffset', (-CIRC).toFixed(2));
          seg.style.transition = 'stroke-dashoffset .7s cubic-bezier(.4,0,.2,1) ' + (i * 60) + 'ms, stroke-width .18s, opacity .18s';
          requestAnimationFrame(() => seg.setAttribute('stroke-dashoffset', finalOffset));
        });
      });

      // Hover: engrossa o segmento, mantém demais normais
      section.querySelectorAll('.donut-seg').forEach(seg => {
        const cat = seg.dataset.cat;
        seg.addEventListener('mouseenter', () => {
          seg.setAttribute('stroke-width', '16');
        });
        seg.addEventListener('mouseleave', () => {
          seg.setAttribute('stroke-width', '12');
        });
        // Click: filtra lista pela categoria (mesmo comportamento do stacked bar)
        seg.addEventListener('click', () => {
          const wasOnly = activeFilters.cats.size === 1 && activeFilters.cats.has(cat);
          activeFilters.cats.clear();
          if(!wasOnly) activeFilters.cats.add(cat);
          else ['SF','FA','LB','AS','AD','AH','AC'].forEach(c => activeFilters.cats.add(c));
          document.querySelectorAll('.filter-section .facet').forEach(f => {
            const nameEl = f.querySelector('.name');
            if(!nameEl) return;
            const catMap = {
              'Start Form':'SF','Fases & Campos':'FA','Labels':'LB',
              'Automação · Status':'AS','Automação · Fase Destino':'AD',
              'Automação · HTTP':'AH','Automação · Condition':'AC',
            };
            const facetCat = catMap[nameEl.textContent.trim()];
            if(facetCat) f.classList.toggle('active', activeFilters.cats.has(facetCat));
          });
          applyFilters();
        });
      });
    }

    function extractFase(s){
      // "] Start Form > ..."
      if(/\]\s*Start\s+Form\b/i.test(s)) return 'Start Form';
      // "] Fase "X" > ..."
      const m = s.match(/Fase\s+"([^"]+)"/i);
      if(m) return m[1];
      return null;
    }

    function parseDivergence(s, idx){
      const cat = categorizeDivergence(s);
      const sev = severityOf(s);
      const m = s.match(/^\[([^\]]+)\]\s*(.*)$/);
      const tipo = m ? m[1] : 'DIFF';
      const rest = m ? m[2] : s;
      const pathMatch = rest.match(/^(.+?):\s*(.+)$/);
      const path = pathMatch ? pathMatch[1] : rest.slice(0, 100);
      const detail = pathMatch ? pathMatch[2] : '';
      const fase = extractFase(s);
      return { idx: idx + 1, cat: cat.cat, catName: cat.name, type: tipo, path, detail, sev, fase, raw: s };
    }

    function escapeHtml(s){
      return String(s || '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
    }

    let PARSED_DIVS = [];

    /* Fix D: limpa rows mock do HTML pra nunca deixar UI zumbi caso applyResults não rode */
    function clearMockList(msg){
      const listEl = document.getElementById('list');
      if(listEl){
        listEl.innerHTML = '<div class="v2-empty-list" style="padding:40px 20px;text-align:center;color:var(--muted);font-size:13px">' + (msg || 'Carregando resultados...') + '</div>';
      }
    }

    /* Helper reutilizável: substitui conteúdo do diff panel direito por mensagem de estado vazio.
       opts: { tone: 'ok'|'err'|'muted', title, hint, extra } */
    function clearDiffPane(opts){
      opts = opts || {};
      const paneRight = document.querySelector('.pane-right');
      if(!paneRight) return;
      const rightTitle = paneRight.querySelector('.right-title');
      const rightMeta = paneRight.querySelector('.right-meta');
      const rightTabs = paneRight.querySelector('.right-tabs');
      const diffBody = paneRight.querySelector('.diff-body');
      if(rightTitle) rightTitle.textContent = opts.title || 'Sem divergência';
      if(rightMeta) rightMeta.style.display = 'none';
      if(rightTabs) rightTabs.style.display = 'none';
      if(diffBody){
        const iconColor = opts.tone === 'ok' ? '#6fd17a' : opts.tone === 'err' ? '#d9534f' : 'var(--muted)';
        const icon = opts.tone === 'ok' ? '✓' : opts.tone === 'err' ? '!' : '—';
        const hint = opts.hint || 'Nenhuma divergência pra exibir.';
        const extra = opts.extra || 'Ao selecionar uma divergência na lista, o diff aparece aqui.';
        diffBody.innerHTML = ''
          + '<div class="v2-diff-empty" style="padding:64px 28px;text-align:center;font-size:12px;line-height:1.6">'
          +   '<div style="font-size:36px;line-height:1;color:' + iconColor + ';margin-bottom:14px;font-weight:300">' + icon + '</div>'
          +   '<div style="font-size:13px;color:var(--ink-2);margin-bottom:6px;font-weight:500">' + escapeHtml(hint) + '</div>'
          +   '<div style="color:var(--muted);max-width:340px;margin:0 auto;font-size:11.5px">' + escapeHtml(extra) + '</div>'
          + '</div>';
      }
    }

    /* Helper: zera valores do popover do stacked bar e esconde a seção quando não há diffs */
    function hideStackedSection(){
      const stacked = document.getElementById('stacked-section');
      if(stacked) stacked.style.display = 'none';
      const pop = document.getElementById('stacked-pop');
      if(pop){
        pop.setAttribute('aria-hidden', 'true');
        pop.style.display = 'none';
      }
      const setText = (id, val) => { const el = document.getElementById(id); if(el) el.textContent = val; };
      setText('pop-cat', '—');
      setText('pop-sub', 'sem categoria ativa');
      setText('pop-num', '0');
      setText('pop-pct', '0% do total');
      setText('pop-axis', '0 → 0');
      setText('pop-v-err', '0');
      setText('pop-v-warn', '0');
      setText('pop-v-info', '0');
    }

    function showStackedSection(){
      const stacked = document.getElementById('stacked-section');
      if(stacked) stacked.style.display = '';
      const pop = document.getElementById('stacked-pop');
      if(pop) pop.style.display = '';
    }

    /* Fix A: renderiza estado de erro/vazio explícito.
       kind: 'no_result' | 'execution_failed' | 'fetch_error'
       data: quando kind=execution_failed, payload do validations.json com status/error */
    function renderEmptyState(kind, data){
      const listEl = document.getElementById('list');
      const meta = data || {};
      let title, hint, tone;
      if(kind === 'execution_failed'){
        title = 'Execução falhou antes de gerar divergências';
        const parts = [];
        if(meta.error) parts.push(meta.error);
        else parts.push('Robot abortou sem produzir validations.json.');
        if(meta.hint) parts.push('💡 ' + meta.hint);
        if(meta.config) parts.push('Preset: ' + meta.config);
        if(typeof meta.exit_code !== 'undefined') parts.push('Exit code: ' + meta.exit_code);
        hint = parts.join('\n');
        tone = 'err';
      } else if(kind === 'fetch_error'){
        title = 'Não foi possível carregar os resultados';
        hint = meta.message || 'Falha de rede ao consultar /api/results.';
        tone = 'warn';
      } else {
        title = 'Nenhum resultado disponível';
        hint = 'Execute uma validação pra ver divergências aqui.';
        tone = 'muted';
      }

      if(listEl){
        const color = tone === 'err' ? '#d9534f' : tone === 'warn' ? '#c9a84c' : 'var(--muted)';
        listEl.innerHTML = ''
          + '<div class="v2-empty-list" style="padding:48px 28px;text-align:center">'
          +   '<div style="font-size:14px;font-weight:500;color:' + color + ';letter-spacing:-.01em;margin-bottom:8px">' + escapeHtml(title) + '</div>'
          +   '<div style="font-size:12px;color:var(--muted);white-space:pre-wrap;line-height:1.55;max-width:520px;margin:0 auto">' + escapeHtml(hint) + '</div>'
          +   '<div style="margin-top:20px;display:flex;gap:8px;justify-content:center">'
          +     '<a href="/reports/log.html" target="_blank" style="padding:6px 12px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:6px;color:var(--ink-2);font-size:11.5px;text-decoration:none">Abrir log.html</a>'
          +     '<a href="' + getConfigUrl() + '" style="padding:6px 12px;background:rgba(201,168,76,.12);border:1px solid rgba(201,168,76,.35);border-radius:6px;color:#c9a84c;font-size:11.5px;text-decoration:none">Nova validação</a>'
          +   '</div>'
          + '</div>';
      }

      // Zera KPIs
      const kpiNumBad = document.querySelector('.kpi-num.bad');
      if(kpiNumBad) kpiNumBad.textContent = '0';
      const allKpis = document.querySelectorAll('.kpi');
      if(allKpis[1]){
        const num = allKpis[1].querySelector('.kpi-num');
        const sub = allKpis[1].querySelector('.kpi-sub');
        if(num) num.textContent = '0';
        if(sub) sub.textContent = 'nenhuma divergência parseada';
      }
      if(allKpis[2]){
        const num = allKpis[2].querySelector('.kpi-num');
        if(num) num.innerHTML = '—<span style="font-size:14px;color:var(--muted);margin-left:2px">s</span>';
      }
      if(allKpis[3]){
        const num = allKpis[3].querySelector('.kpi-num');
        const sub = allKpis[3].querySelector('.kpi-sub');
        if(num) num.innerHTML = '0<span style="font-size:14px;color:var(--muted);margin-left:4px">/ 7</span>';
        if(sub) sub.textContent = 'sem dados';
      }

      // Run status explícito
      const runStatusTxt = document.querySelector('.run-status .txt');
      if(runStatusTxt){
        runStatusTxt.textContent = kind === 'execution_failed' ? 'FAILED · run abortou' :
                                   kind === 'fetch_error'     ? 'ERRO · sem conexão' :
                                                                'SEM RESULTADO';
      }
      const runStatusPill = document.querySelector('.run-status');
      if(runStatusPill){
        runStatusPill.classList.remove('ok');
        runStatusPill.classList.add('fail');
      }

      // Showing counter
      const showing = document.querySelector('.showing');
      if(showing) showing.innerHTML = '<b>0</b> de <b>0</b>';

      // Zera segmentos do stacked bar
      document.querySelectorAll('.stacked-seg').forEach(seg => {
        seg.style.display = 'none';
        seg.setAttribute('data-count', '0');
      });

      // Zera facets de categoria
      document.querySelectorAll('.filter-section .facet .count').forEach(c => c.textContent = '0');

      // Desabilita toolbar (filtros, busca) e sidebar de filtros
      const toolbar = document.querySelector('.center-toolbar');
      if(toolbar){
        toolbar.style.pointerEvents = 'none';
        toolbar.style.opacity = '.45';
      }
      const paneLeft = document.querySelector('.pane-left');
      if(paneLeft){
        paneLeft.style.pointerEvents = 'none';
        paneLeft.style.opacity = '.45';
      }

      // Esvazia diff panel (painel direito) e esconde seção stacked
      clearDiffPane({
        tone: kind === 'execution_failed' || kind === 'fetch_error' ? 'err' : 'muted',
        title: 'Sem divergência',
        hint: kind === 'execution_failed' ? 'Execução falhou' : 'Nenhuma divergência pra exibir',
        extra: 'Quando houver validations.json válido, o diff aparece aqui.',
      });
      hideStackedSection();

      // Atualiza breadcrumb/run-id mesmo no estado vazio, pra matar o run_4f82a1cb mock
      try { applyRunMetaFromSession({}); } catch(e){}
    }

    /* Renderiza estado OK (0 divergências) do Pipefy single/cross/snapshot-comparar:
       hero "Pipes Idênticos" no centro + checklist "Validações Executadas" na direita (estilo legacy) */
    function renderPipefyOkPanel(data){
      const pipeOrigem = (data && data.pipe_origem) || '—';
      const pipeDestino = (data && data.pipe_destino) || '—';

      let durText = '—';
      try {
        const sessMeta = JSON.parse(sessionStorage.getItem('v2-run-meta') || 'null');
        if(sessMeta && typeof sessMeta.elapsedFinal === 'number') durText = sessMeta.elapsedFinal.toFixed(2) + 's';
      } catch(e){}

      // CENTRO: hero
      const listEl = document.getElementById('list');
      if(listEl){
        const flowLine = (pipeOrigem.length + pipeDestino.length) > 60
          ? escapeHtml(truncMid(pipeOrigem, 28)) + ' → ' + escapeHtml(truncMid(pipeDestino, 28))
          : escapeHtml(pipeOrigem) + ' → ' + escapeHtml(pipeDestino);
        listEl.innerHTML = ''
          + '<div class="v2-pipefy-ok-hero" style="padding:56px 28px 40px;text-align:center;border-bottom:1px solid rgba(255,255,255,.05);background:rgba(111,209,122,.06)">'
          +   '<div style="font-size:56px;line-height:1;margin-bottom:16px;color:#6fd17a;font-weight:300">✓</div>'
          +   '<div style="font-size:18px;font-weight:500;color:var(--ink);letter-spacing:-.01em;margin-bottom:8px">Pipes Idênticos</div>'
          +   '<div style="font-size:12.5px;color:var(--muted);margin-bottom:18px;font-family:var(--mono);max-width:580px;margin-left:auto;margin-right:auto;word-break:break-word" title="' + escapeHtml(pipeOrigem) + ' → ' + escapeHtml(pipeDestino) + '">' + flowLine + '</div>'
          +   '<div style="display:inline-flex;align-items:center;gap:10px;font-size:12px;color:var(--muted);background:rgba(255,255,255,.03);border:1px solid rgba(111,209,122,.25);border-radius:100px;padding:7px 16px">'
          +     '<span style="display:inline-flex;align-items:center;gap:5px"><span style="font-size:14px">⏱</span>' + escapeHtml(durText) + '</span>'
          +   '</div>'
          + '</div>';
      }

      // DIREITA: checklist "Validações Executadas"
      const paneRight = document.querySelector('.pane-right');
      if(!paneRight) return;

      const checks = [
        { k: 'Start Form',            d: 'Campos do formulário inicial' },
        { k: 'Fases & Campos',        d: 'Nomes, tipos, obrigatoriedade, opções' },
        { k: 'Labels',                d: 'Etiquetas e existência' },
        { k: 'Automações (Status)',   d: 'Ativas/inativas, tipo de ação e evento' },
        { k: 'Fase Destino',          d: 'Resolução por nome via phase map' },
        { k: 'URL / HTTP Config',     d: 'Endpoint, método, body, headers' },
        { k: 'Conditions',            d: 'Operador + valor (skip IDs numéricos)' },
      ];

      const itemsHtml = checks.map(c => (
        '<div style="display:flex;align-items:flex-start;gap:10px;padding:9px 0;border-bottom:1px solid rgba(255,255,255,.04)">'
        +   '<span style="flex:0 0 auto;width:18px;height:18px;border-radius:50%;background:rgba(111,209,122,.15);color:#6fd17a;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;line-height:1;margin-top:1px">✓</span>'
        +   '<span style="flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:2px">'
        +     '<span style="font-size:12.5px;color:var(--ink-2);font-weight:500;letter-spacing:-.01em">' + escapeHtml(c.k) + '</span>'
        +     '<span style="font-size:11px;color:var(--muted);line-height:1.4">' + escapeHtml(c.d) + '</span>'
        +   '</span>'
        + '</div>'
      )).join('');

      paneRight.innerHTML = ''
        + '<div class="right-head"><div class="right-title" style="color:var(--ink);font-weight:500;font-size:13px">Pipefy report</div></div>'
        + '<div style="padding:18px 22px 20px;">'
        +   '<div style="font-size:10.5px;font-weight:600;color:var(--muted);letter-spacing:.08em;margin-bottom:10px">VALIDAÇÕES EXECUTADAS</div>'
        +   '<div>' + itemsHtml + '</div>'
        +   '<div style="margin-top:14px;padding-top:12px;border-top:1px solid rgba(255,255,255,.04);font-size:11.5px;color:var(--muted);line-height:1.55">'
        +     '<div style="color:var(--ink-2);font-weight:500;margin-bottom:3px">A estrutura dos dois pipes é idêntica.</div>'
        +     '<div>O deploy está íntegro, fases, campos, labels e automações conferem entre os ambientes.</div>'
        +   '</div>'
        + '</div>';
    }

    /* Trunca string mantendo início e fim, com … no meio quando passa do max. */
    function truncMid(s, max){
      s = String(s || '');
      if(s.length <= max) return s;
      const half = Math.floor((max - 1) / 2);
      return s.slice(0, half) + '…' + s.slice(s.length - half);
    }

    /* Renderiza resultado iPaaS (Activepieces flows). Centro mostra hero + lista de divergências,
       direita mostra checklist "Validações Executadas" estilo legacy. */
    function renderIpaasResults(data){
      const totalDivs = data.total_divergencias || 0;
      const flowsOrigem = data.total_flows_origem != null ? data.total_flows_origem : '?';
      const flowsDestino = data.total_flows_destino != null ? data.total_flows_destino : '?';

      // Repassa pra applyResults pra preencher KPIs/lista/filtros
      const fakeAgg = {
        status: data.status || (totalDivs === 0 ? 'IDENTICOS' : 'DIVERGENCIAS_ENCONTRADAS'),
        pipe_origem: flowsOrigem + ' flows · origem',
        pipe_destino: flowsDestino + ' flows · destino',
        total_divergencias: totalDivs,
        divergencias: data.divergencias || [],
        metadata: data.metadata || {},
      };
      applyResults(fakeAgg);

      const statusIcon = totalDivs === 0 ? '✓' : '✗';
      const statusColor = totalDivs === 0 ? '#6fd17a' : '#d9534f';
      const statusBg = totalDivs === 0 ? 'rgba(111,209,122,.08)' : 'rgba(217,83,79,.08)';
      const statusBorder = totalDivs === 0 ? 'rgba(111,209,122,.25)' : 'rgba(217,83,79,.25)';
      const statusTitle = totalDivs === 0 ? 'Flows Consistentes' : 'Divergências detectadas';
      const statusSub = totalDivs === 0
        ? 'Todos os flows do iPaaS estão consistentes entre os ambientes.'
        : totalDivs + ' divergência' + (totalDivs > 1 ? 's' : '') + ' entre ' + flowsOrigem + ' e ' + flowsDestino + ' flows';

      let durText = '—';
      try {
        const sessMeta = JSON.parse(sessionStorage.getItem('v2-run-meta') || 'null');
        if(sessMeta && typeof sessMeta.elapsedFinal === 'number') durText = sessMeta.elapsedFinal.toFixed(2) + 's';
      } catch(e){}

      // CENTRO: hero principal
      const listEl = document.getElementById('list');
      if(listEl){
        const heroHtml = ''
          + '<div class="v2-ipaas-hero" style="padding:56px 28px 40px;text-align:center;border-bottom:1px solid rgba(255,255,255,.05);background:' + statusBg + '">'
          +   '<div style="font-size:56px;line-height:1;margin-bottom:16px;color:' + statusColor + ';font-weight:300">' + statusIcon + '</div>'
          +   '<div style="font-size:18px;font-weight:500;color:var(--ink);letter-spacing:-.01em;margin-bottom:8px">' + escapeHtml(statusTitle) + '</div>'
          +   '<div style="font-size:13px;color:var(--muted);margin-bottom:18px;max-width:520px;margin-left:auto;margin-right:auto">' + escapeHtml(statusSub) + '</div>'
          +   '<div style="display:inline-flex;align-items:center;gap:14px;font-size:12px;color:var(--muted);background:rgba(255,255,255,.03);border:1px solid ' + statusBorder + ';border-radius:100px;padding:7px 16px">'
          +     '<span style="display:inline-flex;align-items:center;gap:5px"><span style="font-size:14px">⏱</span>' + escapeHtml(durText) + '</span>'
          +     '<span style="color:rgba(255,255,255,.15)">·</span>'
          +     '<span>' + flowsOrigem + ' flow' + (flowsOrigem !== 1 ? 's' : '') + ' validado' + (flowsOrigem !== 1 ? 's' : '') + '</span>'
          +     (totalDivs > 0 ? ('<span style="color:rgba(255,255,255,.15)">·</span><span style="color:#d9534f">' + totalDivs + ' diff' + (totalDivs > 1 ? 's' : '') + '</span>') : '')
          +   '</div>'
          + '</div>';

        if(totalDivs === 0){
          listEl.innerHTML = heroHtml;
        } else {
          listEl.innerHTML = heroHtml + listEl.innerHTML;
        }
      }

      // DIREITA: checklist "Validações Executadas" estilo legacy
      const paneRight = document.querySelector('.pane-right');
      if(!paneRight) return;

      const checks = [
        { k: 'Inventário de Flows',    d: 'Quais flows existem em cada ambiente' },
        { k: 'Status dos Flows',       d: 'ENABLED / DISABLED' },
        { k: 'Triggers',               d: 'Tipo, pipe, fase destino, campos' },
        { k: 'Steps (Tipo & Ação)',    d: 'PIECE, CODE, ROUTER + actionName' },
        { k: 'URLs dos Steps',         d: 'Endpoints HTTP configurados' },
        { k: 'Código Fonte',           d: 'Hash MD5 dos steps JavaScript' },
        { k: 'Router Conditions',      d: 'Regras de decisão dos branches' },
        { k: 'Mapeamento de Campos',   d: 'Input keys de cada step' },
        { k: 'Connections',            d: 'Conexões referenciadas' },
      ];

      const itemsHtml = checks.map(c => (
        '<div style="display:flex;align-items:flex-start;gap:10px;padding:9px 0;border-bottom:1px solid rgba(255,255,255,.04)">'
        +   '<span style="flex:0 0 auto;width:18px;height:18px;border-radius:50%;background:rgba(111,209,122,.15);color:#6fd17a;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;line-height:1;margin-top:1px">✓</span>'
        +   '<span style="flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:2px">'
        +     '<span style="font-size:12.5px;color:var(--ink-2);font-weight:500;letter-spacing:-.01em">' + escapeHtml(c.k) + '</span>'
        +     '<span style="font-size:11px;color:var(--muted);line-height:1.4">' + escapeHtml(c.d) + '</span>'
        +   '</span>'
        + '</div>'
      )).join('');

      paneRight.innerHTML = ''
        + '<div class="right-head"><div class="right-title" style="color:var(--ink);font-weight:500;font-size:13px">iPaaS report</div></div>'
        + '<div style="padding:18px 22px 20px;">'
        +   '<div style="font-size:10.5px;font-weight:600;color:var(--muted);letter-spacing:.08em;margin-bottom:10px">VALIDAÇÕES EXECUTADAS</div>'
        +   '<div>' + itemsHtml + '</div>'
        + '</div>';
    }

    /* Renderiza resultado de batch (múltiplos pipes). Centro mostra resumo hero,
       direita mostra a lista detalhada de pipes com status (inspirado V1 legacy). */
    function renderBatchResults(data){
      const pipes = data.pipes || [];
      const totalDivs = data.total_divergencias || 0;
      const allFlat = [];
      pipes.forEach((p, pIdx) => {
        (p.divergencias || []).forEach(d => allFlat.push({ pipe: p.nome, pipeIdx: pIdx, raw: d }));
      });

      // Passa divergências agregadas pro applyResults preencher KPIs, filtros etc
      const fakeAgg = {
        status: totalDivs === 0 ? 'IDENTICOS' : 'DIVERGENCIAS_ENCONTRADAS',
        pipe_origem: pipes.length + ' pipes validados',
        pipe_destino: 'batch',
        total_divergencias: totalDivs,
        divergencias: allFlat.map(item => '[' + (item.pipe || 'pipe ' + (item.pipeIdx + 1)) + '] ' + item.raw),
        metadata: data.metadata || {},
      };
      applyResults(fakeAgg);

      const statusIcon = totalDivs === 0 ? '✓' : '✗';
      const statusColor = totalDivs === 0 ? '#6fd17a' : '#d9534f';
      const statusBg = totalDivs === 0 ? 'rgba(111,209,122,.08)' : 'rgba(217,83,79,.08)';
      const statusBorder = totalDivs === 0 ? 'rgba(111,209,122,.25)' : 'rgba(217,83,79,.25)';
      const statusText = totalDivs === 0 ? 'Todos os pipes íntegros' : totalDivs + ' divergência' + (totalDivs > 1 ? 's' : '') + ' total';

      let durText = '—';
      try {
        const sessMeta = JSON.parse(sessionStorage.getItem('v2-run-meta') || 'null');
        if(sessMeta && typeof sessMeta.elapsedFinal === 'number') durText = sessMeta.elapsedFinal.toFixed(2) + 's';
      } catch(e){}

      // CENTRO: hero do batch (ícone grande + texto + stats). Aparece sempre, independente de ter diffs.
      // Se houver diffs, applyResults já renderizou lista; substituo por hero + a lista fica visível após o hero.
      const listEl = document.getElementById('list');
      if(listEl){
        const heroHtml = ''
          + '<div class="v2-batch-hero" style="padding:56px 28px 40px;text-align:center;border-bottom:1px solid rgba(255,255,255,.05);background:' + statusBg + '">'
          +   '<div style="font-size:56px;line-height:1;margin-bottom:16px;color:' + statusColor + ';font-weight:300">' + statusIcon + '</div>'
          +   '<div style="font-size:18px;font-weight:500;color:var(--ink);letter-spacing:-.01em;margin-bottom:8px">Batch concluído</div>'
          +   '<div style="font-size:13px;color:var(--muted);margin-bottom:18px">' + escapeHtml(statusText) + '</div>'
          +   '<div style="display:inline-flex;align-items:center;gap:14px;font-size:12px;color:var(--muted);background:rgba(255,255,255,.03);border:1px solid ' + statusBorder + ';border-radius:100px;padding:7px 16px">'
          +     '<span style="display:inline-flex;align-items:center;gap:5px"><span style="font-size:14px">⏱</span>' + escapeHtml(durText) + '</span>'
          +     '<span style="color:rgba(255,255,255,.15)">·</span>'
          +     '<span>' + pipes.length + ' pipe' + (pipes.length > 1 ? 's' : '') + '</span>'
          +     (totalDivs > 0 ? ('<span style="color:rgba(255,255,255,.15)">·</span><span style="color:#d9534f">' + totalDivs + ' diff' + (totalDivs > 1 ? 's' : '') + '</span>') : '')
          +   '</div>'
          + '</div>';

        if(totalDivs === 0){
          listEl.innerHTML = heroHtml;
        } else {
          // Mantém a lista de diffs agregada e insere o hero acima
          listEl.innerHTML = heroHtml + listEl.innerHTML;
        }
      }

      // DIREITA: log estilo legacy com lista de pipes (detalhamento por pipe)
      const paneRight = document.querySelector('.pane-right');
      if(!paneRight) return;

      const rowsHtml = pipes.map((p) => {
        const divs = p.total_divergencias || 0;
        const iconColor = divs === 0 ? '#6fd17a' : '#d9534f';
        const icon = divs === 0 ? '✓' : '✗';
        const countColor = divs === 0 ? 'var(--muted)' : '#d9534f';
        const countText = divs === 0 ? 'idêntico' : divs + ' diff' + (divs > 1 ? 's' : '');
        return ''
          + '<div style="display:flex;align-items:center;gap:12px;padding:11px 0;border-bottom:1px solid rgba(255,255,255,.04)">'
          +   '<span style="flex:0 0 auto;width:20px;height:20px;border-radius:50%;background:' + (divs === 0 ? 'rgba(111,209,122,.15)' : 'rgba(217,83,79,.15)') + ';color:' + iconColor + ';display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;line-height:1">' + icon + '</span>'
          +   '<span style="flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12.5px;color:var(--ink-2);font-weight:500" title="' + escapeHtml(p.nome) + '">' + escapeHtml(p.nome) + '</span>'
          +   '<span style="flex:0 0 auto;font-size:11px;font-family:var(--mono);color:' + countColor + '">' + escapeHtml(countText) + '</span>'
          + '</div>';
      }).join('');

      paneRight.innerHTML = ''
        + '<div class="right-head"><div class="right-title" style="color:var(--ink);font-weight:500;font-size:13px">Pipes validados</div></div>'
        + '<div style="padding:18px 22px;">'
        +   '<div style="font-size:10.5px;font-weight:600;color:var(--muted);letter-spacing:.08em;margin-bottom:10px">' + pipes.length + ' PIPE' + (pipes.length > 1 ? 'S' : '') + '</div>'
        +   '<div>' + rowsHtml + '</div>'
        + '</div>';
    }

    /* Renderiza painel direito do snapshot gerado: ícone + filename + tempo +
       checklist "Dados Capturados" dinâmico (inspirado no V1 legacy) */
    function renderSnapshotRightPane(ctx){
      const paneRight = document.querySelector('.pane-right');
      if(!paneRight) return;

      // Duração formatada
      let durText = '—';
      try {
        const sessMeta = JSON.parse(sessionStorage.getItem('v2-run-meta') || 'null');
        if(sessMeta && typeof sessMeta.elapsedFinal === 'number'){
          durText = sessMeta.elapsedFinal.toFixed(2) + 's';
        }
      } catch(e){}

      const captured = [
        { k: 'Start Form',       d: 'Formulário inicial capturado' },
        { k: 'Fases & Campos',   d: 'Estrutura completa por fase' },
        { k: 'Labels',           d: 'Etiquetas e cores' },
        { k: 'Automações',       d: 'Com params completos' },
        { k: 'Fase Destino',     d: 'Mapeamento de fases por nome' },
        { k: 'URL / HTTP Config',d: 'Endpoints e payloads' },
        { k: 'Conditions',       d: 'Regras de condição' },
        { k: 'Metadata',         d: 'Timestamp, versão, fontes' },
      ];

      const itemsHtml = captured.map(c => (
        '<div style="display:flex;align-items:flex-start;gap:10px;padding:9px 0;border-bottom:1px solid rgba(255,255,255,.04)">'
        +   '<span style="flex:0 0 auto;width:18px;height:18px;border-radius:50%;background:rgba(111,209,122,.15);color:#6fd17a;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;line-height:1;margin-top:1px">✓</span>'
        +   '<span style="flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:2px">'
        +     '<span style="font-size:12.5px;color:var(--ink-2);font-weight:500;letter-spacing:-.01em">' + escapeHtml(c.k) + '</span>'
        +     '<span style="font-size:11px;color:var(--muted);line-height:1.4">' + escapeHtml(c.d) + '</span>'
        +   '</span>'
        + '</div>'
      )).join('');

      paneRight.innerHTML = ''
        + '<div class="right-head"><div class="right-title" style="color:var(--ink);font-weight:500;font-size:13px">Snapshot report</div></div>'
        + '<div class="v2-snap-report" style="padding:18px 22px 20px;">'
        +   '<div style="font-size:10.5px;font-weight:600;color:var(--muted);letter-spacing:.08em;margin-bottom:10px">DADOS CAPTURADOS</div>'
        +   '<div>' + itemsHtml + '</div>'
        + '</div>';
    }

    /* Renderiza estado de sucesso do snapshot gerar: arquivo salvo, counts, link pra Comparar */
    function renderSnapshotGenerated(data){
      const file = data.snapshot_file || '';
      const fileName = file.replace(/^snapshots\//, '').replace(/\.json$/, '');
      const pipeName = data.pipe_name || '';
      const autoCount = data.automacoes != null ? data.automacoes : '—';
      const tempo = data.timestamp || '';

      // KPIs resetados pra contexto de geração (não comparação)
      const kpiNumBad = document.querySelector('.kpi-num.bad');
      if(kpiNumBad){ kpiNumBad.textContent = '1'; kpiNumBad.style.color = '#6fd17a'; }
      const allKpis = document.querySelectorAll('.kpi');
      if(allKpis[0]){
        const lbl = allKpis[0].querySelector('.kpi-label');
        const sub = allKpis[0].querySelector('.kpi-sub');
        if(lbl) lbl.textContent = 'Snapshot salvo';
        if(sub) sub.textContent = 'arquivo JSON gerado';
      }
      if(allKpis[1]){
        const num = allKpis[1].querySelector('.kpi-num');
        const sub = allKpis[1].querySelector('.kpi-sub');
        const lbl = allKpis[1].querySelector('.kpi-label');
        if(num) num.textContent = autoCount;
        if(lbl) lbl.textContent = 'Automações capturadas';
        if(sub) sub.textContent = 'extraídas do pipe';
      }
      if(allKpis[2]){
        const num = allKpis[2].querySelector('.kpi-num');
        const sub = allKpis[2].querySelector('.kpi-sub');
        if(num){
          try {
            const sessMeta = JSON.parse(sessionStorage.getItem('v2-run-meta') || 'null');
            const ef = sessMeta && sessMeta.elapsedFinal;
            if(typeof ef === 'number'){
              num.innerHTML = ef.toFixed(3) + '<span style="font-size:14px;color:var(--muted);margin-left:2px">s</span>';
            } else if(tempo){
              num.innerHTML = escapeHtml(tempo);
            }
          } catch(e){}
        }
        if(sub) sub.textContent = 'tempo de captura';
      }
      if(allKpis[3]){
        const num = allKpis[3].querySelector('.kpi-num');
        const sub = allKpis[3].querySelector('.kpi-sub');
        const lbl = allKpis[3].querySelector('.kpi-label');
        if(lbl) lbl.textContent = 'Arquivo';
        if(num) num.innerHTML = '<span style="font-size:13px;font-family:var(--mono);color:var(--ink-2)">' + escapeHtml(fileName.slice(0, 22)) + (fileName.length > 22 ? '…' : '') + '</span>';
        if(sub) sub.textContent = 'em snapshots/';
      }

      // Run status
      const runStatusTxt = document.querySelector('.run-status .txt');
      if(runStatusTxt) runStatusTxt.textContent = 'OK · snapshot gerado';
      const runStatusPill = document.querySelector('.run-status');
      if(runStatusPill){ runStatusPill.classList.remove('fail'); runStatusPill.classList.add('ok'); }

      // List: mostra o filename como "divergência" simbólica de sucesso
      const listEl = document.getElementById('list');
      if(listEl){
        listEl.innerHTML = ''
          + '<div style="padding:48px 28px;text-align:center">'
          +   '<div style="font-size:42px;line-height:1;color:#6fd17a;margin-bottom:16px;font-weight:300">✓</div>'
          +   '<div style="font-size:14px;font-weight:500;color:var(--ink-2);margin-bottom:6px">Snapshot salvo com sucesso</div>'
          +   '<div style="font-size:12px;color:var(--muted);line-height:1.55;max-width:520px;margin:0 auto 18px">Baseline congelado pra usar em comparações futuras contra o estado live do pipe.</div>'
          +   '<div style="font-family:var(--mono);font-size:12px;color:var(--ink-2);background:rgba(201,168,76,.08);border:1px solid rgba(201,168,76,.25);border-radius:6px;padding:10px 14px;display:inline-block;margin-bottom:18px">' + escapeHtml(file || fileName + '.json') + '</div>'
          +   '<div style="font-size:12px;color:var(--muted);margin-bottom:20px">' + escapeHtml(pipeName) + (autoCount !== '—' ? ' · ' + autoCount + ' automações' : '') + '</div>'
          +   '<div style="display:flex;gap:8px;justify-content:center">'
          +     '<a href="/v2/configuracao?mode=snapshot&sub=comparar" style="padding:8px 14px;background:rgba(201,168,76,.12);border:1px solid rgba(201,168,76,.4);border-radius:6px;color:#c9a84c;font-size:12px;text-decoration:none;font-weight:500">Comparar contra este baseline →</a>'
          +     '<a href="/reports/log.html" target="_blank" style="padding:8px 14px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:6px;color:var(--ink-2);font-size:12px;text-decoration:none">Abrir log.html</a>'
          +   '</div>'
          + '</div>';
      }

      // Showing counter
      const showing = document.querySelector('.showing');
      if(showing) showing.innerHTML = '<b>1</b> arquivo salvo';

      // Esconde stacked, limpa facets
      hideStackedSection();
      document.querySelectorAll('.filter-section .facet .count').forEach(c => c.textContent = '0');
      document.querySelectorAll('.stacked-seg').forEach(seg => seg.style.display = 'none');

      // Coluna direita: "Snapshot Gerado" com lista de Dados Capturados (inspirado no legacy)
      renderSnapshotRightPane({
        file: file,
        fileName: fileName,
        pipeName: pipeName,
        autoCount: autoCount,
      });

      // Toolbar/sidebar disabled visualmente
      const toolbar = document.querySelector('.center-toolbar');
      if(toolbar){ toolbar.style.pointerEvents = 'none'; toolbar.style.opacity = '.4'; }
      const paneLeft = document.querySelector('.pane-left');
      if(paneLeft){ paneLeft.style.pointerEvents = 'none'; paneLeft.style.opacity = '.4'; }

      // Breadcrumb / run-id
      try { applyRunMetaFromSession({}); } catch(e){}

      // Override hero: Pipe origem → label curto "Baseline salvo" (filename completo
      // vai no KPI e no card central, aqui mantém o layout enxuto)
      const envTags = document.querySelectorAll('.meta-flow-hero .env-tag');
      const envNames = document.querySelectorAll('.meta-flow-hero .env-name');
      if(envTags[0]) envTags[0].textContent = 'Pipe';
      if(envNames[0]){
        envNames[0].textContent = pipeName || '—';
        envNames[0].style.maxWidth = '220px';
        envNames[0].style.whiteSpace = 'nowrap';
        envNames[0].style.overflow = 'hidden';
        envNames[0].style.textOverflow = 'ellipsis';
        envNames[0].title = pipeName || '';
      }
      if(envTags[1]) envTags[1].textContent = 'Baseline';
      if(envNames[1]){
        envNames[1].textContent = 'salvo em snapshots/';
        envNames[1].style.maxWidth = '';
        envNames[1].style.whiteSpace = '';
        envNames[1].style.overflow = '';
        envNames[1].style.textOverflow = '';
        envNames[1].title = file || '';
      }

      // Meta-block Pipe (col 2): substitui mock hardcoded pelo pipe real (truncado)
      const metaPipeValue = document.querySelectorAll('.meta-block .meta-value.muted')[0];
      if(metaPipeValue){
        const MAX = 26;
        const shortPipe = (pipeName || '').length > MAX ? (pipeName || '').slice(0, MAX - 1) + '…' : (pipeName || '—');
        metaPipeValue.textContent = '';
        metaPipeValue.appendChild(document.createTextNode(shortPipe));
        metaPipeValue.title = pipeName || '';
        metaPipeValue.style.maxWidth = '220px';
        metaPipeValue.style.whiteSpace = 'nowrap';
        metaPipeValue.style.overflow = 'hidden';
        metaPipeValue.style.textOverflow = 'ellipsis';
        metaPipeValue.style.display = 'inline-block';
        metaPipeValue.style.verticalAlign = 'middle';
      }

      // Duração na meta block
      try {
        const sessMeta = JSON.parse(sessionStorage.getItem('v2-run-meta') || 'null');
        if(sessMeta){
          const elMetaElap = document.getElementById('meta-elapsed');
          const label = sessMeta.elapsedFinalLabel
                     || (typeof sessMeta.elapsedFinal === 'number' ? sessMeta.elapsedFinal.toFixed(3) + 's' : null);
          if(elMetaElap && label) elMetaElap.textContent = label;
        }
      } catch(e){}
    }

    async function loadResults(){
      clearMockList('Carregando resultados...');
      try {
        const res = await (window.V2Utils ? window.V2Utils.apiFetch : fetch)('/api/results');
        if(!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        if(!data){
          console.log('[v2] /api/results retornou null, renderizando empty state');
          renderEmptyState('no_result');
          return;
        }
        if(data.status === 'EXECUTION_FAILED'){
          console.log('[v2] validations.json marca EXECUTION_FAILED, renderizando estado de erro');
          renderEmptyState('execution_failed', data);
          return;
        }
        if(data.snapshot_generated === true){
          console.log('[v2] snapshot gerado detectado, renderizando estado de sucesso');
          renderSnapshotGenerated(data);
          return;
        }
        if(typeof data.total_pipes === 'number' && Array.isArray(data.pipes)){
          console.log('[v2] batch detectado,', data.total_pipes, 'pipes,', data.total_divergencias, 'divergências');
          renderBatchResults(data);
          return;
        }
        if((data.metadata && data.metadata.mode === 'ipaas') || typeof data.total_flows_origem === 'number'){
          console.log('[v2] iPaaS detectado,', data.total_flows_origem, 'flows origem,', data.total_divergencias, 'divergências');
          renderIpaasResults(data);
          return;
        }
        applyResults(data);
      } catch(e) {
        console.warn('[v2] /api/results falhou:', e.message);
        renderEmptyState('fetch_error', { message: e.message });
      }
    }

    /* Aplica meta da run (Run ID, pipe, flow hero, breadcrumb) do sessionStorage */
    function applyRunMetaFromSession(data){
      let meta;
      try { meta = JSON.parse(sessionStorage.getItem('v2-run-meta') || 'null'); } catch(e){ meta = null; }
      if(!meta) return;

      // Breadcrumb
      const bcCurrent = document.querySelector('.crumbs .current');
      if(bcCurrent) bcCurrent.textContent = 'run_' + meta.runId;
      const bcParent = document.querySelectorAll('.crumbs a');
      if(bcParent[1]){
        const parentLabel = meta.mode === 'cross' ? 'Cross Env' :
                            meta.mode === 'snapshot' ? 'Snapshot' :
                            meta.mode === 'batch' ? 'Batch' :
                            meta.mode === 'ipaas' ? 'iPaaS' : 'Single Env';
        bcParent[1].textContent = parentLabel;
      }

      // Run ID hash + suffix
      const runHash = document.querySelector('.runid-hash');
      if(runHash) runHash.textContent = meta.runId;
      const runSuffix = document.querySelector('.runid-suffix');
      if(runSuffix) runSuffix.textContent = meta.startedAtLabel;

      // Flow hero env-names/tags
      const envTags = document.querySelectorAll('.meta-flow-hero .env-tag');
      const envNames = document.querySelectorAll('.meta-flow-hero .env-name');

      // Modo snapshot: usa pipeSrc/pipeDst distintos (ex: Baseline · xxx → Live · pipe)
      // em vez de repetir o envLabel (que fica "Snapshot · comparar" nos 2 lados).
      if(meta.mode === 'snapshot'){
        if(meta.pipeSrc || meta.pipeDst){
          const parseLabel = s => {
            const parts = (s || '').split(' · ');
            return parts.length >= 2 ? { tag: parts[0], name: parts.slice(1).join(' · ') } : { tag: 'Pipe', name: s || '—' };
          };
          const MAX = 20;
          const trunc = s => s.length > MAX ? s.slice(0, MAX - 1) + '…' : s;
          const applyEllipsis = el => {
            el.style.maxWidth = '180px';
            el.style.whiteSpace = 'nowrap';
            el.style.overflow = 'hidden';
            el.style.textOverflow = 'ellipsis';
          };
          const src = parseLabel(meta.pipeSrc);
          const dst = parseLabel(meta.pipeDst);
          if(envTags[0]) envTags[0].textContent = src.tag;
          if(envNames[0]){
            envNames[0].textContent = trunc(src.name);
            envNames[0].title = src.name;
            applyEllipsis(envNames[0]);
          }
          if(envTags[1]) envTags[1].textContent = dst.tag;
          if(envNames[1]){
            envNames[1].textContent = trunc(dst.name);
            envNames[1].title = dst.name;
            applyEllipsis(envNames[1]);
          }
        } else {
          if(envNames[0] && meta.envLabel) envNames[0].textContent = meta.envLabel;
          if(envNames[1] && meta.envLabel) envNames[1].textContent = meta.envLabel;
        }
      } else {
        // Cross/single/batch/ipaas: comportamento legado (envLabel nos 2 ou override cross)
        if(envNames[0] && meta.envLabel) envNames[0].textContent = meta.envLabel;
        if(envNames[1] && meta.envLabel) envNames[1].textContent = meta.envLabel;
        if(meta.mode === 'cross' && meta.config && window.V2Utils){
          const m = window.V2Utils.parseCrossConfigMeta(meta.config);
          if(envNames[0] && m.srcEnvId) envNames[0].textContent = m.srcEnvId;
          if(envNames[1] && m.dstEnvId) envNames[1].textContent = m.dstEnvId;
        }
      }
    }

    function applyResults(data){
      PARSED_DIVS = (data.divergencias || []).map(parseDivergence);
      const total = PARSED_DIVS.length;

      const byCat = {};
      const bySev = { err: 0, warn: 0, info: 0 };
      const bySevByCat = {}; // { FA: {err:X, warn:Y, info:Z}, ... }
      PARSED_DIVS.forEach(d => {
        byCat[d.cat] = (byCat[d.cat] || 0) + 1;
        bySev[d.sev]++;
        if(!bySevByCat[d.cat]) bySevByCat[d.cat] = { err: 0, warn: 0, info: 0 };
        bySevByCat[d.cat][d.sev]++;
      });

      // KPI total
      const kpiNumBad = document.querySelector('.kpi-num.bad');
      if(kpiNumBad) kpiNumBad.textContent = total;

      // KPI sub-values: substitui mocks por dados reais/calculados
      const allKpis = document.querySelectorAll('.kpi');
      if(allKpis[0]){
        const sub = allKpis[0].querySelector('.kpi-sub');
        if(sub){
          const d = new Date(data.metadata && data.metadata.timestamp || Date.now());
          const hh = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
          sub.textContent = 'registradas às ' + hh;
        }
      }
      if(allKpis[1]){
        // Automações comparadas — sem dado exato do backend, pega count de divergências de automação
        const autoCount = (byCat.AS || 0) + (byCat.AD || 0) + (byCat.AH || 0) + (byCat.AC || 0);
        const num = allKpis[1].querySelector('.kpi-num');
        const sub = allKpis[1].querySelector('.kpi-sub');
        if(num) num.textContent = autoCount;
        if(sub) sub.textContent = 'com divergências de automação';
      }
      if(allKpis[2]){
        // Tempo de execução: pega elapsedFinal do sessionStorage se disponível
        const num = allKpis[2].querySelector('.kpi-num');
        const sub = allKpis[2].querySelector('.kpi-sub');
        let elapsedFinal = null;
        let elapsedLabel = null;
        try {
          const sessMeta = JSON.parse(sessionStorage.getItem('v2-run-meta') || 'null');
          if(sessMeta){
            elapsedFinal = sessMeta.elapsedFinal;
            elapsedLabel = sessMeta.elapsedFinalLabel;
          }
        } catch(e){}
        if(num){
          if(elapsedFinal != null){
            num.innerHTML = elapsedFinal.toFixed(3) + '<span style="font-size:14px;color:var(--muted);margin-left:2px">s</span>';
          } else {
            num.innerHTML = '—<span style="font-size:14px;color:var(--muted);margin-left:2px">s</span>';
          }
        }
        if(sub){
          if(elapsedLabel){
            sub.textContent = 'duração total · ' + (data.metadata && data.metadata.tool_version ? 'v' + data.metadata.tool_version : 'validator');
          } else {
            sub.textContent = data.metadata && data.metadata.tool_version ? 'validator v' + data.metadata.tool_version : 'duração indisponível';
          }
        }
      }

      // Atualiza também a Duração na meta block (com valor real do run)
      try {
        const sessMeta2 = JSON.parse(sessionStorage.getItem('v2-run-meta') || 'null');
        if(sessMeta2){
          const elMetaElap = document.getElementById('meta-elapsed');
          const label = sessMeta2.elapsedFinalLabel
                     || (typeof sessMeta2.elapsedFinal === 'number' ? sessMeta2.elapsedFinal.toFixed(3) + 's' : null);
          if(elMetaElap && label) elMetaElap.textContent = label;
        }
      } catch(e){}
      if(allKpis[3]){
        // Categorias afetadas: real count
        const cats = Object.keys(byCat).filter(c => byCat[c] > 0).length;
        const num = allKpis[3].querySelector('.kpi-num');
        const sub = allKpis[3].querySelector('.kpi-sub');
        if(num){
          num.innerHTML = cats + '<span style="font-size:14px;color:var(--muted);margin-left:4px">/ 7</span>';
        }
        if(sub){
          sub.textContent = cats === 0 ? 'nenhuma afetada' :
                            cats === 7 ? 'todas afetadas' :
                            cats + ' afetadas · ' + (7 - cats) + ' limpas';
        }
      }

      // Run status
      const runStatusTxt = document.querySelector('.run-status .txt');
      if(runStatusTxt){
        runStatusTxt.textContent = total === 0 ? 'OK · 0 diffs' : 'FAILED · ' + total + ' diffs';
      }

      // Showing counter
      const showing = document.querySelector('.showing');
      if(showing) showing.innerHTML = '<b>' + total + '</b> de <b>' + total + '</b>';

      // Meta da run via sessionStorage (Run ID, breadcrumb, flow hero)
      applyRunMetaFromSession(data);

      // (Duração já é atualizada via #meta-elapsed acima a partir do sessionStorage)

      // Pipe names da meta (o primeiro meta-value.muted é pipe). Trunca pra não estourar layout.
      const metaPipeValue = document.querySelectorAll('.meta-block .meta-value.muted')[0];
      if(metaPipeValue && data.pipe_origem){
        const pipeName = String(data.pipe_origem).split('·')[0].trim();
        const MAX = 26;
        const short = pipeName.length > MAX ? pipeName.slice(0, MAX - 1) + '…' : pipeName;
        metaPipeValue.textContent = '';
        metaPipeValue.appendChild(document.createTextNode(short));
        metaPipeValue.title = pipeName;
        metaPipeValue.style.maxWidth = '220px';
        metaPipeValue.style.whiteSpace = 'nowrap';
        metaPipeValue.style.overflow = 'hidden';
        metaPipeValue.style.textOverflow = 'ellipsis';
        metaPipeValue.style.display = 'inline-block';
        metaPipeValue.style.verticalAlign = 'middle';
      }

      // Stacked bar popover: atualiza data-attributes dos segmentos com counts reais
      document.querySelectorAll('.stacked-seg').forEach(seg => {
        const cat = seg.dataset.cat;
        const count = byCat[cat] || 0;
        const pct = total > 0 ? (count / total * 100).toFixed(1) : '0';
        const sevBreakdown = bySevByCat[cat] || { err: 0, warn: 0, info: 0 };
        seg.setAttribute('data-count', count);
        seg.setAttribute('data-err', sevBreakdown.err);
        seg.setAttribute('data-warn', sevBreakdown.warn);
        seg.setAttribute('data-info', sevBreakdown.info);
        seg.setAttribute('data-pct', pct);
        // Trend fica mock (backend não expõe acúmulo temporal)
      });

      // Quando run é OK sem diffs: hero no centro + checklist na direita (estilo legacy)
      if(total === 0){
        hideStackedSection();
        renderPipefyOkPanel(data);
      } else {
        showStackedSection();
      }

      // Lista de divergências — substitui TODAS as rows mock
      const listEl = document.getElementById('list');
      if(listEl){
        if(total === 0){
          // listEl já foi tratado por renderPipefyOkPanel acima
        } else {
          listEl.innerHTML = PARSED_DIVS.map((d, i) => (
            '<div class="row' + (i === 0 ? ' selected' : '') + '" data-idx="' + d.idx + '">' +
              '<span class="col-num">' + String(d.idx).padStart(3, '0') + '</span>' +
              '<span class="col-cat"><span class="cat-chip cat-' + d.cat + '">' + d.cat + '</span></span>' +
              '<span class="col-type">' + escapeHtml(d.type) + '</span>' +
              '<span class="col-path">' + escapeHtml(d.path) + '</span>' +
              '<span class="col-field">' + escapeHtml(d.detail) + '</span>' +
              '<span class="col-sev"><span class="sev-dot ' + d.sev + '"></span><span class="sev-label">' + d.sev + '</span></span>' +
            '</div>'
          )).join('');
        }
        // Wire up click handlers
        listEl.querySelectorAll('.row').forEach(row => {
          row.addEventListener('click', () => {
            listEl.querySelectorAll('.row').forEach(r => r.classList.remove('selected'));
            row.classList.add('selected');
            const idx = parseInt(row.dataset.idx, 10);
            const d = PARSED_DIVS[idx - 1];
            if(d) updateDiffPanel(d);
          });
        });
      }

      // Stacked bar segments — usa contadores reais
      document.querySelectorAll('.stacked-seg').forEach(seg => {
        const cat = seg.dataset.cat;
        const count = byCat[cat] || 0;
        const pct = total > 0 ? (count / total * 100).toFixed(1) : '0';
        if(count === 0){
          seg.style.flex = '0';
          seg.style.display = 'none';
        } else {
          seg.style.flex = count;
          seg.style.display = '';
          seg.dataset.count = count;
          seg.dataset.pct = pct;
        }
      });

      // Facets na sidebar esquerda — atualiza contadores
      const catLabelMap = {
        'Start Form': 'SF',
        'Fases & Campos': 'FA',
        'Labels': 'LB',
        'Automação · Status': 'AS',
        'Automação · Fase Destino': 'AD',
        'Automação · HTTP': 'AH',
        'Automação · Condition': 'AC',
      };
      document.querySelectorAll('.filter-section .facet').forEach(f => {
        const nameEl = f.querySelector('.name');
        const countEl = f.querySelector('.count');
        if(!nameEl || !countEl) return;
        const name = nameEl.textContent.trim();
        const cat = catLabelMap[name];
        if(cat) countEl.textContent = byCat[cat] || 0;
      });

      // Severity pills
      document.querySelectorAll('.sev-pill').forEach(pill => {
        const cntEl = pill.querySelector('.sev-count');
        if(!cntEl) return;
        if(pill.classList.contains('err')) cntEl.textContent = bySev.err;
        else if(pill.classList.contains('warn')) cntEl.textContent = bySev.warn;
        else if(pill.classList.contains('info')) cntEl.textContent = bySev.info;
      });

      // --- DONUT CHART na sidebar: distribuição por categoria ---
      renderSidebarDonut(byCat, total);

      // --- FASE facets: repopula do dado real (removendo mock hardcoded) ---
      const byFase = {};
      PARSED_DIVS.forEach(d => { if(d.fase) byFase[d.fase] = (byFase[d.fase] || 0) + 1; });

      document.querySelectorAll('.filter-section').forEach(section => {
        const title = section.querySelector('.filter-title');
        if(!title) return;
        const label = title.textContent.trim();

        if(label === 'Fase'){
          const list = section.querySelector('.src-list');
          const fases = Object.entries(byFase).sort((a, b) => b[1] - a[1]);
          if(fases.length === 0){
            section.style.display = 'none';
          } else {
            section.style.display = '';
            if(list){
              list.innerHTML = fases.map(([name, count]) => (
                '<div class="facet" data-fase="' + escapeHtml(name) + '" style="opacity:.7" title="Fases são apenas referência, filtro por fase não está ativo">'
                + '<span class="check"></span>'
                + '<span class="name">' + escapeHtml(name) + '</span>'
                + '<span class="count">' + count + '</span>'
                + '</div>'
              )).join('');
            }
          }
        } else if(label === 'Ambiente origem'){
          // Esconde: pra uma validação única não faz sentido
          section.style.display = 'none';
        }
      });

      // Abre primeira no diff panel
      if(PARSED_DIVS.length > 0) updateDiffPanel(PARSED_DIVS[0]);
    }

    /* Parse divergence raw string pra extrair valores origem/destino */
    function parseDiffValues(raw){
      // Padrão 1: Origem="X" | Destino="Y"
      let m = raw.match(/Origem\s*=\s*"([^"]*)"\s*\|\s*Destino\s*=\s*"([^"]*)"/i);
      if(m) return { kind: 'modified', origem: m[1], destino: m[2] };

      // Padrão 2: Origem=X | Destino=Y (sem aspas)
      m = raw.match(/Origem\s*=\s*([^\s|]+)\s*\|\s*Destino\s*=\s*([^\s|]+)/i);
      if(m) return { kind: 'modified', origem: m[1], destino: m[2] };

      // Padrão 3: existe no Destino mas NAO no Origem (added no destino)
      if(/existe no\s+Destino\s+mas\s+(NAO|não)\s+no\s+Origem/i.test(raw)){
        const nameMatch = raw.match(/Campo\s+"([^"]+)"|Fase\s+"([^"]+)"|Label\s+"([^"]+)"/i);
        const name = nameMatch ? (nameMatch[1] || nameMatch[2] || nameMatch[3]) : '(item)';
        return { kind: 'added', origem: '(ausente)', destino: name };
      }

      // Padrão 4: existe no Origem mas NAO no Destino (removed no destino)
      if(/existe no\s+Origem\s+mas\s+(NAO|não)\s+no\s+Destino/i.test(raw)){
        const nameMatch = raw.match(/Campo\s+"([^"]+)"|Fase\s+"([^"]+)"|Label\s+"([^"]+)"/i);
        const name = nameMatch ? (nameMatch[1] || nameMatch[2] || nameMatch[3]) : '(item)';
        return { kind: 'removed', origem: name, destino: '(ausente)' };
      }

      // Padrão 5: " → " indicando mudança
      m = raw.match(/:\s*(.+?)\s*(?:→|->)\s*(.+)$/);
      if(m) return { kind: 'modified', origem: m[1].trim(), destino: m[2].trim() };

      return { kind: 'unknown', origem: '', destino: '' };
    }

    /* Monta coluna de diff com línhas numeradas */
    function buildDiffColumn(env, tag, tagClass, d, parsed, isOrigem){
      const value = isOrigem ? parsed.origem : parsed.destino;
      const markClass = parsed.kind === 'modified' ? 'mod'
                      : parsed.kind === 'added' ? (isOrigem ? 'rem' : 'add')
                      : parsed.kind === 'removed' ? (isOrigem ? 'add' : 'rem')
                      : '';
      const markChar = parsed.kind === 'modified' ? '~'
                     : parsed.kind === 'added' ? (isOrigem ? '−' : '+')
                     : parsed.kind === 'removed' ? (isOrigem ? '+' : '−')
                     : ' ';

      const lines = [];
      lines.push('<div class="dline"><span class="dnum">01</span><span class="dmark"> </span><span class="dtxt"><span class="dim"># ' + escapeHtml(d.type) + '</span></span></div>');
      lines.push('<div class="dline"><span class="dnum">02</span><span class="dmark"> </span><span class="dtxt"><span class="dim"># path:</span> ' + escapeHtml(d.path) + '</span></div>');
      lines.push('<div class="dline"><span class="dnum">03</span><span class="dmark"> </span><span class="dtxt"></span></div>');

      if(parsed.kind === 'unknown'){
        // Sem valores parseáveis, mostra o detail bruto
        const detail = d.detail || d.raw;
        const wrapped = wrapLines(detail, 70);
        wrapped.forEach((ln, i) => {
          lines.push('<div class="dline"><span class="dnum">' + String(i+4).padStart(2,'0') + '</span><span class="dmark"> </span><span class="dtxt">' + escapeHtml(ln) + '</span></div>');
        });
      } else {
        lines.push('<div class="dline ' + markClass + '"><span class="dnum">04</span><span class="dmark">' + markChar + '</span><span class="dtxt"><span class="key">value</span>: <span class="str">' + escapeHtml(String(value)) + '</span></span></div>');
      }

      return '<div class="diff-col">'
           + '<div class="diff-colhead ' + (isOrigem ? 'left' : 'right') + '">'
           + escapeHtml(env) + ' <span class="tag">' + tag + '</span>'
           + '</div>'
           + lines.join('')
           + '</div>';
    }

    function wrapLines(text, width){
      const out = [];
      const words = String(text).split(/\s+/);
      let line = '';
      words.forEach(w => {
        if((line + ' ' + w).trim().length > width){
          if(line) out.push(line.trim());
          line = w;
        } else {
          line += ' ' + w;
        }
      });
      if(line.trim()) out.push(line.trim());
      return out.length ? out : [''];
    }

    function updateDiffPanel(d){
      const title = document.querySelector('.right-title');
      if(title){
        title.innerHTML = '<span class="badge cat-' + d.cat + '">' + d.cat + '</span>' + escapeHtml(d.catName);
      }
      const metaVals = document.querySelectorAll('.right-meta .v');
      // Ordem HTML: ID, Fase, Trigger, Campo afetado, Severidade, Detectado em
      if(metaVals[0]) metaVals[0].textContent = d.type;
      if(metaVals[1]) metaVals[1].textContent = (d.path.split('>')[0] || '').trim();
      if(metaVals[2]) metaVals[2].textContent = d.cat + ' · ' + d.catName;  // Trigger/contexto
      if(metaVals[3]) metaVals[3].textContent = (d.path.split('>').pop() || '').trim().split(':')[0].trim();

      // Severidade — atualiza texto E cor pra refletir o valor real
      if(metaVals[4]){
        const sevColorMap = { err: 'var(--red)', warn: 'var(--yellow)', info: 'var(--blue)' };
        const sevLabel = { err: 'error', warn: 'warn', info: 'info' };
        metaVals[4].textContent = sevLabel[d.sev] || d.sev;
        metaVals[4].style.color = sevColorMap[d.sev] || 'var(--ink-2)';
      }

      // Detectado em — se tiver timestamp no JSON, usa; senão deixa placeholder
      if(metaVals[5]) metaVals[5].textContent = '—';

      const parsed = parseDiffValues(d.raw);

      // Pipe names da meta atual — usa os mostrados na tela
      const metaPipeText = document.querySelector('.meta-block .meta-value.muted');
      const currentPipe = metaPipeText ? (metaPipeText.childNodes[0].nodeValue || '').trim() : 'origem';

      // Tenta tirar origem/destino dos pipe names; se não, usa rótulos genéricos
      const envOrigem = 'origem · ' + currentPipe.slice(0, 30);
      const envDestino = 'destino · ' + currentPipe.slice(0, 30);

      const diffBody = document.querySelector('.diff-body');
      if(!diffBody) return;

      if(parsed.kind === 'unknown'){
        // Fallback: mostra raw em ambas colunas pra contexto
        diffBody.innerHTML = '<div class="diff-cols">'
          + buildDiffColumn(envOrigem, 'baseline', 'left', d, parsed, true)
          + buildDiffColumn(envDestino, 'current', 'right', d, parsed, false)
          + '</div>';
      } else {
        diffBody.innerHTML = '<div class="diff-cols">'
          + buildDiffColumn(envOrigem, 'baseline', 'left', d, parsed, true)
          + buildDiffColumn(envDestino, 'current', 'right', d, parsed, false)
          + '</div>';
      }

      // Atualiza o footer com stats
      const foot = document.querySelector('.right-foot');
      if(foot){
        const stats = parsed.kind === 'modified' ? '<span class="stat"><span class="mod-c">~</span><b>1</b> modified</span>'
                    : parsed.kind === 'added' ? '<span class="stat"><span class="add-c">+</span><b>1</b> added</span>'
                    : parsed.kind === 'removed' ? '<span class="stat"><span class="rem-c">−</span><b>1</b> removed</span>'
                    : '<span class="stat"><b>1</b> diff</span>';
        foot.innerHTML = stats
                      + '<span class="spacer"></span>'
                      + '<span class="stat">kind: <b>' + parsed.kind + '</b></span>';
      }
    }

    /* ============================================================
       ETAPA POLISH: FILTROS FUNCIONAIS
       ============================================================ */

    const activeFilters = {
      cats: new Set(['SF','FA','LB','AS','AD','AH','AC']),
      sevs: new Set(['err','warn','info']),
      search: '',
    };

    function applyFilters(){
      const listEl = document.getElementById('list');
      if(!listEl) return;
      const term = activeFilters.search.toLowerCase();
      let visibleCount = 0;
      let bySevVisible = { err: 0, warn: 0, info: 0 };
      const rows = listEl.querySelectorAll('.row');
      rows.forEach(row => {
        const idx = parseInt(row.dataset.idx, 10);
        const d = PARSED_DIVS[idx - 1];
        if(!d){ row.style.display = ''; return; }
        const catOK = activeFilters.cats.has(d.cat);
        const sevOK = activeFilters.sevs.has(d.sev);
        const searchOK = !term || d.raw.toLowerCase().includes(term);
        const show = catOK && sevOK && searchOK;
        row.style.display = show ? '' : 'none';
        if(show){
          visibleCount++;
          bySevVisible[d.sev] = (bySevVisible[d.sev] || 0) + 1;
        }
      });
      const showing = document.querySelector('.showing');
      if(showing) showing.innerHTML = '<b>' + visibleCount + '</b> de <b>' + PARSED_DIVS.length + '</b>';

      // Visual feedback nas pills: se inativas, fica opacas
      document.querySelectorAll('.sev-pill').forEach(pill => {
        const isActive = pill.classList.contains('active');
        pill.style.opacity = isActive ? '1' : '.4';
      });
      // Facets idem
      document.querySelectorAll('.filter-section .facet').forEach(f => {
        const isActive = f.classList.contains('active');
        f.style.opacity = isActive ? '1' : '.45';
      });
    }

    function wireFilterFacets(){
      document.querySelectorAll('.filter-section .facet').forEach(f => {
        if(f.dataset.wired === '1') return;
        f.dataset.wired = '1';
        f.addEventListener('click', () => {
          const nameEl = f.querySelector('.name');
          if(!nameEl) return;
          const catMap = {
            'Start Form':'SF','Fases & Campos':'FA','Labels':'LB',
            'Automação · Status':'AS','Automação · Fase Destino':'AD',
            'Automação · HTTP':'AH','Automação · Condition':'AC',
          };
          const cat = catMap[nameEl.textContent.trim()];
          if(!cat) return;
          if(activeFilters.cats.has(cat)){
            activeFilters.cats.delete(cat);
            f.classList.remove('active');
          } else {
            activeFilters.cats.add(cat);
            f.classList.add('active');
          }
          applyFilters();
        });
      });
    }

    function wireSeverityPills(){
      document.querySelectorAll('.sev-pill').forEach(pill => {
        if(pill.dataset.wired === '1') return;
        pill.dataset.wired = '1';
        pill.addEventListener('click', () => {
          let sev = 'info';
          if(pill.classList.contains('err')) sev = 'err';
          else if(pill.classList.contains('warn')) sev = 'warn';

          if(activeFilters.sevs.has(sev)){
            activeFilters.sevs.delete(sev);
            pill.classList.remove('active');
          } else {
            activeFilters.sevs.add(sev);
            pill.classList.add('active');
          }

          console.log('[v2] sev filter: clicked=' + sev + ' · active=[' + [...activeFilters.sevs].join(',') + ']');

          // Visual pulse pra dar feedback
          pill.style.transition = 'transform .15s, box-shadow .2s';
          pill.style.transform = 'scale(0.95)';
          pill.style.boxShadow = '0 0 0 3px rgba(201,168,76,.25)';
          setTimeout(() => {
            pill.style.transform = '';
            pill.style.boxShadow = '';
          }, 180);

          applyFilters();
        });
      });
    }

    function wireSearchBox(){
      const input = document.querySelector('.search input');
      if(!input || input.dataset.wired === '1') return;
      input.dataset.wired = '1';
      let debounceTimer = null;
      input.addEventListener('input', (e) => {
        if(debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          activeFilters.search = e.target.value.trim();
          applyFilters();
        }, 120);
      });
    }

    function wireStackedSegClicks(){
      document.querySelectorAll('.stacked-seg').forEach(seg => {
        if(seg.dataset.wiredClick === '1') return;
        seg.dataset.wiredClick = '1';
        seg.addEventListener('click', () => {
          const cat = seg.dataset.cat;
          if(!cat) return;
          // Isola: seleciona só esta categoria
          const wasOnly = activeFilters.cats.size === 1 && activeFilters.cats.has(cat);
          activeFilters.cats.clear();
          if(!wasOnly) activeFilters.cats.add(cat);
          else ['SF','FA','LB','AS','AD','AH','AC'].forEach(c => activeFilters.cats.add(c));
          // Reflete no UI dos facets
          document.querySelectorAll('.filter-section .facet').forEach(f => {
            const nameEl = f.querySelector('.name');
            if(!nameEl) return;
            const catMap = {
              'Start Form':'SF','Fases & Campos':'FA','Labels':'LB',
              'Automação · Status':'AS','Automação · Fase Destino':'AD',
              'Automação · HTTP':'AH','Automação · Condition':'AC',
            };
            const facetCat = catMap[nameEl.textContent.trim()];
            if(facetCat) f.classList.toggle('active', activeFilters.cats.has(facetCat));
          });
          applyFilters();
        });
      });
    }

    function wireClearFilter(){
      document.querySelectorAll('.filter-clear').forEach(btn => {
        if(btn.dataset.wired === '1') return;
        btn.dataset.wired = '1';
        btn.addEventListener('click', () => {
          // "Limpar" agora é TOGGLE inteligente:
          //  - Se algo está filtrado (nem tudo selecionado) → desmarca tudo (limpa filtros = mostra nada, força user escolher)
          //  - Se tudo já está selecionado (sem filtro) → desmarca tudo (vai pra zero)
          //  - Se nada está selecionado → marca tudo (restaura ao padrão)
          const allCats = ['SF','FA','LB','AS','AD','AH','AC'];
          const allActive = allCats.every(c => activeFilters.cats.has(c));
          const noneActive = allCats.every(c => !activeFilters.cats.has(c));

          if(noneActive){
            // Restore: ativa tudo
            allCats.forEach(c => activeFilters.cats.add(c));
            document.querySelectorAll('.filter-section .facet').forEach(f => f.classList.add('active'));
            btn.textContent = 'limpar';
          } else {
            // Limpa: desmarca todos os filtros de categoria
            activeFilters.cats.clear();
            document.querySelectorAll('.filter-section .facet').forEach(f => f.classList.remove('active'));
            btn.textContent = 'restaurar';
          }
          applyFilters();
        });
      });
    }

    /* ============================================================
       WIRE-UP COMPLETO DE BOTÕES (polish: estava tudo morto)
       ============================================================ */

    /* URL da tela de configuração que preserva o modo/sub em que a run foi disparada.
       Lê do sessionStorage.v2-run-meta que tem mode, config, snapshotSub (quando aplicável). */
    function getConfigUrl(opts){
      opts = opts || {};
      let meta;
      try { meta = JSON.parse(sessionStorage.getItem('v2-run-meta') || 'null'); } catch(e){ meta = null; }
      if(!meta || !meta.mode) return '/v2/configuracao';
      const params = new URLSearchParams();
      params.set('mode', meta.mode);
      if(meta.mode === 'snapshot' && meta.snapshotSub) params.set('sub', meta.snapshotSub);
      if(meta.config) params.set('config', meta.config);
      // Mode label parent (anchor 1 = "Validações"): vai pra home de config sem params
      if(opts.level === 'root') return '/v2/configuracao';
      return '/v2/configuracao?' + params.toString();
    }

    function injectBackButton(){
      const topRight = document.querySelector('.topbar .top-right');
      if(!topRight || document.getElementById('v2-back-btn')) return;
      const btn = document.createElement('button');
      btn.id = 'v2-back-btn';
      btn.style.cssText = 'display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:6px;border:1px solid var(--line-2);background:rgba(255,255,255,.02);color:var(--ink-2);font-size:11.5px;font-weight:500;font-family:var(--sans);cursor:pointer;margin-right:6px';
      btn.innerHTML = '<svg style="width:13px;height:13px;stroke-width:2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>Nova validação';
      btn.title = 'Voltar pra tela de configuração do mesmo modo';
      btn.addEventListener('mouseenter', () => { btn.style.background = 'rgba(201,168,76,.08)'; btn.style.color = 'var(--accent)'; btn.style.borderColor = 'rgba(201,168,76,.3)'; });
      btn.addEventListener('mouseleave', () => { btn.style.background = 'rgba(255,255,255,.02)'; btn.style.color = 'var(--ink-2)'; btn.style.borderColor = 'var(--line-2)'; });
      btn.addEventListener('click', () => { navigateTo(getConfigUrl()); });
      topRight.insertBefore(btn, topRight.firstChild);
    }

    function wireTopbarActions(){
      // anchor 0 = "Validações" (root), anchor 1 = "Cross Env / Snapshot / ..." (mode atual)
      const anchors = document.querySelectorAll('.crumbs a');
      anchors.forEach((a, idx) => {
        if(a.dataset.wired === '1') return;
        a.dataset.wired = '1';
        const isRoot = idx === 0;
        a.addEventListener('click', (e) => {
          e.preventDefault();
          navigateTo(getConfigUrl({ level: isRoot ? 'root' : 'mode' }));
        });
      });
      document.querySelectorAll('.topbar .top-right .icon-btn').forEach(btn => {
        if(btn.dataset.wired === '1') return;
        btn.dataset.wired = '1';
        btn.addEventListener('click', () => { navigateTo(getConfigUrl()); });
      });
    }

    function wireMetaActions(){
      document.querySelectorAll('.meta-action').forEach(a => {
        if(a.dataset.wired === '1') return;
        a.dataset.wired = '1';
        a.addEventListener('click', (e) => {
          e.preventDefault();
          const text = a.textContent.trim().toLowerCase();
          if(text.includes('report')) window.open('/reports/report.html', '_blank');
          else if(text.includes('log')) window.open('/reports/log.html', '_blank');
          else if(text.includes('json')) window.open('/reports/validations.json', '_blank');
        });
      });
    }

    function wireToolbarButtons(){
      document.querySelectorAll('.center-toolbar .tb-btn').forEach(btn => {
        if(btn.dataset.wired === '1') return;
        btn.dataset.wired = '1';
        const tip = btn.getAttribute('data-tip') || '';
        btn.addEventListener('click', () => {
          if(tip.includes('Filtrar')){
            // Foca o campo de busca com pulse visual
            const searchBox = document.querySelector('.search');
            const searchInput = document.querySelector('.search input');
            if(searchInput){
              searchInput.focus();
              searchInput.select();
            }
            if(searchBox){
              searchBox.style.transition = 'box-shadow .4s, border-color .4s';
              searchBox.style.boxShadow = '0 0 0 3px rgba(201,168,76,.3)';
              searchBox.style.borderColor = 'var(--accent)';
              setTimeout(() => {
                searchBox.style.boxShadow = '';
                searchBox.style.borderColor = '';
              }, 600);
            }
          } else if(tip.includes('Agrupar')){
            toggleGroupByCategory();
          } else if(tip.includes('Copiar resumo')){
            copyResumoToClipboard();
          } else if(tip.includes('Mais')){
            alert('Opções extras em breve: exportar CSV/PDF, compartilhar link.');
          }
        });
      });
    }

    function toggleGroupByCategory(){
      const listEl = document.getElementById('list');
      if(!listEl) return;
      const rows = Array.from(listEl.querySelectorAll('.row'));
      const ordered = rows.slice().sort((a, b) => {
        const da = PARSED_DIVS[parseInt(a.dataset.idx, 10) - 1];
        const db = PARSED_DIVS[parseInt(b.dataset.idx, 10) - 1];
        if(!da || !db) return 0;
        const cmp = da.cat.localeCompare(db.cat);
        return cmp !== 0 ? cmp : da.idx - db.idx;
      });
      const differs = rows.some((r, i) => r !== ordered[i]);
      if(differs){
        ordered.forEach(r => listEl.appendChild(r));
      } else {
        // Já está agrupado, desagrupa (volta à ordem original por idx)
        rows.slice().sort((a, b) => parseInt(a.dataset.idx, 10) - parseInt(b.dataset.idx, 10))
            .forEach(r => listEl.appendChild(r));
      }
    }

    async function copyResumoToClipboard(){
      const total = PARSED_DIVS.length;
      const byCat = {};
      PARSED_DIVS.forEach(d => { byCat[d.catName] = (byCat[d.catName] || 0) + 1; });
      const lines = ['Pipefy Validator · resumo de divergências', '========================================', 'Total: ' + total + ' divergências', ''];
      Object.entries(byCat).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => lines.push('  ' + k + ': ' + v));
      const text = lines.join('\n');
      try {
        await navigator.clipboard.writeText(text);
        showToast('Resumo copiado');
      } catch(e) {
        alert('Falha ao copiar: ' + e.message);
      }
    }

    function showToast(msg){
      const t = document.createElement('div');
      t.textContent = msg;
      t.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);padding:8px 18px;border-radius:8px;background:rgba(11,15,26,.95);border:1px solid var(--accent);color:var(--accent);font-size:12px;font-weight:500;font-family:var(--sans);z-index:999;box-shadow:0 8px 24px rgba(0,0,0,.4);opacity:0;transition:opacity .2s';
      document.body.appendChild(t);
      requestAnimationFrame(() => { t.style.opacity = '1'; });
      setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 220); }, 1800);
    }

    function wireRightPanelButtons(){
      document.querySelectorAll('.right-actions .icon-btn').forEach(btn => {
        if(btn.dataset.wired === '1') return;
        btn.dataset.wired = '1';
        const tip = btn.getAttribute('data-tip') || '';
        btn.addEventListener('click', () => {
          if(tip.includes('Copiar')) copyDiffToClipboard();
          else if(tip.includes('Pipefy')) alert('Abrir no Pipefy: requer configuração do URL template. Em breve.');
          else if(tip.includes('Próxima') || tip.includes('Next')) selectNextRow();
          else if(tip.includes('Anterior') || tip.includes('Prev')) selectPrevRow();
        });
      });
    }

    async function copyDiffToClipboard(){
      const selected = document.querySelector('.row.selected');
      if(!selected) return;
      const idx = parseInt(selected.dataset.idx, 10);
      const d = PARSED_DIVS[idx - 1];
      if(!d) return;
      try {
        await navigator.clipboard.writeText(d.raw);
        showToast('Diff copiado');
      } catch(e) { alert('Falha ao copiar: ' + e.message); }
    }

    function selectNextRow(){
      const all = Array.from(document.querySelectorAll('.row')).filter(r => r.style.display !== 'none');
      const idx = all.findIndex(r => r.classList.contains('selected'));
      if(idx < 0) { if(all[0]) all[0].click(); return; }
      const next = all[Math.min(all.length - 1, idx + 1)];
      if(next && next !== all[idx]){
        next.click();
        next.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }

    function selectPrevRow(){
      const all = Array.from(document.querySelectorAll('.row')).filter(r => r.style.display !== 'none');
      const idx = all.findIndex(r => r.classList.contains('selected'));
      if(idx <= 0) return;
      const prev = all[idx - 1];
      prev.click();
      prev.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function wireRightTabs(){
      document.querySelectorAll('.right-tab').forEach(tab => {
        if(tab.dataset.wired === '1') return;
        tab.dataset.wired = '1';
        tab.addEventListener('click', () => {
          document.querySelectorAll('.right-tab').forEach(t => t.classList.remove('active'));
          tab.classList.add('active');
          const label = tab.textContent.trim().toLowerCase();
          const selected = document.querySelector('.row.selected');
          const idx = selected ? parseInt(selected.dataset.idx, 10) : 1;
          const d = PARSED_DIVS[idx - 1];
          if(!d) return;
          const diffBody = document.querySelector('.diff-body');
          if(!diffBody) return;

          if(label.includes('side-by-side')){
            updateDiffPanel(d);
          } else if(label.includes('unified')){
            const parsed = parseDiffValues(d.raw);
            diffBody.innerHTML = '<div style="padding:20px;font-family:var(--mono);font-size:12px;line-height:1.65">'
              + '<div style="color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px">' + escapeHtml(d.type) + '</div>'
              + '<div style="color:var(--ink-2);font-size:11px;margin-bottom:14px">path: ' + escapeHtml(d.path) + '</div>'
              + (parsed.kind === 'unknown'
                 ? '<pre style="color:var(--ink-2);white-space:pre-wrap">' + escapeHtml(d.raw) + '</pre>'
                 : '<div style="background:rgba(224,101,101,.06);padding:6px 10px;color:#efa5a5;border-left:2px solid var(--red);margin-bottom:2px">- value: ' + escapeHtml(parsed.origem) + '</div>'
                 + '<div style="background:rgba(108,194,108,.06);padding:6px 10px;color:#b8e0b8;border-left:2px solid var(--green)">+ value: ' + escapeHtml(parsed.destino) + '</div>')
              + '</div>';
          } else if(label.includes('raw')){
            diffBody.innerHTML = '<pre style="padding:22px;color:var(--ink-2);white-space:pre-wrap;word-break:break-word;font-family:var(--mono);font-size:12px;line-height:1.65">' + escapeHtml(d.raw) + '</pre>';
          } else if(label.includes('context')){
            const ctx = { idx: d.idx, type: d.type, category: d.cat + ' · ' + d.catName, severity: d.sev, path: d.path, detail: d.detail };
            diffBody.innerHTML = '<pre style="padding:22px;color:var(--ink-2);white-space:pre;font-family:var(--mono);font-size:12px;line-height:1.7">' + escapeHtml(JSON.stringify(ctx, null, 2)) + '</pre>';
          }
        });
      });
    }

    // Wire tudo após o primeiro render
    setTimeout(() => {
      injectBackButton();
      wireTopbarActions();
      wireMetaActions();
      wireFilterFacets();
      wireSeverityPills();
      wireSearchBox();
      wireStackedSegClicks();
      wireClearFilter();
      wireToolbarButtons();
      wireRightPanelButtons();
      wireRightTabs();
    }, 300);

    loadResults();
  })();
