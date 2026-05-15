"""Testes da Frente 3 (Fase C) - smoke test runner (Datadog Synthetics equivalent).

Cobre:
- smoke_runner.load_rules + resolve_pipe_config (defaults + override)
- build_smoke_plan: phases_to_cover explicito, regex, warnings
- simulate_smoke: steps simulados sem chamar callbacks
- execute_smoke: happy path mockando callbacks, falha em createCard (early
  return sem delete), falha em moveCardToPhase (continua + tenta delete),
  exception captured, delete cleanup sempre chamado quando create OK
- persist_smoke_run + list_smoke_runs
- Endpoints: dry-run, run com gates (enabled, allow_prd, token), webhook
  listener captura hit, history, last, rules listing
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
def smoke_module():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if "smoke_runner" in sys.modules:
        del sys.modules["smoke_runner"]
    return importlib.import_module("smoke_runner")


def _snapshot_v12(phases, env_label="HMG"):
    return {
        "metadata": {"tool_version": "1.2", "env_label": env_label,
                     "timestamp": "2026-05-15T10:00"},
        "data": {
            "pipe": {"id": "p1", "name": "P1", "phases": phases},
            "automations": [],
        },
    }


# ============== load_rules + resolve_pipe_config ==============

def test_load_rules_default_estrutura(smoke_module, tmp_path):
    """Arquivo inexistente -> retorna estrutura vazia."""
    rules = smoke_module.load_rules(str(tmp_path / "nao_existe.json"))
    assert rules["pipes"] == {}
    assert rules["default_card_name_prefix"] == "[SMOKE-TEST]"
    assert rules["allow_prd_global"] is False


def test_load_rules_arquivo_corrompido(smoke_module, tmp_path):
    p = tmp_path / "r.json"
    p.write_text("nao-eh-json", encoding="utf-8")
    rules = smoke_module.load_rules(str(p))
    assert rules["pipes"] == {}


def test_resolve_pipe_config_combina_defaults(smoke_module):
    rules = {
        "default_card_name_prefix": "[GLOBAL]",
        "default_phases_match": "^.*$",
        "allow_prd_global": False,
        "pipes": {
            "p1": {"enabled": True, "card_name_prefix": "[CUSTOM]", "allow_prd": True},
        },
    }
    cfg = smoke_module.resolve_pipe_config(rules, "p1")
    assert cfg["enabled"] is True
    assert cfg["card_name_prefix"] == "[CUSTOM]"
    assert cfg["allow_prd"] is True


def test_resolve_pipe_config_pipe_nao_listado(smoke_module):
    rules = {"default_card_name_prefix": "[X]", "pipes": {}}
    cfg = smoke_module.resolve_pipe_config(rules, "novato")
    assert cfg["enabled"] is False
    assert cfg["allow_prd"] is False


# ============== build_smoke_plan ==============

def test_plan_com_phases_to_cover_explicitas(smoke_module):
    phases = [
        {"id": "ph_a", "name": "Triagem"},
        {"id": "ph_b", "name": "Análise"},
        {"id": "ph_c", "name": "Aprovação"},
    ]
    snap = _snapshot_v12(phases)
    cfg = {"phases_to_cover": ["Análise", "Aprovação"], "card_name_prefix": "[X]"}
    plan = smoke_module.build_smoke_plan("p1", snap, cfg)
    assert [p["name"] for p in plan["phases"]] == ["Análise", "Aprovação"]
    assert plan["card_name"].startswith("[X]")


def test_plan_warning_quando_phase_nao_existe(smoke_module):
    snap = _snapshot_v12([{"id": "ph_a", "name": "Triagem"}])
    cfg = {"phases_to_cover": ["Triagem", "Fantasma"], "card_name_prefix": "[X]"}
    plan = smoke_module.build_smoke_plan("p1", snap, cfg)
    assert len(plan["phases"]) == 1
    assert any("Fantasma" in w for w in plan["warnings"])


def test_plan_com_regex_match(smoke_module):
    phases = [
        {"id": "ph_a", "name": "Setup"},
        {"id": "ph_b", "name": "Análise"},
        {"id": "ph_c", "name": "Aprovação"},
    ]
    snap = _snapshot_v12(phases)
    cfg = {"phases_match_regex": "^(An[áa]lise|Aprova[çc][ãa]o)", "card_name_prefix": "[X]"}
    plan = smoke_module.build_smoke_plan("p1", snap, cfg)
    names = [p["name"] for p in plan["phases"]]
    assert "Análise" in names
    assert "Aprovação" in names
    assert "Setup" not in names


def test_plan_snapshot_sem_phases_warning(smoke_module):
    snap = _snapshot_v12([])
    cfg = {"phases_match_regex": "^.*$", "card_name_prefix": "[X]"}
    plan = smoke_module.build_smoke_plan("p1", snap, cfg)
    assert plan["phases"] == []
    assert any("sem phases" in w.lower() for w in plan["warnings"])


def test_plan_regex_invalido_warning(smoke_module):
    snap = _snapshot_v12([{"id": "p", "name": "X"}])
    cfg = {"phases_match_regex": "[invalido(", "card_name_prefix": "[X]"}
    plan = smoke_module.build_smoke_plan("p1", snap, cfg)
    # Regex invalido vira "^.*$" fallback, entao pega tudo + warning.
    assert any("invalido" in w.lower() for w in plan["warnings"])


# ============== simulate_smoke ==============

def test_simulate_retorna_steps_simulados(smoke_module):
    plan = {
        "pipe_id": "p1", "card_name": "[X] teste",
        "phases": [{"id": "ph_a", "name": "A"}, {"id": "ph_b", "name": "B"}],
        "start_form_values": {}, "warnings": [],
    }
    res = smoke_module.simulate_smoke(plan)
    assert res["dry_run"] is True
    assert res["ok"] is True
    # 1 create + 2 move + 1 delete = 4
    assert res["total_steps"] == 4
    assert all(s["simulated"] for s in res["steps"])
    assert all(s["elapsed_ms"] == 0 for s in res["steps"])


# ============== execute_smoke ==============

def test_execute_happy_path(smoke_module):
    plan = {
        "pipe_id": "p1", "card_name": "[X] teste",
        "phases": [{"id": "ph_a", "name": "A"}, {"id": "ph_b", "name": "B"}],
        "start_form_values": {}, "warnings": [],
    }
    calls = []
    def create(pid, name, fields):
        calls.append(("create", pid, name))
        return "card-123", None
    def move(cid, pid):
        calls.append(("move", cid, pid))
        return True, None
    def delete(cid):
        calls.append(("delete", cid))
        return True, None

    res = smoke_module.execute_smoke(plan, create, move, delete, pause_between_steps_s=0)
    assert res["ok"] is True
    assert res["dry_run"] is False
    assert res["card_id"] == "card-123"
    assert len(res["steps"]) == 4  # create + 2 move + delete
    assert calls[0][0] == "create"
    assert calls[-1][0] == "delete"


def test_execute_falha_no_create_nao_chama_move_nem_delete(smoke_module):
    plan = {
        "pipe_id": "p1", "card_name": "X",
        "phases": [{"id": "ph_a", "name": "A"}],
        "start_form_values": {}, "warnings": [],
    }
    moved = []
    deleted = []
    def create(pid, name, fields):
        return None, "Token invalido"
    def move(cid, pid):
        moved.append(pid)
        return True, None
    def delete(cid):
        deleted.append(cid)
        return True, None
    res = smoke_module.execute_smoke(plan, create, move, delete, pause_between_steps_s=0)
    assert res["ok"] is False
    assert res["card_id"] is None
    assert moved == []
    assert deleted == []  # nao deleta pq nao criou
    assert any("create_card failed" in e for e in res["errors"])


def test_execute_falha_em_move_continua_e_deleta(smoke_module):
    """Move falhou em 1 phase: continua proximas, sempre tenta delete no fim."""
    plan = {
        "pipe_id": "p1", "card_name": "X",
        "phases": [
            {"id": "ph_a", "name": "A"},
            {"id": "ph_b", "name": "B"},
            {"id": "ph_c", "name": "C"},
        ],
        "start_form_values": {}, "warnings": [],
    }
    calls_move = []
    def create(*a, **kw): return "card-1", None
    def move(cid, pid):
        calls_move.append(pid)
        return (pid != "ph_b"), (None if pid != "ph_b" else "phase locked")
    def delete(cid): return True, None
    res = smoke_module.execute_smoke(plan, create, move, delete, pause_between_steps_s=0)
    assert res["ok"] is False
    assert calls_move == ["ph_a", "ph_b", "ph_c"]  # nao parou em ph_b
    # delete foi chamado mesmo com move falhando
    assert res["steps"][-1]["kind"] == "delete_card"
    assert res["steps"][-1]["ok"] is True


def test_execute_delete_falha_cria_alerta_de_orfao(smoke_module):
    plan = {
        "pipe_id": "p1", "card_name": "X",
        "phases": [{"id": "ph_a", "name": "A"}],
        "start_form_values": {}, "warnings": [],
    }
    def create(*a, **kw): return "card-orphan", None
    def move(*a, **kw): return True, None
    def delete(cid): return False, "permission denied"
    res = smoke_module.execute_smoke(plan, create, move, delete, pause_between_steps_s=0)
    assert res["ok"] is False
    assert any("ORFAO" in e for e in res["errors"])
    assert any("card-orphan" in e for e in res["errors"])


def test_execute_exception_em_callback_capturada(smoke_module):
    plan = {
        "pipe_id": "p1", "card_name": "X",
        "phases": [], "start_form_values": {}, "warnings": [],
    }
    def create(*a, **kw): raise RuntimeError("boom")
    def move(*a, **kw): return True, None
    def delete(*a, **kw): return True, None
    res = smoke_module.execute_smoke(plan, create, move, delete, pause_between_steps_s=0)
    assert res["ok"] is False
    assert any("exception" in e for e in res["errors"])


# ============== persist + list ==============

def test_persist_e_list(smoke_module, tmp_path):
    smoke_module.persist_smoke_run(str(tmp_path), "p1", {
        "ok": True, "dry_run": True, "steps": [], "elapsed_ms": 12,
    })
    runs = smoke_module.list_smoke_runs(str(tmp_path), "p1")
    assert len(runs) == 1
    assert runs[0]["pipe_id"] == "p1"
    assert runs[0]["ok"] is True


# ============== Endpoints ==============

def _reload_server(tmp_path, monkeypatch, env=None):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for k in ("APP_PASSWORD", "APP_USERNAME", "LIDERANCA_USERNAME", "LIDERANCA_PASSWORD",
              "SMOKE_PIPEFY_TOKEN", "SMOKE_PIPEFY_BASE_URL", "SMOKE_ALLOW_PRD"):
        monkeypatch.delenv(k, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    for d in ("config", "results", "snapshots", "snapshots/auto", "tmp"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    for f in ("complexity_weights.json", "semantic_rules.json", "quality_rules.json", "smoke_rules.json"):
        src = REPO_ROOT / "config" / f
        if src.exists():
            (tmp_path / "config" / f).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for mod in ("server", "smoke_runner", "semantic_scanner", "quality_scanner"):
        if mod in sys.modules:
            del sys.modules[mod]
    server = importlib.import_module("server")
    server.app.config["TESTING"] = True
    return server


def _write_snapshot(tmp_path, pipe_id, phases, env_label="HMG"):
    pipe_dir = tmp_path / "snapshots" / "auto" / pipe_id
    pipe_dir.mkdir(parents=True, exist_ok=True)
    snap = {
        "metadata": {"tool_version": "1.2", "env_label": env_label,
                     "timestamp": "2026-05-15T10:00", "pipe_id": pipe_id},
        "data": {"pipe": {"id": pipe_id, "name": pipe_id, "phases": phases}, "automations": []},
    }
    (pipe_dir / "20260515_100000.json").write_text(json.dumps(snap), encoding="utf-8")


def test_endpoint_dry_run_gated(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    res = server.app.test_client().post(
        "/api/smoke/dry-run",
        headers={"Authorization": _basic("demo", "demosecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"pipe_id": "p1"}),
    )
    assert res.status_code == 403


def test_endpoint_dry_run_400_sem_pipe_id(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().post(
        "/api/smoke/dry-run",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({}),
    )
    assert res.status_code == 400


def test_endpoint_dry_run_404_pipe_sem_snapshot(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().post(
        "/api/smoke/dry-run",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"pipe_id": "novato"}),
    )
    assert res.status_code == 404


def test_endpoint_dry_run_happy_path(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    _write_snapshot(tmp_path, "p1", [
        {"id": "ph_a", "name": "Análise"},
        {"id": "ph_b", "name": "Aprovação"},
    ])
    res = server.app.test_client().post(
        "/api/smoke/dry-run",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"pipe_id": "p1"}),
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["dry_run"] is True
    assert data["pipe_id"] == "p1"
    assert "plan" in data
    assert data["total_steps"] >= 1


def test_endpoint_run_real_bloqueado_sem_enabled(tmp_path, monkeypatch):
    """Sem pipe na whitelist, /run com dry_run=false retorna 403."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
        "SMOKE_PIPEFY_TOKEN": "Bearer abc",
    })
    _write_snapshot(tmp_path, "p1", [{"id": "ph_a", "name": "Análise"}])
    res = server.app.test_client().post(
        "/api/smoke/run",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"pipe_id": "p1", "dry_run": False}),
    )
    assert res.status_code == 403
    assert "nao habilitado" in res.get_json()["error"]


def test_endpoint_run_real_bloqueado_sem_token(tmp_path, monkeypatch):
    """Pipe enabled mas SMOKE_PIPEFY_TOKEN vazio -> 503."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    _write_snapshot(tmp_path, "p1", [{"id": "ph_a", "name": "Análise"}])
    (tmp_path / "config" / "smoke_rules.json").write_text(json.dumps({
        "version": "1.0",
        "pipes": {"p1": {"enabled": True}},
    }), encoding="utf-8")
    res = server.app.test_client().post(
        "/api/smoke/run",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"pipe_id": "p1", "dry_run": False}),
    )
    assert res.status_code == 503


def test_endpoint_run_real_bloqueado_em_prd_sem_allow_prd(tmp_path, monkeypatch):
    """Pipe PRD + enabled + token, mas allow_prd false -> 403."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
        "SMOKE_PIPEFY_TOKEN": "Bearer abc",
        # SMOKE_ALLOW_PRD nao setado
    })
    _write_snapshot(tmp_path, "p1", [{"id": "ph_a", "name": "Análise"}], env_label="PRD")
    (tmp_path / "config" / "smoke_rules.json").write_text(json.dumps({
        "version": "1.0",
        "pipes": {"p1": {"enabled": True, "allow_prd": True}},  # so config, sem env
    }), encoding="utf-8")
    res = server.app.test_client().post(
        "/api/smoke/run",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"pipe_id": "p1", "dry_run": False}),
    )
    assert res.status_code == 403
    assert "allow_prd" in res.get_json()["error"]


def test_endpoint_run_dry_default_true(tmp_path, monkeypatch):
    """/run sem 'dry_run' no body -> default true (seguro)."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    _write_snapshot(tmp_path, "p1", [{"id": "ph_a", "name": "Análise"}])
    res = server.app.test_client().post(
        "/api/smoke/run",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"pipe_id": "p1"}),
    )
    assert res.status_code == 200
    assert res.get_json()["dry_run"] is True


def test_endpoint_run_real_executa_com_mocks(tmp_path, monkeypatch):
    """Pipe enabled HMG + token + dry_run=false: chama mutations mockadas."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
        "SMOKE_PIPEFY_TOKEN": "Bearer abc",
    })
    _write_snapshot(tmp_path, "p1", [
        {"id": "ph_a", "name": "Análise"},
        {"id": "ph_b", "name": "Aprovação"},
    ])
    (tmp_path / "config" / "smoke_rules.json").write_text(json.dumps({
        "version": "1.0",
        "pipes": {"p1": {"enabled": True, "phases_to_cover": ["Análise", "Aprovação"]}},
    }), encoding="utf-8")
    # Mocka as 3 mutations.
    monkeypatch.setattr(server, "_pipefy_create_card", lambda pid, name, fields: ("card-XYZ", None))
    monkeypatch.setattr(server, "_pipefy_move_card", lambda cid, phid: (True, None))
    monkeypatch.setattr(server, "_pipefy_delete_card", lambda cid: (True, None))

    res = server.app.test_client().post(
        "/api/smoke/run",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"pipe_id": "p1", "dry_run": False}),
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["dry_run"] is False
    assert data["ok"] is True
    assert data["card_id"] == "card-XYZ"


def test_endpoint_webhook_listener_captura_hit(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={})
    res = server.app.test_client().post(
        "/api/smoke/webhook/p1",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"event": "card.move", "data": {"card_id": "x"}}),
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    assert body["hits"] >= 1


def test_endpoint_smoke_last_sem_runs(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/api/smoke/last?pipe_id=p1",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    body = res.get_json()
    assert body["available"] is False


def test_endpoint_smoke_history_gated(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    res = server.app.test_client().get(
        "/api/smoke/history?pipe_id=p1",
        headers={"Authorization": _basic("demo", "demosecret")},
    )
    assert res.status_code == 403


def test_endpoint_smoke_rules_listing(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/api/smoke/rules",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert "token_configured" in body
    assert "allow_prd_env" in body
    assert "pipes" in body


def test_dry_run_persiste_no_historico(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret", "LIDERANCA_PASSWORD": "ldsecret",
    })
    _write_snapshot(tmp_path, "p1", [{"id": "ph_a", "name": "Análise"}])
    server.app.test_client().post(
        "/api/smoke/run",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"pipe_id": "p1", "dry_run": True}),
    )
    hist_dir = tmp_path / "results" / "smoke_runs" / "p1"
    assert hist_dir.is_dir()
    assert len(list(hist_dir.glob("*.json"))) == 1
