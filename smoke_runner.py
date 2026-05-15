"""Smoke test runner — Frente 3 (Fase C) do PLANO-VALIDACAO-HMG-PRD.

Equivalente Datadog Synthetics aplicado a Pipefy. Diferente das Fases A e B
(read-only sobre snapshot), este modulo ESCREVE no Pipefy: cria card, move
por phases criticas, deleta. Por isso o gate eh forte:

- Default dry_run=true em todas funcoes
- Pipe precisa estar whitelistado em config/smoke_rules.json com enabled=true
- Pipes PRD exigem allow_prd=true explicito (gate adicional)

A execucao real depende de mutations GraphQL Pipefy (createCard, moveCardToPhase,
deleteCard). Elas sao injetadas via callable nos parametros pra permitir mock
em testes e isolar do server.py.

Funcoes puras (sem efeito colateral) ate execute_smoke ser chamado com dry_run=false.
"""
from __future__ import annotations

import datetime as _dt
import json
import os as _os
import re as _re
import time as _time
from typing import Any, Callable, Dict, List, Optional, Tuple


_SAFE_ID_RE = _re.compile(r"[^a-zA-Z0-9_-]")


def _safe_pipe_id(pipe_id: str) -> str:
    return _SAFE_ID_RE.sub("_", pipe_id or "")[:64] or "unknown"


def load_rules(rules_path: str) -> Dict[str, Any]:
    """Carrega config/smoke_rules.json. Em caso de IOError/JSON invalido,
    retorna estrutura vazia em vez de levantar (smoke nao deve quebrar app).
    Sempre aplica defaults pra fields ausentes."""
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError, FileNotFoundError):
        data = {"version": "0"}
    data.setdefault("pipes", {})
    data.setdefault("default_card_name_prefix", "[SMOKE-TEST]")
    data.setdefault("default_phases_match", "^.*$")
    data.setdefault("allow_prd_global", False)
    return data


def resolve_pipe_config(rules: Dict[str, Any], pipe_id: str) -> Dict[str, Any]:
    """Retorna config combinado (defaults globais + override do pipe).
    Inclui chave 'enabled' (default False — pipe nao whitelistado nao roda
    smoke real)."""
    pipes = rules.get("pipes") or {}
    pipe_cfg = pipes.get(pipe_id) or {}
    return {
        "enabled": bool(pipe_cfg.get("enabled", False)),
        "card_name_prefix": pipe_cfg.get("card_name_prefix")
            or rules.get("default_card_name_prefix") or "[SMOKE-TEST]",
        "phases_to_cover": pipe_cfg.get("phases_to_cover"),
        "phases_match_regex": pipe_cfg.get("phases_match_regex")
            or rules.get("default_phases_match") or "^.*$",
        "start_form_values": pipe_cfg.get("start_form_values") or {},
        "allow_prd": bool(pipe_cfg.get("allow_prd", rules.get("allow_prd_global", False))),
    }


def build_smoke_plan(
    pipe_id: str,
    snapshot: Dict[str, Any],
    pipe_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    """Monta plano de smoke a partir do snapshot e config.

    Retorna {pipe_id, env_label, phases: [...], start_form_values: {...},
    card_name, warnings: [...]}.

    Phases incluidas: se pipe_cfg.phases_to_cover (lista) eh dado, usa essa
    ordem exata. Senao, filtra phases do snapshot por phases_match_regex.

    Warnings: phase listada em phases_to_cover que nao existe no snapshot,
    snapshot sem phases, etc."""
    warnings: List[str] = []
    pipe_data = (snapshot or {}).get("data", {}).get("pipe", {})
    env_label = (snapshot or {}).get("metadata", {}).get("env_label", "")
    all_phases = pipe_data.get("phases") or []
    phases_index = {p.get("name"): p for p in all_phases if p.get("name")}

    selected: List[Dict[str, Any]] = []
    explicit = pipe_cfg.get("phases_to_cover")
    if isinstance(explicit, list) and explicit:
        for name in explicit:
            phase = phases_index.get(name)
            if phase:
                selected.append({"id": phase.get("id"), "name": phase.get("name")})
            else:
                warnings.append(f"Phase configurada '{name}' nao existe no snapshot")
    else:
        try:
            regex = _re.compile(pipe_cfg.get("phases_match_regex") or "^.*$")
        except _re.error:
            warnings.append(f"phases_match_regex invalido: {pipe_cfg.get('phases_match_regex')}")
            regex = _re.compile("^.*$")
        for p in all_phases:
            if p.get("name") and regex.search(p["name"]):
                selected.append({"id": p.get("id"), "name": p.get("name")})

    if not all_phases:
        warnings.append("Snapshot sem phases — smoke nao pode rodar")
    if not selected and all_phases:
        warnings.append("Nenhuma phase do snapshot bate com a config — plano vazio")

    prefix = pipe_cfg.get("card_name_prefix") or "[SMOKE-TEST]"
    card_name = f"{prefix} {_dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"

    return {
        "pipe_id": pipe_id,
        "env_label": env_label,
        "phases": selected,
        "start_form_values": pipe_cfg.get("start_form_values") or {},
        "card_name": card_name,
        "warnings": warnings,
    }


def simulate_smoke(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Dry-run puro: nao chama Pipefy. Retorna steps que seriam executados
    com timing simulado de 0. Util pra UI mostrar plano antes de execucao."""
    steps: List[Dict[str, Any]] = [
        {"kind": "create_card", "card_name": plan.get("card_name"),
         "fields": plan.get("start_form_values"), "ok": True,
         "elapsed_ms": 0, "simulated": True},
    ]
    for phase in plan.get("phases") or []:
        steps.append({
            "kind": "move_to_phase",
            "phase_id": phase.get("id"),
            "phase_name": phase.get("name"),
            "ok": True, "elapsed_ms": 0, "simulated": True,
        })
    steps.append({"kind": "delete_card", "ok": True, "elapsed_ms": 0, "simulated": True})
    return {
        "ok": True,
        "dry_run": True,
        "steps": steps,
        "total_steps": len(steps),
        "warnings": plan.get("warnings", []),
    }


def execute_smoke(
    plan: Dict[str, Any],
    create_card_fn: Callable[[str, str, Dict[str, Any]], Tuple[Optional[str], Optional[str]]],
    move_card_fn: Callable[[str, str], Tuple[bool, Optional[str]]],
    delete_card_fn: Callable[[str], Tuple[bool, Optional[str]]],
    pause_between_steps_s: float = 0.5,
) -> Dict[str, Any]:
    """Executa smoke real chamando callbacks injetados (mocks em testes,
    chamadas GraphQL no server.py).

    create_card_fn(pipe_id, card_name, fields) -> (card_id ou None, error ou None)
    move_card_fn(card_id, phase_id) -> (ok, error)
    delete_card_fn(card_id) -> (ok, error)

    A funcao SEMPRE tenta deletar o card no final, mesmo se algum move falhou
    (cleanup defensivo). Retorna {ok, dry_run=False, card_id, steps[], elapsed_ms,
    errors[]}.
    """
    steps: List[Dict[str, Any]] = []
    errors: List[str] = []
    card_id: Optional[str] = None
    started_at = _time.time()

    # Step 1: createCard
    t0 = _time.time()
    try:
        card_id, err = create_card_fn(
            plan["pipe_id"], plan["card_name"], plan.get("start_form_values") or {}
        )
    except Exception as ex:
        card_id, err = None, f"exception: {ex}"
    steps.append({
        "kind": "create_card", "card_name": plan["card_name"],
        "ok": card_id is not None and not err, "card_id": card_id,
        "error": err, "elapsed_ms": int((_time.time() - t0) * 1000),
        "simulated": False,
    })
    if not card_id or err:
        errors.append(f"create_card failed: {err}")
        return {
            "ok": False, "dry_run": False, "card_id": None,
            "steps": steps, "elapsed_ms": int((_time.time() - started_at) * 1000),
            "errors": errors, "warnings": plan.get("warnings", []),
        }

    # Step 2..N: moveCardToPhase
    for phase in plan.get("phases") or []:
        if pause_between_steps_s > 0:
            _time.sleep(pause_between_steps_s)
        t = _time.time()
        try:
            ok, err = move_card_fn(card_id, phase["id"])
        except Exception as ex:
            ok, err = False, f"exception: {ex}"
        steps.append({
            "kind": "move_to_phase", "phase_id": phase.get("id"),
            "phase_name": phase.get("name"),
            "ok": bool(ok), "error": err,
            "elapsed_ms": int((_time.time() - t) * 1000), "simulated": False,
        })
        if not ok:
            errors.append(f"move_to_phase {phase.get('name')}: {err}")
            # Nao break: continua tentando proximas phases pra coletar todos os erros

    # Step final: deleteCard (sempre tenta, mesmo se moves falharam)
    t = _time.time()
    try:
        ok, err = delete_card_fn(card_id)
    except Exception as ex:
        ok, err = False, f"exception: {ex}"
    steps.append({
        "kind": "delete_card", "card_id": card_id,
        "ok": bool(ok), "error": err,
        "elapsed_ms": int((_time.time() - t) * 1000), "simulated": False,
    })
    if not ok:
        errors.append(f"delete_card: {err} (CARD ORFAO id={card_id} pode ter sobrado em PRD!)")

    elapsed_ms = int((_time.time() - started_at) * 1000)
    return {
        "ok": all(s["ok"] for s in steps),
        "dry_run": False,
        "card_id": card_id,
        "steps": steps,
        "elapsed_ms": elapsed_ms,
        "errors": errors,
        "warnings": plan.get("warnings", []),
    }


def persist_smoke_run(
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
    filename = now.strftime("%Y%m%d_%H%M%S") + ".json"
    path = _os.path.join(pipe_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    if retention > 0:
        files = sorted(f for f in _os.listdir(pipe_dir) if f.endswith(".json"))
        excess = len(files) - retention
        for i in range(excess):
            try:
                _os.remove(_os.path.join(pipe_dir, files[i]))
            except OSError:
                pass
    return path


def list_smoke_runs(
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
