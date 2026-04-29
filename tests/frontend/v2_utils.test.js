/**
 * Unit tests pras funções utilitárias puras do V2 frontend.
 * Roda com: `npm run test` (vitest).
 */
import { describe, it, expect, beforeEach } from 'vitest';
import V2Utils from '../../web/designs/assets/v2_utils.js';

const {
  slugify,
  escapeHtml,
  truncMid,
  parseCrossConfigMeta,
  getCrossTokenStatus,
  computeSuggestedSnapLabel,
  categorize,
  severityOf,
  vaultList,
  vaultSave,
  vaultGet,
  vaultRemove,
  vaultClear,
  vaultSanitized,
  buildRunPayload,
  VAULT_KEY,
} = V2Utils;

// Mock localStorage e sessionStorage no Node
class MemoryStorage {
  constructor(){ this._d = {}; }
  getItem(k){ return Object.prototype.hasOwnProperty.call(this._d, k) ? this._d[k] : null; }
  setItem(k, v){ this._d[k] = String(v); }
  removeItem(k){ delete this._d[k]; }
  clear(){ this._d = {}; }
}

beforeEach(() => {
  globalThis.window = {
    localStorage: new MemoryStorage(),
    sessionStorage: new MemoryStorage(),
  };
});

describe('slugify', () => {
  it('converte espaços em underscore e baixa case', () => {
    expect(slugify('Mesa Credito PF')).toBe('mesa_credito_pf');
  });
  it('remove caracteres especiais', () => {
    expect(slugify('Mesa Credito PF (Origem)')).toBe('mesa_credito_pf_origem');
  });
  it('aceita string vazia ou null', () => {
    expect(slugify('')).toBe('');
    expect(slugify(null)).toBe('');
    expect(slugify(undefined)).toBe('');
  });
  it('colapsa múltiplos separadores', () => {
    expect(slugify('a -- b __ c')).toBe('a_b_c');
  });
  it('remove underscores nas pontas', () => {
    expect(slugify('  __xyz__  ')).toBe('xyz');
  });
});

describe('escapeHtml', () => {
  it('escapa HTML básico', () => {
    expect(escapeHtml('<script>alert("x")</script>')).toBe(
      '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;'
    );
  });
  it('escapa &', () => {
    expect(escapeHtml('A & B')).toBe('A &amp; B');
  });
  it('aceita null', () => {
    expect(escapeHtml(null)).toBe('');
  });
  it('preserva texto sem chars especiais', () => {
    expect(escapeHtml('foo bar 123')).toBe('foo bar 123');
  });
});

describe('truncMid', () => {
  it('não trunca se cabe no max', () => {
    expect(truncMid('foobar', 10)).toBe('foobar');
  });
  it('trunca pelo meio com elipsis', () => {
    const result = truncMid('foobarbazquxquux', 9);
    expect(result).toContain('…');
    expect(result.length).toBeLessThanOrEqual(9);
  });
  it('trata strings vazias', () => {
    expect(truncMid('', 5)).toBe('');
    expect(truncMid(null, 5)).toBe('');
  });
});

describe('parseCrossConfigMeta', () => {
  it('detecta cross_<src>_x_<dst> com env_ids extraídos', () => {
    const r = parseCrossConfigMeta('cross_fourd_hmg_x_fourd_prd');
    expect(r.srcEnvId).toBe('fourd_hmg');
    expect(r.dstEnvId).toBe('fourd_prd');
    expect(r.status).toBe('typical');
  });
  it('detecta selfcheck (mesmo env nos dois lados)', () => {
    const r = parseCrossConfigMeta('cross_fourd_hmg_selfcheck');
    expect(r.srcEnvId).toBe('fourd_hmg');
    expect(r.dstEnvId).toBe('fourd_hmg');
    expect(r.status).toBe('ok');
  });
  it('fallback quando id não casa com nenhum padrão', () => {
    const r = parseCrossConfigMeta('cross_unknown');
    expect(r.srcEnvId).toBeNull();
    expect(r.dstEnvId).toBeNull();
    expect(r.status).toBe('typical');
  });
});

describe('getCrossTokenStatus', () => {
  const envsData = {
    pipefy: [
      { id: 'fourd_hmg', name: 'FourD Sandbox', has_token: true },
      { id: 'fourd_prd', name: 'FourD PRD', has_token: false },
      { id: 'demo_hmg', name: 'Demo Sandbox', has_token: true },
    ],
  };

  it('retorna ok quando ambos têm token', () => {
    const r = getCrossTokenStatus('cross_fourd_hmg_x_demo_hmg', envsData);
    expect(r.ok).toBe(true);
    expect(r.missing).toEqual([]);
  });

  it('marca pendente quando destino sem token', () => {
    const r = getCrossTokenStatus('cross_fourd_hmg_x_fourd_prd', envsData);
    expect(r.ok).toBe(false);
    expect(r.missing).toContain('fourd_prd');
    expect(r.labels).toContain('FourD PRD');
  });

  it('selfcheck só conta o env uma vez', () => {
    const r = getCrossTokenStatus('cross_fourd_hmg_selfcheck', envsData);
    expect(r.ok).toBe(true);
  });

  it('retorna ok quando envsData é null (não bloqueia)', () => {
    const r = getCrossTokenStatus('cross_fourd_hmg_x_fourd_prd', null);
    expect(r.ok).toBe(true);
  });

  it('retorna ok quando o cross não tem srcEnvId/dstEnvId conhecidos', () => {
    const r = getCrossTokenStatus('cross_unknown', envsData);
    expect(r.ok).toBe(true);
  });
});

describe('computeSuggestedSnapLabel', () => {
  it('combina pipe + env', () => {
    expect(computeSuggestedSnapLabel('Mesa Credito', 'fourd_hmg'))
      .toBe('mesa_credito_fourd_hmg');
  });
  it('aceita pipe sem env', () => {
    expect(computeSuggestedSnapLabel('Mesa Credito', '')).toBe('mesa_credito');
  });
  it('retorna vazio sem pipe', () => {
    expect(computeSuggestedSnapLabel('', 'fourd_hmg')).toBe('');
    expect(computeSuggestedSnapLabel(null, 'fourd_hmg')).toBe('');
  });
  it('normaliza chars especiais do nome do pipe', () => {
    expect(computeSuggestedSnapLabel('Mesa Credito PF (Origem)', 'fourd_hmg'))
      .toBe('mesa_credito_pf_origem_fourd_hmg');
  });
});

describe('categorize', () => {
  it('classifica START FORM como SF', () => {
    expect(categorize('[START FORM] Campo missing').cat).toBe('SF');
  });
  it('classifica LABEL como LB', () => {
    expect(categorize('[LABEL EXTRA] foo').cat).toBe('LB');
  });
  it('classifica FASE_DESTINO como AD', () => {
    expect(categorize('[AUTOMACAO FASE_DESTINO] xyz').cat).toBe('AD');
  });
  it('classifica HTTP como AH', () => {
    expect(categorize('[AUTOMACAO HTTP_METHOD] post').cat).toBe('AH');
  });
  it('classifica CONDITION como AC', () => {
    expect(categorize('[AUTOMACAO CONDITION] equals').cat).toBe('AC');
  });
  it('classifica STATUS como AS', () => {
    expect(categorize('[AUTOMACAO STATUS] active=False').cat).toBe('AS');
  });
  it('default genérico vai pra FA', () => {
    expect(categorize('[CAMPO EXTRA] alguma coisa').cat).toBe('FA');
  });
});

describe('severityOf', () => {
  it('CAMPO EXTRA é warn', () => {
    expect(severityOf('[CAMPO EXTRA] foo existe')).toBe('warn');
  });
  it('REMOVIDO é warn', () => {
    expect(severityOf('Automação removida')).toBe('warn');
  });
  it('default é error', () => {
    expect(severityOf('[REQUIRED DIFERENTE] foo')).toBe('err');
  });
});

// =============================================================
// Vault (localStorage / sessionStorage de envs)
// =============================================================

describe('vault', () => {
  it('vaultList retorna lista vazia inicialmente', () => {
    expect(vaultList()).toEqual([]);
  });

  function _readPersisted(){
    try { return JSON.parse(window.localStorage.getItem(VAULT_KEY) || '[]'); }
    catch(_) { return []; }
  }
  function _readEphemeral(){
    try { return JSON.parse(window.sessionStorage.getItem(VAULT_KEY) || '[]'); }
    catch(_) { return []; }
  }

  it('vaultSave persiste em localStorage quando remember=true', () => {
    vaultSave({
      id: 'fourd_hmg', name: 'FourD', type: 'pipefy',
      base_url: 'https://api.pipefy.com/graphql', token: 'Bearer xyz',
      remember: true,
    });
    const list = vaultList();
    expect(list.length).toBe(1);
    expect(list[0].id).toBe('fourd_hmg');
    expect(_readPersisted().some(e => e.id === 'fourd_hmg')).toBe(true);
    expect(_readEphemeral().some(e => e.id === 'fourd_hmg')).toBe(false);
  });

  it('vaultSave persiste em sessionStorage quando remember=false', () => {
    vaultSave({
      id: 'temp_env', name: 'Temp', type: 'pipefy',
      base_url: 'x', token: 'y',
      remember: false,
    });
    expect(_readPersisted().some(e => e.id === 'temp_env')).toBe(false);
    expect(_readEphemeral().some(e => e.id === 'temp_env')).toBe(true);
  });

  it('vaultSave sobrescreve env existente (mesmo id)', () => {
    vaultSave({ id: 'a', name: 'Original', token: 't1', remember: true });
    vaultSave({ id: 'a', name: 'Atualizado', token: 't2', remember: true });
    const list = vaultList();
    expect(list.length).toBe(1);
    expect(list[0].name).toBe('Atualizado');
  });

  it('vaultSave migra de session pra local quando remember muda', () => {
    vaultSave({ id: 'm', name: 'M', token: 't', remember: false });
    expect(_readEphemeral().some(e => e.id === 'm')).toBe(true);
    vaultSave({ id: 'm', name: 'M', token: 't', remember: true });
    expect(_readPersisted().some(e => e.id === 'm')).toBe(true);
    expect(_readEphemeral().some(e => e.id === 'm')).toBe(false);
  });

  it('vaultGet retorna env por id', () => {
    vaultSave({ id: 'x', name: 'X', token: 'tok', remember: true });
    const env = vaultGet('x');
    expect(env).toBeTruthy();
    expect(env.token).toBe('tok');
    expect(vaultGet('inexistente')).toBeNull();
  });

  it('vaultRemove apaga de ambos os stores', () => {
    vaultSave({ id: 'r', name: 'R', token: 't', remember: true });
    vaultRemove('r');
    expect(vaultGet('r')).toBeNull();
  });

  it('vaultClear esvazia tudo', () => {
    vaultSave({ id: 'a', name: 'A', token: 't', remember: true });
    vaultSave({ id: 'b', name: 'B', token: 't', remember: false });
    vaultClear();
    expect(vaultList()).toEqual([]);
  });

  it('vaultSanitized não expõe token mas marca has_token', () => {
    vaultSave({ id: 'p', name: 'P', token: 'Bearer abcdefghij', remember: true });
    vaultSave({ id: 'q', name: 'Q', token: '', remember: true });
    const list = vaultSanitized();
    const p = list.find(e => e.id === 'p');
    const q = list.find(e => e.id === 'q');
    expect(p.token).toBeUndefined();
    expect(p.has_token).toBe(true);
    expect(q.has_token).toBe(false);
  });
});

// =============================================================
// buildRunPayload
// =============================================================

describe('buildRunPayload', () => {
  beforeEach(() => {
    vaultSave({
      id: 'fourd_hmg', name: 'FourD', type: 'pipefy',
      base_url: 'https://api.pipefy.com/graphql', org_id: '999',
      auth_mode: 'bearer', verify_ssl: false,
      token: 'Bearer src_tok',
      remember: true,
    });
    vaultSave({
      id: 'fourd_prd', name: 'FourD PRD', type: 'pipefy',
      base_url: 'https://api.pipefy.com/graphql', org_id: '999',
      auth_mode: 'bearer', verify_ssl: false,
      token: 'Bearer dst_tok',
      remember: true,
    });
    vaultSave({
      id: 'ipaas_fourd', name: 'iPaaS', type: 'ipaas',
      base_url: 'https://ipaas.pipefy.com/api/v1', project_id: 'p1',
      token: 'Bearer ipaas_tok',
      remember: true,
    });
  });

  it('single inclui token + base_url do env selecionado', () => {
    const p = buildRunPayload('single', { src: 'fourd_hmg' }, { config: 'fourd_hmg' });
    expect(p.mode).toBe('single');
    expect(p.token).toBe('Bearer src_tok');
    expect(p.base_url).toBe('https://api.pipefy.com/graphql');
    expect(p.org_id).toBe('999');
  });

  it('cross inclui src_* e dst_* prefixados', () => {
    const p = buildRunPayload('cross', { src: 'fourd_hmg', dst: 'fourd_prd' }, {});
    expect(p.src_token).toBe('Bearer src_tok');
    expect(p.dst_token).toBe('Bearer dst_tok');
    expect(p.src_base_url).toBe('https://api.pipefy.com/graphql');
    expect(p.dst_base_url).toBe('https://api.pipefy.com/graphql');
  });

  it('ipaas inclui ipaas_token e ipaas_base_url', () => {
    const p = buildRunPayload('ipaas', { ipaas: 'ipaas_fourd' }, {});
    expect(p.mode).toBe('ipaas');
    expect(p.ipaas_token).toBe('Bearer ipaas_tok');
    expect(p.ipaas_base_url).toBe('https://ipaas.pipefy.com/api/v1');
    expect(p.ipaas_project_id).toBe('p1');
  });

  it('healthcheck nao inclui credenciais (testa só camadas internas)', () => {
    const p = buildRunPayload('healthcheck', {}, {});
    expect(p.mode).toBe('healthcheck');
    expect(p.token).toBeUndefined();
  });

  it('mescla campos extras (categories, pipes_selected) no payload', () => {
    const p = buildRunPayload('batch', { src: 'fourd_hmg' }, {
      pipes_selected: ['u1', 'u2'],
      categories: ['SF', 'FA'],
    });
    expect(p.token).toBe('Bearer src_tok');
    expect(p.pipes_selected).toEqual(['u1', 'u2']);
    expect(p.categories).toEqual(['SF', 'FA']);
  });

  it('cross com env id inexistente nao seta credenciais', () => {
    const p = buildRunPayload('cross', { src: 'fourd_hmg', dst: 'inexistente' }, {});
    expect(p.src_token).toBe('Bearer src_tok');
    expect(p.dst_token).toBeUndefined();
  });
});
