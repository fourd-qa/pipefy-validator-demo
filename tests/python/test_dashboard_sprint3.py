"""Testes da Sprint 3 do Dashboard de Produtividade.

Cobre:
- dashboard_metrics.compute_hotspots: detecta phase_create/delete/rename, field
  changes em phases e start_form, calcula score e level.
- dashboard_metrics.compute_leadtime: pareia HMG/PRD por nome base, filtra
  baseline, retorna lag em dias uteis e pendentes.
- /api/dashboard/hotspots: gated por lideranca, defaulta pra primeiro pipe
  enabled, retorna 200 com payload.
- /api/dashboard/leadtime: gated, retorna pares com promovidos.
- /api/dashboard/data: agrega hot spots + lead time junto de velocity/debt.
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


def _basic(user, pw):
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


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


# ============== compute_hotspots — engine puro ==============

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


def test_hotspots_sem_snapshots_retorna_indisponivel(tmp_path, metrics_module, weights_path):
    res = metrics_module.compute_hotspots(str(tmp_path), "missing-pipe", weights_path)
    assert res["available"] is False
    assert res["snapshot_count"] == 0


def test_hotspots_com_um_snapshot_retorna_indisponivel(tmp_path, metrics_module, weights_path):
    snap = _build_snapshot(
        "p1", "P1", "HMG", dt.datetime(2026, 4, 21, 10),
        phases=[{"id": "ph_a", "name": "A", "fields": []}],
        start_form=[],
    )
    _write_snapshots_dir(tmp_path, "p1", [snap])
    res = metrics_module.compute_hotspots(str(tmp_path), "p1", weights_path)
    assert res["available"] is False
    assert res["snapshot_count"] == 1


def test_hotspots_detecta_phase_rename(tmp_path, metrics_module, weights_path):
    s1 = _build_snapshot("p1", "P1", "HMG", dt.datetime(2026, 4, 21, 10),
                         phases=[{"id": "ph_a", "name": "Antiga", "fields": []}], start_form=[])
    s2 = _build_snapshot("p1", "P1", "HMG", dt.datetime(2026, 4, 22, 10),
                         phases=[{"id": "ph_a", "name": "Nova", "fields": []}], start_form=[])
    _write_snapshots_dir(tmp_path, "p1", [s1, s2])
    res = metrics_module.compute_hotspots(str(tmp_path), "p1", weights_path)
    assert res["available"] is True
    assert res["total_changes"] == 1
    assert res["phases"][0]["phase_id"] == "ph_a"
    assert res["phases"][0]["change_count"] == 1
    assert res["phases"][0]["phase_name"] == "Nova"


def test_hotspots_detecta_phase_create(tmp_path, metrics_module, weights_path):
    s1 = _build_snapshot("p1", "P1", "HMG", dt.datetime(2026, 4, 21, 10),
                         phases=[{"id": "ph_a", "name": "A", "fields": []}], start_form=[])
    s2 = _build_snapshot("p1", "P1", "HMG", dt.datetime(2026, 4, 22, 10),
                         phases=[{"id": "ph_a", "name": "A", "fields": []},
                                 {"id": "ph_b", "name": "B", "fields": []}],
                         start_form=[])
    _write_snapshots_dir(tmp_path, "p1", [s1, s2])
    res = metrics_module.compute_hotspots(str(tmp_path), "p1", weights_path)
    assert res["total_changes"] == 1
    by_phase = {p["phase_id"]: p for p in res["phases"]}
    assert by_phase["ph_b"]["change_count"] == 1
    assert by_phase["ph_b"]["score"] >= 6  # peso de [FASE EXTRA]


def test_hotspots_detecta_field_create_em_phase(tmp_path, metrics_module, weights_path):
    s1 = _build_snapshot("p1", "P1", "HMG", dt.datetime(2026, 4, 21, 10),
                         phases=[{"id": "ph_a", "name": "A", "fields": []}], start_form=[])
    s2 = _build_snapshot("p1", "P1", "HMG", dt.datetime(2026, 4, 22, 10),
                         phases=[{"id": "ph_a", "name": "A", "fields": [
                             {"id": "f1", "label": "F1", "type": "short_text", "required": False},
                         ]}], start_form=[])
    _write_snapshots_dir(tmp_path, "p1", [s1, s2])
    res = metrics_module.compute_hotspots(str(tmp_path), "p1", weights_path)
    assert res["total_changes"] == 1
    assert res["phases"][0]["phase_id"] == "ph_a"


def test_hotspots_detecta_startform_change(tmp_path, metrics_module, weights_path):
    s1 = _build_snapshot("p1", "P1", "HMG", dt.datetime(2026, 4, 21, 10),
                         phases=[], start_form=[])
    s2 = _build_snapshot("p1", "P1", "HMG", dt.datetime(2026, 4, 22, 10),
                         phases=[],
                         start_form=[{"id": "nome", "label": "Nome", "type": "short_text", "required": True}])
    _write_snapshots_dir(tmp_path, "p1", [s1, s2])
    res = metrics_module.compute_hotspots(str(tmp_path), "p1", weights_path)
    assert res["total_changes"] == 1
    by_phase = {p["phase_id"]: p for p in res["phases"]}
    assert "_startform_" in by_phase
    assert by_phase["_startform_"]["change_count"] == 1


def test_hotspots_classifica_level_high(tmp_path, metrics_module, weights_path):
    """Phase com 4 mudancas tipo connection_field/phase_create acumula pontos."""
    base_phase = {"id": "ph_a", "name": "A", "fields": []}
    s1 = _build_snapshot("p1", "P1", "HMG", dt.datetime(2026, 4, 21), phases=[base_phase], start_form=[])
    # 6 fields adicionados em snapshots consecutivos.
    snaps = [s1]
    for i in range(6):
        snaps.append(_build_snapshot("p1", "P1", "HMG", dt.datetime(2026, 4, 22 + i),
                                     phases=[{"id": "ph_a", "name": "A", "fields": [
                                         {"id": f"f{j}", "label": f"F{j}", "type": "short_text", "required": False}
                                         for j in range(i + 1)
                                     ]}], start_form=[]))
    _write_snapshots_dir(tmp_path, "p1", snaps)
    res = metrics_module.compute_hotspots(str(tmp_path), "p1", weights_path)
    by_phase = {p["phase_id"]: p for p in res["phases"]}
    assert by_phase["ph_a"]["change_count"] == 6
    assert by_phase["ph_a"]["level"] in ("MEDIUM", "HIGH")


# ============== compute_leadtime ==============

def test_leadtime_sem_pares_retorna_indisponivel(tmp_path, metrics_module):
    res = metrics_module.compute_leadtime(str(tmp_path), [])
    assert res["available"] is False


def test_leadtime_com_par_HMG_PRD_calcula_lag(tmp_path, metrics_module):
    """HMG ganha phase ph_b no dia 22, PRD ganha no dia 25 -> lag 3 dias uteis."""
    monitored = [
        {"id": "p-hmg", "name": "Mesa - HMG", "env_label": "HMG", "enabled": True},
        {"id": "p-prd", "name": "Mesa - PRD", "env_label": "PRD", "enabled": True},
    ]
    # Baseline em ambos no dia 21.
    base_hmg_t0 = _build_snapshot("p-hmg", "Mesa - HMG", "HMG", dt.datetime(2026, 4, 21, 14),
                                  phases=[{"id": "ph_a", "name": "A", "fields": []}], start_form=[])
    base_prd_t0 = _build_snapshot("p-prd", "Mesa - PRD", "PRD", dt.datetime(2026, 4, 21, 14),
                                  phases=[{"id": "ph_a", "name": "A", "fields": []}], start_form=[])
    # HMG ganha ph_b no dia 22 (qua).
    hmg_v2 = _build_snapshot("p-hmg", "Mesa - HMG", "HMG", dt.datetime(2026, 4, 22, 14),
                             phases=[{"id": "ph_a", "name": "A", "fields": []},
                                     {"id": "ph_b", "name": "B", "fields": []}], start_form=[])
    # PRD continua igual no dia 22, 23, 24.
    prd_22 = _build_snapshot("p-prd", "Mesa - PRD", "PRD", dt.datetime(2026, 4, 22, 14),
                             phases=[{"id": "ph_a", "name": "A", "fields": []}], start_form=[])
    # PRD ganha ph_b no dia 27 (seg, +3 dias uteis pulando fim de semana).
    prd_v2 = _build_snapshot("p-prd", "Mesa - PRD", "PRD", dt.datetime(2026, 4, 27, 14),
                             phases=[{"id": "ph_a", "name": "A", "fields": []},
                                     {"id": "ph_b", "name": "B", "fields": []}], start_form=[])

    _write_snapshots_dir(tmp_path, "p-hmg", [base_hmg_t0, hmg_v2])
    _write_snapshots_dir(tmp_path, "p-prd", [base_prd_t0, prd_22, prd_v2])

    res = metrics_module.compute_leadtime(str(tmp_path), monitored)
    assert res["available"] is True
    assert len(res["pairs"]) == 1
    pair = res["pairs"][0]
    assert pair["promoted_count"] == 1
    assert pair["pending_count"] == 0
    promoted = pair["promoted"][0]
    assert promoted["id"] == "ph_b"
    assert promoted["lag_days"] == 3.0


def test_leadtime_marca_pendente_quando_nao_chegou_em_prd(tmp_path, metrics_module):
    monitored = [
        {"id": "p-hmg", "name": "Mesa - HMG", "env_label": "HMG", "enabled": True},
        {"id": "p-prd", "name": "Mesa - PRD", "env_label": "PRD", "enabled": True},
    ]
    base_hmg = _build_snapshot("p-hmg", "Mesa - HMG", "HMG", dt.datetime(2026, 4, 21, 14),
                               phases=[{"id": "ph_a", "name": "A", "fields": []}], start_form=[])
    base_prd = _build_snapshot("p-prd", "Mesa - PRD", "PRD", dt.datetime(2026, 4, 21, 14),
                               phases=[{"id": "ph_a", "name": "A", "fields": []}], start_form=[])
    hmg_new = _build_snapshot("p-hmg", "Mesa - HMG", "HMG", dt.datetime(2026, 4, 22, 14),
                              phases=[{"id": "ph_a", "name": "A", "fields": []},
                                      {"id": "ph_novo", "name": "Novo", "fields": []}], start_form=[])

    _write_snapshots_dir(tmp_path, "p-hmg", [base_hmg, hmg_new])
    _write_snapshots_dir(tmp_path, "p-prd", [base_prd])

    res = metrics_module.compute_leadtime(str(tmp_path), monitored)
    pair = res["pairs"][0]
    assert pair["promoted_count"] == 0
    assert pair["pending_count"] == 1
    assert pair["pending"][0]["id"] == "ph_novo"


def test_leadtime_pareia_pelo_nome_base_ignorando_sufixo(tmp_path, metrics_module):
    """Pipe nomes 'X — HMG' e 'X — PRD' devem virar par."""
    monitored = [
        {"id": "h", "name": "Crédito PF — HMG", "env_label": "HMG", "enabled": True},
        {"id": "p", "name": "Crédito PF — PRD", "env_label": "PRD", "enabled": True},
    ]
    s = _build_snapshot("h", "Crédito PF — HMG", "HMG", dt.datetime(2026, 4, 21, 14),
                        phases=[], start_form=[])
    s2 = _build_snapshot("p", "Crédito PF — PRD", "PRD", dt.datetime(2026, 4, 21, 14),
                         phases=[], start_form=[])
    _write_snapshots_dir(tmp_path, "h", [s])
    _write_snapshots_dir(tmp_path, "p", [s2])
    res = metrics_module.compute_leadtime(str(tmp_path), monitored)
    assert res["available"] is True
    assert len(res["pairs"]) == 1


# ============== Endpoints ==============

def _reload_server(tmp_path, monkeypatch, env=None):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for k in ("APP_PASSWORD", "APP_USERNAME", "LIDERANCA_USERNAME", "LIDERANCA_PASSWORD",
              "CRON_SNAPSHOT_TOKEN", "MONITOR_PIPEFY_TOKEN", "MONITOR_PIPEFY_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    for d in ("config", "results", "snapshots", "snapshots/auto", "tmp"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    # Copia complexity_weights pra tmp.
    src_w = REPO_ROOT / "config" / "complexity_weights.json"
    (tmp_path / "config" / "complexity_weights.json").write_text(
        src_w.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.app.config["TESTING"] = True
    return server


def _setup_seed(tmp_path):
    """Popula tmp_path/snapshots/auto com 2 snapshots HMG+PRD pra rota nao
    retornar 'sem dados'."""
    auto = tmp_path / "snapshots" / "auto"
    s1 = _build_snapshot("ph", "Pipe HMG", "HMG", dt.datetime(2026, 4, 21, 14),
                         phases=[{"id": "ph_a", "name": "A", "fields": []}], start_form=[])
    s2 = _build_snapshot("ph", "Pipe HMG", "HMG", dt.datetime(2026, 4, 22, 14),
                         phases=[{"id": "ph_a", "name": "A2", "fields": []}], start_form=[])
    _write_snapshots_dir(auto, "ph", [s1, s2])
    p1 = _build_snapshot("pp", "Pipe PRD", "PRD", dt.datetime(2026, 4, 21, 14),
                         phases=[{"id": "ph_a", "name": "A", "fields": []}], start_form=[])
    _write_snapshots_dir(auto, "pp", [p1])

    # Configura monitored_pipes com par.
    (tmp_path / "config" / "monitored_pipes.json").write_text(json.dumps({
        "version": "1.0",
        "pipes": [
            {"id": "ph", "name": "Pipe — HMG", "env_label": "HMG", "enabled": True},
            {"id": "pp", "name": "Pipe — PRD", "env_label": "PRD", "enabled": True},
        ],
    }), encoding="utf-8")


def test_hotspots_endpoint_gated_demo_recebe_403(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    res = server.app.test_client().get(
        "/api/dashboard/hotspots",
        headers={"Authorization": _basic("demo", "demosecret")},
    )
    assert res.status_code == 403


def test_hotspots_endpoint_lideranca_retorna_payload(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    _setup_seed(tmp_path)
    res = server.app.test_client().get(
        "/api/dashboard/hotspots",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["available"] is True
    assert body["pipe_id"] == "ph"
    assert body["snapshot_count"] == 2


def test_hotspots_endpoint_param_pipe_id(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    _setup_seed(tmp_path)
    res = server.app.test_client().get(
        "/api/dashboard/hotspots?pipe_id=pp",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["pipe_id"] == "pp"


def test_hotspots_endpoint_sem_pipes_monitorados(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/api/dashboard/hotspots",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["available"] is False


def test_leadtime_endpoint_gated(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    res = server.app.test_client().get(
        "/api/dashboard/leadtime",
        headers={"Authorization": _basic("demo", "demosecret")},
    )
    assert res.status_code == 403


def test_leadtime_endpoint_retorna_pares(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    _setup_seed(tmp_path)
    res = server.app.test_client().get(
        "/api/dashboard/leadtime",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["available"] is True
    assert len(body["pairs"]) == 1


def test_dashboard_data_inclui_hotspots_e_leadtime(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    _setup_seed(tmp_path)
    res = server.app.test_client().get(
        "/api/dashboard/data",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert "hotspots" in body
    assert "leadtime" in body
    assert body["hotspots"]["available"] is True
    assert body["leadtime"]["available"] is True
