"""Engine de metricas pro Dashboard executivo.

Funcoes puras (sem efeito colateral no estado do app) que consomem o output
existente do validador (results/validations.json e snapshots/) e produzem
metricas de produtividade.

Sprint 1: compute_velocity(), compute_debt().
Sprint 3: compute_hotspots(), compute_leadtime().
Sprints futuras: compute_burnup().

Tudo que esta aqui e read-only sobre arquivos. Nao mexe em validations.json,
nao escreve no filesystem (a menos que explicitamente pedido).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
from glob import glob
from typing import Any, Dict, Iterable, List, Optional, Tuple


# Regex pra extrair prefixo entre colchetes do inicio da string de divergencia.
# Ex: "[CAMPO AUSENTE] Campo X..." -> "[CAMPO AUSENTE]"
_PREFIX_RE = re.compile(r"^(\[[^\]]+\])")


def load_weights(weights_path: str) -> Dict[str, Any]:
    """Carrega o complexity_weights.json. Retorna dict puro."""
    with open(weights_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_prefix(divergencia: str) -> Optional[str]:
    """Extrai o prefixo '[CATEGORIA]' da string de divergencia.
    Retorna None se nao casa o pattern."""
    if not isinstance(divergencia, str):
        return None
    match = _PREFIX_RE.match(divergencia.strip())
    return match.group(1) if match else None


def score_divergencia(divergencia: str, weights: Dict[str, Any]) -> Dict[str, Any]:
    """Pontua uma unica divergencia. Retorna dict com:
    - prefix: prefixo identificado (ou None)
    - weight: peso aplicado
    - bucket: balde da UI (visual/structure/logic/integration)
    - label: descricao legivel
    - text: texto original da divergencia
    """
    prefix = extract_prefix(divergencia)
    prefix_map = weights.get("divergencia_prefix_weights", {})
    default = weights.get("default_weight", {"weight": 2, "bucket": "structure", "label": "Generica"})

    entry = prefix_map.get(prefix) if prefix else None
    if not entry:
        entry = default

    return {
        "prefix": prefix,
        # entry["weight"] pode existir como null no JSON. `... or 0` cobre
        # None E 0 explicito (identidade), antes float(None) levantava TypeError.
        "weight": float(entry.get("weight") or 0),
        "bucket": entry.get("bucket", "structure"),
        "label": entry.get("label", "Generica"),
        "text": divergencia,
    }


def score_validations(validations: Dict[str, Any], weights: Dict[str, Any]) -> Dict[str, Any]:
    """Pontua um validations.json inteiro. Retorna agregado:
    - total_points: soma dos pesos
    - by_bucket: {visual: X, structure: Y, logic: Z, integration: W}
    - by_prefix: {prefixo: {count, total_weight}}
    - top_items: top 10 divergencias por peso (descendente)
    - meta: timestamp, status, pipe_origem, pipe_destino do input
    """
    divergencias = validations.get("divergencias", []) or []
    scored = [score_divergencia(d, weights) for d in divergencias]

    by_bucket: Dict[str, float] = {"visual": 0.0, "structure": 0.0, "logic": 0.0, "integration": 0.0}
    by_prefix: Dict[str, Dict[str, float]] = {}

    for s in scored:
        bucket = s["bucket"]
        if bucket not in by_bucket:
            by_bucket[bucket] = 0.0
        by_bucket[bucket] += s["weight"]

        prefix = s["prefix"] or "(sem prefixo)"
        if prefix not in by_prefix:
            by_prefix[prefix] = {"count": 0, "total_weight": 0.0, "label": s["label"]}
        by_prefix[prefix]["count"] += 1
        by_prefix[prefix]["total_weight"] += s["weight"]

    total_points = round(sum(s["weight"] for s in scored), 2)
    by_bucket = {k: round(v, 2) for k, v in by_bucket.items()}
    for p in by_prefix.values():
        p["total_weight"] = round(p["total_weight"], 2)

    top_items = sorted(scored, key=lambda x: x["weight"], reverse=True)[:10]

    metadata = validations.get("metadata", {}) or {}

    return {
        "total_points": total_points,
        "by_bucket": by_bucket,
        "by_prefix": by_prefix,
        "top_items": [
            {"weight": s["weight"], "bucket": s["bucket"], "label": s["label"], "text": s["text"]}
            for s in top_items
        ],
        "meta": {
            "status": validations.get("status"),
            "pipe_origem": validations.get("pipe_origem"),
            "pipe_destino": validations.get("pipe_destino"),
            "total_divergencias": validations.get("total_divergencias", len(divergencias)),
            "timestamp": metadata.get("timestamp"),
            "tool_version": metadata.get("tool_version"),
        },
        "weights_version": weights.get("version", "unknown"),
    }


def list_historical_validations(results_dir: str) -> List[str]:
    """Lista arquivos validations*.json em results/ pra Sprint 3+ ter historico.
    Hoje so existe results/validations.json (rolling). Quando tivermos snapshots
    com timestamp, esta funcao retorna paths ordenados por timestamp."""
    if not os.path.isdir(results_dir):
        return []
    paths = sorted(glob(os.path.join(results_dir, "validations*.json")))
    return paths


def classify_debt_level(total_points: float) -> str:
    """Classifica pontos totais em nivel de debito categorico.

    Sprint 1 usa proxy de divergencias (cross-env). Limites calibrados por
    intuicao, ajustar apos 2-3 sprints de uso.
    - 0 pts        -> CLEAN  (verde, nenhum debito detectado)
    - 1-30 pts     -> LOW    (amarelo claro, debito controlado)
    - 31-80 pts    -> MEDIUM (laranja, atencao)
    - 80+ pts      -> HIGH   (vermelho, refator urgente)
    """
    pts = total_points or 0
    if pts <= 0:
        return "CLEAN"
    if pts <= 30:
        return "LOW"
    if pts <= 80:
        return "MEDIUM"
    return "HIGH"


def compute_debt(
    validations_path: str,
    weights_path: str,
) -> Dict[str, Any]:
    """Computa Debt Index sobre o validations.json mais recente.

    Sprint 1: usa divergencias cross-env como proxy de debito (mais
    divergencias = mais problemas que ainda precisam ser endereçados).
    Sprint 3 vai expandir pra debito intrinseco (regras estaticas sobre
    snapshot atual: automation sem condition, field sem doc, etc).
    """
    if not os.path.exists(validations_path):
        return {
            "available": False,
            "reason": "Sem validacao executada ainda. Rode uma comparacao primeiro.",
            "level": "CLEAN",
            "total_points": 0,
            "by_bucket": {"visual": 0, "structure": 0, "logic": 0, "integration": 0},
            "issues_count": 0,
            "top_issues": [],
        }

    try:
        with open(validations_path, "r", encoding="utf-8") as f:
            validations = json.load(f)
    except (json.JSONDecodeError, IOError) as ex:
        return {
            "available": False,
            "reason": f"Falha lendo validations.json: {ex}",
            "level": "CLEAN",
            "total_points": 0,
            "by_bucket": {"visual": 0, "structure": 0, "logic": 0, "integration": 0},
            "issues_count": 0,
            "top_issues": [],
        }

    weights = load_weights(weights_path)
    scoring = score_validations(validations, weights)

    total = scoring["total_points"]
    level = classify_debt_level(total)
    issues_count = scoring["meta"].get("total_divergencias", 0)

    return {
        "available": True,
        "level": level,
        "total_points": total,
        "by_bucket": scoring["by_bucket"],
        "by_prefix": scoring["by_prefix"],
        "issues_count": issues_count,
        "top_issues": scoring["top_items"],
        "meta": scoring["meta"],
        "weights_version": scoring["weights_version"],
        "thresholds": {
            "CLEAN": "0 pts",
            "LOW": "1-30 pts",
            "MEDIUM": "31-80 pts",
            "HIGH": "80+ pts",
        },
    }


def compute_velocity(
    validations_path: str,
    weights_path: str,
) -> Dict[str, Any]:
    """Computa velocity da run mais recente (Sprint 1).

    Le results/validations.json e config/complexity_weights.json,
    aplica scoring, retorna agregado pronto pra UI.

    Sprint 3 vai estender pra computar serie historica.
    """
    if not os.path.exists(validations_path):
        return {
            "available": False,
            "reason": "Sem validacao executada ainda. Rode uma comparacao primeiro.",
            "total_points": 0,
            "by_bucket": {"visual": 0, "structure": 0, "logic": 0, "integration": 0},
            "by_prefix": {},
            "top_items": [],
            "meta": {},
        }

    try:
        with open(validations_path, "r", encoding="utf-8") as f:
            validations = json.load(f)
    except (json.JSONDecodeError, IOError) as ex:
        return {
            "available": False,
            "reason": f"Falha lendo validations.json: {ex}",
            "total_points": 0,
            "by_bucket": {"visual": 0, "structure": 0, "logic": 0, "integration": 0},
            "by_prefix": {},
            "top_items": [],
            "meta": {},
        }

    weights = load_weights(weights_path)
    result = score_validations(validations, weights)
    result["available"] = True
    return result


# ============================================================
# Sprint 3 — Hot Spots e Lead Time
# ============================================================

# Pesos pra mudancas temporais (snapshot N vs N+1 do mesmo pipe).
# Reaproveitam a tabela de divergencias (config/complexity_weights.json) via
# divergencia_prefix_weights, mas hot spots opera sobre eventos (kind),
# entao mantemos um mapa kind -> prefix de divergencia pra reusar pesos.
_HOTSPOT_KIND_TO_PREFIX = {
    "phase_create":            "[FASE EXTRA]",
    "phase_delete":            "[FASE AUSENTE]",
    "phase_rename":            "[LABEL EXTRA]",   # rename = mudanca de apresentacao (peso 1)
    "phase_field_create":      "[CAMPO EXTRA]",
    "phase_field_delete":      "[CAMPO AUSENTE]",
    "phase_field_type_change": "[TIPO DIFERENTE]",
    "phase_field_required":    "[REQUIRED DIFERENTE]",
    "startform_field_create":  "[START FORM - CAMPO EXTRA]",
    "startform_field_delete":  "[START FORM - CAMPO AUSENTE]",
    "startform_field_type_change": "[TIPO DIFERENTE]",
}


def _read_snapshot(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _safe_id(pipe_id: str) -> str:
    """Sanitiza pipe_id pra usar como nome de pasta no filesystem."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", pipe_id or "")[:64] or "unknown"


def _list_pipe_snapshots(snapshots_root: str, pipe_id: str) -> List[Tuple[str, Dict[str, Any]]]:
    """Lista snapshots de um pipe ordenados ascendente.

    Ordem preferida: metadata.timestamp parseado quando disponivel (robusto a
    nomenclatura nao padronizada). Fallback: nome do arquivo. Antes assumia
    sempre YYYYMMDD_HHMMSS no filename e quebrava cronologia se algum arquivo
    fugia do padrao."""
    pipe_dir = os.path.join(snapshots_root, _safe_id(pipe_id))
    if not os.path.isdir(pipe_dir):
        return []
    files = [f for f in os.listdir(pipe_dir) if f.endswith(".json")]
    out: List[Tuple[str, Dict[str, Any]]] = []
    for f in files:
        snap = _read_snapshot(os.path.join(pipe_dir, f))
        if snap is not None:
            out.append((f, snap))
    def _sort_key(entry):
        ts = _ts_of(entry[1])
        # Tupla (kind, value): 0 pra snapshots com timestamp valido, 1 pra
        # fallback por nome (vao depois). Garante ordem total estavel.
        if ts is not None:
            return (0, ts, entry[0])
        return (1, _dt.datetime.min, entry[0])
    out.sort(key=_sort_key)
    return out


def _extract_pipe_schema(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza snapshot pra forma {phases: {id: {name, fields: {id: field}}}, start_form: {id: field}}."""
    pipe = (snapshot.get("data") or {}).get("pipe") or {}
    phases_index: Dict[str, Dict[str, Any]] = {}
    for ph in pipe.get("phases") or []:
        pid = ph.get("id")
        if not pid:
            continue
        fields_index: Dict[str, Dict[str, Any]] = {}
        for fld in ph.get("fields") or []:
            fid = fld.get("id")
            if fid:
                fields_index[fid] = fld
        phases_index[pid] = {
            "name": ph.get("name", ""),
            "fields": fields_index,
        }
    sf_index: Dict[str, Dict[str, Any]] = {}
    for fld in pipe.get("start_form_fields") or []:
        fid = fld.get("id")
        if fid:
            sf_index[fid] = fld
    return {"phases": phases_index, "start_form": sf_index}


def _diff_schemas(prev: Dict[str, Any], curr: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compara dois schemas normalizados e retorna lista de eventos.
    Cada evento: {kind, phase_id (ou None), phase_name, field_id (opcional), detail}."""
    events: List[Dict[str, Any]] = []

    prev_phases = prev.get("phases", {})
    curr_phases = curr.get("phases", {})

    # Phases criadas
    for pid in curr_phases.keys() - prev_phases.keys():
        events.append({
            "kind": "phase_create",
            "phase_id": pid,
            "phase_name": curr_phases[pid]["name"],
        })
    # Phases deletadas
    for pid in prev_phases.keys() - curr_phases.keys():
        events.append({
            "kind": "phase_delete",
            "phase_id": pid,
            "phase_name": prev_phases[pid]["name"],
        })
    # Phases existentes em ambos
    for pid in prev_phases.keys() & curr_phases.keys():
        prev_p = prev_phases[pid]
        curr_p = curr_phases[pid]
        if prev_p["name"] != curr_p["name"]:
            events.append({
                "kind": "phase_rename",
                "phase_id": pid,
                "phase_name": curr_p["name"],
                "detail": f"{prev_p['name']!r} -> {curr_p['name']!r}",
            })
        # Fields da phase
        prev_f = prev_p["fields"]
        curr_f = curr_p["fields"]
        for fid in curr_f.keys() - prev_f.keys():
            events.append({
                "kind": "phase_field_create",
                "phase_id": pid, "phase_name": curr_p["name"],
                "field_id": fid, "detail": curr_f[fid].get("label", ""),
            })
        for fid in prev_f.keys() - curr_f.keys():
            events.append({
                "kind": "phase_field_delete",
                "phase_id": pid, "phase_name": curr_p["name"],
                "field_id": fid, "detail": prev_f[fid].get("label", ""),
            })
        for fid in prev_f.keys() & curr_f.keys():
            if prev_f[fid].get("type") != curr_f[fid].get("type"):
                events.append({
                    "kind": "phase_field_type_change",
                    "phase_id": pid, "phase_name": curr_p["name"],
                    "field_id": fid,
                    "detail": f"{prev_f[fid].get('type')} -> {curr_f[fid].get('type')}",
                })
            if bool(prev_f[fid].get("required")) != bool(curr_f[fid].get("required")):
                events.append({
                    "kind": "phase_field_required",
                    "phase_id": pid, "phase_name": curr_p["name"],
                    "field_id": fid,
                    "detail": f"required {prev_f[fid].get('required')} -> {curr_f[fid].get('required')}",
                })

    # Start form: nao tem phase, agrupa em phase_id virtual "_startform_".
    prev_sf = prev.get("start_form", {})
    curr_sf = curr.get("start_form", {})
    for fid in curr_sf.keys() - prev_sf.keys():
        events.append({
            "kind": "startform_field_create",
            "phase_id": "_startform_", "phase_name": "(Start Form)",
            "field_id": fid, "detail": curr_sf[fid].get("label", ""),
        })
    for fid in prev_sf.keys() - curr_sf.keys():
        events.append({
            "kind": "startform_field_delete",
            "phase_id": "_startform_", "phase_name": "(Start Form)",
            "field_id": fid, "detail": prev_sf[fid].get("label", ""),
        })
    for fid in prev_sf.keys() & curr_sf.keys():
        if prev_sf[fid].get("type") != curr_sf[fid].get("type"):
            events.append({
                "kind": "startform_field_type_change",
                "phase_id": "_startform_", "phase_name": "(Start Form)",
                "field_id": fid,
                "detail": f"{prev_sf[fid].get('type')} -> {curr_sf[fid].get('type')}",
            })
    return events


def _weight_for_kind(kind: str, weights: Dict[str, Any]) -> Tuple[float, str, str]:
    """Retorna (peso, bucket, label) pra um kind de mudanca temporal."""
    prefix = _HOTSPOT_KIND_TO_PREFIX.get(kind)
    if not prefix:
        d = weights.get("default_weight", {})
        return (float(d.get("weight") or 2), d.get("bucket", "structure"), d.get("label", "Mudanca generica"))
    entry = (weights.get("divergencia_prefix_weights") or {}).get(prefix)
    if not entry:
        d = weights.get("default_weight", {})
        return (float(d.get("weight") or 2), d.get("bucket", "structure"), d.get("label", "Mudanca generica"))
    # `or 0` cobre weight: null e weight ausente sem levantar TypeError.
    return (float(entry.get("weight") or 0), entry.get("bucket", "structure"), entry.get("label", kind))


def _classify_hotspot_level(score: float) -> str:
    """Limites calibrados por intuicao em cima do cenario do seed.
    Recalibrar apos 2-3 sprints de dado real. Score = total_weight de mudancas
    naquela phase no perido analisado."""
    if score <= 0:
        return "CLEAN"
    if score < 8:
        return "LOW"
    if score < 20:
        return "MEDIUM"
    return "HIGH"


def compute_hotspots(
    snapshots_root: str,
    pipe_id: str,
    weights_path: str,
    max_samples_per_phase: int = 5,
) -> Dict[str, Any]:
    """Computa hot spots de um pipe a partir do historico de snapshots.

    Estrategia: ordena snapshots por timestamp, compara cada par consecutivo,
    extrai eventos (rename/create/delete/type_change), agrega por phase_id.
    Phases que mais mudam acumulam score = soma de pesos das mudancas.
    """
    snapshots = _list_pipe_snapshots(snapshots_root, pipe_id)
    if len(snapshots) < 2:
        return {
            "available": False,
            "reason": "Historico insuficiente. Sao necessarios >= 2 snapshots.",
            "pipe_id": pipe_id,
            "snapshot_count": len(snapshots),
            "phases": [],
        }

    weights = load_weights(weights_path)

    # Agrega por phase_id.
    phases_agg: Dict[str, Dict[str, Any]] = {}
    total_changes = 0
    first_ts = snapshots[0][1].get("metadata", {}).get("timestamp")
    last_ts = snapshots[-1][1].get("metadata", {}).get("timestamp")

    for i in range(1, len(snapshots)):
        prev_filename, prev_snap = snapshots[i-1]
        curr_filename, curr_snap = snapshots[i]
        prev_schema = _extract_pipe_schema(prev_snap)
        curr_schema = _extract_pipe_schema(curr_snap)
        events = _diff_schemas(prev_schema, curr_schema)

        when = curr_snap.get("metadata", {}).get("timestamp", curr_filename)
        for ev in events:
            pid = ev.get("phase_id") or "(sem phase)"
            weight, bucket, label = _weight_for_kind(ev["kind"], weights)
            total_changes += 1

            if pid not in phases_agg:
                phases_agg[pid] = {
                    "phase_id": pid,
                    "phase_name": ev.get("phase_name", ""),
                    "change_count": 0,
                    "total_weight": 0.0,
                    "by_bucket": {"visual": 0.0, "structure": 0.0, "logic": 0.0, "integration": 0.0},
                    "samples": [],
                }
            entry = phases_agg[pid]
            # Mantem ultimo nome conhecido (em rename, prefere o novo).
            entry["phase_name"] = ev.get("phase_name", entry["phase_name"])
            entry["change_count"] += 1
            entry["total_weight"] = round(entry["total_weight"] + weight, 2)
            if bucket in entry["by_bucket"]:
                entry["by_bucket"][bucket] = round(entry["by_bucket"][bucket] + weight, 2)

            if len(entry["samples"]) < max_samples_per_phase:
                entry["samples"].append({
                    "when": when,
                    "kind": ev["kind"],
                    "label": label,
                    "weight": weight,
                    "bucket": bucket,
                    "detail": ev.get("detail", ""),
                    "field_id": ev.get("field_id"),
                })

    # Score = total_weight (frequencia ja esta embutida no somatorio).
    phases_list = []
    for pid, data in phases_agg.items():
        score = data["total_weight"]
        phases_list.append({
            **data,
            "score": score,
            "level": _classify_hotspot_level(score),
        })
    phases_list.sort(key=lambda x: x["score"], reverse=True)
    max_score = phases_list[0]["score"] if phases_list else 0.0

    return {
        "available": True,
        "pipe_id": pipe_id,
        "snapshot_count": len(snapshots),
        "window_start": first_ts,
        "window_end": last_ts,
        "total_changes": total_changes,
        "max_score": max_score,
        "phases": phases_list,
        "thresholds": {
            "CLEAN": "0",
            "LOW": "<8",
            "MEDIUM": "8-19",
            "HIGH": ">=20",
        },
    }


def _normalize_base_name(name: str) -> str:
    """Extrai nome base de um pipe pra casar pares HMG/PRD.
    Remove sufixos de ambiente comuns: -HMG, -PRD, (HMG), (PRD), (demo).
    Case-insensitive."""
    s = (name or "").strip()
    # Remove sufixos com hifen/em-dash/parenteses.
    s = re.sub(r"\s*[-–—]\s*(HMG|PRD|HML|PROD|UAT|DEV)\b.*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*\(\s*(HMG|PRD|HML|PROD|UAT|DEV)\s*\)", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*\(\s*demo\s*\)", "", s, flags=re.IGNORECASE)
    return s.strip().lower()


def _pair_monitored_pipes(monitored: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Agrupa pipes monitorados em pares HMG/PRD pelo nome base."""
    by_base: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for p in monitored or []:
        if not p.get("enabled", True):
            continue
        base = _normalize_base_name(p.get("name", ""))
        env = (p.get("env_label") or "").strip().upper()
        if not base or env not in ("HMG", "PRD"):
            continue
        slot = by_base.setdefault(base, {})
        slot[env] = p

    pairs: List[Dict[str, Any]] = []
    for base, slot in by_base.items():
        if "HMG" in slot and "PRD" in slot:
            pairs.append({"base_name": base, "hmg": slot["HMG"], "prd": slot["PRD"]})
    return pairs


def _ts_of(snapshot: Dict[str, Any]) -> Optional[_dt.datetime]:
    """Parseia metadata.timestamp pra datetime naive.

    Aceita formatos com sufixo Z (UTC) e offset explicito (+HH:MM).
    Normaliza pra UTC naive antes de retornar — antes podia retornar mix
    aware/naive que levantava TypeError em comparacoes
    (_business_days_between, sort). Snapshots sem timezone ficam naive como
    antes (sem suposicao implicita de fuso, mantem compat historica)."""
    ts = snapshot.get("metadata", {}).get("timestamp")
    if not ts:
        return None
    s = str(ts).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(_dt.timezone.utc).replace(tzinfo=None)
    return dt


def _first_appearance_index(
    snapshots: List[Tuple[str, Dict[str, Any]]],
) -> Tuple[Dict[str, _dt.datetime], Dict[str, _dt.datetime], Dict[Tuple[str, str], _dt.datetime]]:
    """Retorna (first_seen_phases, first_seen_startform_fields, first_seen_phase_fields).
    O ultimo dicionario indexa por (phase_id, field_id) pra rastrear quando um
    field nasceu DENTRO de uma phase."""
    first_phase: Dict[str, _dt.datetime] = {}
    first_field: Dict[str, _dt.datetime] = {}
    first_phase_field: Dict[Tuple[str, str], _dt.datetime] = {}
    for _, snap in snapshots:
        when = _ts_of(snap)
        if when is None:
            continue
        schema = _extract_pipe_schema(snap)
        for pid, phase_data in schema["phases"].items():
            first_phase.setdefault(pid, when)
            for fid in phase_data["fields"].keys():
                first_phase_field.setdefault((pid, fid), when)
        for fid in schema["start_form"].keys():
            first_field.setdefault(fid, when)
    return first_phase, first_field, first_phase_field


def _business_days_between(a: _dt.datetime, b: _dt.datetime) -> float:
    """Retorna dias uteis (Mon-Fri) entre a e b. Float pra preservar fracao
    quando snapshots ocorrem em horas distintas. Ignora feriados."""
    if a is None or b is None:
        return 0.0
    if b < a:
        a, b = b, a
    days = 0.0
    cur = a
    # Fracao do dia inicial ate fim do dia (se util).
    if cur.weekday() < 5:
        end_of_day = _dt.datetime(cur.year, cur.month, cur.day, 23, 59, 59)
        days += min((end_of_day - cur).total_seconds(), (b - cur).total_seconds()) / 86400.0
    cur = _dt.datetime(cur.year, cur.month, cur.day) + _dt.timedelta(days=1)
    while cur.date() < b.date():
        if cur.weekday() < 5:
            days += 1.0
        cur += _dt.timedelta(days=1)
    if cur.date() == b.date() and b.weekday() < 5:
        start_of_day = _dt.datetime(b.year, b.month, b.day)
        days += (b - start_of_day).total_seconds() / 86400.0
    return round(days, 2)


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return round((s[n // 2 - 1] + s[n // 2]) / 2.0, 2)


def compute_leadtime(
    snapshots_root: str,
    monitored: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Computa lead time HMG -> PRD pra todos os pares de pipes monitorados.

    Estrategia: elementos que ja existiam no PRIMEIRO snapshot de HMG (e
    tambem no primeiro de PRD) sao baseline pre-existente, nao representam
    promocao real, entao sao filtrados. So conta lag pra elementos cuja
    primeira aparicao em HMG foi DEPOIS do primeiro snapshot, ou seja, eles
    nasceram durante a janela observada.

    Pra cada par (HMG, PRD):
        - first_appearance de cada phase/field em cada lado
        - filtra baseline (existia em ambos no t0)
        - lag = first_seen_PRD - first_seen_HMG em dias uteis
        - pendentes = nasceu em HMG durante a janela mas ainda nao chegou em PRD
    """
    pairs = _pair_monitored_pipes(monitored)
    if not pairs:
        return {
            "available": False,
            "reason": "Sem pares HMG/PRD configurados em monitored_pipes.json (precisa de 2 pipes com mesmo nome base e env_label HMG/PRD).",
            "pairs": [],
        }

    pair_results: List[Dict[str, Any]] = []
    all_lags: List[float] = []

    for pair in pairs:
        hmg_pipe = pair["hmg"]
        prd_pipe = pair["prd"]
        hmg_snaps = _list_pipe_snapshots(snapshots_root, hmg_pipe.get("id", ""))
        prd_snaps = _list_pipe_snapshots(snapshots_root, prd_pipe.get("id", ""))

        if not hmg_snaps or not prd_snaps:
            pair_results.append({
                "base_name": pair["base_name"],
                "available": False,
                "reason": "Pipe sem snapshots ainda.",
                "hmg_id": hmg_pipe.get("id"),
                "prd_id": prd_pipe.get("id"),
                "hmg_snapshot_count": len(hmg_snaps),
                "prd_snapshot_count": len(prd_snaps),
            })
            continue

        hmg_t0 = _ts_of(hmg_snaps[0][1])
        hmg_phase_first, hmg_sf_first, hmg_pf_first = _first_appearance_index(hmg_snaps)
        prd_phase_first, prd_sf_first, prd_pf_first = _first_appearance_index(prd_snaps)

        # Identifica baseline: elementos que apareceram no proprio t0 em HMG
        # E tambem em PRD ate aquele mesmo dia. Sao schema pre-existente.
        prd_t0 = _ts_of(prd_snaps[0][1])

        def _is_baseline(hmg_when, prd_when):
            return (hmg_t0 is not None and hmg_when <= hmg_t0 and
                    prd_when is not None and prd_t0 is not None and prd_when <= prd_t0)

        promoted: List[Dict[str, Any]] = []
        pending: List[Dict[str, Any]] = []
        baseline_count = 0

        for pid, hmg_when in hmg_phase_first.items():
            prd_when = prd_phase_first.get(pid)
            if _is_baseline(hmg_when, prd_when):
                baseline_count += 1
                continue
            if prd_when is None:
                pending.append({"kind": "phase", "id": pid, "label": pid, "hmg_when": hmg_when.isoformat()})
                continue
            lag = _business_days_between(hmg_when, prd_when)
            promoted.append({
                "kind": "phase",
                "id": pid,
                "label": pid,
                "hmg_when": hmg_when.isoformat(),
                "prd_when": prd_when.isoformat(),
                "lag_days": lag,
            })
            all_lags.append(lag)

        for fid, hmg_when in hmg_sf_first.items():
            prd_when = prd_sf_first.get(fid)
            if _is_baseline(hmg_when, prd_when):
                baseline_count += 1
                continue
            if prd_when is None:
                pending.append({"kind": "startform_field", "id": fid, "label": fid, "hmg_when": hmg_when.isoformat()})
                continue
            lag = _business_days_between(hmg_when, prd_when)
            promoted.append({
                "kind": "startform_field",
                "id": fid,
                "label": fid,
                "hmg_when": hmg_when.isoformat(),
                "prd_when": prd_when.isoformat(),
                "lag_days": lag,
            })
            all_lags.append(lag)

        for (pid, fid), hmg_when in hmg_pf_first.items():
            prd_when = prd_pf_first.get((pid, fid))
            if _is_baseline(hmg_when, prd_when):
                baseline_count += 1
                continue
            if prd_when is None:
                pending.append({"kind": "phase_field", "id": f"{pid}.{fid}", "label": f"{pid}.{fid}", "hmg_when": hmg_when.isoformat()})
                continue
            lag = _business_days_between(hmg_when, prd_when)
            promoted.append({
                "kind": "phase_field",
                "id": f"{pid}.{fid}",
                "label": f"{pid}.{fid}",
                "hmg_when": hmg_when.isoformat(),
                "prd_when": prd_when.isoformat(),
                "lag_days": lag,
            })
            all_lags.append(lag)

        promoted.sort(key=lambda x: x["lag_days"], reverse=True)
        pair_lags = [p["lag_days"] for p in promoted]
        pair_results.append({
            "base_name": pair["base_name"],
            "available": True,
            "hmg_pipe": {"id": hmg_pipe.get("id"), "name": hmg_pipe.get("name")},
            "prd_pipe": {"id": prd_pipe.get("id"), "name": prd_pipe.get("name")},
            "hmg_snapshot_count": len(hmg_snaps),
            "prd_snapshot_count": len(prd_snaps),
            "baseline_count": baseline_count,
            "promoted_count": len(promoted),
            "pending_count": len(pending),
            "median_lag_days": _median(pair_lags),
            "mean_lag_days": round(sum(pair_lags) / len(pair_lags), 2) if pair_lags else 0.0,
            "max_lag_days": max(pair_lags) if pair_lags else 0.0,
            "promoted": promoted,
            "pending": pending,
        })

    return {
        "available": True,
        "pairs": pair_results,
        "global_median_lag_days": _median(all_lags),
        "global_mean_lag_days": round(sum(all_lags) / len(all_lags), 2) if all_lags else 0.0,
        "total_promoted_elements": len(all_lags),
    }


# ============================================================
# Sprint 4 — Burnup vs Blueprint
# ============================================================

def _blueprint_path(blueprints_root: str, pipe_id: str) -> str:
    return os.path.join(blueprints_root, f"{_safe_id(pipe_id)}.json")


def load_blueprint(blueprints_root: str, pipe_id: str) -> Optional[Dict[str, Any]]:
    """Le blueprint marcado pra um pipe. Retorna None se nao existe."""
    path = _blueprint_path(blueprints_root, pipe_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_blueprint(
    blueprints_root: str,
    pipe_id: str,
    snapshot: Dict[str, Any],
    source_filename: str,
    marked_at: Optional[str] = None,
) -> str:
    """Persiste copia do snapshot como blueprint do pipe.
    Estrutura: {marked_at, source_snapshot, snapshot}.
    Retorna path do arquivo gravado."""
    os.makedirs(blueprints_root, exist_ok=True)
    payload = {
        "marked_at": marked_at or _dt.datetime.now().isoformat(),
        "source_snapshot": source_filename,
        "snapshot": snapshot,
    }
    path = _blueprint_path(blueprints_root, pipe_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def delete_blueprint(blueprints_root: str, pipe_id: str) -> bool:
    """Remove blueprint do pipe. Retorna True se algo foi apagado."""
    path = _blueprint_path(blueprints_root, pipe_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def _coverage(covered_keys: Iterable, blueprint_keys: Iterable) -> Dict[str, Any]:
    """Calcula cobertura entre 2 sets de chaves."""
    blueprint_set = set(blueprint_keys)
    covered_set = set(covered_keys) & blueprint_set
    total = len(blueprint_set)
    covered = len(covered_set)
    pct = round((covered / total) * 100, 1) if total else 100.0
    missing = sorted(blueprint_set - covered_set)
    return {
        "covered": covered,
        "total": total,
        "pct": pct,
        "missing": missing,
    }


def compute_burnup(
    snapshots_root: str,
    blueprints_root: str,
    pipe_id: str,
) -> Dict[str, Any]:
    """Compara o snapshot mais recente do pipe contra o blueprint marcado.

    Cobertura = quantos elementos do blueprint ja existem no estado atual,
    por categoria (phases, phase_fields, start_form_fields). Itens que nao
    estao no blueprint mas estao no atual NAO penalizam (pode ser feature
    fora do escopo da migracao).
    """
    blueprint = load_blueprint(blueprints_root, pipe_id)
    if not blueprint:
        return {
            "available": False,
            "reason": "Sem blueprint marcado pra este pipe. Marque um snapshot como blueprint pra ter referencia.",
            "pipe_id": pipe_id,
        }

    snaps = _list_pipe_snapshots(snapshots_root, pipe_id)
    if not snaps:
        return {
            "available": False,
            "reason": "Pipe sem snapshots ainda. Cron precisa coletar pelo menos 1.",
            "pipe_id": pipe_id,
        }

    current_filename, current_snap = snaps[-1]
    current_schema = _extract_pipe_schema(current_snap)
    blueprint_schema = _extract_pipe_schema(blueprint.get("snapshot", {}))

    cov_phases = _coverage(
        current_schema["phases"].keys(),
        blueprint_schema["phases"].keys(),
    )
    cov_startform = _coverage(
        current_schema["start_form"].keys(),
        blueprint_schema["start_form"].keys(),
    )
    # phase_fields key = (phase_id, field_id).
    bp_pf = {(pid, fid) for pid, p in blueprint_schema["phases"].items() for fid in p["fields"].keys()}
    cur_pf = {(pid, fid) for pid, p in current_schema["phases"].items() for fid in p["fields"].keys()}
    cov_pf_raw = _coverage(cur_pf, bp_pf)
    cov_pf = {
        **cov_pf_raw,
        "missing": [f"{pid}.{fid}" for (pid, fid) in cov_pf_raw["missing"]],
    }

    # Overall: media ponderada por total de itens da categoria.
    total_all = cov_phases["total"] + cov_startform["total"] + cov_pf["total"]
    covered_all = cov_phases["covered"] + cov_startform["covered"] + cov_pf["covered"]
    overall_pct = round((covered_all / total_all) * 100, 1) if total_all else 100.0

    # Hidrata missing phases com nome legivel do blueprint.
    cov_phases["missing"] = [
        {"id": pid, "label": blueprint_schema["phases"][pid]["name"]}
        for pid in cov_phases["missing"]
    ]
    cov_startform["missing"] = [
        {"id": fid, "label": blueprint_schema["start_form"][fid].get("label", fid)}
        for fid in cov_startform["missing"]
    ]
    pf_labels = []
    for label_id in cov_pf["missing"]:
        try:
            pid, fid = label_id.split(".", 1)
            phase = blueprint_schema["phases"].get(pid, {})
            field = phase.get("fields", {}).get(fid, {})
            pf_labels.append({
                "id": label_id,
                "label": f"{phase.get('name', pid)} · {field.get('label', fid)}",
            })
        except ValueError:
            pf_labels.append({"id": label_id, "label": label_id})
    cov_pf["missing"] = pf_labels

    return {
        "available": True,
        "pipe_id": pipe_id,
        "overall_pct": overall_pct,
        "overall_covered": covered_all,
        "overall_total": total_all,
        "by_category": {
            "phases": cov_phases,
            "start_form_fields": cov_startform,
            "phase_fields": cov_pf,
        },
        "blueprint": {
            "marked_at": blueprint.get("marked_at"),
            "source_snapshot": blueprint.get("source_snapshot"),
            "blueprint_timestamp": blueprint.get("snapshot", {}).get("metadata", {}).get("timestamp"),
        },
        "current": {
            "filename": current_filename,
            "timestamp": current_snap.get("metadata", {}).get("timestamp"),
        },
    }
