"""Testes da Sprint 4 do Dashboard de Produtividade.

Cobre:
- dashboard_metrics.load_blueprint / save_blueprint / delete_blueprint: persistencia
  do snapshot-meta na pasta snapshots/blueprints/.
- dashboard_metrics.compute_burnup: compara snapshot atual contra blueprint marcado,
  calcula cobertura por categoria (phases, phase_fields, start_form_fields).
- /api/dashboard/blueprint (GET/POST/DELETE): gated por lideranca, valida payload,
  rejeita path traversal no filename.
- /api/dashboard/burnup: gated, defaulta pra primeiro pipe enabled, retorna shape
  esperado pela UI.
- /api/dashboard/data: agrega burnup junto de velocity/debt/hotspots/leadtime.
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
    paths = []
    for snap in snaps:
        ts = snap["metadata"]["timestamp"].replace(":", "").replace("-", "").replace("T", "_")[:15]
        path = pipe_dir / f"{ts}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snap, f)
        paths.append(path)
    return paths


@pytest.fixture
def metrics_module():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if "dashboard_metrics" in sys.modules:
        del sys.modules["dashboard_metrics"]
    return importlib.import_module("dashboard_metrics")


# ============== load/save/delete_blueprint — persistencia ==============

def test_load_blueprint_inexistente_retorna_none(tmp_path, metrics_module):
    assert metrics_module.load_blueprint(str(tmp_path), "qualquer-pipe") is None


def test_load_blueprint_arquivo_corrompido_retorna_none(tmp_path, metrics_module):
    (tmp_path / "p1.json").write_text("nao-eh-json", encoding="utf-8")
    assert metrics_module.load_blueprint(str(tmp_path), "p1") is None


def test_save_blueprint_cria_arquivo_e_carrega_de_volta(tmp_path, metrics_module):
    snap = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 1, 10),
                           phases=[{"id": "ph_a", "name": "A", "fields": []}], start_form=[])
    path = metrics_module.save_blueprint(str(tmp_path), "p1", snap, "snap.json")
    assert os.path.isfile(path)
    loaded = metrics_module.load_blueprint(str(tmp_path), "p1")
    assert loaded is not None
    assert loaded["source_snapshot"] == "snap.json"
    assert loaded["snapshot"]["metadata"]["pipe_id"] == "p1"
    assert loaded["marked_at"]


def test_save_blueprint_aceita_marked_at_explicito(tmp_path, metrics_module):
    snap = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 1, 10), [], [])
    metrics_module.save_blueprint(str(tmp_path), "p1", snap, "x.json", marked_at="2026-05-05T15:00:00")
    loaded = metrics_module.load_blueprint(str(tmp_path), "p1")
    assert loaded["marked_at"] == "2026-05-05T15:00:00"


def test_delete_blueprint_remove_arquivo(tmp_path, metrics_module):
    snap = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 1), [], [])
    metrics_module.save_blueprint(str(tmp_path), "p1", snap, "s.json")
    assert metrics_module.delete_blueprint(str(tmp_path), "p1") is True
    assert metrics_module.load_blueprint(str(tmp_path), "p1") is None


def test_delete_blueprint_quando_inexistente_retorna_false(tmp_path, metrics_module):
    assert metrics_module.delete_blueprint(str(tmp_path), "nope") is False


def test_save_blueprint_sanitiza_pipe_id_no_filename(tmp_path, metrics_module):
    """Pipe id com caracteres especiais nao deve quebrar o filesystem."""
    snap = _build_snapshot("p/1", "P1", "PRD", dt.datetime(2026, 5, 1), [], [])
    path = metrics_module.save_blueprint(str(tmp_path), "p/1", snap, "s.json")
    assert os.path.isfile(path)
    assert "/" not in os.path.basename(path)


# ============== compute_burnup ==============

def test_burnup_sem_blueprint_retorna_indisponivel(tmp_path, metrics_module):
    auto = tmp_path / "auto"; auto.mkdir()
    bps = tmp_path / "bps"; bps.mkdir()
    res = metrics_module.compute_burnup(str(auto), str(bps), "p1")
    assert res["available"] is False
    assert "Sem blueprint" in res["reason"]
    assert res["pipe_id"] == "p1"


def test_burnup_sem_snapshots_retorna_indisponivel(tmp_path, metrics_module):
    auto = tmp_path / "auto"; auto.mkdir()
    bps = tmp_path / "bps"; bps.mkdir()
    snap = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 1), [], [])
    metrics_module.save_blueprint(str(bps), "p1", snap, "s.json")
    res = metrics_module.compute_burnup(str(auto), str(bps), "p1")
    assert res["available"] is False
    assert "snapshot" in res["reason"].lower()


def test_burnup_cobertura_total_quando_atual_igual_blueprint(tmp_path, metrics_module):
    auto = tmp_path / "auto"; auto.mkdir()
    bps = tmp_path / "bps"; bps.mkdir()
    phases = [{"id": "ph_a", "name": "A", "fields": [
        {"id": "f1", "label": "F1", "type": "short_text", "required": False},
    ]}]
    sf = [{"id": "nome", "label": "Nome", "type": "short_text", "required": True}]
    snap_bp = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 1), phases, sf)
    snap_atual = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 5), phases, sf)
    _write_snapshots_dir(auto, "p1", [snap_atual])
    metrics_module.save_blueprint(str(bps), "p1", snap_bp, "s.json")

    res = metrics_module.compute_burnup(str(auto), str(bps), "p1")
    assert res["available"] is True
    assert res["overall_pct"] == 100.0
    assert res["overall_covered"] == res["overall_total"]
    assert res["by_category"]["phases"]["pct"] == 100.0
    assert res["by_category"]["phase_fields"]["pct"] == 100.0
    assert res["by_category"]["start_form_fields"]["pct"] == 100.0


def test_burnup_gap_phase_faltando(tmp_path, metrics_module):
    auto = tmp_path / "auto"; auto.mkdir()
    bps = tmp_path / "bps"; bps.mkdir()
    # Blueprint tem 2 phases, atual so tem 1 -> 50% nas phases.
    bp_phases = [
        {"id": "ph_a", "name": "A", "fields": []},
        {"id": "ph_doc", "name": "Documentacao Final", "fields": []},
    ]
    cur_phases = [{"id": "ph_a", "name": "A", "fields": []}]
    snap_bp = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 1), bp_phases, [])
    snap_atual = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 5), cur_phases, [])
    _write_snapshots_dir(auto, "p1", [snap_atual])
    metrics_module.save_blueprint(str(bps), "p1", snap_bp, "s.json")

    res = metrics_module.compute_burnup(str(auto), str(bps), "p1")
    assert res["available"] is True
    assert res["by_category"]["phases"]["pct"] == 50.0
    assert res["by_category"]["phases"]["covered"] == 1
    assert res["by_category"]["phases"]["total"] == 2
    missing = res["by_category"]["phases"]["missing"]
    assert len(missing) == 1
    assert missing[0]["id"] == "ph_doc"
    assert missing[0]["label"] == "Documentacao Final"


def test_burnup_phase_fields_missing_usa_label_composta(tmp_path, metrics_module):
    auto = tmp_path / "auto"; auto.mkdir()
    bps = tmp_path / "bps"; bps.mkdir()
    bp_phases = [{"id": "ph_a", "name": "Analise", "fields": [
        {"id": "f1", "label": "Campo Antigo", "type": "short_text", "required": False},
        {"id": "f2", "label": "Decisao do motor", "type": "dropdown", "required": False},
    ]}]
    cur_phases = [{"id": "ph_a", "name": "Analise", "fields": [
        {"id": "f1", "label": "Campo Antigo", "type": "short_text", "required": False},
    ]}]
    snap_bp = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 1), bp_phases, [])
    snap_atual = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 5), cur_phases, [])
    _write_snapshots_dir(auto, "p1", [snap_atual])
    metrics_module.save_blueprint(str(bps), "p1", snap_bp, "s.json")

    res = metrics_module.compute_burnup(str(auto), str(bps), "p1")
    pf = res["by_category"]["phase_fields"]
    assert pf["pct"] == 50.0
    assert len(pf["missing"]) == 1
    assert pf["missing"][0]["id"] == "ph_a.f2"
    # Label combina nome da phase + nome do field.
    assert "Analise" in pf["missing"][0]["label"]
    assert "Decisao do motor" in pf["missing"][0]["label"]


def test_burnup_start_form_missing(tmp_path, metrics_module):
    auto = tmp_path / "auto"; auto.mkdir()
    bps = tmp_path / "bps"; bps.mkdir()
    bp_sf = [
        {"id": "nome", "label": "Nome", "type": "short_text", "required": True},
        {"id": "renda_familiar", "label": "Renda familiar declarada", "type": "currency", "required": False},
    ]
    cur_sf = [{"id": "nome", "label": "Nome", "type": "short_text", "required": True}]
    snap_bp = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 1), [], bp_sf)
    snap_atual = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 5), [], cur_sf)
    _write_snapshots_dir(auto, "p1", [snap_atual])
    metrics_module.save_blueprint(str(bps), "p1", snap_bp, "s.json")

    res = metrics_module.compute_burnup(str(auto), str(bps), "p1")
    sf = res["by_category"]["start_form_fields"]
    assert sf["pct"] == 50.0
    assert len(sf["missing"]) == 1
    assert sf["missing"][0]["id"] == "renda_familiar"
    assert sf["missing"][0]["label"] == "Renda familiar declarada"


def test_burnup_features_extras_no_atual_nao_penalizam(tmp_path, metrics_module):
    """Itens no snapshot atual que NAO estao no blueprint nao baixam o score."""
    auto = tmp_path / "auto"; auto.mkdir()
    bps = tmp_path / "bps"; bps.mkdir()
    bp_phases = [{"id": "ph_a", "name": "A", "fields": []}]
    cur_phases = [
        {"id": "ph_a", "name": "A", "fields": []},
        {"id": "ph_extra", "name": "Extra fora do escopo", "fields": []},
    ]
    snap_bp = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 1), bp_phases, [])
    snap_atual = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 5), cur_phases, [])
    _write_snapshots_dir(auto, "p1", [snap_atual])
    metrics_module.save_blueprint(str(bps), "p1", snap_bp, "s.json")

    res = metrics_module.compute_burnup(str(auto), str(bps), "p1")
    assert res["by_category"]["phases"]["pct"] == 100.0


def test_burnup_usa_snapshot_mais_recente(tmp_path, metrics_module):
    """Quando ha varios snapshots, usa o ultimo (sorted ascendente, [-1])."""
    auto = tmp_path / "auto"; auto.mkdir()
    bps = tmp_path / "bps"; bps.mkdir()
    bp_phases = [
        {"id": "ph_a", "name": "A", "fields": []},
        {"id": "ph_b", "name": "B", "fields": []},
    ]
    cur_old = [{"id": "ph_a", "name": "A", "fields": []}]  # antigo: gap
    cur_new = bp_phases  # mais recente: completo
    s_old = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 1), cur_old, [])
    s_new = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 5), cur_new, [])
    snap_bp = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 1), bp_phases, [])
    _write_snapshots_dir(auto, "p1", [s_old, s_new])
    metrics_module.save_blueprint(str(bps), "p1", snap_bp, "s.json")

    res = metrics_module.compute_burnup(str(auto), str(bps), "p1")
    assert res["overall_pct"] == 100.0


def test_burnup_blueprint_vazio_overall_100(tmp_path, metrics_module):
    """Edge: blueprint sem nada vira 100% (nao divide por zero)."""
    auto = tmp_path / "auto"; auto.mkdir()
    bps = tmp_path / "bps"; bps.mkdir()
    snap_bp = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 1), [], [])
    snap_atual = _build_snapshot("p1", "P1", "PRD", dt.datetime(2026, 5, 5), [], [])
    _write_snapshots_dir(auto, "p1", [snap_atual])
    metrics_module.save_blueprint(str(bps), "p1", snap_bp, "s.json")
    res = metrics_module.compute_burnup(str(auto), str(bps), "p1")
    assert res["overall_pct"] == 100.0
    assert res["overall_total"] == 0


# ============== Endpoints ==============

def _reload_server(tmp_path, monkeypatch, env=None):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for k in ("APP_PASSWORD", "APP_USERNAME", "LIDERANCA_USERNAME", "LIDERANCA_PASSWORD",
              "CRON_SNAPSHOT_TOKEN", "MONITOR_PIPEFY_TOKEN", "MONITOR_PIPEFY_BASE_URL"):
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
    if "server" in sys.modules:
        del sys.modules["server"]
    if "dashboard_metrics" in sys.modules:
        del sys.modules["dashboard_metrics"]
    server = importlib.import_module("server")
    server.app.config["TESTING"] = True
    return server


def _setup_pipe_com_blueprint(tmp_path, pipe_id="p1"):
    """Cria 1 snapshot atual + 1 blueprint com gap conhecido."""
    auto = tmp_path / "snapshots" / "auto"
    bps = tmp_path / "snapshots" / "blueprints"
    bp_phases = [
        {"id": "ph_a", "name": "A", "fields": []},
        {"id": "ph_b", "name": "B", "fields": []},
    ]
    cur_phases = [{"id": "ph_a", "name": "A", "fields": []}]
    snap_bp = _build_snapshot(pipe_id, "P1", "PRD", dt.datetime(2026, 5, 1), bp_phases, [])
    snap_atual = _build_snapshot(pipe_id, "P1", "PRD", dt.datetime(2026, 5, 5), cur_phases, [])
    _write_snapshots_dir(auto, pipe_id, [snap_atual])

    bps.mkdir(parents=True, exist_ok=True)
    with open(bps / f"{pipe_id}.json", "w", encoding="utf-8") as f:
        json.dump({
            "marked_at": "2026-05-05T15:00:00",
            "source_snapshot": "bp.json",
            "snapshot": snap_bp,
        }, f)

    (tmp_path / "config" / "monitored_pipes.json").write_text(json.dumps({
        "version": "1.0",
        "pipes": [{"id": pipe_id, "name": "P1", "env_label": "PRD", "enabled": True}],
    }), encoding="utf-8")


def test_burnup_endpoint_gated_demo_recebe_403(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    res = server.app.test_client().get(
        "/api/dashboard/burnup",
        headers={"Authorization": _basic("demo", "demosecret")},
    )
    assert res.status_code == 403


def test_burnup_endpoint_sem_pipes_monitorados(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/api/dashboard/burnup",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["available"] is False
    assert body["pipe_id"] == ""


def test_burnup_endpoint_default_usa_primeiro_pipe(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    _setup_pipe_com_blueprint(tmp_path)
    res = server.app.test_client().get(
        "/api/dashboard/burnup",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["available"] is True
    assert body["pipe_id"] == "p1"
    assert body["overall_pct"] == 50.0


def test_burnup_endpoint_param_pipe_id(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    _setup_pipe_com_blueprint(tmp_path, pipe_id="custom")
    res = server.app.test_client().get(
        "/api/dashboard/burnup?pipe_id=custom",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    assert res.get_json()["pipe_id"] == "custom"


def test_burnup_endpoint_pipe_sem_blueprint(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    (tmp_path / "config" / "monitored_pipes.json").write_text(json.dumps({
        "version": "1.0",
        "pipes": [{"id": "naomarcado", "name": "X", "env_label": "PRD", "enabled": True}],
    }), encoding="utf-8")
    res = server.app.test_client().get(
        "/api/dashboard/burnup",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["available"] is False
    assert "Sem blueprint" in body["reason"]


def test_get_blueprint_400_sem_pipe_id(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/api/dashboard/blueprint",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 400


def test_get_blueprint_marked_false_quando_inexistente(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/api/dashboard/blueprint?pipe_id=novato",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["marked"] is False
    assert body["pipe_id"] == "novato"


def test_get_blueprint_retorna_metadata_quando_marcado(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    _setup_pipe_com_blueprint(tmp_path)
    res = server.app.test_client().get(
        "/api/dashboard/blueprint?pipe_id=p1",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["marked"] is True
    assert body["source_snapshot"] == "bp.json"
    assert body["marked_at"] == "2026-05-05T15:00:00"


def test_post_blueprint_400_sem_campos_obrigatorios(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().post(
        "/api/dashboard/blueprint",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"pipe_id": "p1"}),
    )
    assert res.status_code == 400


def test_post_blueprint_404_snapshot_inexistente(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().post(
        "/api/dashboard/blueprint",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"pipe_id": "p1", "snapshot_filename": "nao_existe.json"}),
    )
    assert res.status_code == 404


def test_post_blueprint_rejeita_path_traversal(tmp_path, monkeypatch):
    """snapshot_filename com '../' deve ser rejeitado antes de tentar abrir arquivo."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().post(
        "/api/dashboard/blueprint",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"pipe_id": "p1", "snapshot_filename": "../../etc/passwd"}),
    )
    assert res.status_code == 400


def test_post_blueprint_marca_e_get_reflete(tmp_path, monkeypatch):
    """Fluxo end-to-end: POST marca snapshot, GET reflete metadata."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    # Cria snapshot real em auto/
    auto = tmp_path / "snapshots" / "auto"
    snap = _build_snapshot("pX", "PX", "PRD", dt.datetime(2026, 5, 1),
                           phases=[{"id": "ph_a", "name": "A", "fields": []}], start_form=[])
    paths = _write_snapshots_dir(auto, "pX", [snap])
    filename = paths[0].name

    client = server.app.test_client()
    res = client.post(
        "/api/dashboard/blueprint",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"pipe_id": "pX", "snapshot_filename": filename}),
    )
    assert res.status_code == 200
    assert res.get_json()["ok"] is True

    # GET reflete.
    res2 = client.get(
        "/api/dashboard/blueprint?pipe_id=pX",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    body = res2.get_json()
    assert body["marked"] is True
    assert body["source_snapshot"] == filename


def test_delete_blueprint_400_sem_pipe_id(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().delete(
        "/api/dashboard/blueprint",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 400


def test_delete_blueprint_removed_true(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    _setup_pipe_com_blueprint(tmp_path)
    res = server.app.test_client().delete(
        "/api/dashboard/blueprint?pipe_id=p1",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    assert body["removed"] is True


def test_delete_blueprint_removed_false_quando_inexistente(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().delete(
        "/api/dashboard/blueprint?pipe_id=fantasma",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    body = res.get_json()
    assert body["removed"] is False


def test_blueprint_endpoints_gated_demo(tmp_path, monkeypatch):
    """GET/POST/DELETE /api/dashboard/blueprint todos negam demo."""
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    client = server.app.test_client()
    h = {"Authorization": _basic("demo", "demosecret")}
    assert client.get("/api/dashboard/blueprint?pipe_id=x", headers=h).status_code == 403
    assert client.post("/api/dashboard/blueprint", headers={**h, "Content-Type": "application/json"},
                       data=json.dumps({"pipe_id": "x", "snapshot_filename": "s.json"})).status_code == 403
    assert client.delete("/api/dashboard/blueprint?pipe_id=x", headers=h).status_code == 403


def test_dashboard_data_inclui_burnup(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    _setup_pipe_com_blueprint(tmp_path)
    res = server.app.test_client().get(
        "/api/dashboard/data",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert "burnup" in body
    assert body["burnup"]["available"] is True
    assert body["burnup"]["pipe_id"] == "p1"
    assert body["burnup"]["overall_pct"] == 50.0


def test_dashboard_data_burnup_sem_pipes_monitorados(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/api/dashboard/data",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    body = res.get_json()
    assert body["burnup"]["available"] is False
