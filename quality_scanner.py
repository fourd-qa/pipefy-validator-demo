"""Quality scanner — Frente 2 (Fase B) do PLANO-VALIDACAO-HMG-PRD.

Equivalente SonarQube aplicado a pipes Pipefy. Procura:
- dangling triggerFieldIds (apontam pra field deletado)
- automations com complexidade alta (muitas expressions)
- dead code (fields nunca referenciados)
- naming inconsistente (configuravel via regex)
- magic IDs em condition values
- automations inativas com triggers (stale)

Engine pura — opera sobre o snapshot (tool_version 1.2+) coletado pelo cron.
Mesmo padrao do semantic_scanner pra reuso de UX no dashboard.
"""
from __future__ import annotations

import datetime as _dt
import json
import os as _os
import re as _re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


_SEVERITY_RANK = {"high": 3, "med": 2, "low": 1}


def load_rules(rules_path: str) -> List[Dict[str, Any]]:
    """Carrega config/quality_rules.json. Filtra disabled. Compila label_regex
    nos params se a check tiver. Retorna [] se arquivo nao existe ou esta
    corrompido (consistente com coverage/smoke scanners; antes derrubava o caller)."""
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, IOError, json.JSONDecodeError):
        return []
    out: List[Dict[str, Any]] = []
    for check in data.get("checks", []) or []:
        if not check.get("enabled", True):
            continue
        check = dict(check)
        params = dict(check.get("params") or {})
        if "label_regex" in params:
            try:
                params["_label_regex_compiled"] = _re.compile(params["label_regex"])
            except _re.error:
                continue
        check["params"] = params
        out.append(check)
    return out


def _index_pipe_schema(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza snapshot pra forma indexada:
        {phases: {pid: {name, fields: {fid: field}}},
         start_form: {fid: field},
         all_field_ids: set}.
    """
    pipe = ((snapshot or {}).get("data") or {}).get("pipe") or {}
    phases: Dict[str, Dict[str, Any]] = {}
    all_field_ids: Set[str] = set()
    for ph in pipe.get("phases") or []:
        pid = ph.get("id")
        if not pid:
            continue
        fields_idx: Dict[str, Dict[str, Any]] = {}
        for fld in ph.get("fields") or []:
            fid = fld.get("id")
            if fid:
                fields_idx[fid] = fld
                all_field_ids.add(fid)
        phases[pid] = {"name": ph.get("name", ""), "fields": fields_idx}
    sf: Dict[str, Dict[str, Any]] = {}
    for fld in pipe.get("start_form_fields") or []:
        fid = fld.get("id")
        if fid:
            sf[fid] = fld
            all_field_ids.add(fid)
    return {"phases": phases, "start_form": sf, "all_field_ids": all_field_ids}


def _referenced_field_ids(automations: List[Dict[str, Any]]) -> Set[str]:
    """Coleta todos os field_ids referenciados por automations (event_params
    triggerFieldIds, condition.field_address)."""
    refs: Set[str] = set()
    for auto in automations or []:
        if not isinstance(auto, dict):
            continue
        ev = auto.get("event_params") or {}
        for fid in ev.get("triggerFieldIds") or []:
            if isinstance(fid, str):
                refs.add(fid)
            elif isinstance(fid, dict) and fid.get("id"):
                refs.add(fid["id"])
        cond = auto.get("condition") or {}
        for expr in cond.get("expressions") or []:
            addr = expr.get("field_address")
            if isinstance(addr, str):
                refs.add(addr)
            elif isinstance(addr, dict) and addr.get("id"):
                refs.add(addr["id"])
    return refs


def _make_finding(check, target_kind, target_id, target_name, detail=None, extra=None):
    f = {
        "check_id": check["id"],
        "category": check.get("category"),
        "severity": check.get("severity", "med"),
        "message": check.get("message"),
        "target_kind": target_kind,
        "target_id": target_id,
        "target_name": target_name,
        "detail": detail,
    }
    if extra:
        f.update(extra)
    return f


def _check_dangling_triggers(check, automations, schema):
    findings = []
    valid = schema["all_field_ids"]
    for auto in automations or []:
        ev = auto.get("event_params") or {}
        trigger_ids = ev.get("triggerFieldIds") or []
        for fid in trigger_ids:
            field_id = fid if isinstance(fid, str) else (fid.get("id") if isinstance(fid, dict) else None)
            if not field_id:
                continue
            if field_id not in valid:
                findings.append(_make_finding(
                    check, "automation", auto.get("id", ""), auto.get("name", ""),
                    detail=f"triggerFieldId '{field_id}' nao existe no pipe",
                    extra={"missing_field_id": field_id},
                ))
    return findings


def _count_expressions(condition):
    if not isinstance(condition, dict):
        return 0
    return len(condition.get("expressions") or [])


def _check_high_complexity(check, automations, schema):
    threshold = check["params"].get("threshold", 8)
    findings = []
    for auto in automations or []:
        cond = auto.get("condition") or {}
        n = _count_expressions(cond)
        if n >= threshold:
            findings.append(_make_finding(
                check, "automation", auto.get("id", ""), auto.get("name", ""),
                detail=f"{n} expressoes (threshold {threshold})",
                extra={"expression_count": n, "threshold": threshold},
            ))
    return findings


def _check_dead_fields(check, automations, schema, scope):
    """scope = 'start_form' ou 'phase'."""
    refs = _referenced_field_ids(automations)
    findings = []
    if scope == "start_form":
        for fid, fld in schema["start_form"].items():
            if fid not in refs:
                findings.append(_make_finding(
                    check, "field", fid, fld.get("label", fid),
                    detail="Field do start form sem referencia em nenhuma automation",
                    extra={"field_type": fld.get("type")},
                ))
    elif scope == "phase":
        for pid, phase in schema["phases"].items():
            for fid, fld in phase["fields"].items():
                if fid not in refs:
                    findings.append(_make_finding(
                        check, "field", fid, fld.get("label", fid),
                        detail=f"Field da phase '{phase['name']}' sem referencia",
                        extra={"phase_id": pid, "phase_name": phase["name"]},
                    ))
    return findings


def _check_inactive_with_trigger(check, automations, schema):
    findings = []
    for auto in automations or []:
        if auto.get("active") is False:
            ev = auto.get("event_params") or {}
            triggers = ev.get("triggerFieldIds") or []
            if triggers:
                findings.append(_make_finding(
                    check, "automation", auto.get("id", ""), auto.get("name", ""),
                    detail=f"Inativa com {len(triggers)} trigger(s) configurado(s)",
                ))
    return findings


_UUID_RE = _re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", _re.IGNORECASE)


def _looks_like_id(value, min_length):
    """Heuristica pra detectar 'magic ID' em condition.value.

    Pipefy phase/connector IDs sao UUIDs ou numericos curtos (~9 digitos).
    Versao anterior flaggava qualquer string numerica >= min_length, gerando
    falso positivo em CPF (11 digitos), CNPJ (14), telefone, codigo de barras.
    Excluir tamanhos tipicos de documento BR reduz falso positivo sem perder
    UUIDs ou IDs numericos legitimos.
    """
    if not isinstance(value, str):
        return False
    s = value.strip()
    if len(s) < min_length:
        return False
    if _UUID_RE.match(s):
        return True
    # ID numerico: precisa ser >= min_length E nao parecer CPF (11) ou CNPJ (14).
    # Esses tamanhos sao quase sempre documentos validos comparados em condition,
    # nao referencias a pipe/phase/connector.
    if s.isdigit() and len(s) >= min_length and len(s) not in (11, 14):
        return True
    return False


def _check_magic_id_in_condition(check, automations, schema):
    min_len = check["params"].get("min_length", 12)
    findings = []
    for auto in automations or []:
        cond = auto.get("condition") or {}
        for idx, expr in enumerate(cond.get("expressions") or []):
            val = expr.get("value")
            if _looks_like_id(val, min_len):
                findings.append(_make_finding(
                    check, "automation", auto.get("id", ""), auto.get("name", ""),
                    detail=f"Expression #{idx + 1} compara com valor hardcoded '{val[:20]}...'",
                    extra={"expression_index": idx},
                ))
    return findings


def _check_naming_inconsistent(check, automations, schema):
    regex = check["params"].get("_label_regex_compiled")
    if regex is None:
        return []
    findings = []
    for fid, fld in schema["start_form"].items():
        label = fld.get("label") or ""
        if label and not regex.match(label):
            findings.append(_make_finding(
                check, "field", fid, label,
                detail="Label fora do padrao do regex configurado",
                extra={"scope": "start_form"},
            ))
    for pid, phase in schema["phases"].items():
        for fid, fld in phase["fields"].items():
            label = fld.get("label") or ""
            if label and not regex.match(label):
                findings.append(_make_finding(
                    check, "field", fid, label,
                    detail="Label fora do padrao do regex configurado",
                    extra={"scope": "phase", "phase_id": pid},
                ))
    return findings


_CHECK_FUNCTIONS = {
    "dangling_trigger_field": _check_dangling_triggers,
    "high_complexity_automation": _check_high_complexity,
    "dead_start_form_field": lambda c, a, s: _check_dead_fields(c, a, s, "start_form"),
    "dead_phase_field": lambda c, a, s: _check_dead_fields(c, a, s, "phase"),
    "inactive_automation_with_trigger": _check_inactive_with_trigger,
    "magic_id_in_condition": _check_magic_id_in_condition,
    "naming_inconsistent_field": _check_naming_inconsistent,
}


def scan_pipe_quality(
    snapshot: Dict[str, Any],
    rules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Aplica todos os checks de qualidade habilitados ao snapshot.

    Snapshot esperado: tool_version >= 1.1 (com data.automations); checks de
    phase field exigem tool_version >= 1.2 (com data.pipe.phases[*].fields)."""
    if not isinstance(snapshot, dict):
        return []
    schema = _index_pipe_schema(snapshot)
    automations = ((snapshot.get("data") or {}).get("automations")) or []

    findings: List[Dict[str, Any]] = []
    import logging as _logging
    _log = _logging.getLogger(__name__)
    for check in rules or []:
        fn = _CHECK_FUNCTIONS.get(check["id"])
        if fn is None:
            continue
        try:
            findings.extend(fn(check, automations, schema))
        except Exception as ex:
            # Antes era `except: continue` cego; checks quebrados ficavam
            # silenciosos e usuario via "0 findings" falso. Agora loga.
            _log.warning("check %s falhou: %s", check.get("id", "?"), ex)
            continue

    findings.sort(key=lambda f: (
        -_SEVERITY_RANK.get(f["severity"], 0),
        f.get("category", ""),
        f.get("check_id", ""),
    ))
    return findings


def summarize_findings(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrega findings pra cards/KPIs da UI."""
    by_severity = {"high": 0, "med": 0, "low": 0}
    by_category: Dict[str, int] = {}
    by_check: Dict[str, int] = {}
    for f in findings:
        sev = f.get("severity", "med")
        if sev in by_severity:
            by_severity[sev] += 1
        cat = f.get("category", "outros")
        by_category[cat] = by_category.get(cat, 0) + 1
        cid = f.get("check_id", "")
        if cid:
            by_check[cid] = by_check.get(cid, 0) + 1
    return {
        "total": len(findings),
        "by_severity": by_severity,
        "by_category": by_category,
        "by_check": by_check,
    }


# ============================================================
# Historico (mesma estrutura do semantic_scanner)
# ============================================================

_SAFE_ID_RE = _re.compile(r"[^a-zA-Z0-9_-]")


def _safe_pipe_id(pipe_id: str) -> str:
    return _SAFE_ID_RE.sub("_", pipe_id or "")[:64] or "unknown"


def persist_scan_run(
    history_root: str,
    pipe_id: str,
    run_data: Dict[str, Any],
    retention: int = 50,
) -> str:
    safe_id = _safe_pipe_id(pipe_id)
    pipe_dir = _os.path.join(history_root, safe_id)
    _os.makedirs(pipe_dir, exist_ok=True)
    now = _dt.datetime.now()
    payload = {
        "run_timestamp": now.isoformat(),
        "pipe_id": pipe_id,
        **run_data,
    }
    # Microsegundos evitam colisao quando 2 runs no mesmo segundo.
    filename = now.strftime("%Y%m%d_%H%M%S_%f") + ".json"
    path = _os.path.join(pipe_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    if retention > 0:
        # Filtra apenas filenames no padrao timestamp pra nao apagar arquivos
        # manuais (summary.json, etc).
        _SCAN_FNAME_RE = _re.compile(r"^\d{8}_\d{6}(?:_\d+)?\.json$")
        files = sorted(f for f in _os.listdir(pipe_dir) if _SCAN_FNAME_RE.match(f))
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


def compute_quality_trend(
    history_root: str,
    pipe_id: str,
    limit: int = 10,
) -> Dict[str, Any]:
    runs = list_scan_runs(history_root, pipe_id, limit=limit)
    if not runs:
        return {
            "available": False,
            "reason": "Sem historico de quality scans pra este pipe ainda.",
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
        def _key(f):
            return (f.get("check_id"), f.get("target_id"))
        prev_keys = {_key(f) for f in (prev.get("findings") or [])}
        curr_keys = {_key(f) for f in (curr.get("findings") or [])}
        for f in curr.get("findings") or []:
            if _key(f) not in prev_keys:
                new_findings.append({
                    "check_id": f.get("check_id"),
                    "severity": f.get("severity"),
                    "target_name": f.get("target_name"),
                    "message": f.get("message"),
                })
        for f in prev.get("findings") or []:
            if _key(f) not in curr_keys:
                resolved_findings.append({
                    "check_id": f.get("check_id"),
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
