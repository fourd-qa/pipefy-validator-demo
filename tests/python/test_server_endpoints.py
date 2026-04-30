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


# ---------- /api/discover-pipes ----------

def _mock_requests_post(monkeypatch, server, status_code=200, json_body=None, raise_exc=None):
    """Mocka requests.post pro endpoint discover-pipes."""
    fake_resp = MagicMock()
    fake_resp.status_code = status_code
    fake_resp.json.return_value = json_body if json_body is not None else {}
    fake_resp.text = json.dumps(json_body) if json_body is not None else ""

    captured = {}
    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        if raise_exc:
            raise raise_exc
        return fake_resp

    import requests as _req
    monkeypatch.setattr(_req, "post", fake_post)
    return captured


def test_discover_pipes_sem_token_retorna_400(client):
    res = client.post("/api/discover-pipes", json={"org_id": "999"})
    assert res.status_code == 400
    assert "token" in res.get_json()["error"].lower()


def test_discover_pipes_sem_org_id_retorna_400(client, pipefy_payload):
    payload = dict(pipefy_payload)
    payload.pop("org_id")
    res = client.post("/api/discover-pipes", json=payload)
    assert res.status_code == 400
    assert "org_id" in res.get_json()["error"].lower()


def test_discover_pipes_sucesso_retorna_lista(workdir, client, pipefy_payload, monkeypatch):
    _, server = workdir
    captured = _mock_requests_post(monkeypatch, server, status_code=200, json_body={
        "data": {
            "organization": {
                "name": "FourD",
                "pipes": [
                    {"id": "111", "uuid": "uuid-a", "name": "Pipe A"},
                    {"id": "222", "uuid": "uuid-b", "name": "Pipe B"},
                ]
            }
        }
    })
    res = client.post("/api/discover-pipes", json=pipefy_payload)
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    assert body["count"] == 2
    assert body["org_name"] == "FourD"
    assert body["pipes"][0] == {"name": "Pipe A", "uuid": "uuid-a", "repo_id": "111"}
    # URL e Authorization corretos
    assert captured["url"] == "https://api.pipefy.com/graphql"
    assert captured["kwargs"]["headers"]["Authorization"] == "Bearer fake_token_xyz"


def test_discover_pipes_filtra_pipes_sem_uuid(workdir, client, pipefy_payload, monkeypatch):
    _mock_requests_post(monkeypatch, workdir[1], status_code=200, json_body={
        "data": {"organization": {"name": "X", "pipes": [
            {"id": "111", "uuid": "uuid-ok", "name": "OK"},
            {"id": "222", "uuid": None, "name": "Sem UUID"},
            {"id": "333", "uuid": "uuid-3", "name": ""},
        ]}}
    })
    res = client.post("/api/discover-pipes", json=pipefy_payload)
    body = res.get_json()
    assert body["count"] == 1
    assert body["pipes"][0]["name"] == "OK"


def test_discover_pipes_401_propaga(workdir, client, pipefy_payload, monkeypatch):
    _mock_requests_post(monkeypatch, workdir[1], status_code=401, json_body={"errors": [{"message": "unauth"}]})
    res = client.post("/api/discover-pipes", json=pipefy_payload)
    assert res.status_code == 401
    assert "rejeitado" in res.get_json()["error"].lower() or "401" in res.get_json()["error"]


def test_discover_pipes_graphql_errors_502(workdir, client, pipefy_payload, monkeypatch):
    _mock_requests_post(monkeypatch, workdir[1], status_code=200, json_body={
        "errors": [{"message": "Organization not found"}]
    })
    res = client.post("/api/discover-pipes", json=pipefy_payload)
    assert res.status_code == 502
    assert "graphql" in res.get_json()["error"].lower() or "Organization" in res.get_json()["error"]


def test_discover_pipes_network_error_502(workdir, client, pipefy_payload, monkeypatch):
    import requests as _req
    _mock_requests_post(monkeypatch, workdir[1], raise_exc=_req.exceptions.ConnectionError("dns failed"))
    res = client.post("/api/discover-pipes", json=pipefy_payload)
    assert res.status_code == 502


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


# ---------- Regressão: edge cases de /api/run ----------

def test_api_run_token_sem_prefixo_bearer_e_normalizado(workdir, client, monkeypatch):
    """Token cru (sem 'Bearer ') deve ser normalizado pra 'Bearer xxx' no .robot."""
    tmp_path, server = workdir
    captured = _capture_active_at_popen(monkeypatch, server, tmp_path)

    payload = {
        "mode": "single",
        "token": "tok_cru_sem_prefixo",
        "base_url": "https://api.pipefy.com/graphql",
        "org_id": "999",
    }
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    _wait_finished(server)
    assert "Bearer tok_cru_sem_prefixo" in captured["content"]


def test_api_run_payload_com_quebra_de_linha_no_token_e_sanitizado(workdir, client, monkeypatch):
    """Token com \\n no meio não pode quebrar a linha do .robot."""
    tmp_path, server = workdir
    captured = _capture_active_at_popen(monkeypatch, server, tmp_path)

    payload = {
        "mode": "single",
        "token": "tok\nmalicioso",
        "base_url": "https://api.pipefy.com/graphql",
    }
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    _wait_finished(server)
    # Não pode ter quebra de linha real no token (só vira espaço)
    lines = [l for l in captured["content"].splitlines() if "PIPEFY_TOKEN" in l]
    assert len(lines) == 1, f"esperava 1 linha PIPEFY_TOKEN, achou {len(lines)}"


def test_api_run_body_invalido_string_nao_500(client):
    """POST /api/run com body string (não dict) não pode crashar com 500."""
    res = client.post("/api/run", data='"not_a_dict"', content_type="application/json")
    # Espera 400 (sem token) ou 409, nunca 500
    assert res.status_code in (400, 409)


def test_api_run_payload_vazio_400(client):
    res = client.post("/api/run", json={})
    assert res.status_code == 400


def test_api_run_mode_desconhecido_cai_em_single(workdir, client, pipefy_payload, monkeypatch):
    """mode='inventado' deve cair no else (single) e ser aceito."""
    _, server = workdir
    _mock_popen(monkeypatch, server)
    payload = dict(pipefy_payload, mode="modo_que_nao_existe")
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200


def test_api_run_cancel_sem_process_attr(workdir, client):
    """cancel quando running=True mas process foi limpo (race condition)."""
    _, server = workdir
    server._state["running"] = True
    server._state["process"] = None
    res = client.post("/api/run/cancel")
    assert res.status_code == 404
    server._state["running"] = False


# ---------- Regressão: tokens client-side não persistem em arquivo ----------

def test_api_run_active_robot_esterilizado_apos_run(workdir, client, pipefy_payload, monkeypatch):
    """Após run, config/active.robot não pode conter o token original."""
    tmp_path, server = workdir
    _mock_popen(monkeypatch, server)

    payload = dict(pipefy_payload, mode="single")
    payload["token"] = "Bearer SEGREDO_ABC123"
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    _wait_finished(server)

    active = (tmp_path / "config" / "active.robot").read_text(encoding="utf-8")
    assert "SEGREDO_ABC123" not in active
    assert "sterilized" in active.lower()


def test_api_run_cross_active_cross_esterilizado_apos_run(workdir, client, cross_payload, monkeypatch):
    tmp_path, server = workdir
    _mock_popen(monkeypatch, server)
    cross_payload["src_token"] = "Bearer SEGREDO_SRC"
    cross_payload["dst_token"] = "Bearer SEGREDO_DST"
    res = client.post("/api/run", json=dict(cross_payload, mode="cross"))
    assert res.status_code == 200
    _wait_finished(server)

    content = (tmp_path / "config" / "active_cross.robot").read_text(encoding="utf-8")
    assert "SEGREDO_SRC" not in content
    assert "SEGREDO_DST" not in content


# ---------- Regressão: discover-pipes não vaza erro completo ao usuário ----------

def test_discover_pipes_payload_truncado_em_erro(workdir, client, pipefy_payload, monkeypatch):
    """upstream_body truncado em 300 chars pra não vazar payload inteiro."""
    huge_body = "X" * 5000
    fake_resp = MagicMock()
    fake_resp.status_code = 500
    fake_resp.text = huge_body
    fake_resp.json.return_value = {}

    import requests as _req
    monkeypatch.setattr(_req, "post", lambda *a, **kw: fake_resp)

    res = client.post("/api/discover-pipes", json=pipefy_payload)
    body = res.get_json()
    assert res.status_code == 502
    assert len(body.get("upstream_body", "")) <= 300


# ---------- Auth com APP_USERNAME custom ----------

def test_basic_auth_custom_username(monkeypatch, tmp_path):
    """APP_USERNAME custom é respeitado, default 'demo'."""
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_USERNAME", "andre")
    (tmp_path / "config").mkdir()
    (tmp_path / "results").mkdir()
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "tmp").mkdir()
    monkeypatch.chdir(tmp_path)
    import sys, importlib
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    cli = server.app.test_client()

    # Username errado falha
    bad = base64.b64encode(b"demo:secret").decode()
    r1 = cli.get("/api/status", headers={"Authorization": "Basic " + bad})
    assert r1.status_code == 401

    # Username certo passa
    good = base64.b64encode(b"andre:secret").decode()
    r2 = cli.get("/api/status", headers={"Authorization": "Basic " + good})
    assert r2.status_code == 200


def test_basic_auth_password_apenas_espacos_eh_tratado_como_vazio(monkeypatch, tmp_path):
    """APP_PASSWORD com whitespace só não ativa auth (strip())."""
    monkeypatch.setenv("APP_PASSWORD", "   ")
    (tmp_path / "config").mkdir()
    (tmp_path / "results").mkdir()
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "tmp").mkdir()
    monkeypatch.chdir(tmp_path)
    import sys, importlib
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    cli = server.app.test_client()
    res = cli.get("/api/status")
    assert res.status_code == 200
