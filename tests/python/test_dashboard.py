"""Testes do login 'lideranca' + Dashboard executivo.

Cobre:
- /api/whoami sem auth (modo dev) -> role 'open'
- /api/whoami com demo -> role 'demo'
- /api/whoami com lideranca -> role 'lideranca'
- /v2/dashboard: 200 pra lideranca/open, 403 pra demo
- /api/dashboard/data: 200 pra lideranca/open, 403 pra demo
- 401 quando credenciais inválidas
- LIDERANCA_PASSWORD via env var
"""
import base64
import importlib
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _reload_server(tmp_path, monkeypatch, env=None):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for k in ("APP_PASSWORD", "APP_USERNAME", "LIDERANCA_USERNAME", "LIDERANCA_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    for d in ("config", "results", "snapshots", "tmp"):
        p = tmp_path / d
        if not p.exists():
            p.mkdir()
    monkeypatch.chdir(tmp_path)
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.app.config["TESTING"] = True
    return server


def _basic(user, pw):
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


# ---------- whoami ----------

def test_whoami_modo_dev_retorna_open(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch)
    res = server.app.test_client().get("/api/whoami")
    assert res.status_code == 200
    body = res.get_json()
    assert body["role"] == "open"
    assert body["auth_enabled"] is False


def test_whoami_demo_autenticado_retorna_demo(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "APP_USERNAME": "demo",
    })
    res = server.app.test_client().get(
        "/api/whoami", headers={"Authorization": _basic("demo", "demosecret")}
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["role"] == "demo"
    assert body["auth_enabled"] is True


def test_whoami_lideranca_autenticado_retorna_lideranca(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
    })
    res = server.app.test_client().get(
        "/api/whoami", headers={"Authorization": _basic("lideranca", "lideranca")}
    )
    assert res.status_code == 200
    assert res.get_json()["role"] == "lideranca"


def test_whoami_credenciais_invalidas_401(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
    })
    res = server.app.test_client().get(
        "/api/whoami", headers={"Authorization": _basic("demo", "errado")}
    )
    assert res.status_code == 401


# ---------- /v2/dashboard ----------

def test_dashboard_modo_dev_serve_html(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch)
    res = server.app.test_client().get("/v2/dashboard")
    assert res.status_code == 200
    assert b"<" in res.data


def test_dashboard_lideranca_serve_html(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
    })
    res = server.app.test_client().get(
        "/v2/dashboard", headers={"Authorization": _basic("lideranca", "lideranca")}
    )
    assert res.status_code == 200
    assert b"Dashboard" in res.data


def test_dashboard_demo_recebe_403(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
    })
    res = server.app.test_client().get(
        "/v2/dashboard", headers={"Authorization": _basic("demo", "demosecret")}
    )
    assert res.status_code == 403
    assert "restrito" in res.get_json().get("error", "").lower()


def test_dashboard_sem_auth_recebe_401_quando_app_password_setada(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
    })
    res = server.app.test_client().get("/v2/dashboard")
    assert res.status_code == 401


# ---------- /api/dashboard/data ----------

def test_dashboard_data_lideranca_retorna_payload(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
    })
    res = server.app.test_client().get(
        "/api/dashboard/data", headers={"Authorization": _basic("lideranca", "lideranca")}
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["role"] == "lideranca"
    assert body["placeholder"] is True


def test_dashboard_data_demo_recebe_403(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
    })
    res = server.app.test_client().get(
        "/api/dashboard/data", headers={"Authorization": _basic("demo", "demosecret")}
    )
    assert res.status_code == 403


def test_dashboard_data_modo_dev_retorna_payload(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch)
    res = server.app.test_client().get("/api/dashboard/data")
    assert res.status_code == 200
    assert res.get_json()["role"] == "open"


# ---------- LIDERANCA_PASSWORD via env var ----------

def test_lideranca_password_pode_ser_override_via_env(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "outrasenha",
    })
    # Senha default 'lideranca' não funciona quando env var altera
    res = server.app.test_client().get(
        "/api/whoami", headers={"Authorization": _basic("lideranca", "lideranca")}
    )
    assert res.status_code == 401
    # Senha custom funciona
    res = server.app.test_client().get(
        "/api/whoami", headers={"Authorization": _basic("lideranca", "outrasenha")}
    )
    assert res.status_code == 200
    assert res.get_json()["role"] == "lideranca"


def test_lideranca_username_pode_ser_override_via_env(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_USERNAME": "diretor",
    })
    res = server.app.test_client().get(
        "/api/whoami", headers={"Authorization": _basic("diretor", "lideranca")}
    )
    assert res.status_code == 200
    assert res.get_json()["role"] == "lideranca"


# ---------- Integridade: rotas existentes não quebraram ----------

def test_demo_continua_acessando_v2_configuracao(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
    })
    res = server.app.test_client().get(
        "/v2/configuracao", headers={"Authorization": _basic("demo", "demosecret")}
    )
    assert res.status_code == 200


def test_lideranca_tambem_acessa_v2_configuracao(tmp_path, monkeypatch):
    """Lideranca herda acesso ao app inteiro (não fica preso só no dashboard)."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
    })
    res = server.app.test_client().get(
        "/v2/configuracao", headers={"Authorization": _basic("lideranca", "lideranca")}
    )
    assert res.status_code == 200
