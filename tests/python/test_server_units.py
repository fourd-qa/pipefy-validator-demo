"""Testes unitários das funções puras do server.py.

Cobre as funções que não fazem subprocess/IO de rede e podem ser testadas isoladamente.
"""
import json


# ---------- _normalize_token ----------

def test_normalize_token_adiciona_prefixo_bearer(workdir):
    _, server = workdir
    assert server._normalize_token("xyz789") == "Bearer xyz789"


def test_normalize_token_preserva_prefixo_existente(workdir):
    _, server = workdir
    assert server._normalize_token("Bearer xyz789") == "Bearer xyz789"


def test_normalize_token_case_insensitive_no_prefixo(workdir):
    _, server = workdir
    # Aceita BEARER, bearer, Bearer; sempre normaliza pra "Bearer xyz"
    assert server._normalize_token("bearer xyz") == "Bearer xyz"


def test_normalize_token_vazio_retorna_vazio(workdir):
    _, server = workdir
    assert server._normalize_token("") == ""
    assert server._normalize_token(None) == ""


# ---------- _escape_robot_value ----------

def test_escape_robot_remove_quebras_de_linha(workdir):
    _, server = workdir
    assert server._escape_robot_value("a\nb\rc") == "a b c"


def test_escape_robot_aceita_none(workdir):
    _, server = workdir
    assert server._escape_robot_value(None) == ""


# ---------- _extract_pipefy_creds ----------

def _basic_pipefy_payload():
    return {
        "token": "Bearer abcdef",
        "base_url": "https://api.pipefy.com/graphql",
        "org_id": "999",
        "auth_mode": "bearer",
        "verify_ssl": False,
    }


def test_extract_pipefy_creds_retorna_dict_quando_completo(workdir):
    _, server = workdir
    creds = server._extract_pipefy_creds(_basic_pipefy_payload())
    assert creds["token"] == "Bearer abcdef"
    assert creds["base_url"] == "https://api.pipefy.com/graphql"
    assert creds["org_id"] == "999"
    assert creds["verify_ssl"] == "false"


def test_extract_pipefy_creds_retorna_none_sem_token(workdir):
    _, server = workdir
    payload = _basic_pipefy_payload()
    payload.pop("token")
    assert server._extract_pipefy_creds(payload) is None


def test_extract_pipefy_creds_retorna_none_sem_base_url(workdir):
    _, server = workdir
    payload = _basic_pipefy_payload()
    payload.pop("base_url")
    assert server._extract_pipefy_creds(payload) is None


def test_extract_pipefy_creds_aceita_prefixo_src(workdir):
    _, server = workdir
    payload = {
        "src_token": "tok123",
        "src_base_url": "https://src.pipefy.com/graphql",
        "src_org_id": "1",
    }
    creds = server._extract_pipefy_creds(payload, prefix="src_")
    assert creds is not None
    assert creds["token"] == "Bearer tok123"
    assert creds["base_url"] == "https://src.pipefy.com/graphql"


def test_extract_pipefy_creds_normaliza_token(workdir):
    _, server = workdir
    payload = _basic_pipefy_payload()
    payload["token"] = "rawtoken"
    creds = server._extract_pipefy_creds(payload)
    assert creds["token"] == "Bearer rawtoken"


# ---------- _extract_ipaas_creds ----------

def test_extract_ipaas_creds_retorna_dict_quando_completo(workdir):
    _, server = workdir
    payload = {
        "ipaas_token": "Bearer ipaas_xyz",
        "ipaas_base_url": "https://ipaas.pipefy.com/api/v1",
        "ipaas_project_id": "p1",
    }
    creds = server._extract_ipaas_creds(payload)
    assert creds["token"] == "Bearer ipaas_xyz"
    assert creds["project_id"] == "p1"


def test_extract_ipaas_creds_retorna_none_sem_token(workdir):
    _, server = workdir
    payload = {"ipaas_base_url": "https://ipaas.pipefy.com/api/v1"}
    assert server._extract_ipaas_creds(payload) is None


# ---------- _generate_robot ----------

def test_generate_robot_inclui_token_e_uuids(workdir):
    _, server = workdir
    creds = server._extract_pipefy_creds(_basic_pipefy_payload())
    data = {"pipe_origem_uuid": "u-orig", "pipe_destino_uuid": "u-dest",
            "pipe_origem_repo_id": "111", "pipe_destino_repo_id": "222"}
    robot = server._generate_robot(creds, data)
    assert "${PIPEFY_TOKEN}         Bearer abcdef" in robot
    assert "${PIPE_ORIGEM_UUID}     u-orig" in robot
    assert "${PIPE_DESTINO_UUID}    u-dest" in robot
    assert "${PIPE_ORIGEM_REPO_ID}      111" in robot
    assert "${PIPE_DESTINO_REPO_ID}     222" in robot


def test_generate_robot_verify_ssl_false_quando_payload_diz_false(workdir):
    _, server = workdir
    creds = server._extract_pipefy_creds(_basic_pipefy_payload())
    robot = server._generate_robot(creds, {})
    assert "${VERIFY_SSL}           false" in robot


def test_generate_robot_aceita_data_sem_pipes(workdir):
    _, server = workdir
    creds = server._extract_pipefy_creds(_basic_pipefy_payload())
    robot = server._generate_robot(creds, {})
    # Não estoura, gera defaults vazios pra UUID e REPO_ID
    assert "${PIPE_ORIGEM_UUID}" in robot
    assert "${PIPE_DESTINO_UUID}" in robot


# ---------- _generate_ipaas_robot ----------

def test_generate_ipaas_robot_inclui_token_e_project_id(workdir):
    _, server = workdir
    creds = server._extract_ipaas_creds({
        "ipaas_token": "Bearer ipaas_xyz",
        "ipaas_base_url": "https://ipaas.pipefy.com/api/v1",
        "ipaas_project_id": "proj_123",
    })
    robot = server._generate_ipaas_robot(creds)
    assert "${IPAAS_TOKEN}           Bearer ipaas_xyz" in robot
    assert "${IPAAS_PROJECT_ID}      proj_123" in robot
    assert "${IPAAS_BASE_URL}       https://ipaas.pipefy.com/api/v1" in robot


# ---------- _generate_cross_robot_runtime ----------

def test_generate_cross_robot_inclui_dois_tokens(workdir):
    _, server = workdir
    src = server._extract_pipefy_creds({
        "token": "src_tok", "base_url": "https://src.pipefy.com/graphql",
    })
    dst = server._extract_pipefy_creds({
        "token": "dst_tok", "base_url": "https://dst.pipefy.com/graphql",
    })
    data = {"pipe_origem_uuid": "u1", "pipe_destino_uuid": "u2"}
    robot = server._generate_cross_robot_runtime(src, dst, data)
    assert "${ORIGEM_PIPEFY_TOKEN}         Bearer src_tok" in robot
    assert "${DESTINO_PIPEFY_TOKEN}        Bearer dst_tok" in robot
    assert "${PIPE_ORIGEM_UUID}            u1" in robot
    assert "${PIPE_DESTINO_UUID}           u2" in robot


# ---------- _extract_fail_from_output_xml ----------

def _write_output_xml(workdir, content):
    tmp_path, server = workdir
    path = tmp_path / "results" / "output.xml"
    path.write_text(content, encoding="utf-8")
    return path


def test_extract_fail_retorna_vazio_quando_sem_output_xml(workdir):
    _, server = workdir
    msg, hint = server._extract_fail_from_output_xml()
    assert msg == ""
    assert hint == ""


def test_extract_fail_pega_primeira_mensagem_fail(workdir):
    _, server = workdir
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<robot>
  <kw name="Test">
    <msg level="INFO">apenas info</msg>
    <msg level="FAIL">HTTPError: 401 Client Error: Unauthorized for url</msg>
  </kw>
</robot>"""
    _write_output_xml(workdir, xml)
    msg, hint = server._extract_fail_from_output_xml()
    assert "401" in msg
    assert "Token" in hint


def test_extract_fail_detecta_permission_denied(workdir):
    _, server = workdir
    xml = """<?xml version="1.0"?>
<robot>
  <msg level="FAIL">GraphQL retornou erro: PERMISSION_DENIED Acesso negado ao pipe</msg>
</robot>"""
    _write_output_xml(workdir, xml)
    msg, hint = server._extract_fail_from_output_xml()
    assert "PERMISSION_DENIED" in msg
    assert "permissão" in hint.lower() or "permis" in hint.lower()


def test_extract_fail_detecta_404(workdir):
    _, server = workdir
    xml = """<?xml version="1.0"?>
<robot>
  <msg level="FAIL">HTTP 404 Not Found ao buscar pipe</msg>
</robot>"""
    _write_output_xml(workdir, xml)
    msg, hint = server._extract_fail_from_output_xml()
    assert "404" in msg
    assert "não encontrado" in hint.lower() or "nao encontrado" in hint.lower()


def test_extract_fail_detecta_timeout(workdir):
    _, server = workdir
    xml = """<?xml version="1.0"?>
<robot>
  <msg level="FAIL">Connection timed out after 30s</msg>
</robot>"""
    _write_output_xml(workdir, xml)
    msg, hint = server._extract_fail_from_output_xml()
    assert "timed out" in msg.lower() or "timeout" in msg.lower()
    assert hint


def test_extract_fail_sem_msg_fail_retorna_vazio(workdir):
    _, server = workdir
    xml = """<?xml version="1.0"?>
<robot>
  <msg level="INFO">tudo certo</msg>
  <msg level="WARN">aviso menor</msg>
</robot>"""
    _write_output_xml(workdir, xml)
    msg, hint = server._extract_fail_from_output_xml()
    assert msg == ""
    assert hint == ""


def test_extract_fail_trunca_msg_longa(workdir):
    _, server = workdir
    longa = "X" * 1500
    xml = f"""<?xml version="1.0"?>
<robot><msg level="FAIL">{longa}</msg></robot>"""
    _write_output_xml(workdir, xml)
    msg, _hint = server._extract_fail_from_output_xml()
    assert len(msg) <= 600
