"""Gera massa fictícia de snapshots históricos pra Dashboard Sprint 3.

Sprint 3 (Hot Spots + Lead Time) precisa de 1-2 semanas de snapshots
acumulados pelo cron pra os engines terem o que processar. Este script
cria a massa determinística enquanto o cron real não roda em produção
(bloqueado nos 3 setups manuais descritos em HANDOFF-DASHBOARD.md §2).

Cenário (deterministico, sem rng):
    par HMG/PRD do "produto" Mesa de Credito PF
    janela: 10 dias uteis 2026-04-21 -> 2026-05-05 (pula feriado 2026-05-01)
    HMG evolui em 7 estados (v1 -> v7), PRD segue defasado 3-5 dias uteis

Forma os snapshots no MESMO formato que o cron real produz em
server.py::_fetch_and_save_pipe_snapshot, com 1 extensao: phases tem
fields aninhados (`pipe.phases[].fields`) — necessario pro engine de
hot spots ranquear complexidade por phase. A query do cron real sera
ampliada na mesma sprint pra coletar isso tambem.

Idempotente: limpa snapshots/auto/<pipe>/ dos 2 pipes demo antes de
recriar. Tambem registra os 2 pipes em config/monitored_pipes.json se
ainda nao estiverem la (preserva pipes reais que o usuario tenha
adicionado pela UI).

Uso:
    python scripts/seed_dashboard_snapshots.py
    python scripts/seed_dashboard_snapshots.py --dry-run
    python scripts/seed_dashboard_snapshots.py --no-monitored

Saida: imprime resumo das datas geradas e caminho dos arquivos.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
from typing import Any, Dict, List, Tuple


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOTS_DIR = os.path.join(REPO_ROOT, "snapshots", "auto")
CONFIG_DIR = os.path.join(REPO_ROOT, "config")
MONITORED_PIPES_FILE = os.path.join(CONFIG_DIR, "monitored_pipes.json")


HMG_PIPE = {
    "id": "pipe-mesa-credito-hmg",
    "name": "Mesa de Credito PF - HMG (demo)",
    "repo_id": "301001",
    "env_label": "HMG",
    "enabled": True,
}
PRD_PIPE = {
    "id": "pipe-mesa-credito-prd",
    "name": "Mesa de Credito PF - PRD (demo)",
    "repo_id": "301002",
    "env_label": "PRD",
    "enabled": True,
}


def _safe_id(pipe_id: str) -> str:
    """Replica server.py::_fetch_and_save_pipe_snapshot pra path consistente."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", pipe_id)[:64] or "unknown"


def _phase(id_: str, name: str, fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"id": id_, "name": name, "fields": fields}


def _field(id_: str, label: str, type_: str, required: bool = False) -> Dict[str, Any]:
    return {"id": id_, "label": label, "type": type_, "required": required}


def _build_state_v1() -> Dict[str, Any]:
    """Estado inicial: 5 phases, start form com 5 campos."""
    return {
        "phases": [
            _phase("phase_setup", "Setup", [
                _field("statement_intro", "Bem-vindo", "statement", required=False),
            ]),
            _phase("phase_triagem", "Triagem", [
                _field("score_inicial", "Score inicial", "number", required=True),
                _field("obs_triagem", "Observacoes da triagem", "long_text"),
            ]),
            _phase("phase_analise", "Analise de Credito", [
                _field("score_credito", "Score Serasa", "number", required=True),
                _field("limite_aprovado", "Limite aprovado", "currency"),
            ]),
            _phase("phase_aprovacao", "Aprovacao", [
                _field("aprovador", "Aprovador", "assignee_select", required=True),
            ]),
            _phase("phase_concluido", "Concluido", []),
        ],
        "start_form_fields": [
            _field("nome", "Nome Completo", "short_text", required=True),
            _field("cpf", "CPF", "cpf", required=True),
            _field("telefone", "Telefone", "phone"),
            _field("email", "Email", "email"),
            _field("valor_solicitado", "Valor solicitado", "currency", required=True),
        ],
        "labels": [
            {"id": "lbl_urgente", "name": "Urgente", "color": "#e56b6b"},
            {"id": "lbl_revisar", "name": "Revisar", "color": "#dba844"},
        ],
    }


def _evolve(state: Dict[str, Any], mutation) -> Dict[str, Any]:
    """Aplica uma mutacao retornando novo state (deep copy)."""
    new_state = json.loads(json.dumps(state))
    mutation(new_state)
    return new_state


def _build_states() -> List[Dict[str, Any]]:
    """Retorna lista de 7 estados (v1..v7) com mudancas tipadas."""
    v1 = _build_state_v1()

    # v2: adiciona campo data_de_nascimento no start form (FIELD CREATE).
    def m_v2(s):
        s["start_form_fields"].append(
            _field("data_de_nascimento", "Data de nascimento", "date")
        )
    v2 = _evolve(v1, m_v2)

    # v3: adiciona campo open_banking dentro da phase Analise (FIELD em phase).
    def m_v3(s):
        for p in s["phases"]:
            if p["id"] == "phase_analise":
                p["fields"].append(
                    _field("open_banking", "Validacao Open Banking", "connector")
                )
                break
    v3 = _evolve(v2, m_v3)

    # v4: cria phase nova "Validacao de Renda" entre Analise e Aprovacao.
    def m_v4(s):
        new_phase = _phase("phase_validacao_renda", "Validacao de Renda", [
            _field("comprovante_renda", "Comprovante de renda", "attachment", required=True),
            _field("renda_validada", "Renda validada", "currency"),
        ])
        idx = next((i for i, p in enumerate(s["phases"]) if p["id"] == "phase_aprovacao"), -1)
        if idx >= 0:
            s["phases"].insert(idx, new_phase)
        else:
            s["phases"].append(new_phase)
    v4 = _evolve(v3, m_v4)

    # v5: rename phase Analise de Credito -> Analise PF (PHASE RENAME).
    def m_v5(s):
        for p in s["phases"]:
            if p["id"] == "phase_analise":
                p["name"] = "Analise PF"
                break
    v5 = _evolve(v4, m_v5)

    # v6: adiciona campo score_externo na phase Analise (FIELD CREATE em phase).
    def m_v6(s):
        for p in s["phases"]:
            if p["id"] == "phase_analise":
                p["fields"].append(
                    _field("score_externo", "Score externo (bureau)", "number")
                )
                break
    v6 = _evolve(v5, m_v6)

    # v7: rename Analise PF -> Analise de Credito (CHURN: 2x rename em <14d).
    def m_v7(s):
        for p in s["phases"]:
            if p["id"] == "phase_analise":
                p["name"] = "Analise de Credito"
                break
    v7 = _evolve(v6, m_v7)

    return [v1, v2, v3, v4, v5, v6, v7]


# Datas reais (10 dias uteis, pula feriado 2026-05-01 dia do trabalho).
BUSINESS_DAYS: List[dt.date] = [
    dt.date(2026, 4, 21),  # ter
    dt.date(2026, 4, 22),  # qua
    dt.date(2026, 4, 23),  # qui
    dt.date(2026, 4, 24),  # sex
    dt.date(2026, 4, 27),  # seg
    dt.date(2026, 4, 28),  # ter
    dt.date(2026, 4, 29),  # qua
    dt.date(2026, 4, 30),  # qui
    dt.date(2026, 5, 4),   # seg (pula sex 2026-05-01 feriado)
    dt.date(2026, 5, 5),   # ter (hoje)
]


# Mapeamento data -> indice de estado (versao do schema naquele dia).
HMG_TIMELINE: List[Tuple[dt.date, int]] = [
    (dt.date(2026, 4, 21), 0),  # v1
    (dt.date(2026, 4, 22), 1),  # v2 — start_form ganha data_nascimento
    (dt.date(2026, 4, 23), 2),  # v3 — Analise ganha open_banking
    (dt.date(2026, 4, 24), 3),  # v4 — phase Validacao de Renda criada
    (dt.date(2026, 4, 27), 4),  # v5 — Analise renomeada -> Analise PF
    (dt.date(2026, 4, 28), 4),  # estavel
    (dt.date(2026, 4, 29), 5),  # v6 — Analise PF ganha score_externo
    (dt.date(2026, 4, 30), 5),  # estavel
    (dt.date(2026, 5, 4),  6),  # v7 — Analise PF -> Analise de Credito (churn)
    (dt.date(2026, 5, 5),  6),  # estavel
]

# PRD segue HMG defasado em ~3-5 dias uteis.
PRD_TIMELINE: List[Tuple[dt.date, int]] = [
    (dt.date(2026, 4, 21), 0),  # v1
    (dt.date(2026, 4, 22), 0),
    (dt.date(2026, 4, 23), 0),
    (dt.date(2026, 4, 24), 0),
    (dt.date(2026, 4, 27), 1),  # v2 promovido (lead time 3 uteis)
    (dt.date(2026, 4, 28), 2),  # v3 (lead time 3 uteis)
    (dt.date(2026, 4, 29), 3),  # v4 (lead time 3 uteis)
    (dt.date(2026, 4, 30), 3),
    (dt.date(2026, 5, 4),  4),  # v5 (lead time 5 uteis)
    (dt.date(2026, 5, 5),  5),  # v6 (lead time 4 uteis); v7 ainda nao chegou
]


def _build_snapshot(pipe: Dict[str, Any], when: dt.date, state: Dict[str, Any]) -> Dict[str, Any]:
    """Monta snapshot no formato emitido pelo cron real (server.py)."""
    # Hora ficticia 14:30 BRT pra parecer um disparo de cron */30 em horario comercial.
    timestamp = dt.datetime(when.year, when.month, when.day, 14, 30, 0).isoformat()
    return {
        "metadata": {
            "timestamp": timestamp,
            "pipe_id": pipe["id"],
            "pipe_name": pipe["name"],
            "env_label": pipe["env_label"],
            "source": "seed_demo",
            "tool_version": "1.0",
        },
        "data": {
            "pipe": {
                "id": pipe["id"],
                "name": pipe["name"],
                "phases": state["phases"],
                "start_form_fields": state["start_form_fields"],
                "labels": state["labels"],
            }
        },
    }


def _write_pipe_history(
    pipe: Dict[str, Any],
    timeline: List[Tuple[dt.date, int]],
    states: List[Dict[str, Any]],
    dry_run: bool,
) -> List[str]:
    """Limpa a pasta do pipe e gera um snapshot por entrada da timeline."""
    safe = _safe_id(pipe["id"])
    pipe_dir = os.path.join(SNAPSHOTS_DIR, safe)

    if os.path.isdir(pipe_dir) and not dry_run:
        shutil.rmtree(pipe_dir)
    if not dry_run:
        os.makedirs(pipe_dir, exist_ok=True)

    written: List[str] = []
    for when, version in timeline:
        snapshot = _build_snapshot(pipe, when, states[version])
        ts_label = dt.datetime(when.year, when.month, when.day, 14, 30, 0).strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(pipe_dir, f"{ts_label}.json")
        if not dry_run:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)
        written.append(out_path)
    return written


def _ensure_monitored_pipes(skip: bool) -> None:
    """Adiciona os 2 pipes demo a monitored_pipes.json se nao existirem.
    Preserva pipes reais que o usuario tenha adicionado pela UI."""
    if skip:
        print("[skip] --no-monitored: nao toca config/monitored_pipes.json")
        return

    if os.path.exists(MONITORED_PIPES_FILE):
        with open(MONITORED_PIPES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"version": "1.0", "pipes": []}

    pipes = data.get("pipes", [])
    existing_ids = {p.get("id") for p in pipes}
    added = 0
    for demo in (HMG_PIPE, PRD_PIPE):
        if demo["id"] not in existing_ids:
            pipes.append(dict(demo))
            added += 1
    data["pipes"] = pipes
    data["updated_at"] = dt.date.today().isoformat()

    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(MONITORED_PIPES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[monitored_pipes] {added} pipe(s) demo adicionados (total na config: {len(pipes)})")


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="So lista o que faria")
    parser.add_argument("--no-monitored", action="store_true", help="Nao mexe monitored_pipes.json")
    args = parser.parse_args(argv)

    states = _build_states()

    print(f"[seed] {len(BUSINESS_DAYS)} dias uteis x 2 pipes = {len(BUSINESS_DAYS) * 2} snapshots")
    print(f"[seed] saida em {SNAPSHOTS_DIR}")
    if args.dry_run:
        print("[seed] DRY RUN — nada vai ser escrito")

    hmg_files = _write_pipe_history(HMG_PIPE, HMG_TIMELINE, states, args.dry_run)
    prd_files = _write_pipe_history(PRD_PIPE, PRD_TIMELINE, states, args.dry_run)

    print(f"[hmg] {len(hmg_files)} snapshots em {os.path.dirname(hmg_files[0])}")
    print(f"[prd] {len(prd_files)} snapshots em {os.path.dirname(prd_files[0])}")

    _ensure_monitored_pipes(skip=args.no_monitored or args.dry_run)

    print("[seed] OK. Cenario:")
    print("  - phase 'Analise de Credito' acumula 4 mudancas em HMG -> hot spot HIGH")
    print("  - phase 'Validacao de Renda' tem 1 mudanca (criada em v4) -> hot spot LOW")
    print("  - rename Analise de Credito -> Analise PF -> Analise de Credito (churn)")
    print("  - lead time HMG -> PRD mediano ~3-4 dias uteis (v2..v6)")
    print("  - v7 (rename mais recente) ainda nao chegou em PRD -> aparece como pendente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
