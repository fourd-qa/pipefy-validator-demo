"""Testes da engine de scoring (dashboard_metrics.py) + endpoints velocity.

Sprint 1 do Dashboard de Produtividade.
"""
import base64
import importlib
import json
import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def metrics_module():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if "dashboard_metrics" in sys.modules:
        del sys.modules["dashboard_metrics"]
    return importlib.import_module("dashboard_metrics")


@pytest.fixture
def weights_path():
    return str(REPO_ROOT / "config" / "complexity_weights.json")


@pytest.fixture
def sample_validations():
    return {
        "status": "DIVERGENCIAS_ENCONTRADAS",
        "pipe_origem": "Mesa Crédito HMG",
        "pipe_destino": "Mesa Crédito PRD",
        "total_divergencias": 6,
        "divergencias": [
            "[CAMPO AUSENTE] Campo \"valor_aprovado\" existe na Origem mas NAO no Destino",
            "[FASE AUSENTE] Fase \"Pre-aprovacao\" existe na Origem mas NAO no Destino",
            "[AUTOMACAO URL] Automation X URL diverge: https://hmg vs https://prd",
            "[AUTOMACAO CONDITION] Automation X condition diverge",
            "[LABEL EXTRA] Label \"vermelho\" existe no Destino mas NAO na Origem",
            "[TIPO DIFERENTE] Campo \"id\" tipo diverge: text vs number",
        ],
        "metadata": {
            "timestamp": "2026-05-05T14:30:00",
            "tool_version": "1.0",
        },
    }


# ---------- extract_prefix ----------

def test_extract_prefix_padrao_simples(metrics_module):
    assert metrics_module.extract_prefix("[CAMPO AUSENTE] Campo X") == "[CAMPO AUSENTE]"


def test_extract_prefix_com_espacos_iniciais(metrics_module):
    assert metrics_module.extract_prefix("  [FASE EXTRA] Fase Y") == "[FASE EXTRA]"


def test_extract_prefix_padrao_composto(metrics_module):
    assert metrics_module.extract_prefix("[START FORM - CAMPO AUSENTE] Campo Z") == "[START FORM - CAMPO AUSENTE]"


def test_extract_prefix_sem_colchetes_retorna_none(metrics_module):
    assert metrics_module.extract_prefix("Mensagem livre sem prefixo") is None


def test_extract_prefix_input_nao_string(metrics_module):
    assert metrics_module.extract_prefix(None) is None
    assert metrics_module.extract_prefix(42) is None
    assert metrics_module.extract_prefix({}) is None


# ---------- score_divergencia ----------

def test_score_divergencia_prefixo_conhecido(metrics_module, weights_path):
    weights = metrics_module.load_weights(weights_path)
    result = metrics_module.score_divergencia(
        "[CAMPO AUSENTE] Campo \"x\"", weights
    )
    assert result["prefix"] == "[CAMPO AUSENTE]"
    assert result["weight"] == 3
    assert result["bucket"] == "structure"


def test_score_divergencia_automation_url_eh_logic(metrics_module, weights_path):
    weights = metrics_module.load_weights(weights_path)
    result = metrics_module.score_divergencia(
        "[AUTOMACAO URL] X muda", weights
    )
    assert result["bucket"] == "logic"
    assert result["weight"] == 8


def test_score_divergencia_label_eh_visual_e_baixo(metrics_module, weights_path):
    weights = metrics_module.load_weights(weights_path)
    result = metrics_module.score_divergencia("[LABEL EXTRA] vermelho", weights)
    assert result["bucket"] == "visual"
    assert result["weight"] == 1


def test_score_divergencia_prefixo_desconhecido_usa_default(metrics_module, weights_path):
    weights = metrics_module.load_weights(weights_path)
    result = metrics_module.score_divergencia("[NOVO TIPO INESPERADO] X", weights)
    assert result["weight"] == 2  # default_weight do JSON
    assert result["bucket"] == "structure"


def test_score_divergencia_sem_prefixo_usa_default(metrics_module, weights_path):
    weights = metrics_module.load_weights(weights_path)
    result = metrics_module.score_divergencia("mensagem livre", weights)
    assert result["prefix"] is None
    assert result["weight"] == 2


# ---------- score_validations ----------

def test_score_validations_total_correto(metrics_module, weights_path, sample_validations):
    weights = metrics_module.load_weights(weights_path)
    result = metrics_module.score_validations(sample_validations, weights)
    # 3 (CAMPO AUSENTE) + 6 (FASE AUSENTE) + 8 (AUTOMACAO URL) + 5 (AUTOMACAO CONDITION) + 1 (LABEL EXTRA) + 5 (TIPO DIFERENTE)
    assert result["total_points"] == 28


def test_score_validations_breakdown_por_balde(metrics_module, weights_path, sample_validations):
    weights = metrics_module.load_weights(weights_path)
    result = metrics_module.score_validations(sample_validations, weights)
    buckets = result["by_bucket"]
    # visual: 1 (LABEL EXTRA)
    assert buckets["visual"] == 1
    # structure: 3 (CAMPO AUSENTE) + 6 (FASE AUSENTE) + 5 (TIPO DIFERENTE) = 14
    assert buckets["structure"] == 14
    # logic: 8 (URL) + 5 (CONDITION) = 13
    assert buckets["logic"] == 13
    # integration: 0
    assert buckets["integration"] == 0


def test_score_validations_top_items_ordenado_desc(metrics_module, weights_path, sample_validations):
    weights = metrics_module.load_weights(weights_path)
    result = metrics_module.score_validations(sample_validations, weights)
    weights_sorted = [item["weight"] for item in result["top_items"]]
    assert weights_sorted == sorted(weights_sorted, reverse=True)
    assert result["top_items"][0]["weight"] == 8  # URL


def test_score_validations_meta_preservada(metrics_module, weights_path, sample_validations):
    weights = metrics_module.load_weights(weights_path)
    result = metrics_module.score_validations(sample_validations, weights)
    assert result["meta"]["status"] == "DIVERGENCIAS_ENCONTRADAS"
    assert result["meta"]["pipe_origem"] == "Mesa Crédito HMG"
    assert result["meta"]["timestamp"] == "2026-05-05T14:30:00"


def test_score_validations_zero_divergencias(metrics_module, weights_path):
    weights = metrics_module.load_weights(weights_path)
    result = metrics_module.score_validations(
        {"status": "IDENTICOS", "divergencias": [], "metadata": {}}, weights
    )
    assert result["total_points"] == 0
    assert result["by_bucket"] == {"visual": 0, "structure": 0, "logic": 0, "integration": 0}
    assert result["top_items"] == []


def test_score_validations_by_prefix_agrupa_e_conta(metrics_module, weights_path):
    weights = metrics_module.load_weights(weights_path)
    validations = {
        "divergencias": [
            "[CAMPO AUSENTE] x",
            "[CAMPO AUSENTE] y",
            "[CAMPO AUSENTE] z",
            "[LABEL EXTRA] cor",
        ],
    }
    result = metrics_module.score_validations(validations, weights)
    assert result["by_prefix"]["[CAMPO AUSENTE]"]["count"] == 3
    assert result["by_prefix"]["[CAMPO AUSENTE]"]["total_weight"] == 9
    assert result["by_prefix"]["[LABEL EXTRA]"]["count"] == 1


# ---------- compute_velocity ----------

def test_compute_velocity_arquivo_inexistente(metrics_module, weights_path, tmp_path):
    result = metrics_module.compute_velocity(
        str(tmp_path / "naoexiste.json"), weights_path
    )
    assert result["available"] is False
    assert result["total_points"] == 0
    assert "Sem validacao" in result["reason"]


def test_compute_velocity_arquivo_corrompido(metrics_module, weights_path, tmp_path):
    bad = tmp_path / "validations.json"
    bad.write_text("{ this is not valid json", encoding="utf-8")
    result = metrics_module.compute_velocity(str(bad), weights_path)
    assert result["available"] is False
    assert "Falha lendo" in result["reason"]


def test_compute_velocity_arquivo_valido(metrics_module, weights_path, tmp_path, sample_validations):
    valid = tmp_path / "validations.json"
    valid.write_text(json.dumps(sample_validations), encoding="utf-8")
    result = metrics_module.compute_velocity(str(valid), weights_path)
    assert result["available"] is True
    assert result["total_points"] == 28
    assert result["meta"]["pipe_origem"] == "Mesa Crédito HMG"


# ---------- Endpoints HTTP ----------

def _basic(user, pw):
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


def _reload_server_with_validations(tmp_path, monkeypatch, validations_dict, env=None):
    """Helper: cria filesystem temporario com validations.json + carrega server."""
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
    (tmp_path / "results" / "validations.json").write_text(
        json.dumps(validations_dict), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    if "server" in sys.modules:
        del sys.modules["server"]
    if "dashboard_metrics" in sys.modules:
        del sys.modules["dashboard_metrics"]
    server = importlib.import_module("server")
    server.app.config["TESTING"] = True
    return server


def test_endpoint_velocity_lideranca_retorna_pontuacao(tmp_path, monkeypatch, sample_validations):
    server = _reload_server_with_validations(tmp_path, monkeypatch, sample_validations, env={
        "APP_PASSWORD": "demosecret",
    })
    res = server.app.test_client().get(
        "/api/dashboard/velocity",
        headers={"Authorization": _basic("lideranca", "lideranca")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["available"] is True
    assert body["total_points"] == 28
    assert body["by_bucket"]["logic"] == 13


def test_endpoint_velocity_demo_recebe_403(tmp_path, monkeypatch, sample_validations):
    server = _reload_server_with_validations(tmp_path, monkeypatch, sample_validations, env={
        "APP_PASSWORD": "demosecret",
    })
    res = server.app.test_client().get(
        "/api/dashboard/velocity",
        headers={"Authorization": _basic("demo", "demosecret")},
    )
    assert res.status_code == 403


def test_endpoint_velocity_modo_dev_libera(tmp_path, monkeypatch, sample_validations):
    server = _reload_server_with_validations(tmp_path, monkeypatch, sample_validations)
    res = server.app.test_client().get("/api/dashboard/velocity")
    assert res.status_code == 200
    assert res.get_json()["total_points"] == 28


def test_endpoint_dashboard_data_inclui_velocity(tmp_path, monkeypatch, sample_validations):
    """Garante que /api/dashboard/data agora carrega velocity junto."""
    server = _reload_server_with_validations(tmp_path, monkeypatch, sample_validations)
    res = server.app.test_client().get("/api/dashboard/data")
    assert res.status_code == 200
    body = res.get_json()
    assert "velocity" in body
    assert body["velocity"]["total_points"] == 28


def test_endpoint_velocity_sem_validations_retorna_unavailable(tmp_path, monkeypatch):
    """Cenário inicial: app subiu mas ninguém rodou validação ainda."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    for d in ("config", "results", "snapshots", "tmp"):
        (tmp_path / d).mkdir()
    monkeypatch.chdir(tmp_path)
    if "server" in sys.modules:
        del sys.modules["server"]
    if "dashboard_metrics" in sys.modules:
        del sys.modules["dashboard_metrics"]
    server = importlib.import_module("server")
    server.app.config["TESTING"] = True

    res = server.app.test_client().get("/api/dashboard/velocity")
    assert res.status_code == 200
    body = res.get_json()
    assert body["available"] is False
    assert body["total_points"] == 0


def test_endpoint_velocity_quebrado_nao_derruba_app(tmp_path, monkeypatch):
    """Se complexity_weights.json sumir (config volume nao montado), endpoint
    cai num fallback ao arquivo do repo."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    for d in ("config", "results", "snapshots", "tmp"):
        (tmp_path / d).mkdir()
    # config/complexity_weights.json NAO existe no tmp_path
    (tmp_path / "results" / "validations.json").write_text(
        json.dumps({"divergencias": ["[CAMPO AUSENTE] x"], "metadata": {}}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    if "server" in sys.modules:
        del sys.modules["server"]
    if "dashboard_metrics" in sys.modules:
        del sys.modules["dashboard_metrics"]
    server = importlib.import_module("server")
    server.app.config["TESTING"] = True

    res = server.app.test_client().get("/api/dashboard/velocity")
    assert res.status_code == 200
    body = res.get_json()
    # Fallback funcionou: leu weights do repo, computou
    assert body["available"] is True
    assert body["total_points"] == 3  # peso de [CAMPO AUSENTE]
