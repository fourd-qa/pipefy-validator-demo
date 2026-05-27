"""Coverage scanner — Fase D do PLANO-VALIDACAO-HMG-PRD.

Faz "blast radius" + coverage scan sobre o snapshot do pipe:
- Pra cada phase, quantos cards reais estao parados (cards_count do snapshot
  v1.3+). Mudar phase com 100 cards eh muito mais arriscado que mudar phase
  com 0 cards.
- Phases orfas (sem automation que entra ou sai)
- Phases sem SLA configurado
- Fields sem description (documentacao baixa)
- Identificacao de phases "heavy" (>= threshold de cards)

Engine pura. Mesmo padrao dos outros scanners (load_rules opcional,
scan_pipe_coverage, summarize, persist + list + trend).

Limitacoes: SLAs detalhados, permissoes, email templates ficam pra Fase D
parte 2 (exigem queries GraphQL Pipefy adicionais).
"""
from __future__ import annotations

import datetime as _dt
import json
import os as _os
import re as _re
from typing import Any, Dict, List, Optional, Set


_SAFE_ID_RE = _re.compile(r"[^a-zA-Z0-9_-]")
_SEVERITY_RANK = {"high": 3, "med": 2, "low": 1}


def _safe_pipe_id(pipe_id: str) -> str:
    return _SAFE_ID_RE.sub("_", pipe_id or "")[:64] or "unknown"


def load_rules(rules_path: str) -> Dict[str, Any]:
    """Carrega config/coverage_rules.json. Em caso de IOError/JSON invalido,
    retorna defaults seguros."""
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError, FileNotFoundError):
        data = {"version": "0"}
    data.setdefault("heavy_phase_threshold", 50)
    data.setdefault("require_description_for_fields", True)
    data.setdefault("require_sla_for_phases", True)
    data.setdefault("flag_orphan_phases", True)
    return data


def _automation_phase_references(automations: List[Dict[str, Any]]) -> Dict[str, Dict[str, Set[str]]]:
    """Pra cada phase referenciada, retorna {phase_id: {ins: {auto_ids}, outs: {auto_ids}}}.

    'ins': automations que MOVEM um card PRA esta phase (action_params.to_phase_id
           ou event_params.to_phase_id apontam pra ela).
    'outs': automations cujo TRIGGER eh nesta phase (event_params.phase.id ou
            fromPhaseId ou inPhaseId apontam pra ela).

    Phase com 0 ins = orfa (so cria card manualmente).
    Phase com 0 outs = "fim de fluxo" (mas isso eh OK se for phase de conclusao).
    """
    refs: Dict[str, Dict[str, Set[str]]] = {}

    def _phase_id_from(obj):
        """Helper: aceita string ou dict {id, name}."""
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            return obj.get("id")
        return None

    for auto in automations or []:
        if not isinstance(auto, dict):
            continue
        auto_id = auto.get("id", "")

        # 'in' refs: pra onde a automation MOVE um card.
        action = auto.get("action_params") or {}
        for key in ("to_phase_id", "phase"):
            pid = _phase_id_from(action.get(key))
            if pid:
                refs.setdefault(pid, {"ins": set(), "outs": set()})["ins"].add(auto_id)

        event = auto.get("event_params") or {}
        for key in ("to_phase_id",):
            pid = _phase_id_from(event.get(key))
            if pid:
                refs.setdefault(pid, {"ins": set(), "outs": set()})["ins"].add(auto_id)

        # 'out' refs: phase onde a automation dispara.
        for key in ("phase", "fromPhaseId", "inPhaseId"):
            pid = _phase_id_from(event.get(key))
            if pid:
                refs.setdefault(pid, {"ins": set(), "outs": set()})["outs"].add(auto_id)

    return refs


def compute_blast_radius(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pra cada phase do snapshot, calcula 'blast radius' indicativo:
    cards_count quando disponivel, contagem de automations que entram e
    saem da phase, peso final (combinacao). Retorna lista ordenada por
    peso desc.

    Saida pra UI: pra cada phase, mostra "Mexer aqui afeta N cards reais
    e M automations".
    """
    pipe = (snapshot or {}).get("data", {}).get("pipe", {})
    phases = pipe.get("phases") or []
    automations = (snapshot or {}).get("data", {}).get("automations") or []
    auto_refs = _automation_phase_references(automations)

    out: List[Dict[str, Any]] = []
    for ph in phases:
        pid = ph.get("id")
        if not pid:
            continue
        cards_count = ph.get("cards_count")  # None pra snapshots v1.0-1.2 ou se Pipefy nao retornou
        refs = auto_refs.get(pid, {"ins": set(), "outs": set()})
        ins_count = len(refs["ins"])
        outs_count = len(refs["outs"])
        # Peso indicativo (heuristica): cards * 1 + automations * 5
        weight = (cards_count or 0) + (ins_count + outs_count) * 5
        out.append({
            "phase_id": pid,
            "phase_name": ph.get("name", ""),
            "cards_count": cards_count,
            "automations_in": ins_count,
            "automations_out": outs_count,
            "automations_total": ins_count + outs_count,
            "weight": weight,
        })
    out.sort(key=lambda p: -p["weight"])
    return out


def compute_phase_coverage(
    snapshot: Dict[str, Any],
    rules: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Identifica problemas de cobertura por phase:
    - orphan: phase sem automation que ENTRA (so chega via criacao manual)
    - no_sla: phase sem expiration_time_by_card
    - no_description: phase sem description
    - heavy: phase com cards_count >= threshold
    """
    rules = rules or {}
    threshold = rules.get("heavy_phase_threshold", 50)
    flag_orphan = rules.get("flag_orphan_phases", True)
    require_sla = rules.get("require_sla_for_phases", True)

    pipe = (snapshot or {}).get("data", {}).get("pipe", {})
    phases = pipe.get("phases") or []
    automations = (snapshot or {}).get("data", {}).get("automations") or []
    auto_refs = _automation_phase_references(automations)

    findings: List[Dict[str, Any]] = []
    for idx, ph in enumerate(phases):
        pid = ph.get("id")
        if not pid:
            continue
        name = ph.get("name", "")
        refs = auto_refs.get(pid, {"ins": set(), "outs": set()})

        # orphan_phase: pular a primeira phase do pipe.
        # Pipefy entrega phases em ordem; a primeira recebe cards via start_form
        # (criacao manual), nao via automation. Sinalizar ela como orfa eh falso
        # positivo garantido em todo pipe.
        if flag_orphan and idx > 0 and len(refs["ins"]) == 0:
            findings.append({
                "check_id": "orphan_phase",
                "category": "consistency",
                "severity": "med",
                "phase_id": pid, "phase_name": name,
                "message": f"Phase '{name}' nao tem automation que move card pra ela (so chega via criacao manual)",
            })
        if require_sla and not ph.get("expiration_time_by_card"):
            findings.append({
                "check_id": "phase_without_sla",
                "category": "sla",
                "severity": "low",
                "phase_id": pid, "phase_name": name,
                "message": f"Phase '{name}' sem SLA (expiration_time_by_card) configurado",
            })
        if not ph.get("description"):
            findings.append({
                "check_id": "phase_without_description",
                "category": "documentation",
                "severity": "low",
                "phase_id": pid, "phase_name": name,
                "message": f"Phase '{name}' sem descricao",
            })
        cards_count = ph.get("cards_count")
        if cards_count is not None and cards_count >= threshold:
            findings.append({
                "check_id": "heavy_phase",
                "category": "blast_radius",
                "severity": "high",
                "phase_id": pid, "phase_name": name,
                "message": f"Phase '{name}' tem {cards_count} cards (>= {threshold}) — mudancas tem alto blast radius",
                "cards_count": cards_count,
            })

    return findings


def compute_field_coverage(
    snapshot: Dict[str, Any],
    rules: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Identifica problemas de cobertura por field:
    - sem description (documentacao baixa)
    """
    rules = rules or {}
    require_desc = rules.get("require_description_for_fields", True)
    if not require_desc:
        return []

    findings: List[Dict[str, Any]] = []
    pipe = (snapshot or {}).get("data", {}).get("pipe", {})
    for fld in pipe.get("start_form_fields") or []:
        if not fld.get("description"):
            findings.append({
                "check_id": "field_without_description",
                "category": "documentation",
                "severity": "low",
                "field_id": fld.get("id"),
                "field_label": fld.get("label"),
                "scope": "start_form",
                "message": f"Start form field '{fld.get('label', fld.get('id'))}' sem descricao",
            })
    for ph in pipe.get("phases") or []:
        pname = ph.get("name", "")
        for fld in ph.get("fields") or []:
            if not fld.get("description"):
                findings.append({
                    "check_id": "field_without_description",
                    "category": "documentation",
                    "severity": "low",
                    "field_id": fld.get("id"),
                    "field_label": fld.get("label"),
                    "scope": "phase",
                    "phase_name": pname,
                    "message": f"Phase '{pname}' · field '{fld.get('label', fld.get('id'))}' sem descricao",
                })
    return findings


def scan_pipe_coverage(
    snapshot: Dict[str, Any],
    rules: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Roda todos os scans de coverage e retorna estrutura agregada com
    blast_radius (lista de phases) + findings (problemas detectados) +
    summary."""
    blast = compute_blast_radius(snapshot)
    findings = compute_phase_coverage(snapshot, rules) + compute_field_coverage(snapshot, rules)
    findings.sort(key=lambda f: (-_SEVERITY_RANK.get(f.get("severity", "low"), 0),
                                 f.get("category", "")))
    return {
        "blast_radius": blast,
        "findings": findings,
        "summary": summarize_coverage(blast, findings),
    }


def summarize_coverage(blast: List[Dict[str, Any]], findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_severity = {"high": 0, "med": 0, "low": 0}
    by_category: Dict[str, int] = {}
    by_check: Dict[str, int] = {}
    for f in findings:
        sev = f.get("severity", "low")
        if sev in by_severity:
            by_severity[sev] += 1
        cat = f.get("category", "outros")
        by_category[cat] = by_category.get(cat, 0) + 1
        cid = f.get("check_id", "")
        if cid:
            by_check[cid] = by_check.get(cid, 0) + 1

    total_cards = sum((p.get("cards_count") or 0) for p in blast)
    phases_with_cards = sum(1 for p in blast if (p.get("cards_count") or 0) > 0)
    heaviest = blast[:3] if blast else []
    return {
        "total_findings": len(findings),
        "by_severity": by_severity,
        "by_category": by_category,
        "by_check": by_check,
        "phases_total": len(blast),
        "cards_total": total_cards,
        "phases_with_cards": phases_with_cards,
        "top_heavy_phases": [
            {"phase_id": p["phase_id"], "phase_name": p["phase_name"],
             "cards_count": p.get("cards_count"), "weight": p.get("weight")}
            for p in heaviest
        ],
    }


# ============================================================
# Historico (mesma estrutura dos outros scanners)
# ============================================================

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
    # Inclui microsegundos no filename pra evitar colisao quando 2 runs ocorrem
    # no mesmo segundo (cron paralelo + trigger manual, por exemplo).
    filename = now.strftime("%Y%m%d_%H%M%S_%f") + ".json"
    path = _os.path.join(pipe_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    if retention > 0:
        # Filtra apenas filenames no padrao YYYYMMDD_HHMMSS[_microsec].json
        # pra retencao nao apagar arquivos manuais (summary.json, etc).
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
