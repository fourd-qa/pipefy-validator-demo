/**
 * v2_utils.js — funções utilitárias puras compartilhadas entre os arquivos do V2.
 *
 * Exporta como módulo CommonJS (Node/vitest) e como global window.V2Utils (browser).
 * Foi extraído pra permitir unit tests sem refatorar os IIFEs grandes.
 */
(function(global){
  'use strict';

  function slugify(s){
    return String(s || '').toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_|_$/g, '');
  }

  function escapeHtml(s){
    return String(s || '').replace(/[&<>"]/g, function(c){
      return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c];
    });
  }

  /** Trunca string mantendo início e fim, com … no meio quando passa do max. */
  function truncMid(s, max){
    s = String(s || '');
    if(s.length <= max) return s;
    var half = Math.floor((max - 1) / 2);
    return s.slice(0, half) + '…' + s.slice(s.length - half);
  }

  /** Parse id de cross config (cross_<src>_x_<dst> ou cross_<x>_selfcheck) pra extrair env_ids. */
  function parseCrossConfigMeta(id){
    var clean = String(id || '').replace(/^cross_/, '');
    var selfMatch = clean.match(/^(.+)_selfcheck$/i);
    if(selfMatch){
      var envId = selfMatch[1];
      return { src: envId, dst: envId, srcEnvId: envId, dstEnvId: envId, status: 'ok', hint: '0 diffs esperados' };
    }
    var crossMatch = clean.match(/^(.+?)_x_(.+)$/);
    if(crossMatch){
      return { src: crossMatch[1], dst: crossMatch[2], srcEnvId: crossMatch[1], dstEnvId: crossMatch[2], status: 'typical', hint: 'validação cruzada' };
    }
    return {
      src: clean || 'origem',
      dst: clean || 'destino',
      srcEnvId: null,
      dstEnvId: null,
      status: 'typical',
      hint: 'validação cruzada',
    };
  }

  /** Verifica se ambos ambientes do cross têm token configurado.
   *  envsData = { pipefy: [{id, name, has_token}] } */
  function getCrossTokenStatus(crossId, envsData){
    var meta = parseCrossConfigMeta(crossId);
    if(!envsData || !meta.srcEnvId || !meta.dstEnvId){
      return { ok: true, missing: [], labels: [] };
    }
    var pipefyList = envsData.pipefy || [];
    function findEnv(id){ return pipefyList.find(function(e){ return e.id === id; }); }
    var srcEnv = findEnv(meta.srcEnvId);
    var dstEnv = findEnv(meta.dstEnvId);
    var missing = [];
    var labels = [];
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

  /** Computa label sugerido pra snapshot baseado em pipe + env. */
  function computeSuggestedSnapLabel(pipeName, envId){
    var pipeSlug = slugify(pipeName || '');
    if(!pipeSlug) return '';
    return envId ? (pipeSlug + '_' + envId) : pipeSlug;
  }

  /** Categorias de divergência. Mapeamento tag → categoria visual. */
  var CATEGORIES = [
    { cat: 'SF', name: 'Start Form',           match: function(t){ return /START FORM/i.test(t); } },
    { cat: 'LB', name: 'Labels',               match: function(t){ return /\bLABEL\b/i.test(t); } },
    { cat: 'AD', name: 'Auto · Fase Destino',  match: function(t){ return /FASE_DESTINO|FASE_EVENTO/i.test(t); } },
    { cat: 'AH', name: 'Auto · HTTP',          match: function(t){ return /HTTP_METHOD|HTTP_BODY|HTTP_HEADERS|AUTOMACAO URL/i.test(t); } },
    { cat: 'AC', name: 'Auto · Condition',     match: function(t){ return /(AUTOMACAO )?CONDITION|TRIGGER/i.test(t) && !/IPAAS/i.test(t); } },
    { cat: 'AS', name: 'Auto · Status',        match: function(t){ return /AUTOMACAO STATUS|AUTOMACAO ACTION|AUTOMACAO EVENT|AUTOMACAO AUSENTE|AUTOMACAO EXTRA/i.test(t); } },
    { cat: 'FA', name: 'Fases & Campos',       match: function(t){ return /FASE|CAMPO|TIPO|REQUIRED|OPTIONS/i.test(t); } },
  ];

  function categorize(text){
    var t = String(text || '');
    for(var i = 0; i < CATEGORIES.length; i++){
      if(CATEGORIES[i].match(t)) return { cat: CATEGORIES[i].cat, name: CATEGORIES[i].name };
    }
    return { cat: 'FA', name: 'Fases & Campos' };
  }

  function severityOf(text){
    var t = String(text || '');
    if(/CAMPO EXTRA|CAMPO AUSENTE|REMOVID|NAO\b/i.test(t)) return 'warn';
    if(/info|adicionada|nova/i.test(t) && !/error/i.test(t)) return 'info';
    return 'err';
  }

  /* ===================== VAULT (envs client-side) ======================
     Tokens vivem em local/sessionStorage do navegador. Backend nunca persiste.
     - localStorage[VAULT_KEY]: lista de envs persistentes ("Lembrar")
     - sessionStorage[VAULT_KEY]: envs só dessa sessão (não salvos no disco)
     Schema do env:
       { id, name, type: 'pipefy'|'ipaas', base_url, org_id, auth_mode,
         verify_ssl, token, session_cookie?, csrf_token?, project_id?,
         pipes: [{name, uuid, repo_id}], remember: bool }
     ===================================================================== */
  var VAULT_KEY = 'pv-vault-v1';

  function _readStore(store){
    try {
      var raw = store.getItem(VAULT_KEY);
      if(!raw) return [];
      var arr = JSON.parse(raw);
      return Array.isArray(arr) ? arr : [];
    } catch(_) { return []; }
  }

  function _writeStore(store, list){
    try { store.setItem(VAULT_KEY, JSON.stringify(list || [])); } catch(_) {}
  }

  /** Retorna lista mesclada de envs: localStorage (persistentes) + sessionStorage (efêmeros). */
  function vaultList(){
    if(typeof window === 'undefined') return [];
    var persisted = _readStore(window.localStorage || {getItem: function(){return null;}});
    var ephemeral = _readStore(window.sessionStorage || {getItem: function(){return null;}});
    var seen = {};
    var out = [];
    persisted.forEach(function(e){ if(e && e.id){ seen[e.id] = true; out.push(e); }});
    ephemeral.forEach(function(e){ if(e && e.id && !seen[e.id]){ out.push(e); }});
    return out;
  }

  /** Salva env no vault. Se remember=true vai pra localStorage, senão sessionStorage. */
  function vaultSave(env){
    if(typeof window === 'undefined' || !env || !env.id) return false;
    var remember = env.remember !== false;
    var primary = remember ? window.localStorage : window.sessionStorage;
    var other = remember ? window.sessionStorage : window.localStorage;
    var list = _readStore(primary);
    var idx = list.findIndex(function(e){ return e.id === env.id; });
    if(idx >= 0) list[idx] = env;
    else list.push(env);
    _writeStore(primary, list);
    // Remove de "outro" se mudou de remember
    var otherList = _readStore(other).filter(function(e){ return e.id !== env.id; });
    _writeStore(other, otherList);
    return true;
  }

  /** Remove env do vault (ambos stores). */
  function vaultRemove(envId){
    if(typeof window === 'undefined') return;
    [window.localStorage, window.sessionStorage].forEach(function(store){
      if(!store) return;
      var list = _readStore(store).filter(function(e){ return e.id !== envId; });
      _writeStore(store, list);
    });
  }

  /** Limpa tudo do vault (logout). */
  function vaultClear(){
    if(typeof window === 'undefined') return;
    [window.localStorage, window.sessionStorage].forEach(function(store){
      if(store){ try { store.removeItem(VAULT_KEY); } catch(_) {} }
    });
  }

  /** Retorna env do vault por id. */
  function vaultGet(envId){
    return vaultList().find(function(e){ return e.id === envId; }) || null;
  }

  /** Sanitiza env pra retornar pra UI (sem token), tipo /api/v2/environments antigo. */
  function vaultSanitized(){
    return vaultList().map(function(e){
      var clean = {
        id: e.id, name: e.name, desc: e.desc, type: e.type || 'pipefy',
        base_url: e.base_url, org_id: e.org_id, auth_mode: e.auth_mode,
        verify_ssl: e.verify_ssl, project_id: e.project_id,
        pipes: e.pipes || [],
        has_token: !!(e.token && String(e.token).trim().length > 6),
        remember: e.remember !== false,
      };
      return clean;
    });
  }

  /* ===================== Basic Auth fetch wrapper ===================== */
  var APP_AUTH_KEY = 'pv-app-auth-v1';

  function _readAppAuth(){
    if(typeof window === 'undefined') return '';
    try { return window.sessionStorage.getItem(APP_AUTH_KEY) || ''; } catch(_) { return ''; }
  }

  function _saveAppAuth(b64){
    if(typeof window === 'undefined') return;
    try { window.sessionStorage.setItem(APP_AUTH_KEY, b64 || ''); } catch(_) {}
  }

  function _clearAppAuth(){
    if(typeof window === 'undefined') return;
    try { window.sessionStorage.removeItem(APP_AUTH_KEY); } catch(_) {}
  }

  function _promptAppPassword(){
    if(typeof window === 'undefined' || !window.prompt) return null;
    var user = window.prompt('Usuário do app (default: demo):', 'demo') || 'demo';
    var pw = window.prompt('Senha do app (configurada via APP_PASSWORD):');
    if(!pw) return null;
    var b64 = btoa((user || 'demo') + ':' + pw);
    _saveAppAuth(b64);
    return b64;
  }

  /** Wrapper de fetch que injeta Authorization: Basic. Em 401, limpa e reprompt. */
  function apiFetch(url, options){
    options = options || {};
    var b64 = _readAppAuth();
    options.headers = Object.assign({}, options.headers || {});
    if(b64) options.headers.Authorization = 'Basic ' + b64;
    return fetch(url, options).then(function(res){
      if(res.status !== 401) return res;
      _clearAppAuth();
      var newB64 = _promptAppPassword();
      if(!newB64) return res;
      options.headers.Authorization = 'Basic ' + newB64;
      return fetch(url, options);
    });
  }

  /* ===================== buildRunPayload ===================== */
  /** Empacota credenciais do env selecionado no body do POST /api/run.
   *  mode: 'single'|'cross'|'snapshot'|'batch'|'ipaas'|'healthcheck'
   *  envIds: pra single/snapshot/batch passe { src: 'fourd_hmg' }
   *          pra cross: { src: 'fourd_hmg', dst: 'fourd_prd' }
   *          pra ipaas: { ipaas: 'ipaas_fourd' }
   *  base: dict adicional pra mesclar (mode, test, categories, pipes_selected, etc.)
   */
  function buildRunPayload(mode, envIds, base){
    var payload = Object.assign({ mode: mode }, base || {});
    envIds = envIds || {};
    if(mode === 'cross'){
      var src = envIds.src ? vaultGet(envIds.src) : null;
      var dst = envIds.dst ? vaultGet(envIds.dst) : null;
      if(src){
        payload.src_token = src.token || '';
        payload.src_base_url = src.base_url || '';
        payload.src_org_id = src.org_id || '';
        payload.src_auth_mode = src.auth_mode || 'bearer';
        payload.src_verify_ssl = src.verify_ssl !== true ? false : true;
        payload.src_session_cookie = src.session_cookie || 'NONE';
        payload.src_csrf_token = src.csrf_token || 'NONE';
      }
      if(dst){
        payload.dst_token = dst.token || '';
        payload.dst_base_url = dst.base_url || '';
        payload.dst_org_id = dst.org_id || '';
        payload.dst_auth_mode = dst.auth_mode || 'bearer';
        payload.dst_verify_ssl = dst.verify_ssl !== true ? false : true;
        payload.dst_session_cookie = dst.session_cookie || 'NONE';
        payload.dst_csrf_token = dst.csrf_token || 'NONE';
      }
    } else if(mode === 'ipaas'){
      var ipaas = envIds.ipaas ? vaultGet(envIds.ipaas) : null;
      if(ipaas){
        payload.ipaas_token = ipaas.token || '';
        payload.ipaas_base_url = ipaas.base_url || '';
        payload.ipaas_project_id = ipaas.project_id || '';
        payload.ipaas_verify_ssl = ipaas.verify_ssl === true;
      }
    } else if(mode !== 'healthcheck'){
      var env = envIds.src ? vaultGet(envIds.src) : null;
      if(env){
        payload.token = env.token || '';
        payload.base_url = env.base_url || '';
        payload.org_id = env.org_id || '';
        payload.auth_mode = env.auth_mode || 'bearer';
        payload.verify_ssl = env.verify_ssl === true;
        payload.session_cookie = env.session_cookie || 'NONE';
        payload.csrf_token = env.csrf_token || 'NONE';
      }
    }
    return payload;
  }

  var api = {
    slugify: slugify,
    escapeHtml: escapeHtml,
    truncMid: truncMid,
    parseCrossConfigMeta: parseCrossConfigMeta,
    getCrossTokenStatus: getCrossTokenStatus,
    computeSuggestedSnapLabel: computeSuggestedSnapLabel,
    categorize: categorize,
    severityOf: severityOf,
    vaultList: vaultList,
    vaultSave: vaultSave,
    vaultRemove: vaultRemove,
    vaultClear: vaultClear,
    vaultGet: vaultGet,
    vaultSanitized: vaultSanitized,
    buildRunPayload: buildRunPayload,
    apiFetch: apiFetch,
    clearAppAuth: _clearAppAuth,
    VAULT_KEY: VAULT_KEY,
    APP_AUTH_KEY: APP_AUTH_KEY,
  };

  if(typeof module !== 'undefined' && module.exports){
    module.exports = api;
  } else {
    global.V2Utils = api;
  }
})(typeof window !== 'undefined' ? window : globalThis);
