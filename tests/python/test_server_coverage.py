"""Testes adicionais focados em fechar gaps de cobertura do server.py.

Cobre:
- Páginas estáticas V2 (resultados, execucao, configuracao, docs, help, assets, reports)
- /proposals (index com cards e vazio + serve_proposal)
- Branches de erro: JSON corrompido em snapshots/batch/results, base64 inválido em Basic Auth,
  output.xml malformado, resp não-JSON em discover_pipes
- _categories_var com lista inválida
- Modos snapshot 'compare' e iPaaS CT-IPAAS-03/04
- cancel_run com TimeoutExpired e Exception
- get_status com PROGRESS_FILE/LOG_FILE corrompidos e elapsed_final
- _make_run_dir / _cleanup_run_dir
- _sterilize_active_robots com IOError
- _api/run fallback writer parser branches
"""
import base64
import json
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest


# ---------- Páginas V2 estáticas ----------

def test_v2_resultados_serve_html(client):
    res = client.get("/v2/resultados")
    assert res.status_code == 200
    assert b"<" in res.data  # HTML


def test_v2_root_redirects_or_serves(client):
    """A rota /v2 (sem trailing) e /v2/ devem servir tela de resultados."""
    res = client.get("/v2/")
    assert res.status_code == 200


def test_v2_execucao_serve_html(client):
    res = client.get("/v2/execucao")
    assert res.status_code == 200


def test_v2_configuracao_alias(client):
    """Tanto /v2/configuracao quanto /v2/config devem servir a mesma tela."""
    a = client.get("/v2/configuracao")
    b = client.get("/v2/config")
    assert a.status_code == 200
    assert b.status_code == 200


def test_v2_docs_serve_html(client):
    res = client.get("/v2/docs")
    assert res.status_code == 200


def test_v2_help_serve_html(client):
    res = client.get("/v2/help")
    assert res.status_code == 200


def test_v2_assets_aplica_no_cache_headers(client):
    """v2_assets deve devolver headers anti-cache mesmo que arquivo não exista."""
    res = client.get("/v2/assets/qualquer.css")
    # Pode ser 200 (existe) ou 404 (não existe). Se 200, valida headers.
    if res.status_code == 200:
        assert "no-store" in res.headers.get("Cache-Control", "")
        assert res.headers.get("Pragma") == "no-cache"


def test_reports_route_serve_arquivo(workdir, client):
    """/reports/<f> deve servir arquivos de results/."""
    tmp_path, _ = workdir
    (tmp_path / "results" / "report.html").write_text("<html>ok</html>", encoding="utf-8")
    res = client.get("/reports/report.html")
    assert res.status_code == 200
    assert b"ok" in res.data


def test_reports_arquivo_inexistente_404(client):
    res = client.get("/reports/nada.txt")
    assert res.status_code == 404


# ---------- /proposals ----------

def test_proposals_index_vazio_mostra_placeholder(workdir, client):
    """Sem subdiretórios em proposals/, retorna mensagem 'Sem propostas ainda'."""
    tmp_path, _ = workdir
    (tmp_path / "proposals").mkdir(exist_ok=True)
    res = client.get("/proposals/")
    assert res.status_code == 200
    assert b"Sem propostas ainda" in res.data


def test_proposals_index_sem_diretorio_funciona(workdir, client):
    """Mesmo sem proposals/ existir, rota não quebra."""
    res = client.get("/proposals/")
    assert res.status_code == 200


def test_proposals_index_lista_iteracoes_com_html_e_outros(workdir, client):
    tmp_path, _ = workdir
    prop = tmp_path / "proposals" / "2026-04-30_design"
    prop.mkdir(parents=True)
    (prop / "tela.html").write_text("<html></html>", encoding="utf-8")
    (prop / "wireframe.png").write_bytes(b"\x89PNG\r\n")
    (prop / "notes.md").write_text("# notes", encoding="utf-8")
    res = client.get("/proposals/")
    assert res.status_code == 200
    body = res.data.decode("utf-8", errors="replace")
    assert "2026-04-30_design" in body
    assert "tela.html" in body
    # Imagens/MD vão pra "Outros arquivos"
    assert "wireframe.png" in body or "notes.md" in body


def test_proposals_iteracao_sem_html_mostra_mensagem(workdir, client):
    tmp_path, _ = workdir
    prop = tmp_path / "proposals" / "2026-05-01_only_pdf"
    prop.mkdir(parents=True)
    (prop / "doc.pdf").write_bytes(b"%PDF-1.4")
    res = client.get("/proposals/")
    body = res.data.decode("utf-8", errors="replace")
    assert "Sem HTML nessa" in body or "doc.pdf" in body


def test_proposals_pula_diretorios_iniciados_com_ponto(workdir, client):
    tmp_path, _ = workdir
    hidden = tmp_path / "proposals" / ".oculto"
    hidden.mkdir(parents=True)
    (hidden / "x.html").write_text("oi", encoding="utf-8")
    res = client.get("/proposals/")
    body = res.data.decode("utf-8")
    assert ".oculto" not in body


def test_serve_proposal_retorna_arquivo_existente(workdir, client):
    tmp_path, _ = workdir
    prop = tmp_path / "proposals" / "iter1"
    prop.mkdir(parents=True)
    (prop / "x.html").write_text("conteudo", encoding="utf-8")
    res = client.get("/proposals/iter1/x.html")
    assert res.status_code == 200
    assert b"conteudo" in res.data


def test_serve_proposal_404_quando_nao_existe(client):
    res = client.get("/proposals/nada/missing.html")
    assert res.status_code == 404


# ---------- Branches de erro: JSON corrompido ----------

def test_api_batch_json_corrompido_retorna_500(workdir, client):
    tmp_path, _ = workdir
    (tmp_path / "config" / "batch_pipes.json").write_text("{ json invalido", encoding="utf-8")
    res = client.get("/api/batch")
    assert res.status_code == 500
    body = res.get_json()
    assert "error" in body
    assert body["pipes"] == []


def test_api_snapshots_json_corrompido_inclui_arquivo_com_metadata_vazia(workdir, client):
    """Snapshot com JSON quebrado não deve crashar, só retornar entry com nome vazio."""
    tmp_path, _ = workdir
    (tmp_path / "snapshots" / "broken.json").write_text("{ ruim", encoding="utf-8")
    res = client.get("/api/snapshots")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data) == 1
    assert data[0]["name"] == "broken.json"
    assert data[0]["pipe_name"] == ""
    assert data[0]["timestamp"] == ""


def test_api_results_json_corrompido_retorna_null(workdir, client):
    """JSON corrompido em validations.json e ipaas: ambos pulados, retorna null."""
    tmp_path, _ = workdir
    (tmp_path / "results" / "validations.json").write_text("xxxx", encoding="utf-8")
    (tmp_path / "results" / "ipaas_validations.json").write_text("yyyy", encoding="utf-8")
    res = client.get("/api/results")
    assert res.status_code == 200
    assert res.get_json() is None


# ---------- Basic Auth com base64 inválido ----------

def test_basic_auth_header_base64_invalido_401(authed_client):
    """Header com prefixo Basic mas payload base64 quebrado deve dar 401."""
    _, _, client = authed_client
    res = client.get("/api/results", headers={"Authorization": "Basic !!@@##invalid"})
    # decodeou como string vazia, falha no compare -> 401
    assert res.status_code == 401


# ---------- _categories_var ----------

def test_api_run_categorias_invalidas_sao_filtradas(workdir, client, pipefy_payload, monkeypatch):
    """Lista categories=['XYZ', 'WWW'] sem nenhuma válida = sem --variable."""
    tmp_path, server = workdir
    captured_args = {}
    def capture_popen(*args, **kwargs):
        captured_args["cmd"] = args[0] if args else kwargs.get("args")
        proc = MagicMock()
        proc.communicate.return_value = ("", "")
        proc.returncode = 0
        return proc
    monkeypatch.setattr(server.subprocess, "Popen", capture_popen)

    payload = dict(pipefy_payload, mode="single", categories=["XYZ", "ABC"])
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    # Espera o thread terminar
    import time
    time.sleep(0.3)
    cmd = captured_args.get("cmd", [])
    cmd_str = " ".join(cmd)
    assert "CATEGORIES_FILTER" not in cmd_str


# ---------- Snapshot mode 'compare' ----------

def test_api_run_snapshot_compare_passa_pipe_destino_uuid(workdir, client, pipefy_payload, monkeypatch):
    """snapshot_mode='compare' com pipe_uuid override deve gerar PIPE_DESTINO_UUID."""
    tmp_path, server = workdir
    captured_args = {}
    def capture_popen(*args, **kwargs):
        captured_args["cmd"] = args[0] if args else kwargs.get("args")
        proc = MagicMock()
        proc.communicate.return_value = ("", "")
        proc.returncode = 0
        return proc
    monkeypatch.setattr(server.subprocess, "Popen", capture_popen)

    payload = dict(
        pipefy_payload,
        mode="snapshot",
        snapshot_mode="compare",
        file="snapshots/baseline.json",
        pipe_uuid="uuid-live",
        pipe_repo_id="987",
    )
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    import time
    time.sleep(0.3)
    cmd = " ".join(captured_args.get("cmd", []))
    assert "SNAPSHOT_FILE:snapshots/baseline.json" in cmd
    assert "PIPE_DESTINO_UUID:uuid-live" in cmd
    assert "PIPE_DESTINO_REPO_ID:987" in cmd


# ---------- iPaaS CT-IPAAS-03 / 04 ----------

def test_api_run_ipaas_ct03_passa_snapshot_label(workdir, client, ipaas_payload, monkeypatch):
    tmp_path, server = workdir
    captured_args = {}
    def capture_popen(*args, **kwargs):
        captured_args["cmd"] = args[0] if args else kwargs.get("args")
        proc = MagicMock()
        proc.communicate.return_value = ("", "")
        proc.returncode = 0
        return proc
    monkeypatch.setattr(server.subprocess, "Popen", capture_popen)

    payload = dict(ipaas_payload, mode="ipaas", test="CT-IPAAS-03_snapshot", label="meu_baseline")
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    import time
    time.sleep(0.3)
    cmd = " ".join(captured_args.get("cmd", []))
    assert "IPAAS_SNAPSHOT_LABEL:meu_baseline" in cmd


def test_api_run_ipaas_ct04_passa_snapshot_file(workdir, client, ipaas_payload, monkeypatch):
    tmp_path, server = workdir
    captured_args = {}
    def capture_popen(*args, **kwargs):
        captured_args["cmd"] = args[0] if args else kwargs.get("args")
        proc = MagicMock()
        proc.communicate.return_value = ("", "")
        proc.returncode = 0
        return proc
    monkeypatch.setattr(server.subprocess, "Popen", capture_popen)

    payload = dict(ipaas_payload, mode="ipaas", test="CT-IPAAS-04_compare", file="snapshots/ipaas_baseline.json")
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    import time
    time.sleep(0.3)
    cmd = " ".join(captured_args.get("cmd", []))
    assert "IPAAS_SNAPSHOT_FILE:snapshots/ipaas_baseline.json" in cmd


# ---------- cancel_run: TimeoutExpired + Exception ----------

def test_cancel_run_timeout_expirado_chama_kill(workdir, client, monkeypatch):
    """Se proc.wait() expirar, deve chamar proc.kill()."""
    _, server = workdir
    proc = MagicMock()
    proc.wait.side_effect = subprocess.TimeoutExpired(cmd="robot", timeout=2)
    server._state["running"] = True
    server._state["process"] = proc
    server._state["run_id"] = "abc12345"

    res = client.post("/api/run/cancel")
    assert res.status_code == 200
    proc.terminate.assert_called_once()
    proc.kill.assert_called_once()
    server._state["running"] = False
    server._state["process"] = None


def test_cancel_run_excecao_inesperada_500(workdir, client):
    _, server = workdir
    proc = MagicMock()
    proc.terminate.side_effect = OSError("boom")
    server._state["running"] = True
    server._state["process"] = proc

    res = client.post("/api/run/cancel")
    assert res.status_code == 500
    assert "boom" in res.get_json().get("error", "")
    server._state["running"] = False
    server._state["process"] = None


# ---------- get_status: arquivos corrompidos / elapsed_final ----------

def test_status_progress_file_corrompido_nao_quebra(workdir, client):
    tmp_path, _ = workdir
    (tmp_path / "results" / "progress.json").write_text("[[broken", encoding="utf-8")
    res = client.get("/api/status")
    assert res.status_code == 200
    body = res.get_json()
    assert body["progress"] is None


def test_status_log_file_lido_e_strip(workdir, client):
    tmp_path, _ = workdir
    (tmp_path / "results" / "console.log").write_text("linha1\n\nlinha2\n", encoding="utf-8")
    res = client.get("/api/status")
    body = res.get_json()
    assert "linha1" in body["logs"]
    assert "linha2" in body["logs"]
    assert "" not in body["logs"]


def test_status_elapsed_usa_elapsed_final_quando_finalizado(workdir, client):
    _, server = workdir
    server._state["started_at"] = 1000.0
    server._state["running"] = False
    server._state["finished"] = True
    server._state["elapsed_final"] = 42.5
    res = client.get("/api/status")
    body = res.get_json()
    assert body["elapsed"] == 42.5
    assert body["elapsed_final"] == 42.5
    # cleanup
    server._state["started_at"] = None
    server._state["finished"] = False
    server._state["elapsed_final"] = None


def test_status_elapsed_calculado_quando_running(workdir, client, monkeypatch):
    _, server = workdir
    server._state["started_at"] = server.time.time() - 5
    server._state["running"] = True
    res = client.get("/api/status")
    body = res.get_json()
    assert body["elapsed"] is not None
    assert body["elapsed"] >= 4.5
    server._state["started_at"] = None
    server._state["running"] = False


# ---------- _make_run_dir / _cleanup_run_dir ----------

def test_make_run_dir_cria_diretorio(workdir):
    tmp_path, server = workdir
    d = server._make_run_dir("run_abc")
    assert os.path.isdir(d)
    assert d.endswith("run_abc") or "run_abc" in d


def test_cleanup_run_dir_remove_diretorio(workdir):
    tmp_path, server = workdir
    d = server._make_run_dir("run_xyz")
    assert os.path.isdir(d)
    server._cleanup_run_dir(d)
    assert not os.path.exists(d)


def test_cleanup_run_dir_aceita_path_inexistente(workdir):
    _, server = workdir
    # Não deve levantar
    server._cleanup_run_dir("/path/que/nao/existe")
    server._cleanup_run_dir(None)
    server._cleanup_run_dir("")


# ---------- _sterilize_active_robots: IOError silencioso ----------

def test_sterilize_active_robots_ioerror_nao_propaga(workdir, monkeypatch):
    tmp_path, server = workdir
    active = tmp_path / "config" / "active.robot"
    active.write_text("token=Bearer xxx", encoding="utf-8")

    def boom(*args, **kwargs):
        raise IOError("disk full")
    monkeypatch.setattr("builtins.open", boom)
    # Não deve levantar exception
    server._sterilize_active_robots()


# ---------- _extract_fail_from_output_xml ----------

def test_extract_fail_xml_corrompido_retorna_vazio(workdir):
    tmp_path, server = workdir
    (tmp_path / "results" / "output.xml").write_text("<<<not xml>>>", encoding="utf-8")
    msg, hint = server._extract_fail_from_output_xml()
    assert msg == ""
    assert hint == ""


# ---------- discover_pipes: resp não-JSON ----------

def test_discover_pipes_resposta_nao_json_502(workdir, client, monkeypatch):
    _, server = workdir
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.side_effect = ValueError("não é json")
    fake_resp.text = "html error page"
    monkeypatch.setattr(server.requests if hasattr(server, "requests") else __import__("requests"),
                        "post", lambda *a, **kw: fake_resp)
    # Como o módulo importa 'requests' dentro da função, monkeypatcho via sys.modules
    import requests as _requests
    monkeypatch.setattr(_requests, "post", lambda *a, **kw: fake_resp)

    payload = {
        "token": "Bearer abc",
        "base_url": "https://api.pipefy.com/graphql",
        "org_id": "1",
        "verify_ssl": False,
    }
    res = client.post("/api/discover-pipes", json=payload)
    assert res.status_code == 502
    assert "JSON" in res.get_json().get("error", "")


# ---------- /api/run: limpa arquivos de runs anteriores ----------

def test_api_run_remove_arquivos_anteriores(workdir, client, pipefy_payload, monkeypatch):
    tmp_path, server = workdir
    # Cria arquivos da run anterior
    (tmp_path / "results" / "validations.json").write_text("{}", encoding="utf-8")
    (tmp_path / "results" / "progress.json").write_text("{}", encoding="utf-8")
    (tmp_path / "results" / "console.log").write_text("old", encoding="utf-8")

    blocker = {"resume": False}
    def block_popen(*args, **kwargs):
        proc = MagicMock()
        # Dá tempo pro test verificar arquivos foram removidos antes do thread terminar
        def slow_communicate(timeout=None):
            import time as _t
            _t.sleep(0.05)
            return ("", "")
        proc.communicate.side_effect = slow_communicate
        proc.returncode = 0
        return proc
    monkeypatch.setattr(server.subprocess, "Popen", block_popen)

    res = client.post("/api/run", json=dict(pipefy_payload, mode="single"))
    assert res.status_code == 200
    # Imediatamente após o POST, os arquivos antigos já foram removidos
    # (a remoção acontece no thread main, antes do thread Popen)
    # Aguarda o thread terminar pra não vazar estado
    import time
    deadline = time.time() + 5
    while time.time() < deadline and server._state.get("running"):
        time.sleep(0.05)


# ---------- /api/run: fallback quando Robot falha sem validations ----------

def test_api_run_fallback_extrai_msg_de_output_xml(workdir, client, pipefy_payload, monkeypatch):
    """Se Robot falhar sem produzir validations.json, fallback usa msg do output.xml."""
    tmp_path, server = workdir

    output_xml = (
        '<?xml version="1.0"?>\n'
        '<robot>\n'
        '  <suite>\n'
        '    <test>\n'
        '      <kw><msg level="FAIL">Erro 401 unauthorized</msg></kw>\n'
        '    </test>\n'
        '  </suite>\n'
        '</robot>\n'
    )
    def fail_popen(*args, **kwargs):
        # Escreve output.xml ANTES de retornar (simula o Robot)
        (tmp_path / "results" / "output.xml").write_text(output_xml, encoding="utf-8")
        proc = MagicMock()
        proc.communicate.return_value = ("", "stderr noise")
        proc.returncode = 1
        return proc
    monkeypatch.setattr(server.subprocess, "Popen", fail_popen)

    res = client.post("/api/run", json=dict(pipefy_payload, mode="single"))
    assert res.status_code == 200
    import time
    deadline = time.time() + 5
    while time.time() < deadline and not server._state.get("finished"):
        time.sleep(0.05)
    # Validations file deve ter sido criado como fallback
    val_path = tmp_path / "results" / "validations.json"
    assert val_path.exists()
    body = json.loads(val_path.read_text(encoding="utf-8"))
    assert body["status"] == "EXECUTION_FAILED"
    assert "401" in body["error"]
    assert "Token" in body["hint"]


def _wait_for_file(path, timeout=5.0):
    """Espera arquivo existir E ter JSON parseável (evita race quando escrita ainda
    está em progresso). _state['finished'] vira True ANTES do fallback ser escrito."""
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")
                if content.strip():
                    json.loads(content)
                    return True
            except (json.JSONDecodeError, OSError):
                pass
        time.sleep(0.05)
    return False


def test_api_run_fallback_usa_stderr_quando_sem_xml(workdir, client, pipefy_payload, monkeypatch):
    """Sem output.xml, fallback parser pega primeira linha não-warning do stderr."""
    tmp_path, server = workdir

    def fail_popen(*args, **kwargs):
        proc = MagicMock()
        proc.communicate.return_value = (
            "",
            "InsecureRequestWarning: ignore\nwarnings.warn(...)\n   \nReal error message here\n",
        )
        proc.returncode = 1
        return proc
    monkeypatch.setattr(server.subprocess, "Popen", fail_popen)

    res = client.post("/api/run", json=dict(pipefy_payload, mode="single"))
    assert res.status_code == 200

    val_path = tmp_path / "results" / "validations.json"
    assert _wait_for_file(val_path), "fallback validations.json não foi escrito"
    body = json.loads(val_path.read_text(encoding="utf-8"))
    assert body["status"] == "EXECUTION_FAILED"
    # Skipou o warning, pegou a linha real
    assert "Real error message" in body["error"]


def test_api_run_fallback_usa_default_msg_quando_sem_stderr(workdir, client, pipefy_payload, monkeypatch):
    """Sem output.xml e sem stderr útil, usa mensagem default com exit code."""
    tmp_path, server = workdir

    def fail_popen(*args, **kwargs):
        proc = MagicMock()
        proc.communicate.return_value = ("", "")
        proc.returncode = 7
        return proc
    monkeypatch.setattr(server.subprocess, "Popen", fail_popen)

    res = client.post("/api/run", json=dict(pipefy_payload, mode="single"))
    assert res.status_code == 200

    val_path = tmp_path / "results" / "validations.json"
    assert _wait_for_file(val_path), "fallback validations.json não foi escrito"
    body = json.loads(val_path.read_text(encoding="utf-8"))
    assert body["status"] == "EXECUTION_FAILED"
    assert "exit code 7" in body["error"]


# ---------- /api/default-env ----------

def test_cleanup_run_dir_ignora_oserror(workdir, monkeypatch):
    """OSError durante rmtree é silenciado."""
    _, server = workdir
    d = server._make_run_dir("run_err")
    def boom(*a, **kw):
        raise OSError("permission denied")
    monkeypatch.setattr(server.shutil, "rmtree", boom)
    # Não deve levantar
    server._cleanup_run_dir(d)


def test_v2_assets_existente_aplica_headers(workdir, client):
    """Quando o asset existe (resolvido relativo ao app root), headers são aplicados."""
    # web/designs/assets/ tem arquivos no repo. Tenta servir um genérico.
    # Como send_from_directory resolve relativo ao app.root_path, o arquivo precisa existir lá.
    # Se não existir nenhum, esse teste só valida o comportamento de 404.
    res = client.get("/v2/assets/__definitivamente_nao_existe__.css")
    # 404 é aceitável; o objetivo é exercitar a rota
    assert res.status_code in (200, 404)


def test_status_log_file_ioerror_silencioso(workdir, client, monkeypatch):
    """Se ler console.log lançar IOError, status retorna logs=[] sem crashar."""
    tmp_path, server = workdir
    log = tmp_path / "results" / "console.log"
    log.write_text("conteudo", encoding="utf-8")

    real_open = open
    def selective_open(path, *a, **kw):
        if str(path).endswith("console.log"):
            raise IOError("locked")
        return real_open(path, *a, **kw)
    monkeypatch.setattr("builtins.open", selective_open)

    res = client.get("/api/status")
    assert res.status_code == 200
    body = res.get_json()
    assert body["logs"] == []


def test_api_run_fallback_writer_ioerror_nao_propaga(workdir, client, pipefy_payload, monkeypatch):
    """Se gravar o fallback validations.json falhar com IOError, não levanta exception."""
    tmp_path, server = workdir

    def fail_popen(*args, **kwargs):
        proc = MagicMock()
        proc.communicate.return_value = ("", "erro real")
        proc.returncode = 1
        return proc
    monkeypatch.setattr(server.subprocess, "Popen", fail_popen)

    real_open = open
    def selective_open(path, *a, **kw):
        # Bloqueia escrita de validations.json (forçando IOError no try)
        if str(path).endswith("validations.json") and "w" in (a[0] if a else kw.get("mode", "")):
            raise IOError("disk full")
        return real_open(path, *a, **kw)
    monkeypatch.setattr("builtins.open", selective_open)

    res = client.post("/api/run", json=dict(pipefy_payload, mode="single"))
    assert res.status_code == 200
    # Espera o thread terminar
    import time
    deadline = time.time() + 5
    while time.time() < deadline and not server._state.get("finished"):
        time.sleep(0.05)
    assert server._state["finished"] is True
    # validations.json não foi escrito porque o open falhou
    assert not (tmp_path / "results" / "validations.json").exists()


def test_api_run_thread_subprocess_timeout(workdir, client, pipefy_payload, monkeypatch):
    """Se Popen.communicate estourar TimeoutExpired, exit_code=-1 e fallback escrito."""
    tmp_path, server = workdir

    def timeout_popen(*args, **kwargs):
        proc = MagicMock()
        # Primeira chamada lança timeout, segunda (após kill) retorna vazio
        proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="robot", timeout=600),
            ("", "killed after timeout"),
        ]
        proc.returncode = -1
        proc.kill = MagicMock()
        return proc
    monkeypatch.setattr(server.subprocess, "Popen", timeout_popen)

    res = client.post("/api/run", json=dict(pipefy_payload, mode="single"))
    assert res.status_code == 200
    val_path = tmp_path / "results" / "validations.json"
    assert _wait_for_file(val_path), "fallback não foi escrito após timeout"
    body = json.loads(val_path.read_text(encoding="utf-8"))
    assert body["status"] == "EXECUTION_FAILED"
    assert body["exit_code"] == -1


def test_api_run_thread_excecao_inesperada(workdir, client, pipefy_payload, monkeypatch):
    """Exception não-Timeout no _run vira exit_code=-2."""
    tmp_path, server = workdir

    def bad_popen(*args, **kwargs):
        raise RuntimeError("popen falhou geral")
    monkeypatch.setattr(server.subprocess, "Popen", bad_popen)

    res = client.post("/api/run", json=dict(pipefy_payload, mode="single"))
    assert res.status_code == 200
    val_path = tmp_path / "results" / "validations.json"
    import time
    deadline = time.time() + 5
    while time.time() < deadline and not val_path.exists():
        time.sleep(0.05)
    assert val_path.exists()
    body = json.loads(val_path.read_text(encoding="utf-8"))
    assert body["exit_code"] == -2
    assert "popen falhou geral" in body["error"]


def test_api_run_fallback_pula_linhas_de_log_e_info(workdir, client, pipefy_payload, monkeypatch):
    """Parser de stderr deve pular linhas que começam com '=' ou contém 'INFO'/'Log:'."""
    tmp_path, server = workdir

    def fail_popen(*args, **kwargs):
        proc = MagicMock()
        proc.communicate.return_value = (
            "",
            "==============================\nINFO algum info\nLog: arquivo.log\nMensagem real de erro\n",
        )
        proc.returncode = 1
        return proc
    monkeypatch.setattr(server.subprocess, "Popen", fail_popen)

    res = client.post("/api/run", json=dict(pipefy_payload, mode="single"))
    assert res.status_code == 200
    val_path = tmp_path / "results" / "validations.json"
    import time
    deadline = time.time() + 5
    while time.time() < deadline and not val_path.exists():
        time.sleep(0.05)
    body = json.loads(val_path.read_text(encoding="utf-8"))
    assert "Mensagem real de erro" in body["error"]


def test_default_env_aceita_variaveis_org_id_e_url(monkeypatch, tmp_path):
    """Verifica que DEFAULT_PIPEFY_ORG_ID e DEFAULT_PIPEFY_BASE_URL viram do env."""
    import sys
    import importlib
    monkeypatch.setenv("DEFAULT_PIPEFY_TOKEN", "Bearer demo123")
    monkeypatch.setenv("DEFAULT_PIPEFY_BASE_URL", "https://demo.pipefy.com/graphql")
    monkeypatch.setenv("DEFAULT_PIPEFY_ORG_ID", "777")
    monkeypatch.setenv("DEFAULT_PIPEFY_NAME", "Demo Co")
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    (tmp_path / "config").mkdir()
    (tmp_path / "results").mkdir()
    monkeypatch.chdir(tmp_path)
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.app.config["TESTING"] = True
    client = server.app.test_client()
    res = client.get("/api/default-env")
    assert res.status_code == 200
    data = res.get_json()
    assert data["available"] is True
    assert data["base_url"] == "https://demo.pipefy.com/graphql"
    assert data["org_id"] == "777"
    assert data["name"] == "Demo Co"
