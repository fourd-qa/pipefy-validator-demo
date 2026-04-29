"""Fixtures pytest pra isolar o server.py em filesystem temporário.

server.py usa os.getcwd() na inicialização pra apontar pra results/ e config/.
Como esses paths já estão fixos como módulo-level, redirecionamos eles via monkeypatch
antes de cada teste, e re-importamos o módulo num CWD limpo.
"""
import os
import sys
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Cria um diretório temporário com config/, results/, snapshots/, tmp/ e
    aponta o server.py pra ele via monkeypatch dos módulos-level paths."""
    (tmp_path / "config").mkdir()
    (tmp_path / "results").mkdir()
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "tmp").mkdir()

    # Garante que o server.py é importado a partir do repo root
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    # Garante que APP_PASSWORD esta vazia pra testes (sem auth)
    monkeypatch.delenv("APP_PASSWORD", raising=False)

    # Faz o módulo recarregar com CWD temporário
    monkeypatch.chdir(tmp_path)
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    return tmp_path, server


@pytest.fixture
def pipefy_payload():
    """Payload mínimo Pipefy pra POST /api/run."""
    return {
        "token": "Bearer fake_token_xyz",
        "base_url": "https://api.pipefy.com/graphql",
        "org_id": "999",
        "auth_mode": "bearer",
        "verify_ssl": False,
        "pipe_origem_uuid": "uuid-origem",
        "pipe_destino_uuid": "uuid-copia",
        "pipe_origem_repo_id": "111",
        "pipe_destino_repo_id": "222",
    }


@pytest.fixture
def cross_payload():
    """Payload cross-env (2 sets de credenciais)."""
    return {
        "src_token": "Bearer src_tok",
        "src_base_url": "https://src.pipefy.com/graphql",
        "src_org_id": "1",
        "dst_token": "Bearer dst_tok",
        "dst_base_url": "https://dst.pipefy.com/graphql",
        "dst_org_id": "2",
        "pipe_origem_uuid": "uuid-src",
        "pipe_destino_uuid": "uuid-dst",
    }


@pytest.fixture
def ipaas_payload():
    """Payload iPaaS."""
    return {
        "ipaas_token": "Bearer ipaas_tok",
        "ipaas_base_url": "https://ipaas.pipefy.com/api/v1",
        "ipaas_project_id": "p1",
    }


@pytest.fixture
def client(workdir):
    """Test client do Flask em modo testing."""
    _, server = workdir
    server.app.config["TESTING"] = True
    return server.app.test_client()


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    """Test client com APP_PASSWORD setada e header Authorization injetado."""
    import base64
    monkeypatch.setenv("APP_PASSWORD", "demosecret")
    monkeypatch.setenv("APP_USERNAME", "demo")
    (tmp_path / "config").mkdir()
    (tmp_path / "results").mkdir()
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "tmp").mkdir()
    monkeypatch.chdir(tmp_path)
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.app.config["TESTING"] = True
    creds = base64.b64encode(b"demo:demosecret").decode()
    client = server.app.test_client()
    # Injeta header padrão em todos os requests
    orig = client.open

    def open_with_auth(*args, **kwargs):
        headers = kwargs.pop("headers", {}) or {}
        if "Authorization" not in headers:
            headers["Authorization"] = "Basic " + creds
        return orig(*args, headers=headers, **kwargs)

    client.open = open_with_auth
    return tmp_path, server, client
