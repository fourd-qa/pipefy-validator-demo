"""Testes pra os 3 fixes P1 de seguranca aplicados na sprint-vistoria:

P1.1 - /api/default-env nao vaza token pra role demo (so lideranca/dev/loopback).
P1.2 - /api/discover-pipes valida base_url contra allowlist (SSRF).
P1.4 - @app.after_request adiciona headers de seguranca em todas as respostas.
"""
import base64
import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _reload_server(tmp_path, monkeypatch, env=None):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for k in (
        "APP_PASSWORD", "APP_USERNAME", "LIDERANCA_USERNAME", "LIDERANCA_PASSWORD",
        "DEFAULT_PIPEFY_TOKEN", "DEFAULT_PIPEFY_BASE_URL", "DEFAULT_PIPEFY_ORG_ID",
        "DEFAULT_PIPEFY_NAME", "ALLOWED_PIPEFY_HOSTS", "ALLOW_OPEN_DASHBOARD",
    ):
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


# ============================================================
# P1.1 - /api/default-env nao vaza token pra role demo
# ============================================================

def test_default_env_sem_token_setado_retorna_unavailable(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch)
    res = server.app.test_client().get("/api/default-env")
    assert res.status_code == 200
    body = res.get_json()
    assert body == {"available": False}


def test_default_env_role_demo_nao_recebe_token(tmp_path, monkeypatch):
    """Regressao P1.1: antes, demo conseguia ler DEFAULT_PIPEFY_TOKEN em texto plano.
    Agora deve receber {available: False} mesmo com token setado."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "DEFAULT_PIPEFY_TOKEN": "supersecret-pat-token-abc123",
        "DEFAULT_PIPEFY_ORG_ID": "42",
    })
    res = server.app.test_client().get(
        "/api/default-env", headers={"Authorization": _basic("demo", "demosecret")}
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body == {"available": False}
    assert "supersecret-pat-token" not in res.get_data(as_text=True)


def test_default_env_role_lideranca_recebe_token(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "DEFAULT_PIPEFY_TOKEN": "lideranca-token-xyz",
        "DEFAULT_PIPEFY_ORG_ID": "42",
        "DEFAULT_PIPEFY_NAME": "Sandbox",
    })
    res = server.app.test_client().get(
        "/api/default-env", headers={"Authorization": _basic("lideranca", "lideranca")}
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["available"] is True
    assert body["token"] == "lideranca-token-xyz"
    assert body["org_id"] == "42"


def test_default_env_modo_dev_libera_loopback(tmp_path, monkeypatch):
    """Sem APP_PASSWORD (modo dev), role='open' e loopback liberam o token.
    Cobre o cenario de uso local sem auth configurada."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "DEFAULT_PIPEFY_TOKEN": "local-dev-token",
    })
    res = server.app.test_client().get("/api/default-env")
    assert res.status_code == 200
    body = res.get_json()
    assert body["available"] is True
    assert body["token"] == "local-dev-token"


# ============================================================
# P1.2 - /api/discover-pipes valida base_url (SSRF)
# ============================================================

def test_discover_pipes_bloqueia_url_aws_metadata(tmp_path, monkeypatch):
    """Regressao P1.2: atacante autenticado nao pode usar discover-pipes pra
    bater em 169.254.169.254 (cloud metadata) ou hosts internos da VPC."""
    server = _reload_server(tmp_path, monkeypatch)
    res = server.app.test_client().post("/api/discover-pipes", json={
        "token": "x",
        "base_url": "http://169.254.169.254/latest/meta-data/",
        "org_id": "1",
    })
    assert res.status_code == 400
    body = res.get_json()
    assert "base_url" in body["error"].lower()
    assert "169.254" in body["error"] or "allowlist" in body["error"].lower()


def test_discover_pipes_bloqueia_localhost(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch)
    res = server.app.test_client().post("/api/discover-pipes", json={
        "token": "x",
        "base_url": "http://localhost:8080/api/internal",
        "org_id": "1",
    })
    assert res.status_code == 400
    assert "allowlist" in res.get_json()["error"].lower() or "localhost" in res.get_json()["error"]


def test_discover_pipes_bloqueia_scheme_file(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch)
    res = server.app.test_client().post("/api/discover-pipes", json={
        "token": "x",
        "base_url": "file:///etc/passwd",
        "org_id": "1",
    })
    assert res.status_code == 400
    assert "scheme" in res.get_json()["error"].lower()


def test_discover_pipes_bloqueia_http_no_pipefy_oficial(tmp_path, monkeypatch):
    """Regressao P2.1: HTTPS obrigatorio mesmo para hosts no allowlist.
    Antes, http://api.pipefy.com passava e expunha o PAT Bearer a MITM."""
    server = _reload_server(tmp_path, monkeypatch)
    res = server.app.test_client().post("/api/discover-pipes", json={
        "token": "x",
        "base_url": "http://api.pipefy.com/graphql",
        "org_id": "1",
    })
    assert res.status_code == 400
    err = res.get_json()["error"].lower()
    assert "http" in err and ("loopback" in err or "https" in err)


def test_discover_pipes_aceita_pipefy_oficial(tmp_path, monkeypatch, mocker):
    """URL oficial passa pela validacao. Mocka requests.post pra nao bater no Pipefy real."""
    server = _reload_server(tmp_path, monkeypatch)

    class _FakeResp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"data": {"organization": {"name": "FourD", "pipes": []}}}

    mocker.patch("requests.post", return_value=_FakeResp())
    res = server.app.test_client().post("/api/discover-pipes", json={
        "token": "x",
        "base_url": "https://api.pipefy.com/graphql",
        "org_id": "1",
    })
    assert res.status_code == 200
    assert res.get_json()["ok"] is True


def test_discover_pipes_aceita_host_no_allowlist_override(tmp_path, monkeypatch, mocker):
    """ALLOWED_PIPEFY_HOSTS env permite adicionar hosts custom (Pipefy on-prem)."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "ALLOWED_PIPEFY_HOSTS": "pipefy-onprem.empresa.com",
    })

    class _FakeResp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"data": {"organization": {"name": "X", "pipes": []}}}

    mocker.patch("requests.post", return_value=_FakeResp())
    res = server.app.test_client().post("/api/discover-pipes", json={
        "token": "x",
        "base_url": "https://pipefy-onprem.empresa.com/graphql",
        "org_id": "1",
    })
    assert res.status_code == 200


# ============================================================
# P1.4 - Headers de seguranca em todas as respostas
# ============================================================

def test_security_headers_em_endpoint_json(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch)
    res = server.app.test_client().get("/healthz")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "same-origin"
    assert "max-age" in res.headers["Strict-Transport-Security"]
    csp = res.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_security_headers_em_endpoint_html(tmp_path, monkeypatch):
    """HTML do dashboard tambem recebe os headers. Cobre o caso de XSS via
    log Robot conseguir escapar e tentar carregar script externo."""
    server = _reload_server(tmp_path, monkeypatch)
    res = server.app.test_client().get("/v2/dashboard")
    assert res.status_code == 200
    assert res.headers["X-Frame-Options"] == "DENY"
    csp = res.headers["Content-Security-Policy"]
    assert "script-src" in csp
    assert "https://api.pipefy.com" in csp


def test_security_headers_em_resposta_de_erro_401(tmp_path, monkeypatch):
    """Headers tambem em respostas 401/403/500 pra nao deixar gap."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
    })
    res = server.app.test_client().get("/api/whoami")
    assert res.status_code == 401
    assert res.headers["X-Content-Type-Options"] == "nosniff"
