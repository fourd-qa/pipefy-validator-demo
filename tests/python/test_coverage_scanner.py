"""Testes da Fase D - coverage scanner (blast radius + cobertura básica).

Cobre:
- load_rules: defaults seguros mesmo sem arquivo
- _automation_phase_references: classifica ins/outs corretamente
- compute_blast_radius: cards_count + automations_total, ordenacao por weight
- compute_phase_coverage: orphan, no_sla, no_description, heavy
- compute_field_coverage: fields sem description (start_form + phase fields)
- scan_pipe_coverage integrado
- summarize_coverage: KPIs agregados
- persist + list scan runs
- Endpoints: dashboard/coverage, coverage/auto, coverage/history (gating + 400 + happy path)
- Integração no /api/dashboard/data + cron persiste
"""
import base64
import importlib
import json
import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _basic(user, pw):
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


@pytest.fixture
def coverage_module():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if "coverage_scanner" in sys.modules:
        del sys.modules["coverage_scanner"]
    return importlib.import_module("coverage_scanner")


def _snapshot(phases=None, start_form=None, automations=None, version="1.3"):
    return {
        "metadata": {"tool_version": version, "env_label": "PRD", "timestamp": "2026-05-15T10:00"},
        "data": {
            "pipe": {"id": "p1", "name": "P1",
                     "phases": phases or [],
                     "start_form_fields": start_form or []},
            "automations": automations or [],
        },
    }


# ============== load_rules ==============

def test_load_rules_default_quando_arquivo_inexistente(coverage_module, tmp_path):
    rules = coverage_module.load_rules(str(tmp_path / "nao_existe.json"))
    assert rules["heavy_phase_threshold"] == 50
    assert rules["require_description_for_fields"] is True
    assert rules["flag_orphan_phases"] is True


def test_load_rules_arquivo_corrompido(coverage_module, tmp_path):
    p = tmp_path / "r.json"
    p.write_text("nao-eh-json", encoding="utf-8")
    rules = coverage_module.load_rules(str(p))
    assert rules["heavy_phase_threshold"] == 50


def test_load_rules_override(coverage_module, tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"heavy_phase_threshold": 10}), encoding="utf-8")
    rules = coverage_module.load_rules(str(p))
    assert rules["heavy_phase_threshold"] == 10


# ============== _automation_phase_references ==============

def test_automation_refs_classifica_in_e_out(coverage_module):
    automations = [
        {"id": "auto_mover", "action_params": {"to_phase_id": "ph_dest"}},
        {"id": "auto_listen", "event_params": {"phase": {"id": "ph_orig"}}},
    ]
    refs = coverage_module._automation_phase_references(automations)
    assert "auto_mover" in refs["ph_dest"]["ins"]
    assert "auto_listen" in refs["ph_orig"]["outs"]


def test_automation_refs_aceita_phase_como_string_ou_dict(coverage_module):
    automations = [
        {"id": "a1", "action_params": {"phase": "ph_x"}},
        {"id": "a2", "action_params": {"phase": {"id": "ph_y", "name": "Y"}}},
    ]
    refs = coverage_module._automation_phase_references(automations)
    assert "a1" in refs["ph_x"]["ins"]
    assert "a2" in refs["ph_y"]["ins"]


# ============== compute_blast_radius ==============

def test_blast_radius_inclui_cards_count(coverage_module):
    phases = [
        {"id": "ph_a", "name": "Análise", "cards_count": 120, "expiration_time_by_card": 7200},
        {"id": "ph_b", "name": "Aprovação", "cards_count": 10},
    ]
    blast = coverage_module.compute_blast_radius(_snapshot(phases=phases))
    assert len(blast) == 2
    # ordenado por weight desc; ph_a tem 120 cards -> peso maior.
    assert blast[0]["phase_id"] == "ph_a"
    assert blast[0]["cards_count"] == 120


def test_blast_radius_cards_count_none_em_snapshot_antigo(coverage_module):
    """Snapshot v1.0 sem cards_count -> field None, weight 0 ou só automations."""
    phases = [{"id": "ph_a", "name": "A"}]  # sem cards_count
    blast = coverage_module.compute_blast_radius(_snapshot(phases=phases, version="1.0"))
    assert blast[0]["cards_count"] is None
    assert blast[0]["automations_total"] == 0


def test_blast_radius_pesa_automations(coverage_module):
    """Phase com varias automations ligadas tem weight maior."""
    phases = [
        {"id": "ph_pesada", "name": "Pesada", "cards_count": 0},
        {"id": "ph_leve", "name": "Leve", "cards_count": 0},
    ]
    automations = [
        {"id": "a1", "action_params": {"to_phase_id": "ph_pesada"}},
        {"id": "a2", "action_params": {"to_phase_id": "ph_pesada"}},
        {"id": "a3", "event_params": {"phase": {"id": "ph_pesada"}}},
    ]
    blast = coverage_module.compute_blast_radius(_snapshot(phases=phases, automations=automations))
    assert blast[0]["phase_id"] == "ph_pesada"
    assert blast[0]["automations_total"] == 3


# ============== compute_phase_coverage ==============

def test_coverage_detecta_orphan_phase(coverage_module):
    phases = [
        {"id": "ph_orfa", "name": "Orfã"},  # sem automation entrando
        {"id": "ph_ok", "name": "OK"},
    ]
    automations = [{"id": "a1", "action_params": {"to_phase_id": "ph_ok"}}]
    findings = coverage_module.compute_phase_coverage(
        _snapshot(phases=phases, automations=automations),
        {"heavy_phase_threshold": 50, "flag_orphan_phases": True},
    )
    orphans = [f for f in findings if f["check_id"] == "orphan_phase"]
    assert len(orphans) == 1
    assert orphans[0]["phase_id"] == "ph_orfa"


def test_coverage_detecta_phase_sem_sla(coverage_module):
    phases = [
        {"id": "ph_sem_sla", "name": "Sem SLA"},
        {"id": "ph_com_sla", "name": "Com SLA", "expiration_time_by_card": 3600},
    ]
    findings = coverage_module.compute_phase_coverage(
        _snapshot(phases=phases),
        {"require_sla_for_phases": True, "flag_orphan_phases": False},
    )
    sla_findings = [f for f in findings if f["check_id"] == "phase_without_sla"]
    assert len(sla_findings) == 1
    assert sla_findings[0]["phase_id"] == "ph_sem_sla"


def test_coverage_detecta_heavy_phase(coverage_module):
    phases = [
        {"id": "ph_pesada", "name": "Pesada", "cards_count": 100},
        {"id": "ph_leve", "name": "Leve", "cards_count": 5},
    ]
    findings = coverage_module.compute_phase_coverage(
        _snapshot(phases=phases),
        {"heavy_phase_threshold": 50, "flag_orphan_phases": False, "require_sla_for_phases": False},
    )
    heavy = [f for f in findings if f["check_id"] == "heavy_phase"]
    assert len(heavy) == 1
    assert heavy[0]["phase_id"] == "ph_pesada"
    assert heavy[0]["severity"] == "high"


def test_coverage_ignora_heavy_se_cards_count_none(coverage_module):
    """Snapshot v1.0/1.1/1.2 sem cards_count -> nao flag heavy_phase."""
    phases = [{"id": "ph_a", "name": "A"}]  # sem cards_count
    findings = coverage_module.compute_phase_coverage(
        _snapshot(phases=phases, version="1.1"),
        {"heavy_phase_threshold": 1, "flag_orphan_phases": False, "require_sla_for_phases": False},
    )
    heavy = [f for f in findings if f["check_id"] == "heavy_phase"]
    assert heavy == []


# ============== compute_field_coverage ==============

def test_field_coverage_detecta_sem_description(coverage_module):
    start_form = [
        {"id": "f1", "label": "Documentado", "description": "Help text"},
        {"id": "f2", "label": "Sem doc"},
    ]
    phases = [{"id": "ph_a", "name": "A", "fields": [
        {"id": "f3", "label": "Phase field sem doc"},
    ]}]
    findings = coverage_module.compute_field_coverage(
        _snapshot(phases=phases, start_form=start_form),
        {"require_description_for_fields": True},
    )
    assert len(findings) == 2
    ids = {f["field_id"] for f in findings}
    assert ids == {"f2", "f3"}


def test_field_coverage_disabled_via_rules(coverage_module):
    start_form = [{"id": "f1", "label": "X"}]
    findings = coverage_module.compute_field_coverage(
        _snapshot(start_form=start_form),
        {"require_description_for_fields": False},
    )
    assert findings == []


# ============== scan_pipe_coverage ==============

def test_scan_integrado_retorna_blast_findings_summary(coverage_module):
    phases = [
        {"id": "ph_pesada", "name": "Pesada", "cards_count": 100,
         "expiration_time_by_card": 3600, "description": "desc"},
    ]
    rules = {"heavy_phase_threshold": 50, "flag_orphan_phases": True}
    result = coverage_module.scan_pipe_coverage(_snapshot(phases=phases), rules)
    assert "blast_radius" in result
    assert "findings" in result
    assert "summary" in result
    assert result["summary"]["phases_total"] == 1


def test_summarize_agrega_top_heavy(coverage_module):
    blast = [
        {"phase_id": "ph_a", "phase_name": "A", "cards_count": 100, "weight": 100},
        {"phase_id": "ph_b", "phase_name": "B", "cards_count": 50, "weight": 50},
    ]
    s = coverage_module.summarize_coverage(blast, [])
    assert s["phases_total"] == 2
    assert s["cards_total"] == 150
    assert s["top_heavy_phases"][0]["phase_id"] == "ph_a"


# ============== persist + list ==============

def test_persist_e_list(coverage_module, tmp_path):
    coverage_module.persist_scan_run(str(tmp_path), "p1", {
        "summary": {"total_findings": 3}, "findings": [], "blast_radius": [],
    })
    runs = coverage_module.list_scan_runs(str(tmp_path), "p1")
    assert len(runs) == 1
    assert runs[0]["pipe_id"] == "p1"


# ============== Endpoints ==============

def _reload_server(tmp_path, monkeypatch, env=None):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for k in ("APP_PASSWORD", "APP_USERNAME", "LIDERANCA_USERNAME", "LIDERANCA_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    for d in ("config", "results", "snapshots", "snapshots/auto", "tmp"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    for f in ("complexity_weights.json", "semantic_rules.json", "quality_rules.json",
              "smoke_rules.json", "coverage_rules.json"):
        src = REPO_ROOT / "config" / f
        if src.exists():
            (tmp_path / "config" / f).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for mod in ("server", "coverage_scanner", "semantic_scanner", "quality_scanner", "smoke_runner"):
        if mod in sys.modules:
            del sys.modules[mod]
    server = importlib.import_module("server")
    server.app.config["TESTING"] = True
    return server


def _write_snapshot(tmp_path, pipe_id, phases, start_form=None, automations=None, version="1.3"):
    pipe_dir = tmp_path / "snapshots" / "auto" / pipe_id
    pipe_dir.mkdir(parents=True, exist_ok=True)
    snap = {
        "metadata": {"tool_version": version, "env_label": "PRD",
                     "timestamp": "2026-05-15T10:00", "pipe_id": pipe_id},
        "data": {
            "pipe": {"id": pipe_id, "name": pipe_id, "phases": phases,
                     "start_form_fields": start_form or []},
            "automations": automations or [],
        },
    }
    (pipe_dir / "20260515_100000.json").write_text(json.dumps(snap), encoding="utf-8")


def test_endpoint_dashboard_coverage_sem_pipes(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/api/dashboard/coverage",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    assert res.get_json()["available"] is False


def test_endpoint_dashboard_coverage_com_snapshot(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    (tmp_path / "config" / "monitored_pipes.json").write_text(json.dumps({
        "version": "1.0",
        "pipes": [{"id": "p1", "name": "Mesa PRD", "env_label": "PRD", "enabled": True}],
    }), encoding="utf-8")
    _write_snapshot(tmp_path, "p1", [
        {"id": "ph_a", "name": "Pesada", "cards_count": 100},
        {"id": "ph_b", "name": "Leve", "cards_count": 5},
    ])
    res = server.app.test_client().get(
        "/api/dashboard/coverage",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["available"] is True
    assert "blast_radius" in body
    assert "summary" in body
    assert body["summary"]["cards_total"] == 105


def test_endpoint_coverage_auto_400_sem_pipe(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/api/coverage/auto",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 400


def test_endpoint_coverage_auto_gated(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    res = server.app.test_client().get(
        "/api/coverage/auto?pipe_id=x",
        headers={"Authorization": _basic("demo", "demosecret")},
    )
    assert res.status_code == 403


def test_endpoint_coverage_history(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/api/coverage/history?pipe_id=novato",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    body = res.get_json()
    assert body["pipe_id"] == "novato"
    assert body["runs"] == []


def test_dashboard_data_inclui_coverage(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    (tmp_path / "config" / "monitored_pipes.json").write_text(json.dumps({
        "version": "1.0",
        "pipes": [{"id": "p1", "name": "P1", "env_label": "PRD", "enabled": True}],
    }), encoding="utf-8")
    _write_snapshot(tmp_path, "p1", [{"id": "ph_a", "name": "A", "cards_count": 10}])
    res = server.app.test_client().get(
        "/api/dashboard/data",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    body = res.get_json()
    assert "coverage" in body
    assert body["coverage"]["available"] is True
