"""Engine de metricas pro Dashboard executivo.

Funcoes puras (sem efeito colateral no estado do app) que consomem o output
existente do validador (results/validations.json e snapshots/) e produzem
metricas de produtividade.

Sprint 1 entrega: compute_velocity().
Sprints futuras adicionam: compute_debt_ratio(), compute_lead_time(),
compute_hot_spots(), compute_burnup().

Tudo que esta aqui e read-only sobre arquivos. Nao mexe em validations.json,
nao escreve no filesystem (a menos que explicitamente pedido).
"""
from __future__ import annotations

import json
import os
import re
from glob import glob
from typing import Any, Dict, List, Optional, Tuple


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
        "weight": float(entry.get("weight", 0)),
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
