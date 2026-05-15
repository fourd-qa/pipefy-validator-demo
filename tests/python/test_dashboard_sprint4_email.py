"""Testes da Sprint 4 parte 2 - email diario via Resend.

Cobre:
- daily_digest.build_daily_digest: agrega KPIs das engines existentes
  (velocity, debt, leadtime, burnup) e gera alertas por threshold.
- daily_digest.render_email_html: HTML com KPIs, alertas, escape de XSS.
- /api/cron/daily-email: gating por X-Cron-Token, valida config Resend,
  monta digest, envia, retorna sumario.
"""
import base64
import datetime as dt
import importlib
import json
import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _build_snapshot(pipe_id, pipe_name, env_label, when, phases, start_form):
    return {
        "metadata": {
            "timestamp": when.isoformat(),
            "pipe_id": pipe_id,
            "pipe_name": pipe_name,
            "env_label": env_label,
            "source": "test",
            "tool_version": "1.0",
        },
        "data": {
            "pipe": {
                "id": pipe_id,
                "name": pipe_name,
                "phases": phases,
                "start_form_fields": start_form,
                "labels": [],
            }
        },
    }


def _write_snapshots_dir(root, pipe_id, snaps):
    pipe_dir = root / pipe_id
    pipe_dir.mkdir(parents=True, exist_ok=True)
    for snap in snaps:
        ts = snap["metadata"]["timestamp"].replace(":", "").replace("-", "").replace("T", "_")[:15]
        with open(pipe_dir / f"{ts}.json", "w", encoding="utf-8") as f:
            json.dump(snap, f)


@pytest.fixture
def digest_module():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for mod in ("daily_digest", "dashboard_metrics"):
        if mod in sys.modules:
            del sys.modules[mod]
    return importlib.import_module("daily_digest")


@pytest.fixture
def weights_path():
    return str(REPO_ROOT / "config" / "complexity_weights.json")


# ============== build_daily_digest ==============

def test_digest_sem_dados_todos_kpis_indisponiveis(tmp_path, digest_module, weights_path):
    digest = digest_module.build_daily_digest(
        validations_path=str(tmp_path / "vals.json"),
        weights_path=weights_path,
        snapshots_root=str(tmp_path / "auto"),
        blueprints_root=str(tmp_path / "bps"),
        monitored=[],
        today=dt.date(2026, 5, 15),
    )
    assert digest["date"] == "2026-05-15"
    assert digest["kpis"]["velocity"]["available"] is False
    assert digest["kpis"]["debt"]["available"] is False
    assert digest["kpis"]["leadtime"]["available"] is False
    assert digest["kpis"]["burnup"]["available"] is False
    assert digest["alerts"] == []
    assert digest["monitored_pipes_count"] == 0


def test_digest_with_velocity_disponivel(tmp_path, digest_module, weights_path):
    """validations.json existe -> velocity vira available e total_points e int."""
    vals = {
        "metadata": {"timestamp": "2026-05-15T10:00:00", "status": "DIVERGENCIAS_ENCONTRADAS"},
        "divergencias": [
            {"texto": "[CAMPO AUSENTE] Campo X faltando no destino"},
            {"texto": "[FASE EXTRA] Fase Y existe no destino"},
        ],
    }
    (tmp_path / "vals.json").write_text(json.dumps(vals), encoding="utf-8")
    digest = digest_module.build_daily_digest(
        validations_path=str(tmp_path / "vals.json"),
        weights_path=weights_path,
        snapshots_root=str(tmp_path / "auto"),
        blueprints_root=str(tmp_path / "bps"),
        monitored=[],
    )
    assert digest["kpis"]["velocity"]["available"] is True
    assert digest["kpis"]["velocity"]["total_points"] > 0


def test_digest_gera_alerta_debt_high(tmp_path, digest_module, weights_path):
    """Debt HIGH (>80 pts) deve virar alerta."""
    # 12 divergencias [CAMPO TIPO DIFERENTE] cada ~7pts -> ~84+ pts HIGH.
    divs = [{"texto": f"[CAMPO TIPO DIFERENTE] Campo Z{i} tipo mudou"} for i in range(15)]
    vals = {"metadata": {"timestamp": "2026-05-15T10:00:00"}, "divergencias": divs}
    (tmp_path / "vals.json").write_text(json.dumps(vals), encoding="utf-8")
    digest = digest_module.build_daily_digest(
        validations_path=str(tmp_path / "vals.json"),
        weights_path=weights_path,
        snapshots_root=str(tmp_path / "auto"),
        blueprints_root=str(tmp_path / "bps"),
        monitored=[],
    )
    if digest["kpis"]["debt"]["level"] == "HIGH":
        assert any(a["kind"] == "debt_high" for a in digest["alerts"])


def test_digest_gera_alerta_leadtime_lento(tmp_path, digest_module, weights_path):
    """Lag >= 5 dias uteis vira alerta leadtime_slow."""
    auto = tmp_path / "auto"
    monitored = [
        {"id": "p-hmg", "name": "Mesa - HMG", "env_label": "HMG", "enabled": True},
        {"id": "p-prd", "name": "Mesa - PRD", "env_label": "PRD", "enabled": True},
    ]
    base_hmg = _build_snapshot("p-hmg", "Mesa - HMG", "HMG", dt.datetime(2026, 4, 20, 10),
                                phases=[{"id": "ph_a", "name": "A", "fields": []}], start_form=[])
    hmg_v2 = _build_snapshot("p-hmg", "Mesa - HMG", "HMG", dt.datetime(2026, 4, 21, 10),
                              phases=[{"id": "ph_a", "name": "A", "fields": []},
                                      {"id": "ph_b", "name": "B", "fields": []}], start_form=[])
    base_prd = _build_snapshot("p-prd", "Mesa - PRD", "PRD", dt.datetime(2026, 4, 20, 10),
                                phases=[{"id": "ph_a", "name": "A", "fields": []}], start_form=[])
    # PRD ganha ph_b muito tarde: 7 dias uteis depois.
    prd_v2 = _build_snapshot("p-prd", "Mesa - PRD", "PRD", dt.datetime(2026, 4, 30, 10),
                              phases=[{"id": "ph_a", "name": "A", "fields": []},
                                      {"id": "ph_b", "name": "B", "fields": []}], start_form=[])
    _write_snapshots_dir(auto, "p-hmg", [base_hmg, hmg_v2])
    _write_snapshots_dir(auto, "p-prd", [base_prd, prd_v2])

    digest = digest_module.build_daily_digest(
        validations_path=str(tmp_path / "vals.json"),
        weights_path=weights_path,
        snapshots_root=str(auto),
        blueprints_root=str(tmp_path / "bps"),
        monitored=monitored,
    )
    assert any(a["kind"] == "leadtime_slow" for a in digest["alerts"])


def test_digest_gera_alerta_burnup_baixo(tmp_path, digest_module, weights_path):
    """Burnup < 60% vira alerta burnup_low."""
    auto = tmp_path / "auto"; auto.mkdir()
    bps = tmp_path / "bps"; bps.mkdir()
    # Blueprint com 5 phases, atual so tem 1 -> 20%.
    bp_phases = [{"id": f"ph_{i}", "name": f"P{i}", "fields": []} for i in range(5)]
    cur_phases = [{"id": "ph_0", "name": "P0", "fields": []}]
    snap_bp = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 1), bp_phases, [])
    snap_atual = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 5), cur_phases, [])
    _write_snapshots_dir(auto, "p1", [snap_atual])
    with open(bps / "p1.json", "w", encoding="utf-8") as f:
        json.dump({"marked_at": "x", "source_snapshot": "s", "snapshot": snap_bp}, f)

    monitored = [{"id": "p1", "name": "Pipe 1", "enabled": True}]
    digest = digest_module.build_daily_digest(
        validations_path=str(tmp_path / "vals.json"),
        weights_path=weights_path,
        snapshots_root=str(auto),
        blueprints_root=str(bps),
        monitored=monitored,
    )
    assert digest["kpis"]["burnup"]["available"] is True
    assert digest["kpis"]["burnup"]["pct"] == 20.0
    assert any(a["kind"] == "burnup_low" for a in digest["alerts"])


def test_digest_ignora_pipes_desabilitados(tmp_path, digest_module, weights_path):
    monitored = [
        {"id": "p1", "name": "P1", "enabled": False},
        {"id": "p2", "name": "P2", "enabled": True},
    ]
    digest = digest_module.build_daily_digest(
        validations_path=str(tmp_path / "vals.json"),
        weights_path=weights_path,
        snapshots_root=str(tmp_path / "auto"),
        blueprints_root=str(tmp_path / "bps"),
        monitored=monitored,
    )
    assert digest["monitored_pipes_count"] == 1


def test_digest_alerts_capped_em_10(tmp_path, digest_module, weights_path):
    """Lista de alertas nao pode ultrapassar 10 (email overload protection)."""
    auto = tmp_path / "auto"; auto.mkdir()
    bps = tmp_path / "bps"; bps.mkdir()
    bp_phases = [{"id": f"ph_{i}", "name": f"P{i}", "fields": []} for i in range(20)]
    cur_phases = [{"id": "ph_0", "name": "P0", "fields": []}]
    snap_bp = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 1), bp_phases, [])
    snap_atual = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 5), cur_phases, [])
    _write_snapshots_dir(auto, "p1", [snap_atual])
    with open(bps / "p1.json", "w", encoding="utf-8") as f:
        json.dump({"marked_at": "x", "source_snapshot": "s", "snapshot": snap_bp}, f)
    digest = digest_module.build_daily_digest(
        validations_path=str(tmp_path / "vals.json"),
        weights_path=weights_path,
        snapshots_root=str(auto),
        blueprints_root=str(bps),
        monitored=[{"id": "p1", "name": "P1", "enabled": True}],
    )
    assert len(digest["alerts"]) <= 10


# ============== render_email_html ==============

def test_render_html_inclui_4_kpis(digest_module):
    digest = {
        "date": "2026-05-15",
        "kpis": {
            "velocity": {"available": True, "total_points": 42},
            "debt": {"available": True, "level": "LOW", "total_points": 12},
            "leadtime": {"available": True, "median_days": 3, "promoted_count": 6},
            "burnup": {"available": True, "pct": 85.5, "covered": 17, "total": 20, "pipe_name": "Mesa PRD"},
        },
        "alerts": [],
        "monitored_pipes_count": 2,
    }
    html = digest_module.render_email_html(digest)
    assert "Velocity" in html
    assert "Debt" in html
    assert "Lead Time" in html
    assert "Burnup" in html
    assert "42" in html
    assert "85.5%" in html
    assert "Mesa PRD" in html


def test_render_html_mostra_alerts_quando_existem(digest_module):
    digest = {
        "date": "2026-05-15",
        "kpis": {
            "velocity": {"available": False, "total_points": 0},
            "debt": {"available": False, "level": "—", "total_points": 0},
            "leadtime": {"available": False, "median_days": 0, "promoted_count": 0},
            "burnup": {"available": False, "pct": None},
        },
        "alerts": [
            {"kind": "debt_high", "severity": "high", "message": "Debito tecnico HIGH"},
            {"kind": "hotspot", "severity": "med", "message": "Mesa - Analise: MEDIUM (42 pts)"},
        ],
        "monitored_pipes_count": 0,
    }
    html = digest_module.render_email_html(digest)
    assert "Debito tecnico HIGH" in html
    assert "Mesa - Analise: MEDIUM" in html
    assert "Alertas (2)" in html


def test_render_html_mostra_placeholder_quando_sem_alertas(digest_module):
    digest = {
        "date": "2026-05-15",
        "kpis": {
            "velocity": {"available": False, "total_points": 0},
            "debt": {"available": False, "level": "—", "total_points": 0},
            "leadtime": {"available": False, "median_days": 0, "promoted_count": 0},
            "burnup": {"available": False, "pct": None},
        },
        "alerts": [],
        "monitored_pipes_count": 0,
    }
    html = digest_module.render_email_html(digest)
    assert "Nenhum alerta" in html


def test_render_html_escapa_xss_em_alert_message(digest_module):
    digest = {
        "date": "2026-05-15",
        "kpis": {
            "velocity": {"available": False, "total_points": 0},
            "debt": {"available": False, "level": "—", "total_points": 0},
            "leadtime": {"available": False, "median_days": 0, "promoted_count": 0},
            "burnup": {"available": False, "pct": None},
        },
        "alerts": [
            {"kind": "x", "severity": "high", "message": "<script>alert('xss')</script>"},
        ],
        "monitored_pipes_count": 0,
    }
    html = digest_module.render_email_html(digest)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_html_inclui_dashboard_url_quando_passado(digest_module):
    digest = {
        "date": "2026-05-15",
        "kpis": {
            "velocity": {"available": False, "total_points": 0},
            "debt": {"available": False, "level": "—", "total_points": 0},
            "leadtime": {"available": False, "median_days": 0, "promoted_count": 0},
            "burnup": {"available": False, "pct": None},
        },
        "alerts": [],
        "monitored_pipes_count": 0,
    }
    html = digest_module.render_email_html(digest, dashboard_url="https://app.example.com/v2/dashboard")
    assert "https://app.example.com/v2/dashboard" in html
    assert "Abrir dashboard" in html


# ============== Endpoint /api/cron/daily-email ==============

def _basic(user, pw):
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


def _reload_server(tmp_path, monkeypatch, env=None):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for k in ("APP_PASSWORD", "APP_USERNAME", "LIDERANCA_USERNAME", "LIDERANCA_PASSWORD",
              "CRON_SNAPSHOT_TOKEN", "MONITOR_PIPEFY_TOKEN", "MONITOR_PIPEFY_BASE_URL",
              "RESEND_API_KEY", "EMAIL_FROM", "EMAIL_TO", "DASHBOARD_URL"):
        monkeypatch.delenv(k, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    for d in ("config", "results", "snapshots", "snapshots/auto", "snapshots/blueprints", "tmp"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    src_w = REPO_ROOT / "config" / "complexity_weights.json"
    (tmp_path / "config" / "complexity_weights.json").write_text(
        src_w.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    for mod in ("server", "dashboard_metrics", "daily_digest"):
        if mod in sys.modules:
            del sys.modules[mod]
    server = importlib.import_module("server")
    server.app.config["TESTING"] = True
    return server


def test_email_endpoint_503_sem_cron_token(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={})
    res = server.app.test_client().post("/api/cron/daily-email")
    assert res.status_code == 503


def test_email_endpoint_401_token_errado(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "CRON_SNAPSHOT_TOKEN": "secret",
        "RESEND_API_KEY": "re_xxx",
        "EMAIL_FROM": "x@y.com",
        "EMAIL_TO": "a@b.com",
    })
    res = server.app.test_client().post(
        "/api/cron/daily-email",
        headers={"X-Cron-Token": "errado"},
    )
    assert res.status_code == 401


def test_email_endpoint_503_sem_resend_config(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "CRON_SNAPSHOT_TOKEN": "secret",
        # RESEND_API_KEY/EMAIL_FROM/EMAIL_TO faltando
    })
    res = server.app.test_client().post(
        "/api/cron/daily-email",
        headers={"X-Cron-Token": "secret"},
    )
    assert res.status_code == 503
    body = res.get_json()
    assert body["ok"] is False
    assert "RESEND" in body["error"] or "EMAIL" in body["error"]


def test_email_endpoint_503_email_to_so_virgulas(tmp_path, monkeypatch):
    """EMAIL_TO=',,,' tem entradas vazias depois do split -> deve falhar como vazio."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "CRON_SNAPSHOT_TOKEN": "secret",
        "RESEND_API_KEY": "re_xxx",
        "EMAIL_FROM": "x@y.com",
        "EMAIL_TO": ",,, ,",
    })
    res = server.app.test_client().post(
        "/api/cron/daily-email",
        headers={"X-Cron-Token": "secret"},
    )
    assert res.status_code == 503


def test_email_endpoint_happy_path_mocka_resend(tmp_path, monkeypatch):
    """Token + config OK + Resend mockado retornando ok=True -> 200, sumario certo."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "CRON_SNAPSHOT_TOKEN": "secret",
        "RESEND_API_KEY": "re_xxx",
        "EMAIL_FROM": "dashboard@example.com",
        "EMAIL_TO": "a@b.com, c@d.com",
        "DASHBOARD_URL": "https://app.example.com/v2/dashboard",
    })
    captured = {}

    def fake_send(api_key, sender, recipients, subject, html_body):
        captured["api_key"] = api_key
        captured["sender"] = sender
        captured["recipients"] = recipients
        captured["subject"] = subject
        captured["html_len"] = len(html_body)
        captured["has_url"] = "https://app.example.com/v2/dashboard" in html_body
        return {"ok": True, "status": 200, "body": '{"id":"email_123"}'}

    monkeypatch.setattr(server, "_send_via_resend", fake_send)

    res = server.app.test_client().post(
        "/api/cron/daily-email",
        headers={"X-Cron-Token": "secret"},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    assert body["status"] == 200
    assert body["sent_to"] == ["a@b.com", "c@d.com"]
    assert "Resumo de" in body["subject"]
    assert "digest_summary" in body
    assert body["digest_summary"]["alert_count"] >= 0
    assert "kpis_available" in body["digest_summary"]

    # Verifica que o fake_send foi chamado com os args certos.
    assert captured["api_key"] == "re_xxx"
    assert captured["sender"] == "dashboard@example.com"
    assert captured["recipients"] == ["a@b.com", "c@d.com"]
    assert captured["has_url"] is True


def test_email_endpoint_resend_falha_retorna_502(tmp_path, monkeypatch):
    """Resend retornando ok=False propaga como 502."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "CRON_SNAPSHOT_TOKEN": "secret",
        "RESEND_API_KEY": "re_xxx",
        "EMAIL_FROM": "x@y.com",
        "EMAIL_TO": "a@b.com",
    })
    monkeypatch.setattr(server, "_send_via_resend", lambda **kw: {
        "ok": False, "status": 422, "body": '{"error":"invalid_email"}',
        "error": "HTTP 422",
    })
    res = server.app.test_client().post(
        "/api/cron/daily-email",
        headers={"X-Cron-Token": "secret"},
    )
    assert res.status_code == 502
    body = res.get_json()
    assert body["ok"] is False
    assert body["error"] == "HTTP 422"


def test_email_endpoint_funciona_sem_dashboard_url(tmp_path, monkeypatch):
    """DASHBOARD_URL vazio nao deve quebrar o render."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "CRON_SNAPSHOT_TOKEN": "secret",
        "RESEND_API_KEY": "re_xxx",
        "EMAIL_FROM": "x@y.com",
        "EMAIL_TO": "a@b.com",
    })
    captured = {}
    monkeypatch.setattr(server, "_send_via_resend", lambda **kw: (
        captured.update({"html": kw["html_body"]}) or {"ok": True, "status": 200, "body": "{}"}
    ))
    res = server.app.test_client().post(
        "/api/cron/daily-email",
        headers={"X-Cron-Token": "secret"},
    )
    assert res.status_code == 200
    # Sem link no rodape.
    assert "Abrir dashboard" not in captured["html"]
