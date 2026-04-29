"""Smoke tests dos endpoints HTTP do server.py via Flask test client.

Mocka subprocess.Popen pra não chamar o Robot de verdade nos testes do /api/run.
"""
import base64
import json
from unittest.mock import MagicMock


# ---------- Páginas estáticas ----------

def test_index_redireciona_pra_v2_configuracao(client):
    res = client.get("/")
    assert res.status_code == 302
    assert "/v2/configuracao" in res.headers["Location"]


def test_healthz_sempre_responde(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.get_json() == {"ok": True}


# ---------- /api/configs (deprecated, retorna vazio) ----------

def test_api_configs_retorna_lista_vazia(client):
    """Configs viraram client-side. Endpoint legacy retorna vazio."""
    res = client.get("/api/configs")
    assert res.status_code == 200
    data = res.get_json()
    assert data == {"single": [], "cross": []}


def test_api_configs_post_410_gone(client):
    res = client.post("/api/configs", json={"id": "qualquer", "src_env_id": "x", "dst_env_id": "y"})
    assert res.status_code == 410
    body = res.get_json()
    assert body.get("deprecated") is True


# ---------- /api/environments (deprecated, retorna vazio) ----------

def test_api_environments_get_410(client):
    res = client.get("/api/environments")
    assert res.status_code == 410
    body = res.get_json()
    assert body.get("pipefy") == []


def test_api_v2_environments_get_410(client):
    res = client.get("/api/v2/environments")
    assert res.status_code == 410


def test_api_environments_post_410(client):
    res = client.post("/api/environments", json={"type": "pipefy", "env": {"id": "x"}})
    assert res.status_code == 410


def test_api_environments_delete_410(client):
    res = client.delete("/api/environments/pipefy/whatever")
    assert res.status_code == 410


# ---------- /api/snapshots ----------

def test_api_snapshots_lista_arquivos_no_volume(workdir, client):
    tmp_path, _ = workdir
    snap = {
        "metadata": {"timestamp": "2026-04-24T17:00:00", "label": "test_snap"},
        "pipe": {"name": "Pipe Teste"},
        "automations": [{}, {}, {}],
    }
    (tmp_path / "snapshots" / "test_snap_20260424.json").write_text(json.dumps(snap), encoding="utf-8")
    res = client.get("/api/snapshots")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data) == 1
    assert data[0]["name"] == "test_snap_20260424.json"
    assert data[0]["pipe_name"] == "Pipe Teste"
    assert data[0]["automacoes"] == 3
    assert data[0]["is_ipaas"] is False


def test_api_snapshots_detecta_ipaas(workdir, client):
    tmp_path, _ = workdir
    snap = {"label": "ipaas_snap", "total_flows": 9, "flows": []}
    (tmp_path / "snapshots" / "ipaas_snap_20260424.json").write_text(json.dumps(snap), encoding="utf-8")
    res = client.get("/api/snapshots")
    data = res.get_json()
    assert data[0]["is_ipaas"] is True
    assert data[0]["total_flows"] == 9


def test_api_snapshots_vazio_quando_sem_arquivos(workdir, client):
    res = client.get("/api/snapshots")
    assert res.status_code == 200
    assert res.get_json() == []


# ---------- /api/batch ----------

def test_api_batch_le_arquivo(workdir, client):
    tmp_path, _ = workdir
    batch = {
        "pipes": [
            {"nome": "Pipe A", "env_id": "fourd_hmg", "uuid_origem": "u1", "uuid_destino": "u1", "repo_origem": "r1", "repo_destino": "r1"}
        ]
    }
    (tmp_path / "config" / "batch_pipes.json").write_text(json.dumps(batch), encoding="utf-8")
    res = client.get("/api/batch")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["pipes"]) == 1
    assert data["pipes"][0]["env_id"] == "fourd_hmg"


def test_api_batch_retorna_pipes_vazio_se_arquivo_ausente(workdir, client):
    res = client.get("/api/batch")
    assert res.status_code == 200
    assert res.get_json() == {"pipes": []}


# ---------- /api/results ----------

def test_api_results_pipefy(workdir, client):
    tmp_path, _ = workdir
    payload = {"status": "IDENTICOS", "total_divergencias": 0, "divergencias": []}
    (tmp_path / "results" / "validations.json").write_text(json.dumps(payload), encoding="utf-8")
    res = client.get("/api/results")
    assert res.status_code == 200
    assert res.get_json()["status"] == "IDENTICOS"


def test_api_results_ipaas_tem_prioridade(workdir, client):
    tmp_path, _ = workdir
    (tmp_path / "results" / "validations.json").write_text(
        json.dumps({"status": "IDENTICOS", "metadata": {"mode": "single"}}), encoding="utf-8"
    )
    (tmp_path / "results" / "ipaas_validations.json").write_text(
        json.dumps({"status": "IDENTICOS", "metadata": {"mode": "ipaas"}}), encoding="utf-8"
    )
    res = client.get("/api/results")
    assert res.get_json()["metadata"]["mode"] == "ipaas"


def test_api_results_retorna_null_quando_sem_arquivos(workdir, client):
    res = client.get("/api/results")
    assert res.status_code == 200
    assert res.get_json() is None


# ---------- /api/run ----------

def _mock_popen(monkeypatch, server, returncode=0, stdout="", stderr=""):
    """Helper: mocka subprocess.Popen pra retornar um proc fake."""
    fake_proc = MagicMock()
    fake_proc.communicate.return_value = (stdout, stderr)
    fake_proc.returncode = returncode
    fake_proc.terminate = MagicMock()
    fake_proc.wait = MagicMock()
    fake_proc.kill = MagicMock()
    popen_mock = MagicMock(return_value=fake_proc)
    monkeypatch.setattr(server.subprocess, "Popen", popen_mock)
    return popen_mock, fake_proc


def _wait_finished(server, timeout=5.0):
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        if server._state.get("finished"):
            return
        time.sleep(0.05)


def test_api_run_rejeita_sem_token(client):
    res = client.post("/api/run", json={"mode": "single"})
    assert res.status_code == 400
    assert "token" in res.get_json().get("error", "").lower()


def test_api_run_rejeita_sem_base_url(client, pipefy_payload):
    payload = dict(pipefy_payload)
    payload["mode"] = "single"
    payload.pop("base_url")
    res = client.post("/api/run", json=payload)
    assert res.status_code == 400


def test_api_run_inicia_validacao_single(workdir, client, pipefy_payload, monkeypatch):
    _, server = workdir
    _mock_popen(monkeypatch, server)

    payload = dict(pipefy_payload, mode="single", test="CT01*")
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "started"
    assert body["mode"] == "single"
    assert "run_id" in body and len(body["run_id"]) == 8


def _capture_active_at_popen(monkeypatch, server, tmp_path, filename="active.robot", returncode=0):
    """Captura conteudo de config/<filename> no momento em que Popen é chamado
    (antes do _run thread esterilizar o arquivo no finally)."""
    captured = {}
    def capture(*args, **kwargs):
        path = tmp_path / "config" / filename
        captured["content"] = path.read_text(encoding="utf-8") if path.exists() else ""
        fake_proc = MagicMock()
        fake_proc.communicate.return_value = ("", "")
        fake_proc.returncode = returncode
        return fake_proc
    monkeypatch.setattr(server.subprocess, "Popen", capture)
    return captured


def test_api_run_gera_active_robot_com_token_do_body(workdir, client, pipefy_payload, monkeypatch):
    """active.robot gerado contém o token do body (capturado antes da esterilização)."""
    tmp_path, server = workdir
    captured = _capture_active_at_popen(monkeypatch, server, tmp_path)

    payload = dict(pipefy_payload, mode="single", test="CT01*")
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    _wait_finished(server)

    assert "Bearer fake_token_xyz" in captured["content"]
    assert "https://api.pipefy.com/graphql" in captured["content"]


def test_api_run_esteriliza_active_robot_no_finally(workdir, client, pipefy_payload, monkeypatch):
    """Após run terminar, active.robot fica zerado (sem token)."""
    tmp_path, server = workdir
    _mock_popen(monkeypatch, server)

    res = client.post("/api/run", json=dict(pipefy_payload, mode="single"))
    assert res.status_code == 200
    _wait_finished(server)

    active = tmp_path / "config" / "active.robot"
    content = active.read_text(encoding="utf-8")
    assert "Bearer fake_token_xyz" not in content
    assert "sterilized" in content.lower()


def test_api_run_409_quando_ja_executando(client, pipefy_payload):
    from server import _state
    _state["running"] = True
    res = client.post("/api/run", json=dict(pipefy_payload, mode="single"))
    assert res.status_code == 409
    _state["running"] = False


def test_api_run_cross_rejeita_sem_dst_token(client, pipefy_payload):
    """Cross-env precisa src_token + dst_token."""
    payload = {
        "mode": "cross",
        "src_token": "abc",
        "src_base_url": "https://src.pipefy.com/graphql",
        # sem dst_*
    }
    res = client.post("/api/run", json=payload)
    assert res.status_code == 400


def test_api_run_cross_gera_active_cross(workdir, client, cross_payload, monkeypatch):
    tmp_path, server = workdir
    captured = _capture_active_at_popen(monkeypatch, server, tmp_path, filename="active_cross.robot")

    payload = dict(cross_payload, mode="cross")
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    _wait_finished(server)

    assert "Bearer src_tok" in captured["content"]
    assert "Bearer dst_tok" in captured["content"]


def test_api_run_ipaas_rejeita_sem_token(client):
    res = client.post("/api/run", json={"mode": "ipaas"})
    assert res.status_code == 400


def test_api_run_ipaas_gera_robot(workdir, client, ipaas_payload, monkeypatch):
    tmp_path, server = workdir
    captured = _capture_active_at_popen(monkeypatch, server, tmp_path, filename="ipaas_fourd.robot")

    payload = dict(ipaas_payload, mode="ipaas", test="CT-IPAAS-01*")
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    _wait_finished(server)

    assert "Bearer ipaas_tok" in captured["content"]


def test_api_run_healthcheck_sem_token(workdir, client, monkeypatch):
    """Healthcheck pode rodar sem token."""
    _, server = workdir
    _mock_popen(monkeypatch, server)
    res = client.post("/api/run", json={"mode": "healthcheck"})
    assert res.status_code == 200


def test_api_run_passa_pipe_uuid_via_variable_no_snapshot_create(workdir, client, pipefy_payload, monkeypatch):
    _, server = workdir
    popen_mock, _ = _mock_popen(monkeypatch, server)

    payload = dict(pipefy_payload, mode="snapshot", snapshot_mode="create",
                   label="minha_label", pipe_uuid="uuid-xyz", pipe_repo_id="999")
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    _wait_finished(server)

    cmd = popen_mock.call_args[0][0]
    assert "--variable" in cmd
    assert "SNAPSHOT_LABEL:minha_label" in cmd
    assert "PIPE_ORIGEM_UUID:uuid-xyz" in cmd
    assert "PIPE_ORIGEM_REPO_ID:999" in cmd


def test_api_run_passa_batch_env_no_modo_batch(workdir, client, pipefy_payload, monkeypatch):
    _, server = workdir
    popen_mock, _ = _mock_popen(monkeypatch, server)

    payload = dict(pipefy_payload, mode="batch", batch_env="fourd_hmg")
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    _wait_finished(server)

    cmd = popen_mock.call_args[0][0]
    assert "BATCH_ENV:fourd_hmg" in cmd


def test_api_run_grava_fallback_quando_robot_falha_sem_validations(workdir, client, pipefy_payload, monkeypatch):
    tmp_path, server = workdir
    _mock_popen(monkeypatch, server, returncode=1, stderr="HTTPError: 401 Client Error: Unauthorized")

    res = client.post("/api/run", json=dict(pipefy_payload, mode="single"))
    assert res.status_code == 200

    import time
    validations = tmp_path / "results" / "validations.json"
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if validations.exists():
            break
        time.sleep(0.05)

    assert validations.exists()
    data = json.loads(validations.read_text(encoding="utf-8"))
    assert data["status"] == "EXECUTION_FAILED"
    assert data["exit_code"] == 1
    assert "401" in data.get("error", "") or "Unauthorized" in data.get("error", "")


# ---------- /api/status ----------

def test_api_status_retorna_estado_atual(workdir, client):
    _, server = workdir
    server._state["running"] = False
    server._state["finished"] = True
    server._state["exit_code"] = 0
    server._state["started_at"] = None
    server._state["elapsed_final"] = 1.234
    server._state["mode"] = "single"
    server._state["run_id"] = "deadbeef"

    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["finished"] is True
    assert data["exit_code"] == 0
    assert data["elapsed_final"] == 1.234
    assert data["run_id"] == "deadbeef"


def test_api_run_passa_categorias_filtradas_via_variable(workdir, client, pipefy_payload, monkeypatch):
    _, server = workdir
    popen_mock, _ = _mock_popen(monkeypatch, server)

    payload = dict(pipefy_payload, mode="single", categories=["SF", "FA", "LB"])
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    _wait_finished(server)
    cmd = popen_mock.call_args[0][0]
    assert "CATEGORIES_FILTER:SF,FA,LB" in cmd


def test_api_run_categorias_todas_nao_envia_variable(workdir, client, pipefy_payload, monkeypatch):
    _, server = workdir
    popen_mock, _ = _mock_popen(monkeypatch, server)

    payload = dict(pipefy_payload, mode="single",
                   categories=["SF", "FA", "LB", "AS", "AD", "AH", "AC"])
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    _wait_finished(server)
    cmd = popen_mock.call_args[0][0]
    flat = " ".join(str(x) for x in cmd)
    assert "CATEGORIES_FILTER" not in flat


def test_api_run_passa_batch_selected_via_variable(workdir, client, pipefy_payload, monkeypatch):
    _, server = workdir
    popen_mock, _ = _mock_popen(monkeypatch, server)

    payload = dict(pipefy_payload, mode="batch", pipes_selected=["uuid-1", "uuid-2"])
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    _wait_finished(server)
    cmd = popen_mock.call_args[0][0]
    assert "BATCH_SELECTED:uuid-1,uuid-2" in cmd


def test_api_run_categorias_ipaas_aceitas(workdir, client, ipaas_payload, monkeypatch):
    _, server = workdir
    popen_mock, _ = _mock_popen(monkeypatch, server)

    payload = dict(ipaas_payload, mode="ipaas", test="CT-IPAAS-01*", categories=["IF", "IT"])
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    _wait_finished(server)
    cmd = popen_mock.call_args[0][0]
    assert "CATEGORIES_FILTER:IF,IT" in cmd


def test_api_run_categorias_ipaas_todas_nao_envia(workdir, client, ipaas_payload, monkeypatch):
    _, server = workdir
    popen_mock, _ = _mock_popen(monkeypatch, server)

    payload = dict(ipaas_payload, mode="ipaas", categories=["IF", "IT", "IS"])
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    _wait_finished(server)
    cmd = popen_mock.call_args[0][0]
    flat = " ".join(str(x) for x in cmd)
    assert "CATEGORIES_FILTER" not in flat


def test_api_cancel_sem_run_retorna_404(client):
    res = client.post("/api/run/cancel")
    assert res.status_code == 404


def test_api_cancel_mata_processo_em_curso(workdir, client):
    _, server = workdir
    fake_proc = MagicMock()
    fake_proc.terminate = MagicMock()
    fake_proc.wait = MagicMock()

    server._state["running"] = True
    server._state["process"] = fake_proc
    server._state["run_id"] = "test1234"

    res = client.post("/api/run/cancel")
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    assert body["run_id"] == "test1234"
    fake_proc.terminate.assert_called_once()
    assert server._state["cancelled"] is True

    # cleanup
    server._state["running"] = False
    server._state["process"] = None
    server._state["cancelled"] = False


def test_api_status_inclui_progress_quando_arquivo_existe(workdir, client):
    tmp_path, _ = workdir
    progress = {"step": 3, "total": 7, "label": "Comparando", "status": "running"}
    (tmp_path / "results" / "progress.json").write_text(json.dumps(progress), encoding="utf-8")
    res = client.get("/api/status")
    data = res.get_json()
    assert data["progress"] == progress


# ---------- Basic Auth ----------

def test_basic_auth_quando_app_password_setada(authed_client):
    """Com APP_PASSWORD setada, requests sem header retornam 401."""
    tmp_path, server, client = authed_client
    # Request com auth: ok
    res = client.get("/api/status")
    assert res.status_code == 200
    # Request sem auth: 401
    res2 = server.app.test_client().get("/api/status")
    assert res2.status_code == 401
    assert "WWW-Authenticate" in res2.headers


def test_basic_auth_credenciais_erradas_401(authed_client):
    _, server, _ = authed_client
    bad = base64.b64encode(b"demo:wrong").decode()
    res = server.app.test_client().get("/api/status", headers={"Authorization": "Basic " + bad})
    assert res.status_code == 401


def test_healthz_acessivel_sem_auth(authed_client):
    """Healthz sempre responde, mesmo com APP_PASSWORD."""
    _, server, _ = authed_client
    res = server.app.test_client().get("/healthz")
    assert res.status_code == 200
