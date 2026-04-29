/* v2_theme.js — Toggle dia/noite com persistência em localStorage.
   Auto-injeta um botão no header de cada tela do V2 (topbar, help-topbar, docs-topbar).
   Aplica data-theme="light" ou data-theme="dark" no <html>. */

(function () {
  'use strict';

  const STORAGE_KEY = 'v2-theme';

  function getTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY) || 'dark';
    } catch (e) {
      return 'dark';
    }
  }

  function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) { /* sem storage = sem persistência, OK */ }
    updateButtonIcons();
  }

  function toggle() {
    const next = getTheme() === 'dark' ? 'light' : 'dark';
    setTheme(next);
  }

  // Ícones SVG: sun (modo dia ativo) / moon (modo noite ativo).
  // O ícone exibido representa o tema PARA O QUAL o click vai TROCAR.
  function moonIconSvg() {
    return '<svg viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
  }
  function sunIconSvg() {
    return '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
  }

  function updateButtonIcons() {
    const isDark = getTheme() === 'dark';
    document.querySelectorAll('.v2-theme-toggle').forEach((btn) => {
      btn.innerHTML = isDark ? sunIconSvg() : moonIconSvg();
      btn.title = isDark ? 'Mudar pra modo claro' : 'Mudar pra modo escuro';
      btn.setAttribute('aria-label', btn.title);
    });
  }

  function injectButton() {
    // Procura o container de ações do header em cada tipo de tela do V2
    const candidates = [
      '.topbar .top-right',         // configuracao, execucao, resultados (V2)
      '.help-topbar .help-actions', // /v2/help
      '.docs-topbar',               // /v2/docs (insere antes do back button)
    ];

    let target = null;
    for (const sel of candidates) {
      const el = document.querySelector(sel);
      if (el) { target = el; break; }
    }
    if (!target) return; // tela sem header conhecido

    // Evita duplicar se já existir
    if (target.querySelector('.v2-theme-toggle')) return;

    const btn = document.createElement('button');
    btn.className = 'v2-theme-toggle';
    btn.type = 'button';
    btn.addEventListener('click', toggle);

    // Insere como PRIMEIRO filho do container (canto esquerdo do top-right)
    target.insertBefore(btn, target.firstChild);
    updateButtonIcons();
  }

  // Aplica tema o quanto antes (evita flash de tema errado)
  setTheme(getTheme());

  // Injeta botão depois do DOM estar pronto
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectButton);
  } else {
    injectButton();
  }
})();
