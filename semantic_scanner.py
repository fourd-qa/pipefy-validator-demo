"""Scanner de regras semanticas - Frente 1 (Fase A) do PLANO-VALIDACAO-HMG-PRD.

Equivalente a Gitleaks + Snyk Code aplicado a automations Pipefy. Procura
padroes inseguros em URLs, headers, bodies de automation HTTP. Funcoes puras,
sem efeito colateral (nao escreve arquivo, nao chama API).

Uso tipico:
    rules = load_rules("config/semantic_rules.json")
    targets = extract_targets_from_automations(automations_list, env_label="PRD")
    findings = scan_targets(targets, rules)

Cada finding eh um dict com:
    {rule_id, category, severity, message, target_kind, target_name,
     target_id, field, snippet, env_label}
"""
from __future__ import annotations

import datetime as _dt
import json
import os as _os
import re
from typing import Any, Dict, List, Optional


# Severidades validas pra ordenacao consistente.
_SEVERITY_RANK = {"high": 3, "med": 2, "low": 1}


def load_rules(rules_path: str) -> List[Dict[str, Any]]:
    """Carrega config/semantic_rules.json e compila os regex pra atributo
    '_compiled'. Filtra regras com enabled=false."""
    with open(rules_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: List[Dict[str, Any]] = []
    for rule in data.get("rules", []) or []:
        if not rule.get("enabled", True):
            continue
        pattern = rule.get("pattern", "")
        try:
            compiled = re.compile(pattern)
        except re.error:
            # Regra com regex invalido eh ignorada (nao quebra o scan).
            continue
        rule = dict(rule)
        rule["_compiled"] = compiled
        out.append(rule)
    return out


def _stringify(value: Any) -> str:
    """Normaliza qualquer valor de campo (str, dict, list) pra string scanavel."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def _snippet(text: str, match: re.Match, ctx: int = 40) -> str:
    """Retorna fatia de texto ao redor do match, com '...' nas pontas."""
    start = max(0, match.start() - ctx)
    end = min(len(text), match.end() + ctx)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    # Mascara secret no snippet (mantem so primeiros 4 chars do match).
    matched = match.group(0)
    if len(matched) > 8:
        masked = matched[:4] + "***"
        snippet = snippet.replace(matched, masked)
    return snippet


def scan_targets(
    targets: List[Dict[str, Any]],
    rules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Aplica regras compiladas a uma lista de targets.

    Target esperado:
        {
          "kind": "automation",  # ou "field", "label", etc.
          "name": "Mover quando aprovado",
          "id": "auto_123",
          "url": "https://...",
          "headers": {...} ou str,
          "body": "..." ou dict,
          "env_label": "PRD",  # opcional
        }

    Regras com env_restrict so disparam quando target.env_label bate.
    """
    findings: List[Dict[str, Any]] = []
    for target in targets or []:
        env_label = (target.get("env_label") or "").strip().upper()
        for rule in rules:
            restrict = (rule.get("env_restrict") or "").strip().upper()
            if restrict and restrict != env_label:
                continue
            for field_name in rule.get("fields", []) or []:
                raw = target.get(field_name)
                if raw is None or raw == "":
                    continue
                text = _stringify(raw)
                match = rule["_compiled"].search(text)
                if not match:
                    continue
                findings.append({
                    "rule_id": rule.get("id"),
                    "category": rule.get("category"),
                    "severity": rule.get("severity", "med"),
                    "message": rule.get("message"),
                    "target_kind": target.get("kind", "unknown"),
                    "target_name": target.get("name", ""),
                    "target_id": target.get("id", ""),
                    "field": field_name,
                    "snippet": _snippet(text, match),
                    "env_label": env_label or None,
                })
    findings.sort(key=lambda f: (
        -_SEVERITY_RANK.get(f["severity"], 0),
        f.get("category", ""),
        f.get("rule_id", ""),
    ))
    return findings


def extract_targets_from_automations(
    automations: List[Dict[str, Any]],
    env_label: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Aceita lista de automation nodes no formato do GraphQL Pipefy
    (resources/queries/automations_list.graphql) e retorna lista de targets
    scanaveis.

    Olha pra action_params.url / headers / body, e tambem condition.expressions
    com valores que podem conter credenciais.
    """
    targets: List[Dict[str, Any]] = []
    for auto in automations or []:
        if not isinstance(auto, dict):
            continue
        action_params = auto.get("action_params") or {}
        if any(action_params.get(k) for k in ("url", "headers", "body")):
            targets.append({
                "kind": "automation",
                "id": auto.get("id", ""),
                "name": auto.get("name", ""),
                "url": action_params.get("url"),
                "headers": action_params.get("headers"),
                "body": action_params.get("body"),
                "env_label": env_label,
            })
        # Conditions com value tambem podem ter credenciais.
        cond = auto.get("condition") or {}
        for expr in cond.get("expressions") or []:
            if expr.get("value"):
                targets.append({
                    "kind": "condition",
                    "id": f"{auto.get('id', '')}:cond",
                    "name": auto.get("name", ""),
                    "body": expr.get("value"),
                    "env_label": env_label,
                })
    return targets


def extract_targets_from_snapshot(
    snapshot: Dict[str, Any],
    env_label: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Extrai targets do formato de snapshot persistido pelo cron
    (snapshots/auto/<pipe>/<ts>.json). Le data.automations[*] e converte.

    Backwards compat: snapshots antigos (tool_version 1.0) sem 'data.automations'
    retornam []. Se 'env_label' nao for passado, usa metadata.env_label."""
    if not isinstance(snapshot, dict):
        return []
    if env_label is None:
        env_label = (snapshot.get("metadata") or {}).get("env_label") or None
    automations = ((snapshot.get("data") or {}).get("automations")) or []
    return extract_targets_from_automations(automations, env_label=env_label)


def summarize_findings(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrega findings pra cards/KPIs da UI."""
    by_severity = {"high": 0, "med": 0, "low": 0}
    by_category: Dict[str, int] = {}
    by_rule: Dict[str, int] = {}
    for f in findings:
        sev = f.get("severity", "med")
        if sev in by_severity:
            by_severity[sev] += 1
        cat = f.get("category", "outros")
        by_category[cat] = by_category.get(cat, 0) + 1
        rid = f.get("rule_id", "")
        if rid:
            by_rule[rid] = by_rule.get(rid, 0) + 1
    return {
        "total": len(findings),
        "by_severity": by_severity,
        "by_category": by_category,
        "by_rule": by_rule,
    }


# ============================================================
# Pendencia 3 — historico de scans pra trend
# ============================================================

_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_-]")


def _safe_pipe_id(pipe_id: str) -> str:
    return _SAFE_ID_RE.sub("_", pipe_id or "")[:64] or "unknown"


def persist_scan_run(
    history_root: str,
    pipe_id: str,
    run_data: Dict[str, Any],
    retention: int = 50,
) -> str:
    """Salva uma execucao do scan em history_root/<safe_pipe_id>/<ts>.json
    e aplica retencao mantendo so as `retention` runs mais recentes.

    run_data tipico: {snapshot_filename, env_label, summary, findings, rules_count}.
    Funcao adiciona 'run_timestamp' e 'pipe_id' antes de salvar.

    Retorna path do arquivo gravado. Raise se nao conseguir escrever
    (chamador decide se trata)."""
    safe_id = _safe_pipe_id(pipe_id)
    pipe_dir = _os.path.join(history_root, safe_id)
    _os.makedirs(pipe_dir, exist_ok=True)
    now = _dt.datetime.now()
    payload = {
        "run_timestamp": now.isoformat(),
        "pipe_id": pipe_id,
        **run_data,
    }
    filename = now.strftime("%Y%m%d_%H%M%S") + ".json"
    path = _os.path.join(pipe_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    # Retencao: mantem N mais recentes (por nome de arquivo, ordem cronologica).
    if retention > 0:
        files = sorted(f for f in _os.listdir(pipe_dir) if f.endswith(".json"))
        excess = len(files) - retention
        for i in range(excess):
            try:
                _os.remove(_os.path.join(pipe_dir, files[i]))
            except OSError:
                pass

    return path


def list_scan_runs(
    history_root: str,
    pipe_id: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Lista as `limit` runs mais recentes do pipe. Retorna lista ordenada
    cronologicamente (mais antiga primeiro pra facilitar plot de trend)."""
    safe_id = _safe_pipe_id(pipe_id)
    pipe_dir = _os.path.join(history_root, safe_id)
    if not _os.path.isdir(pipe_dir):
        return []
    files = sorted(f for f in _os.listdir(pipe_dir) if f.endswith(".json"))
    if limit > 0:
        files = files[-limit:]
    out: List[Dict[str, Any]] = []
    for f in files:
        try:
            with open(_os.path.join(pipe_dir, f), "r", encoding="utf-8") as fh:
                out.append(json.load(fh))
        except (json.JSONDecodeError, IOError):
            continue
    return out


def compute_security_trend(
    history_root: str,
    pipe_id: str,
    limit: int = 10,
) -> Dict[str, Any]:
    """Computa trend simples a partir do histórico: serie temporal de
    contagens por severity + delta vs run anterior + findings novos.

    'Findings novos' = rule_id + target_id na ultima run que nao aparece
    na penultima. 'Findings resolvidos' = inverso. Permite mostrar
    "voce ja tinha X, corrigiu Y, surgiu Z" pra UI.
    """
    runs = list_scan_runs(history_root, pipe_id, limit=limit)
    if not runs:
        return {
            "available": False,
            "reason": "Sem historico de scans pra este pipe ainda.",
            "pipe_id": pipe_id,
            "series": [],
        }

    series = [
        {
            "timestamp": r.get("run_timestamp"),
            "total": (r.get("summary") or {}).get("total", 0),
            "by_severity": (r.get("summary") or {}).get("by_severity", {}),
        }
        for r in runs
    ]

    delta = None
    new_findings: List[Dict[str, Any]] = []
    resolved_findings: List[Dict[str, Any]] = []
    if len(runs) >= 2:
        prev = runs[-2]
        curr = runs[-1]
        delta = {
            "total": ((curr.get("summary") or {}).get("total", 0)
                      - (prev.get("summary") or {}).get("total", 0)),
            "by_severity": {
                sev: ((curr.get("summary") or {}).get("by_severity", {}).get(sev, 0)
                      - (prev.get("summary") or {}).get("by_severity", {}).get(sev, 0))
                for sev in ("high", "med", "low")
            },
        }
        prev_keys = {(f.get("rule_id"), f.get("target_id")) for f in (prev.get("findings") or [])}
        curr_keys = {(f.get("rule_id"), f.get("target_id")) for f in (curr.get("findings") or [])}
        for f in curr.get("findings") or []:
            if (f.get("rule_id"), f.get("target_id")) not in prev_keys:
                new_findings.append({
                    "rule_id": f.get("rule_id"),
                    "severity": f.get("severity"),
                    "target_name": f.get("target_name"),
                    "message": f.get("message"),
                })
        for f in prev.get("findings") or []:
            if (f.get("rule_id"), f.get("target_id")) not in curr_keys:
                resolved_findings.append({
                    "rule_id": f.get("rule_id"),
                    "severity": f.get("severity"),
                    "target_name": f.get("target_name"),
                })

    return {
        "available": True,
        "pipe_id": pipe_id,
        "runs_count": len(runs),
        "series": series,
        "delta_last_vs_prev": delta,
        "new_findings": new_findings[:10],
        "resolved_findings": resolved_findings[:10],
        "latest_summary": (runs[-1].get("summary") if runs else None),
    }
