"""Testes da Frente 2 (Fase B) - quality scanner (SonarQube equivalent).

Cobre:
- quality_scanner.load_rules: disabled filtrado, label_regex compilado/invalido
- _index_pipe_schema: normalizacao do snapshot v1.2
- _referenced_field_ids: extract de triggerFieldIds + condition field_address
- Cada check em TP e TN:
  * dangling_trigger_field
  * high_complexity_automation
  * dead_start_form_field
  * dead_phase_field
  * inactive_automation_with_trigger
  * magic_id_in_condition (UUID + numero longo)
  * naming_inconsistent_field (regex configuravel)
- scan_pipe_quality: integracao + ordering por severity
- persist_scan_run + list_scan_runs + compute_quality_trend
- Endpoints: /api/quality-scan/auto, /rules, /history; /api/dashboard/quality
- Integracao /api/dashboard/data + cron persiste quality run
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
def quality_module():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if "quality_scanner" in sys.modules:
        del sys.modules["quality_scanner"]
    return importlib.import_module("quality_scanner")


def _snapshot_v12(automations=None, phases=None, start_form=None):
    return {
        "metadata": {"tool_version": "1.2", "timestamp": "2026-05-15T10:00"},
        "data": {
            "pipe": {
                "id": "p1", "name": "P1",
                "phases": phases or [],
                "start_form_fields": start_form or [],
            },
            "automations": automations or [],
        },
    }


# ============== load_rules + helpers ==============

def test_load_rules_filtra_disabled(tmp_path, quality_module):
    data = {"version": "1.0", "checks": [
        {"id": "c1", "category": "x", "severity": "high", "enabled": True, "message": "m", "params": {}},
        {"id": "c2", "category": "x", "severity": "low", "enabled": False, "message": "m", "params": {}},
    ]}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    rules = quality_module.load_rules(str(p))
    assert len(rules) == 1
    assert rules[0]["id"] == "c1"


def test_load_rules_compila_label_regex(tmp_path, quality_module):
    data = {"version": "1.0", "checks": [
        {"id": "naming", "category": "naming", "severity": "low", "enabled": True,
         "message": "m", "params": {"label_regex": "^[A-Z].*"}},
    ]}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    rules = quality_module.load_rules(str(p))
    assert "_label_regex_compiled" in rules[0]["params"]


def test_load_rules_ignora_label_regex_invalido(tmp_path, quality_module):
    data = {"version": "1.0", "checks": [
        {"id": "naming", "category": "x", "severity": "low", "enabled": True,
         "message": "m", "params": {"label_regex": "[invalido("}},
        {"id": "ok", "category": "x", "severity": "low", "enabled": True,
         "message": "m", "params": {}},
    ]}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    rules = quality_module.load_rules(str(p))
    assert len(rules) == 1
    assert rules[0]["id"] == "ok"


def test_index_pipe_schema_normaliza_v12(quality_module):
    snap = _snapshot_v12(
        phases=[
            {"id": "ph_a", "name": "A", "fields": [
                {"id": "f1", "label": "F1", "type": "short_text"},
            ]},
        ],
        start_form=[{"id": "sf1", "label": "Nome", "type": "short_text"}],
    )
    idx = quality_module._index_pipe_schema(snap)
    assert "ph_a" in idx["phases"]
    assert "f1" in idx["phases"]["ph_a"]["fields"]
    assert "sf1" in idx["start_form"]
    assert idx["all_field_ids"] == {"f1", "sf1"}


def test_referenced_field_ids_extract(quality_module):
    automations = [{
        "id": "a1", "name": "X",
        "event_params": {"triggerFieldIds": ["f1", "f2"]},
        "condition": {"expressions": [
            {"field_address": "f3", "value": "x"},
        ]},
    }]
    refs = quality_module._referenced_field_ids(automations)
    assert refs == {"f1", "f2", "f3"}


# ============== dangling_trigger_field ==============

def test_check_dangling_trigger_detecta(quality_module):
    rules_data = {"version": "1.0", "checks": [
        {"id": "dangling_trigger_field", "category": "consistency", "severity": "high",
         "enabled": True, "message": "x", "params": {}},
    ]}
    rules = [r for r in [dict(rules_data["checks"][0], _label_regex_compiled=None)] if r]
    # Carrega via load_rules de verdade pra evitar pular params.
    import tempfile, os as _os
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(rules_data, f)
        path = f.name
    rules = quality_module.load_rules(path)
    _os.unlink(path)
    snap = _snapshot_v12(
        automations=[{
            "id": "a1", "name": "Webhook",
            "event_params": {"triggerFieldIds": ["f_existe", "f_deletado"]},
        }],
        start_form=[{"id": "f_existe", "label": "OK", "type": "short_text"}],
    )
    findings = quality_module.scan_pipe_quality(snap, rules)
    assert any(f["check_id"] == "dangling_trigger_field" and "f_deletado" in str(f) for f in findings)


def test_check_dangling_trigger_nenhum_quando_tudo_existe(quality_module, tmp_path):
    rules_data = {"version": "1.0", "checks": [
        {"id": "dangling_trigger_field", "category": "x", "severity": "high",
         "enabled": True, "message": "m", "params": {}},
    ]}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rules_data), encoding="utf-8")
    rules = quality_module.load_rules(str(p))
    snap = _snapshot_v12(
        automations=[{
            "id": "a1", "name": "X",
            "event_params": {"triggerFieldIds": ["f1"]},
        }],
        start_form=[{"id": "f1", "label": "F1", "type": "short_text"}],
    )
    findings = quality_module.scan_pipe_quality(snap, rules)
    assert findings == []


# ============== high_complexity_automation ==============

def test_check_high_complexity_acima_threshold(quality_module, tmp_path):
    rules_data = {"version": "1.0", "checks": [
        {"id": "high_complexity_automation", "category": "x", "severity": "med",
         "enabled": True, "message": "m", "params": {"threshold": 3}},
    ]}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rules_data), encoding="utf-8")
    rules = quality_module.load_rules(str(p))
    snap = _snapshot_v12(automations=[{
        "id": "a1", "name": "Complexa",
        "condition": {"expressions": [
            {"field_address": "f1", "operation": "eq", "value": "a"},
            {"field_address": "f2", "operation": "eq", "value": "b"},
            {"field_address": "f3", "operation": "eq", "value": "c"},
            {"field_address": "f4", "operation": "eq", "value": "d"},
        ]},
    }])
    findings = quality_module.scan_pipe_quality(snap, rules)
    assert len(findings) == 1
    assert findings[0]["check_id"] == "high_complexity_automation"


def test_check_high_complexity_abaixo_threshold(quality_module, tmp_path):
    rules_data = {"version": "1.0", "checks": [
        {"id": "high_complexity_automation", "category": "x", "severity": "med",
         "enabled": True, "message": "m", "params": {"threshold": 10}},
    ]}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rules_data), encoding="utf-8")
    rules = quality_module.load_rules(str(p))
    snap = _snapshot_v12(automations=[{
        "id": "a1", "name": "OK",
        "condition": {"expressions": [{"field_address": "f1", "value": "x"}]},
    }])
    assert quality_module.scan_pipe_quality(snap, rules) == []


# ============== dead_start_form_field / dead_phase_field ==============

def test_check_dead_start_form_field(quality_module, tmp_path):
    rules_data = {"version": "1.0", "checks": [
        {"id": "dead_start_form_field", "category": "x", "severity": "med",
         "enabled": True, "message": "m", "params": {}},
    ]}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rules_data), encoding="utf-8")
    rules = quality_module.load_rules(str(p))
    snap = _snapshot_v12(
        start_form=[
            {"id": "f_usado", "label": "Usado", "type": "short_text"},
            {"id": "f_morto", "label": "Morto", "type": "short_text"},
        ],
        automations=[{
            "id": "a1", "name": "X",
            "event_params": {"triggerFieldIds": ["f_usado"]},
        }],
    )
    findings = quality_module.scan_pipe_quality(snap, rules)
    assert len(findings) == 1
    assert findings[0]["target_id"] == "f_morto"


def test_check_dead_phase_field(quality_module, tmp_path):
    rules_data = {"version": "1.0", "checks": [
        {"id": "dead_phase_field", "category": "x", "severity": "low",
         "enabled": True, "message": "m", "params": {}},
    ]}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rules_data), encoding="utf-8")
    rules = quality_module.load_rules(str(p))
    snap = _snapshot_v12(
        phases=[{"id": "ph_a", "name": "Analise", "fields": [
            {"id": "phf_usado", "label": "OK", "type": "short_text"},
            {"id": "phf_morto", "label": "Morto", "type": "short_text"},
        ]}],
        automations=[{
            "id": "a1", "name": "X",
            "condition": {"expressions": [{"field_address": "phf_usado", "value": "1"}]},
        }],
    )
    findings = quality_module.scan_pipe_quality(snap, rules)
    assert len(findings) == 1
    assert findings[0]["target_id"] == "phf_morto"


# ============== inactive_automation_with_trigger ==============

def test_check_inactive_with_trigger(quality_module, tmp_path):
    rules_data = {"version": "1.0", "checks": [
        {"id": "inactive_automation_with_trigger", "category": "x", "severity": "med",
         "enabled": True, "message": "m", "params": {}},
    ]}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rules_data), encoding="utf-8")
    rules = quality_module.load_rules(str(p))
    snap = _snapshot_v12(automations=[
        {"id": "a1", "name": "Ativa", "active": True,
         "event_params": {"triggerFieldIds": ["f1"]}},
        {"id": "a2", "name": "Inativa esquecida", "active": False,
         "event_params": {"triggerFieldIds": ["f1"]}},
        {"id": "a3", "name": "Inativa limpa", "active": False,
         "event_params": {}},
    ])
    findings = quality_module.scan_pipe_quality(snap, rules)
    assert len(findings) == 1
    assert findings[0]["target_name"] == "Inativa esquecida"


# ============== magic_id_in_condition ==============

def test_check_magic_id_uuid(quality_module, tmp_path):
    rules_data = {"version": "1.0", "checks": [
        {"id": "magic_id_in_condition", "category": "x", "severity": "low",
         "enabled": True, "message": "m", "params": {"min_length": 12}},
    ]}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rules_data), encoding="utf-8")
    rules = quality_module.load_rules(str(p))
    snap = _snapshot_v12(automations=[{
        "id": "a1", "name": "X",
        "condition": {"expressions": [
            {"field_address": "f1", "value": "abc12345-1234-5678-9abc-def012345678"},
        ]},
    }])
    findings = quality_module.scan_pipe_quality(snap, rules)
    assert len(findings) == 1


def test_check_magic_id_numero_longo(quality_module, tmp_path):
    rules_data = {"version": "1.0", "checks": [
        {"id": "magic_id_in_condition", "category": "x", "severity": "low",
         "enabled": True, "message": "m", "params": {"min_length": 8}},
    ]}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rules_data), encoding="utf-8")
    rules = quality_module.load_rules(str(p))
    snap = _snapshot_v12(automations=[{
        "id": "a1", "name": "X",
        "condition": {"expressions": [{"field_address": "f1", "value": "1234567890"}]},
    }])
    findings = quality_module.scan_pipe_quality(snap, rules)
    assert len(findings) == 1


def test_check_magic_id_nao_dispara_pra_valor_curto(quality_module, tmp_path):
    rules_data = {"version": "1.0", "checks": [
        {"id": "magic_id_in_condition", "category": "x", "severity": "low",
         "enabled": True, "message": "m", "params": {"min_length": 12}},
    ]}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rules_data), encoding="utf-8")
    rules = quality_module.load_rules(str(p))
    snap = _snapshot_v12(automations=[{
        "id": "a1", "name": "X",
        "condition": {"expressions": [{"field_address": "f1", "value": "aprovado"}]},
    }])
    assert quality_module.scan_pipe_quality(snap, rules) == []


# ============== naming_inconsistent_field ==============

def test_check_naming_inconsistente(quality_module, tmp_path):
    rules_data = {"version": "1.0", "checks": [
        {"id": "naming_inconsistent_field", "category": "naming", "severity": "low",
         "enabled": True, "message": "m",
         "params": {"label_regex": r"^[A-Z][a-zA-Z ]+$"}},
    ]}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rules_data), encoding="utf-8")
    rules = quality_module.load_rules(str(p))
    snap = _snapshot_v12(start_form=[
        {"id": "f1", "label": "Nome Completo", "type": "short_text"},  # OK
        {"id": "f2", "label": "cpf123", "type": "short_text"},  # nao bate
    ])
    findings = quality_module.scan_pipe_quality(snap, rules)
    assert len(findings) == 1
    assert findings[0]["target_id"] == "f2"


# ============== Integracao + summarize ==============

def test_summarize_agrega(quality_module):
    findings = [
        {"check_id": "c1", "category": "x", "severity": "high"},
        {"check_id": "c1", "category": "x", "severity": "high"},
        {"check_id": "c2", "category": "y", "severity": "low"},
    ]
    s = quality_module.summarize_findings(findings)
    assert s["total"] == 3
    assert s["by_severity"]["high"] == 2
    assert s["by_check"]["c1"] == 2


def test_scan_ordena_por_severity(quality_module, tmp_path):
    rules_data = {"version": "1.0", "checks": [
        {"id": "dangling_trigger_field", "category": "x", "severity": "high",
         "enabled": True, "message": "m", "params": {}},
        {"id": "dead_start_form_field", "category": "x", "severity": "med",
         "enabled": True, "message": "m", "params": {}},
        {"id": "magic_id_in_condition", "category": "x", "severity": "low",
         "enabled": True, "message": "m", "params": {"min_length": 5}},
    ]}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rules_data), encoding="utf-8")
    rules = quality_module.load_rules(str(p))
    snap = _snapshot_v12(
        start_form=[{"id": "f_morto", "label": "x", "type": "short_text"}],
        automations=[{
            "id": "a1", "name": "X",
            "event_params": {"triggerFieldIds": ["f_inexistente"]},
            "condition": {"expressions": [{"field_address": "f1", "value": "12345"}]},
        }],
    )
    findings = quality_module.scan_pipe_quality(snap, rules)
    severities = [f["severity"] for f in findings]
    # ordem deve ser high -> med -> low
    assert severities == sorted(severities, key=lambda s: {"high": 0, "med": 1, "low": 2}[s])


# ============== Historico ==============

def test_persist_e_list_scan_runs(tmp_path, quality_module):
    run = {"summary": {"total": 5, "by_severity": {"high": 2, "med": 2, "low": 1}}}
    quality_module.persist_scan_run(str(tmp_path), "p1", run)
    runs = quality_module.list_scan_runs(str(tmp_path), "p1")
    assert len(runs) == 1
    assert runs[0]["pipe_id"] == "p1"


def test_compute_quality_trend_calcula_delta(tmp_path, quality_module):
    pipe_dir = tmp_path / "p1"
    pipe_dir.mkdir(parents=True)
    r1 = {
        "run_timestamp": "2026-01-01T10:00",
        "summary": {"total": 5, "by_severity": {"high": 2, "med": 2, "low": 1}},
        "findings": [
            {"check_id": "c1", "target_id": "t1", "severity": "high", "target_name": "X"},
        ],
    }
    r2 = {
        "run_timestamp": "2026-01-02T10:00",
        "summary": {"total": 3, "by_severity": {"high": 1, "med": 2, "low": 0}},
        "findings": [
            {"check_id": "c2", "target_id": "t2", "severity": "med", "target_name": "Y"},
        ],
    }
    (pipe_dir / "20260101_100000.json").write_text(json.dumps(r1), encoding="utf-8")
    (pipe_dir / "20260102_100000.json").write_text(json.dumps(r2), encoding="utf-8")

    trend = quality_module.compute_quality_trend(str(tmp_path), "p1")
    assert trend["available"] is True
    assert trend["delta_last_vs_prev"]["total"] == -2
    assert any(f["check_id"] == "c1" for f in trend["resolved_findings"])
    assert any(f["check_id"] == "c2" for f in trend["new_findings"])


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
    for f in ("complexity_weights.json", "semantic_rules.json", "quality_rules.json"):
        src = REPO_ROOT / "config" / f
        if src.exists():
            (tmp_path / "config" / f).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for mod in ("server", "semantic_scanner", "quality_scanner"):
        if mod in sys.modules:
            del sys.modules[mod]
    server = importlib.import_module("server")
    server.app.config["TESTING"] = True
    return server


def _write_snapshot_v12(tmp_path, pipe_id, phases=None, start_form=None, automations=None):
    pipe_dir = tmp_path / "snapshots" / "auto" / pipe_id
    pipe_dir.mkdir(parents=True, exist_ok=True)
    snap = {
        "metadata": {"tool_version": "1.2", "timestamp": "2026-05-15T10:00",
                     "pipe_id": pipe_id, "env_label": "PRD", "source": "test"},
        "data": {
            "pipe": {
                "id": pipe_id, "name": pipe_id,
                "phases": phases or [],
                "start_form_fields": start_form or [],
            },
            "automations": automations or [],
        },
    }
    (pipe_dir / "20260515_100000.json").write_text(json.dumps(snap), encoding="utf-8")


def test_endpoint_quality_rules_listing(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/api/quality-scan/rules",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["rules_count"] >= 5
    assert "checks" in data


def test_endpoint_quality_rules_gated(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    res = server.app.test_client().get(
        "/api/quality-scan/rules",
        headers={"Authorization": _basic("demo", "demosecret")},
    )
    assert res.status_code == 403


def test_endpoint_quality_auto_400_sem_pipe_id(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/api/quality-scan/auto",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 400


def test_endpoint_quality_auto_pipe_sem_snapshot(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/api/quality-scan/auto?pipe_id=novato",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    body = res.get_json()
    assert body["available"] is False


def test_endpoint_quality_auto_com_findings(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    _write_snapshot_v12(
        tmp_path, "p1",
        start_form=[{"id": "f_morto", "label": "Morto", "type": "short_text"}],
        automations=[{"id": "a1", "name": "X",
                      "event_params": {"triggerFieldIds": ["f_inexistente"]}}],
    )
    res = server.app.test_client().get(
        "/api/quality-scan/auto?pipe_id=p1",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["available"] is True
    assert body["total"] >= 1
    assert "top_checks" in body
    assert "top_findings_high" in body


def test_endpoint_dashboard_quality(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    (tmp_path / "config" / "monitored_pipes.json").write_text(json.dumps({
        "version": "1.0",
        "pipes": [{"id": "p1", "name": "P1", "env_label": "PRD", "enabled": True}],
    }), encoding="utf-8")
    _write_snapshot_v12(
        tmp_path, "p1",
        automations=[{"id": "a1", "name": "X",
                      "event_params": {"triggerFieldIds": ["f_inexistente"]}}],
    )
    res = server.app.test_client().get(
        "/api/dashboard/quality",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    body = res.get_json()
    assert body["available"] is True
    assert body["total"] >= 1


def test_endpoint_quality_history_gated(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    res = server.app.test_client().get(
        "/api/quality-scan/history?pipe_id=x",
        headers={"Authorization": _basic("demo", "demosecret")},
    )
    assert res.status_code == 403


def test_endpoint_quality_history_sem_historico(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/api/quality-scan/history?pipe_id=novato",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    body = res.get_json()
    assert body["available"] is False


def test_dashboard_data_inclui_quality(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    (tmp_path / "config" / "monitored_pipes.json").write_text(json.dumps({
        "version": "1.0",
        "pipes": [{"id": "p1", "name": "P1", "env_label": "PRD", "enabled": True}],
    }), encoding="utf-8")
    _write_snapshot_v12(
        tmp_path, "p1",
        automations=[{"id": "a1", "name": "X",
                      "event_params": {"triggerFieldIds": ["f_inexistente"]}}],
    )
    res = server.app.test_client().get(
        "/api/dashboard/data",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    body = res.get_json()
    assert "quality" in body
    assert body["quality"]["available"] is True
