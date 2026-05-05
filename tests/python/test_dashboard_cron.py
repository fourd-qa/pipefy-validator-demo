"""Testes da Sprint 2 do Dashboard de Produtividade.

Cobre:
- /api/dashboard/monitored-pipes GET (gated, retorna lista + flags)
- /api/dashboard/monitored-pipes POST (gated, salva, valida shape)
- /api/cron/snapshot (token-based auth, pula sem pipes, tenta coletar)
- /api/dashboard/auto-snapshots/<pipe_id> (lista historico, gated)
- Persistencia em config/monitored_pipes.json
"""
import base64
import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _basic(user, pw):
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


def _reload_server(tmp_path, monkeypatch, env=None):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for k in ("APP_PASSWORD", "APP_USERNAME", "LIDERANCA_USERNAME", "LIDERANCA_PASSWORD",
              "CRON_SNAPSHOT_TOKEN", "MONITOR_PIPEFY_TOKEN", "MONITOR_PIPEFY_BASE_URL",
              "MONITOR_PIPEFY_ORG_ID"):
        monkeypatch.delenv(k, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    for d in ("config", "results", "snapshots", "tmp"):
        (tmp_path / d).mkdir(exist_ok=True)
    monkeypatch.chdir(tmp_path)
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.app.config["TESTING"] = True
    return server


# ---------- GET /api/dashboard/monitored-pipes ----------

def test_get_monitored_pipes_lista_vazia_quando_sem_arquivo(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch)
    res = server.app.test_client().get("/api/dashboard/monitored-pipes")
    assert res.status_code == 200
    body = res.get_json()
    assert body["pipes"] == []
    assert body["monitor_token_configured"] is False
    assert body["cron_token_configured"] is False


def test_get_monitored_pipes_demo_recebe_403(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    res = server.app.test_client().get(
        "/api/dashboard/monitored-pipes",
        headers={"Authorization": _basic("demo", "demosecret")},
    )
    assert res.status_code == 403


def test_get_monitored_pipes_lideranca_acessa(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    res = server.app.test_client().get(
        "/api/dashboard/monitored-pipes",
        headers={"Authorization": _basic("lideranca", "lideranca")},
    )
    assert res.status_code == 200


def test_get_monitored_pipes_reflete_env_vars(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "CRON_SNAPSHOT_TOKEN": "secret",
        "MONITOR_PIPEFY_TOKEN": "Bearer xxx",
    })
    res = server.app.test_client().get("/api/dashboard/monitored-pipes")
    body = res.get_json()
    assert body["cron_token_configured"] is True
    assert body["monitor_token_configured"] is True


# ---------- POST /api/dashboard/monitored-pipes ----------

def test_post_monitored_pipes_salva_e_persiste(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch)
    pipes = [
        {"id": "uuid-mesa", "name": "Mesa Crédito", "repo_id": "337", "env_label": "HMG", "enabled": True},
        {"id": "uuid-analise", "name": "Análise", "repo_id": "324", "env_label": "PRD", "enabled": False},
    ]
    res = server.app.test_client().post(
        "/api/dashboard/monitored-pipes",
        json={"pipes": pipes},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    assert body["count"] == 2

    # Persistencia: arquivo criado
    config_file = tmp_path / "config" / "monitored_pipes.json"
    assert config_file.exists()
    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert len(data["pipes"]) == 2
    assert data["pipes"][0]["id"] == "uuid-mesa"


def test_post_monitored_pipes_corpo_invalido_400(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch)
    res = server.app.test_client().post(
        "/api/dashboard/monitored-pipes",
        json={"pipes": "nao-eh-lista"},
    )
    assert res.status_code == 400


def test_post_monitored_pipes_filtra_entradas_invalidas(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch)
    pipes = [
        {"id": "valido", "name": "P1", "enabled": True},
        "string solta",  # ignorado
        None,  # ignorado
        {"id": "outro", "name": "P2"},
    ]
    res = server.app.test_client().post(
        "/api/dashboard/monitored-pipes",
        json={"pipes": pipes},
    )
    assert res.status_code == 200
    assert res.get_json()["count"] == 2


def test_post_monitored_pipes_demo_recebe_403(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    res = server.app.test_client().post(
        "/api/dashboard/monitored-pipes",
        json={"pipes": []},
        headers={"Authorization": _basic("demo", "demosecret")},
    )
    assert res.status_code == 403


# ---------- POST /api/cron/snapshot ----------

def test_cron_snapshot_sem_token_configurado_503(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch)
    res = server.app.test_client().post("/api/cron/snapshot")
    assert res.status_code == 503
    assert "CRON_SNAPSHOT_TOKEN" in res.get_json()["error"]


def test_cron_snapshot_token_invalido_401(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"CRON_SNAPSHOT_TOKEN": "secreto"})
    res = server.app.test_client().post(
        "/api/cron/snapshot",
        headers={"X-Cron-Token": "errado"},
    )
    assert res.status_code == 401


def test_cron_snapshot_sem_monitor_token_503(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"CRON_SNAPSHOT_TOKEN": "secreto"})
    res = server.app.test_client().post(
        "/api/cron/snapshot",
        headers={"X-Cron-Token": "secreto"},
    )
    assert res.status_code == 503
    assert "MONITOR_PIPEFY_TOKEN" in res.get_json()["error"]


def test_cron_snapshot_pula_quando_lista_vazia(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "CRON_SNAPSHOT_TOKEN": "secreto",
        "MONITOR_PIPEFY_TOKEN": "Bearer xxx",
    })
    res = server.app.test_client().post(
        "/api/cron/snapshot",
        headers={"X-Cron-Token": "secreto"},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    assert body["skipped"] is True


def test_cron_snapshot_chama_pipefy_e_salva_arquivo(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "CRON_SNAPSHOT_TOKEN": "secreto",
        "MONITOR_PIPEFY_TOKEN": "Bearer xxx",
    })
    # Adiciona 1 pipe monitorado
    server.app.test_client().post(
        "/api/dashboard/monitored-pipes",
        json={"pipes": [{"id": "abc-123", "name": "Mesa", "repo_id": "337", "env_label": "HMG", "enabled": True}]},
    )

    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps({
        "data": {"pipe": {"id": "abc-123", "name": "Mesa", "phases": [], "start_form_fields": [], "labels": []}}
    }).encode("utf-8")
    fake_response.__enter__ = lambda self: fake_response
    fake_response.__exit__ = lambda *args: None

    with patch("urllib.request.urlopen", return_value=fake_response):
        res = server.app.test_client().post(
            "/api/cron/snapshot",
            headers={"X-Cron-Token": "secreto"},
        )

    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    assert body["total_pipes"] == 1
    assert body["results"][0]["ok"] is True

    # Arquivo salvo em snapshots/auto/abc-123/<timestamp>.json
    auto_dir = tmp_path / "snapshots" / "auto" / "abc-123"
    assert auto_dir.exists()
    files = list(auto_dir.glob("*.json"))
    assert len(files) == 1
    saved = json.loads(files[0].read_text(encoding="utf-8"))
    assert saved["metadata"]["pipe_id"] == "abc-123"
    assert saved["metadata"]["source"] == "cron_auto"


def test_cron_snapshot_pipefy_retorna_erro_graphql(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "CRON_SNAPSHOT_TOKEN": "secreto",
        "MONITOR_PIPEFY_TOKEN": "Bearer xxx",
    })
    server.app.test_client().post(
        "/api/dashboard/monitored-pipes",
        json={"pipes": [{"id": "abc-123", "name": "Mesa", "enabled": True}]},
    )

    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps({
        "errors": [{"message": "Unauthorized"}]
    }).encode("utf-8")
    fake_response.__enter__ = lambda self: fake_response
    fake_response.__exit__ = lambda *args: None

    with patch("urllib.request.urlopen", return_value=fake_response):
        res = server.app.test_client().post(
            "/api/cron/snapshot",
            headers={"X-Cron-Token": "secreto"},
        )
    assert res.status_code == 200
    body = res.get_json()
    assert body["results"][0]["ok"] is False
    assert "GraphQL" in body["results"][0]["error"]


def test_cron_snapshot_pipefy_http_error(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "CRON_SNAPSHOT_TOKEN": "secreto",
        "MONITOR_PIPEFY_TOKEN": "Bearer xxx",
    })
    server.app.test_client().post(
        "/api/dashboard/monitored-pipes",
        json={"pipes": [{"id": "abc-123", "name": "Mesa", "enabled": True}]},
    )

    import urllib.error
    err = urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)
    with patch("urllib.request.urlopen", side_effect=err):
        res = server.app.test_client().post(
            "/api/cron/snapshot",
            headers={"X-Cron-Token": "secreto"},
        )
    body = res.get_json()
    assert body["results"][0]["ok"] is False
    assert "HTTP 401" in body["results"][0]["error"]


def test_cron_snapshot_pula_pipes_desabilitados(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "CRON_SNAPSHOT_TOKEN": "secreto",
        "MONITOR_PIPEFY_TOKEN": "Bearer xxx",
    })
    server.app.test_client().post(
        "/api/dashboard/monitored-pipes",
        json={"pipes": [
            {"id": "ativo", "name": "A", "enabled": True},
            {"id": "inativo", "name": "I", "enabled": False},
        ]},
    )

    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps({"data": {"pipe": {"id": "ativo"}}}).encode("utf-8")
    fake_response.__enter__ = lambda self: fake_response
    fake_response.__exit__ = lambda *args: None

    with patch("urllib.request.urlopen", return_value=fake_response):
        res = server.app.test_client().post(
            "/api/cron/snapshot",
            headers={"X-Cron-Token": "secreto"},
        )
    body = res.get_json()
    assert body["total_pipes"] == 1  # so o ativo


# ---------- GET /api/dashboard/auto-snapshots/<pipe_id> ----------

def test_auto_snapshots_pipe_inexistente_retorna_lista_vazia(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch)
    res = server.app.test_client().get("/api/dashboard/auto-snapshots/qualquer-id")
    assert res.status_code == 200
    body = res.get_json()
    assert body["snapshots"] == []


def test_auto_snapshots_lista_arquivos_existentes(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch)
    pipe_dir = tmp_path / "snapshots" / "auto" / "abc-123"
    pipe_dir.mkdir(parents=True)
    (pipe_dir / "20260505_140000.json").write_text("{}", encoding="utf-8")
    (pipe_dir / "20260505_143000.json").write_text("{}", encoding="utf-8")

    res = server.app.test_client().get("/api/dashboard/auto-snapshots/abc-123")
    body = res.get_json()
    assert len(body["snapshots"]) == 2


def test_auto_snapshots_demo_recebe_403(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    res = server.app.test_client().get(
        "/api/dashboard/auto-snapshots/abc",
        headers={"Authorization": _basic("demo", "demosecret")},
    )
    assert res.status_code == 403
