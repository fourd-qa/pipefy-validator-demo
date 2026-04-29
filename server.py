"""
Pipefy Validator — Web Server
Serve o dashboard e executa Robot Framework via API.

Tokens são client-side: cada usuário cola seu Bearer no navegador, frontend manda
no body de /api/run. Backend nunca persiste credenciais. Cada run gera um .robot
descartável em tmp/<run_id>/ e remove no fim.
"""
import base64
import json
import os
import shutil
import subprocess
import threading
import time
import glob
from functools import wraps
from flask import Flask, send_from_directory, jsonify, request, redirect, Response

app = Flask(__name__, static_folder="web")

RESULTS_DIR = os.path.join(os.getcwd(), "results")
CONFIG_DIR = os.path.join(os.getcwd(), "config")
TMP_DIR = os.path.join(os.getcwd(), "tmp")
PROGRESS_FILE = os.path.join(RESULTS_DIR, "progress.json")
LOG_FILE = os.path.join(RESULTS_DIR, "console.log")
VALIDATION_FILE = os.path.join(RESULTS_DIR, "validations.json")
IPAAS_VALIDATION_FILE = os.path.join(RESULTS_DIR, "ipaas_validations.json")
OUTPUT_XML = os.path.join(RESULTS_DIR, "output.xml")

APP_PASSWORD = os.environ.get("APP_PASSWORD", "").strip()
APP_USERNAME = os.environ.get("APP_USERNAME", "demo").strip() or "demo"


def _check_basic_auth():
    """Se APP_PASSWORD estiver setada, exige Basic Auth em todas as rotas exceto
    /healthz. Sem APP_PASSWORD = modo dev liberado.

    Retorna None se ok, ou Response 401 se falhou.
    """
    if not APP_PASSWORD:
        return None
    if request.path == "/healthz":
        return None
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return _auth_challenge()
    try:
        decoded = base64.b64decode(auth[6:]).decode("utf-8", errors="replace")
        user, _, pw = decoded.partition(":")
    except Exception:
        return _auth_challenge()
    if user != APP_USERNAME or pw != APP_PASSWORD:
        return _auth_challenge()
    return None


def _auth_challenge():
    return Response(
        json.dumps({"error": "Autenticação necessária"}),
        status=401,
        mimetype="application/json",
        headers={"WWW-Authenticate": 'Basic realm="Pipefy Validator"'},
    )


@app.before_request
def _global_auth():
    return _check_basic_auth()


@app.route("/healthz")
def healthz():
    """Liveness probe pra Render/K8s. Não exige Basic Auth."""
    return jsonify({"ok": True})


def _extract_fail_from_output_xml():
    """Lê o output.xml do Robot e extrai a primeira mensagem com level=FAIL.
    Retorna (msg, hint) onde hint é uma sugestão amigável (ex: token expirado)."""
    if not os.path.exists(OUTPUT_XML):
        return ("", "")
    try:
        import xml.etree.ElementTree as ET
        # Robot output.xml pode ser grande; iterparse pra eficiência
        for _, elem in ET.iterparse(OUTPUT_XML, events=("end",)):
            if elem.tag == "msg" and elem.get("level") == "FAIL":
                text = (elem.text or "").strip()
                if text:
                    hint = ""
                    low = text.lower()
                    if "401" in text or "unauthorized" in low:
                        hint = "Token de autenticação inválido ou expirado. Renove o token em Configuração > Gerenciar Ambientes."
                    elif "permission_denied" in low or "acesso negado" in low:
                        hint = "Token não tem permissão pra acessar este pipe/projeto. Verifique escopo do PAT."
                    elif "404" in text or "not found" in low:
                        hint = "Recurso não encontrado. Verifique UUID do pipe ou ID do projeto."
                    elif "timeout" in low or "timed out" in low:
                        hint = "Timeout de rede. Verifique proxy corporativo e VERIFY_SSL."
                    return (text[:600], hint)
            if elem.tag == "msg":
                elem.clear()
    except Exception:
        pass
    return ("", "")


def _pipe_override_vars(data):
    """Constrói lista de --variable PIPE_*_UUID/REPO_ID a partir do payload.
    Sobrescreve valores defaultados pelo .robot gerado em tmp/."""
    extras = []
    pairs = (
        ("pipe_origem_uuid",  "PIPE_ORIGEM_UUID"),
        ("pipe_destino_uuid", "PIPE_DESTINO_UUID"),
        ("pipe_origem_repo_id",  "PIPE_ORIGEM_REPO_ID"),
        ("pipe_destino_repo_id", "PIPE_DESTINO_REPO_ID"),
    )
    for payload_key, robot_var in pairs:
        val = str(data.get(payload_key) or "").strip()
        if val:
            extras += ["--variable", f"{robot_var}:{val}"]
    return extras + _categories_var(data)


def _normalize_token(raw):
    """Aceita 'Bearer xxx' ou só 'xxx', retorna sempre 'Bearer xxx'."""
    s = str(raw or "").strip()
    if not s:
        return ""
    if s.lower().startswith("bearer "):
        return "Bearer " + s.split(" ", 1)[1].strip()
    return "Bearer " + s


def _escape_robot_value(s):
    """Escapa valor pra .robot Variables. Robot interpreta ${} mas aspas/quebras
    podem quebrar parsing. Como Variables é assignment estilo k=v simples, basta
    rejeitar caracteres de controle e remover quebras de linha."""
    return str(s or "").replace("\r", " ").replace("\n", " ").strip()


def _extract_pipefy_creds(data, prefix=""):
    """Extrai credenciais Pipefy do body. prefix='' pra single/snapshot/batch,
    'src_'/'dst_' pra cross. Retorna dict ou None se token vazio."""
    p = prefix
    token_raw = data.get(p + "token") or data.get(p + "pipefy_token")
    base_url = data.get(p + "base_url") or data.get(p + "pipefy_base_url")
    org_id = data.get(p + "org_id") or data.get(p + "pipefy_org_id") or ""
    auth_mode = data.get(p + "auth_mode") or "bearer"
    verify_ssl = data.get(p + "verify_ssl")
    session_cookie = data.get(p + "session_cookie") or "NONE"
    csrf_token = data.get(p + "csrf_token") or "NONE"
    if not token_raw or not base_url:
        return None
    return {
        "token": _normalize_token(token_raw),
        "base_url": _escape_robot_value(base_url),
        "org_id": _escape_robot_value(org_id),
        "auth_mode": _escape_robot_value(auth_mode),
        "verify_ssl": "true" if verify_ssl else "false",
        "session_cookie": _escape_robot_value(session_cookie),
        "csrf_token": _escape_robot_value(csrf_token),
    }


def _extract_ipaas_creds(data):
    """Extrai credenciais iPaaS do body. Retorna dict ou None se ausente."""
    token_raw = data.get("ipaas_token") or data.get("token")
    base_url = data.get("ipaas_base_url") or data.get("base_url")
    project_id = data.get("ipaas_project_id") or data.get("project_id") or ""
    verify_ssl = data.get("ipaas_verify_ssl") or data.get("verify_ssl")
    if not token_raw or not base_url:
        return None
    return {
        "token": _normalize_token(token_raw),
        "base_url": _escape_robot_value(base_url),
        "project_id": _escape_robot_value(project_id),
        "verify_ssl": "true" if verify_ssl else "false",
    }


def _build_pipe_lines(data, prefix_origem="PIPE_ORIGEM", prefix_destino="PIPE_DESTINO"):
    """Linhas Variables pra UUIDs/repo_id default. Override real vem via
    --variable do _pipe_override_vars()."""
    return (
        f"${{{prefix_origem}_UUID}}     {_escape_robot_value(data.get('pipe_origem_uuid', ''))}\n"
        f"${{{prefix_destino}_UUID}}    {_escape_robot_value(data.get('pipe_destino_uuid', ''))}\n"
        f"${{{prefix_origem}_REPO_ID}}      {_escape_robot_value(data.get('pipe_origem_repo_id', ''))}\n"
        f"${{{prefix_destino}_REPO_ID}}     {_escape_robot_value(data.get('pipe_destino_repo_id', ''))}\n"
    )


def _categories_var(data):
    """Converte lista categories[] do payload em --variable CATEGORIES_FILTER:CSV.
    Robot keywords pulam categorias não listadas. Vazio = todas.
    Aceita tags Pipefy (SF, FA, LB, AS, AD, AH, AC) e iPaaS (IF, IT, IS).
    Quando todas as tags do dominio estao selecionadas, omite o filtro."""
    cats = data.get("categories")
    if not isinstance(cats, list) or not cats:
        return []
    pipefy = {"SF", "FA", "LB", "AS", "AD", "AH", "AC"}
    ipaas = {"IF", "IT", "IS"}
    filtered = [c for c in cats if c in pipefy or c in ipaas]
    if not filtered:
        return []
    pipefy_sel = [c for c in filtered if c in pipefy]
    ipaas_sel = [c for c in filtered if c in ipaas]
    # Se todas do domínio enviado estão selecionadas, equivale a sem filtro
    is_full_pipefy = pipefy_sel and len(pipefy_sel) == len(pipefy)
    is_full_ipaas = ipaas_sel and len(ipaas_sel) == len(ipaas)
    if (is_full_pipefy and not ipaas_sel) or (is_full_ipaas and not pipefy_sel):
        return []
    return ["--variable", "CATEGORIES_FILTER:" + ",".join(filtered)]


def _generate_robot(creds, data):
    """Gera conteudo .robot pra single-env a partir de credenciais e payload.
    creds vem de _extract_pipefy_creds(); data é o request body completo."""
    return (
        "*** Variables ***\n"
        "# Auto-generated for this run (token vem do client, descartado no fim)\n"
        f"${{AUTH_MODE}}            {creds['auth_mode']}\n"
        f"${{PIPEFY_BASE_URL}}      {creds['base_url']}\n"
        f"${{VERIFY_SSL}}           {creds['verify_ssl']}\n"
        f"${{PIPEFY_TOKEN}}         {creds['token']}\n"
        f"${{PIPEFY_SESSION_COOKIE}}    {creds['session_cookie']}\n"
        f"${{PIPEFY_CSRF_TOKEN}}        {creds['csrf_token']}\n"
        f"${{ORGANIZATION_ID}}      {creds['org_id']}\n"
        + _build_pipe_lines(data)
    )


def _generate_cross_robot_runtime(src_creds, dst_creds, data):
    """Gera conteudo .robot pra cross-env (2 sets de credenciais)."""
    return (
        "*** Variables ***\n"
        "# Auto-generated cross-env run\n"
        f"${{ORIGEM_AUTH_MODE}}            {src_creds['auth_mode']}\n"
        f"${{ORIGEM_PIPEFY_BASE_URL}}      {src_creds['base_url']}\n"
        f"${{ORIGEM_PIPEFY_TOKEN}}         {src_creds['token']}\n"
        f"${{ORIGEM_SESSION_COOKIE}}       {src_creds['session_cookie']}\n"
        f"${{ORIGEM_CSRF_TOKEN}}           {src_creds['csrf_token']}\n"
        f"${{ORIGEM_ORG_ID}}               {src_creds['org_id']}\n"
        f"${{PIPE_ORIGEM_UUID}}            {_escape_robot_value(data.get('pipe_origem_uuid', ''))}\n"
        f"${{PIPE_ORIGEM_REPO_ID}}         {_escape_robot_value(data.get('pipe_origem_repo_id', ''))}\n"
        f"${{DESTINO_AUTH_MODE}}           {dst_creds['auth_mode']}\n"
        f"${{DESTINO_PIPEFY_BASE_URL}}     {dst_creds['base_url']}\n"
        f"${{DESTINO_PIPEFY_TOKEN}}        {dst_creds['token']}\n"
        f"${{DESTINO_SESSION_COOKIE}}      {dst_creds['session_cookie']}\n"
        f"${{DESTINO_CSRF_TOKEN}}          {dst_creds['csrf_token']}\n"
        f"${{DESTINO_ORG_ID}}              {dst_creds['org_id']}\n"
        f"${{PIPE_DESTINO_UUID}}           {_escape_robot_value(data.get('pipe_destino_uuid', ''))}\n"
        f"${{PIPE_DESTINO_REPO_ID}}        {_escape_robot_value(data.get('pipe_destino_repo_id', ''))}\n"
        f"${{VERIFY_SSL}}                  {src_creds['verify_ssl']}\n"
    )


def _generate_ipaas_robot(creds):
    """Gera conteudo .robot para iPaaS a partir de credenciais."""
    return (
        "*** Variables ***\n"
        "# Auto-generated iPaaS run\n"
        f"${{IPAAS_BASE_URL}}       {creds['base_url']}\n"
        f"${{IPAAS_TOKEN}}           {creds['token']}\n"
        f"${{IPAAS_PROJECT_ID}}      {creds['project_id']}\n"
        f"${{VERIFY_SSL}}            {creds['verify_ssl']}\n"
    )


def _make_run_dir(run_id):
    """Cria tmp/<run_id>/ pra esta run. Retorna path absoluto."""
    d = os.path.join(TMP_DIR, run_id)
    os.makedirs(d, exist_ok=True)
    return d


def _cleanup_run_dir(run_dir):
    """Remove tmp/<run_id>/ silenciosamente."""
    if run_dir and os.path.isdir(run_dir):
        try:
            shutil.rmtree(run_dir)
        except OSError:
            pass

# Estado global
_state = {
    "running": False,
    "finished": False,
    "exit_code": None,
    "started_at": None,
    "finished_at": None,      # wall clock quando terminou (pra calcular elapsed_final)
    "elapsed_final": None,    # duração total em segundos (None enquanto rodando)
    "mode": None,             # modo solicitado (single/cross/snapshot/batch/ipaas)
    "config": None,           # config selecionada no POST
    "run_id": None,           # ID gerado no POST pra UI correlacionar
    "process": None,          # Popen do subprocess Robot (pra cancel real)
    "cancelled": False,       # True quando o usuário cancelou via /api/run/cancel
}


@app.route("/")
def index():
    return redirect("/v2/configuracao", code=302)


@app.route("/v2")
@app.route("/v2/")
@app.route("/v2/resultados")
def index_v2():
    """Preview do novo design da tela de Resultados (mock estático, sem API)."""
    return send_from_directory("web/designs", "tela_resultados_v1.html")


@app.route("/v2/execucao")
def index_v2_execucao():
    """Preview do novo design da tela de Execução (mock animado, sem API)."""
    return send_from_directory("web/designs", "tela_execucao_v1.html")


@app.route("/v2/configuracao")
@app.route("/v2/config")
def index_v2_configuracao():
    """Preview do novo design da tela de Configuração (5 modos + modal de ambientes)."""
    return send_from_directory("web/designs", "tela_configuracao_v1.html")


@app.route("/v2/docs")
def index_v2_docs():
    """Documentação estilo Confluence."""
    return send_from_directory("web/designs", "docs.html")


@app.route("/v2/help")
def index_v2_help():
    """Página de ajuda: atalhos, FAQ, como reportar bug, contatos."""
    return send_from_directory("web/designs", "help.html")


@app.route("/v2/assets/<path:filename>")
def v2_assets(filename):
    """Serve CSS/JS externos das telas V2 (no-cache pra desenvolvimento)."""
    resp = send_from_directory("web/designs/assets", filename)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/reports/<path:filename>")
def serve_report(filename):
    """Serve arquivos de relatório do Robot Framework (log.html, report.html)."""
    return send_from_directory(RESULTS_DIR, filename)


PROPOSALS_DIR = os.path.join(os.getcwd(), "proposals")


@app.route("/proposals/")
@app.route("/proposals")
def proposals_index():
    """Lista as iterações de design disponíveis em proposals/.
    Cada subdiretório vira um card com seus arquivos HTML pra comparar com o V2 atual."""
    iterations = []
    if os.path.isdir(PROPOSALS_DIR):
        for entry in sorted(os.listdir(PROPOSALS_DIR), reverse=True):
            sub = os.path.join(PROPOSALS_DIR, entry)
            if not os.path.isdir(sub) or entry.startswith("."):
                continue
            files = []
            for root, _dirs, names in os.walk(sub):
                for n in names:
                    rel = os.path.relpath(os.path.join(root, n), sub).replace("\\", "/")
                    if n.lower().endswith((".html", ".htm", ".png", ".jpg", ".jpeg", ".pdf", ".md")):
                        files.append(rel)
            iterations.append({"id": entry, "files": sorted(files)})

    cards = []
    for it in iterations:
        html_files = [f for f in it["files"] if f.endswith((".html", ".htm"))]
        other_files = [f for f in it["files"] if not f.endswith((".html", ".htm"))]
        links_html = "".join(
            f'<li><a href="/proposals/{it["id"]}/{f}" target="_blank">{f}</a></li>'
            for f in html_files
        ) or '<li style="color:#8089a0;font-style:italic">Sem HTML nessa iteração</li>'
        others = ""
        if other_files:
            others = '<div style="margin-top:10px;color:#8089a0;font-size:11.5px">Outros arquivos: ' + ", ".join(
                f'<a href="/proposals/{it["id"]}/{f}" target="_blank" style="color:#c9a84c">{f}</a>'
                for f in other_files
            ) + '</div>'
        cards.append(
            f'<div style="padding:18px 22px;border:1px solid rgba(255,255,255,.1);border-radius:10px;background:#0f1424;margin-bottom:14px">'
            f'<div style="font-size:14px;font-weight:600;color:#e9ecf3;margin-bottom:10px;font-family:JetBrains Mono,monospace">{it["id"]}</div>'
            f'<ul style="margin:0;padding-left:20px;color:#c5cad6;font-size:12.5px;line-height:1.8">{links_html}</ul>'
            f'{others}'
            f'</div>'
        )

    if not iterations:
        body = (
            '<div style="padding:40px 28px;text-align:center;color:#8089a0;font-size:13px;line-height:1.6">'
            '<div style="font-size:32px;margin-bottom:12px">📐</div>'
            '<div style="color:#e9ecf3;font-size:14px;font-weight:500;margin-bottom:8px">Sem propostas ainda</div>'
            '<div>Crie uma subpasta em <code style="font-family:JetBrains Mono,monospace;color:#c9a84c">proposals/YYYY-MM-DD_label/</code> e dropa os arquivos do designer lá.</div>'
            '<div style="margin-top:14px"><a href="/proposals/README.md" target="_blank" style="color:#c9a84c">Ver README com convenções</a></div>'
            '</div>'
        )
    else:
        body = "".join(cards)

    html = (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<title>Propostas de Design · Pipefy Validator</title>'
        '<style>'
        'body{margin:0;padding:0;background:#0b0f1a;color:#e9ecf3;font-family:Inter,-apple-system,sans-serif;font-size:14px;line-height:1.6}'
        'header{padding:18px 28px;border-bottom:1px solid rgba(255,255,255,.06);background:#0f1424;display:flex;align-items:center;justify-content:space-between}'
        '.brand{display:flex;align-items:center;gap:10px}'
        '.mark{width:28px;height:28px;border-radius:6px;background:linear-gradient(135deg,#c9a84c,#8a6f1e);display:flex;align-items:center;justify-content:center;color:#0b0f1a;font-weight:700;font-size:14px}'
        'a{color:#c9a84c;text-decoration:none}a:hover{text-decoration:underline}'
        '.back{padding:6px 12px;border-radius:6px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.1);color:#c5cad6;font-size:12px}'
        '.back:hover{background:rgba(201,168,76,.08);color:#c9a84c;border-color:rgba(201,168,76,.3);text-decoration:none}'
        'main{max-width:780px;margin:0 auto;padding:32px 28px 60px}'
        'h1{font-size:24px;font-weight:600;letter-spacing:-.02em;margin:0 0 8px}'
        '.lead{color:#8089a0;font-size:14px;margin:0 0 32px}'
        '</style></head><body>'
        '<header><div class="brand"><div class="mark">P</div><div><b>Pipefy Validator</b> <span style="color:#8089a0">· propostas de design</span></div></div>'
        '<a href="/v2/configuracao" class="back">Voltar pro app</a></header>'
        '<main>'
        '<h1>Iterações de design</h1>'
        '<p class="lead">Compare visualmente as propostas do designer com o V2 atual. '
        'Cada iteração é uma subpasta em <code style="font-family:JetBrains Mono,monospace;color:#c9a84c">proposals/</code> (volume mount, reflete sem rebuild).</p>'
        + body +
        '</main></body></html>'
    )
    return html


@app.route("/proposals/<path:filename>")
def serve_proposal(filename):
    """Serve arquivos da pasta proposals/ (HTML, imagens, MD)."""
    return send_from_directory(PROPOSALS_DIR, filename)


@app.route("/api/configs")
def list_configs():
    """Lista os configs disponíveis. Tokens são client-side, então essa rota
    sempre retorna vazia. Frontend deve listar envs do localStorage."""
    return jsonify({"single": [], "cross": []})


@app.route("/api/configs", methods=["POST"])
def create_cross_config_deprecated():
    """Cross configs viraram client-side (localStorage). Endpoint mantido pra
    retornar 410 e indicar caminho atual."""
    return jsonify({
        "deprecated": True,
        "message": "Cross configs agora são salvos no localStorage do frontend.",
    }), 410


@app.route("/api/batch")
def list_batch():
    """Retorna os pares de pipes configurados em batch_pipes.json."""
    path = os.path.join(CONFIG_DIR, "batch_pipes.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return jsonify(json.load(f))
        except (json.JSONDecodeError, IOError) as e:
            return jsonify({"error": str(e), "pipes": []}), 500
    return jsonify({"pipes": []})


@app.route("/api/snapshots")
def list_snapshots():
    """Lista snapshots disponíveis no volume."""
    snap_dir = os.path.join(os.getcwd(), "snapshots")
    snaps = []
    if os.path.isdir(snap_dir):
        for f in sorted(glob.glob(os.path.join(snap_dir, "*.json")), reverse=True):
            name = os.path.basename(f)
            size = os.path.getsize(f)
            # Tenta extrair metadata
            try:
                with open(f) as fh:
                    data = json.load(fh)
                pipe_name = data.get("pipe", {}).get("name", "") or data.get("label", "")
                total_auto = len(data.get("automations", []))
                total_flows = data.get("total_flows", 0)
                ts = data.get("metadata", {}).get("timestamp", "") or data.get("timestamp", "")
            except Exception:
                pipe_name = ""
                total_auto = 0
                total_flows = 0
                ts = ""
            is_ipaas = "ipaas" in name.lower() or total_flows > 0
            snaps.append({
                "file": f"snapshots/{name}",
                "name": name,
                "pipe_name": pipe_name,
                "automacoes": total_auto,
                "total_flows": total_flows,
                "timestamp": ts,
                "size_kb": round(size / 1024, 1),
                "is_ipaas": is_ipaas,
            })
    return jsonify(snaps)


@app.route("/api/environments")
@app.route("/api/v2/environments")
def get_environments_deprecated():
    """Endpoints legacy de ambientes. Removidos: tokens são client-side agora."""
    return jsonify({
        "deprecated": True,
        "message": "Tokens são client-side. Use localStorage no frontend.",
        "pipefy": [],
        "ipaas": [],
    }), 410


@app.route("/api/environments", methods=["POST"])
@app.route("/api/environments/<path:_>", methods=["DELETE"])
def env_write_deprecated(_=None):
    return jsonify({
        "deprecated": True,
        "message": "Tokens são client-side, salvos no localStorage do navegador.",
    }), 410


_STERILE_PIPEFY_ROBOT = (
    "*** Variables ***\n"
    "# sterilized after run (token client-side, descartado)\n"
    "${AUTH_MODE}            bearer\n"
    "${PIPEFY_BASE_URL}      \n"
    "${VERIFY_SSL}           false\n"
    "${PIPEFY_TOKEN}         \n"
    "${PIPEFY_SESSION_COOKIE}    NONE\n"
    "${PIPEFY_CSRF_TOKEN}        NONE\n"
    "${ORGANIZATION_ID}      \n"
    "${PIPE_ORIGEM_UUID}     \n"
    "${PIPE_DESTINO_UUID}    \n"
    "${PIPE_ORIGEM_REPO_ID}      \n"
    "${PIPE_DESTINO_REPO_ID}     \n"
)

_STERILE_CROSS_ROBOT = (
    "*** Variables ***\n"
    "# sterilized after run (tokens client-side, descartados)\n"
    "${ORIGEM_AUTH_MODE}            bearer\n"
    "${ORIGEM_PIPEFY_BASE_URL}      \n"
    "${ORIGEM_PIPEFY_TOKEN}         \n"
    "${ORIGEM_SESSION_COOKIE}       NONE\n"
    "${ORIGEM_CSRF_TOKEN}           NONE\n"
    "${ORIGEM_ORG_ID}               \n"
    "${PIPE_ORIGEM_UUID}            \n"
    "${PIPE_ORIGEM_REPO_ID}         \n"
    "${DESTINO_AUTH_MODE}           bearer\n"
    "${DESTINO_PIPEFY_BASE_URL}     \n"
    "${DESTINO_PIPEFY_TOKEN}        \n"
    "${DESTINO_SESSION_COOKIE}      NONE\n"
    "${DESTINO_CSRF_TOKEN}          NONE\n"
    "${DESTINO_ORG_ID}              \n"
    "${PIPE_DESTINO_UUID}           \n"
    "${PIPE_DESTINO_REPO_ID}        \n"
    "${VERIFY_SSL}                  false\n"
)

_STERILE_IPAAS_ROBOT = (
    "*** Variables ***\n"
    "# sterilized after run\n"
    "${IPAAS_BASE_URL}       \n"
    "${IPAAS_TOKEN}           \n"
    "${IPAAS_PROJECT_ID}      \n"
    "${VERIFY_SSL}            false\n"
)


def _sterilize_active_robots():
    """Após run terminar, sobrescreve config/active.robot etc com placeholders
    sem token. Reduz risco de leak via leitura do filesystem."""
    pairs = (
        (os.path.join(CONFIG_DIR, "active.robot"), _STERILE_PIPEFY_ROBOT),
        (os.path.join(CONFIG_DIR, "active_cross.robot"), _STERILE_CROSS_ROBOT),
        (os.path.join(CONFIG_DIR, "ipaas_fourd.robot"), _STERILE_IPAAS_ROBOT),
    )
    for path, content in pairs:
        if os.path.exists(path):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
            except IOError:
                pass


@app.route("/api/run", methods=["POST"])
def run_validation():
    """Inicia a validação. Credenciais vêm no body do request (client-side)."""
    if _state["running"]:
        return jsonify({"error": "Já existe uma validação em execução"}), 409

    raw = request.get_json(silent=True)
    data = raw if isinstance(raw, dict) else {}
    mode = data.get("mode", "single")
    test = data.get("test", "CT01*")

    # === VALIDA E EXTRAI CREDENCIAIS DO BODY ===
    creds = None
    src_creds = None
    dst_creds = None
    ipaas_creds = None
    if mode == "ipaas":
        ipaas_creds = _extract_ipaas_creds(data)
        if not ipaas_creds:
            return jsonify({"error": "Credenciais iPaaS obrigatórias: token + base_url"}), 400
    elif mode == "cross":
        src_creds = _extract_pipefy_creds(data, prefix="src_")
        dst_creds = _extract_pipefy_creds(data, prefix="dst_")
        if not src_creds or not dst_creds:
            return jsonify({"error": "Cross-env precisa src_token+src_base_url e dst_token+dst_base_url"}), 400
    elif mode == "healthcheck":
        # Healthcheck pode rodar sem token (testa só camadas internas)
        pass
    else:
        # single, snapshot, batch
        creds = _extract_pipefy_creds(data)
        if not creds:
            return jsonify({"error": "Credenciais Pipefy obrigatórias: token + base_url"}), 400

    # Limpa resultados anteriores
    for f in [PROGRESS_FILE, LOG_FILE, VALIDATION_FILE, IPAAS_VALIDATION_FILE]:
        if os.path.exists(f):
            os.remove(f)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)

    # === GERA .robot ATIVO COM CREDENCIAIS DO BODY ===
    # Robot tests importam via "Resource ../config/active.robot" (path estatico).
    # Mantemos esse contrato; arquivo é sobrescrito a cada run e esterilizado no fim.
    # TODO: pra deploy multi-user real, mover pra tmp/<run_id>/ + variabilizar Resource.
    if mode == "ipaas":
        with open(os.path.join(CONFIG_DIR, "ipaas_fourd.robot"), "w", encoding="utf-8") as f:
            f.write(_generate_ipaas_robot(ipaas_creds))
    elif mode == "cross":
        with open(os.path.join(CONFIG_DIR, "active_cross.robot"), "w", encoding="utf-8") as f:
            f.write(_generate_cross_robot_runtime(src_creds, dst_creds, data))
    elif mode == "healthcheck":
        # Healthcheck precisa active.robot existir mas pode estar zerado
        active_path = os.path.join(CONFIG_DIR, "active.robot")
        if not os.path.exists(active_path):
            with open(active_path, "w", encoding="utf-8") as f:
                f.write(_STERILE_PIPEFY_ROBOT)
    else:
        with open(os.path.join(CONFIG_DIR, "active.robot"), "w", encoding="utf-8") as f:
            f.write(_generate_robot(creds, data))

    # Determina a suite e variáveis extras
    extra_vars = []
    if mode == "cross":
        suite = "tests/comparar_cross.robot"
        test_filter = "CT-CROSS*"
        extra_vars = _pipe_override_vars(data)
    elif mode == "snapshot":
        suite = "tests/snapshot.robot"
        test_filter = test
        snap_mode = data.get("snapshot_mode", "create")
        if snap_mode == "create":
            label = data.get("label", "snapshot")
            extra_vars = ["--variable", f"SNAPSHOT_LABEL:{label}"]
            # Override opcional do pipe via --variable (início do A+).
            # Sobrescreve PIPE_ORIGEM_UUID/REPO_ID do config/*.robot ao vivo.
            pipe_uuid = (data.get("pipe_uuid") or "").strip()
            pipe_repo_id = str(data.get("pipe_repo_id") or "").strip()
            if pipe_uuid:
                extra_vars += ["--variable", f"PIPE_ORIGEM_UUID:{pipe_uuid}"]
            if pipe_repo_id:
                extra_vars += ["--variable", f"PIPE_ORIGEM_REPO_ID:{pipe_repo_id}"]
        else:
            snap_file = data.get("file", "")
            extra_vars = ["--variable", f"SNAPSHOT_FILE:{snap_file}"]
            # Pipe live alternativo no compare (override via --variable PIPE_DESTINO_*)
            pipe_uuid = (data.get("pipe_uuid") or "").strip()
            pipe_repo_id = str(data.get("pipe_repo_id") or "").strip()
            if pipe_uuid:
                extra_vars += ["--variable", f"PIPE_DESTINO_UUID:{pipe_uuid}"]
            if pipe_repo_id:
                extra_vars += ["--variable", f"PIPE_DESTINO_REPO_ID:{pipe_repo_id}"]
    elif mode == "batch":
        suite = "tests/batch.robot"
        test_filter = "CT-BATCH*"
        # batch_env opcional pra filtrar batch_pipes.json por env_id
        batch_env = (data.get("batch_env") or "").strip()
        if batch_env:
            extra_vars = ["--variable", f"BATCH_ENV:{batch_env}"]
        # A+: respeita seleção da UI via lista de UUIDs origem
        selected = data.get("pipes_selected")
        if isinstance(selected, list) and selected:
            csv = ",".join(str(s).strip() for s in selected if str(s).strip())
            if csv:
                extra_vars += ["--variable", f"BATCH_SELECTED:{csv}"]
        extra_vars += _categories_var(data)
    elif mode == "ipaas":
        suite = "tests/ipaas_validation.robot"
        test_filter = test or "CT-IPAAS-01*"
        if "CT-IPAAS-03" in test_filter:
            label = data.get("label", "ipaas_snapshot")
            extra_vars = ["--variable", f"IPAAS_SNAPSHOT_LABEL:{label}"]
        elif "CT-IPAAS-04" in test_filter:
            snap_file = data.get("file", "")
            extra_vars = ["--variable", f"IPAAS_SNAPSHOT_FILE:{snap_file}"]
        extra_vars += _categories_var(data)
    elif mode == "healthcheck":
        suite = "tests/healthcheck.robot"
        test_filter = "HC*"
        # Healthcheck só liga iPaaS se tiver creds no body
        if not _extract_ipaas_creds(data):
            extra_vars = ["--variable", "HC_IPAAS_ENABLED:false"]
    else:
        # mode = single (default)
        suite = "tests/comparar_pipes.robot"
        test_filter = test
        extra_vars = _pipe_override_vars(data)

    # Gera run_id curto (8 chars base36) pra UI correlacionar
    import uuid
    run_id = uuid.uuid4().hex[:8]

    # config virou metadata opcional (frontend manda label só pra trace)
    config = (data.get("config") or "").strip()

    _state["running"] = True
    _state["finished"] = False
    _state["exit_code"] = None
    _state["started_at"] = time.time()
    _state["finished_at"] = None
    _state["elapsed_final"] = None
    _state["mode"] = mode
    _state["config"] = config
    _state["run_id"] = run_id
    _state["cancelled"] = False
    _state["process"] = None

    def _run():
        stderr_tail = ""
        stdout_tail = ""
        proc = None
        try:
            cmd = ["python", "-m", "robot", "-d", "results", "-t", test_filter] + extra_vars + [suite]
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            _state["process"] = proc
            try:
                stdout, stderr = proc.communicate(timeout=120)
                _state["exit_code"] = proc.returncode
                stderr_tail = (stderr or "")[-2000:]
                stdout_tail = (stdout or "")[-2000:]
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                _state["exit_code"] = -1
                stderr_tail = f"TIMEOUT após 120s: {(stderr or '')[-1500:]}"
        except Exception as ex:
            _state["exit_code"] = -2
            stderr_tail = f"Exceção não esperada: {ex}"
        finally:
            _state["process"] = None
            _state["running"] = False
            _state["finished"] = True
            _state["finished_at"] = time.time()
            if _state["started_at"]:
                _state["elapsed_final"] = round(_state["finished_at"] - _state["started_at"], 3)

            # Fix B: se Robot abortou sem gerar validations.json, grava um fallback
            # com status EXECUTION_FAILED pra frontend renderizar estado de erro explícito
            # em vez de ficar em mock zumbi.
            exit_code = _state["exit_code"]
            validations_written = os.path.exists(VALIDATION_FILE)
            ipaas_written = os.path.exists(IPAAS_VALIDATION_FILE)
            needs_fallback = (
                exit_code not in (0, None)
                and not validations_written
                and not ipaas_written
            )
            if needs_fallback:
                import datetime
                # Prefere mensagem de FAIL do output.xml (mais específica que stderr/stdout warnings)
                fail_msg, hint = _extract_fail_from_output_xml()
                err_msg = fail_msg
                if not err_msg:
                    # Fallback: stderr/stdout, ignorando warnings de SSL
                    for blob in (stderr_tail, stdout_tail):
                        for line in (blob or "").splitlines():
                            s = line.strip()
                            if not s:
                                continue
                            low = s.lower()
                            if "insecurerequestwarning" in low or "warnings.warn" in low:
                                continue
                            if s.startswith("=") or "INFO" in s or "Log:" in s:
                                continue
                            err_msg = s
                            break
                        if err_msg:
                            break
                if not err_msg:
                    err_msg = (
                        "Robot terminou com exit code " + str(exit_code)
                        + " sem produzir validations.json. Veja log.html pra detalhes."
                    )

                fallback = {
                    "status": "EXECUTION_FAILED",
                    "error": err_msg,
                    "hint": hint,
                    "exit_code": exit_code,
                    "mode": mode,
                    "config": config,
                    "run_id": run_id,
                    "pipe_origem": "",
                    "pipe_destino": "",
                    "total_divergencias": 0,
                    "divergencias": [],
                    "stderr_tail": stderr_tail[-1200:],
                    "metadata": {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "origem_source": "n/a",
                        "destino_source": "n/a",
                        "tool_version": "1.0",
                    },
                }
                target = IPAAS_VALIDATION_FILE if mode == "ipaas" else VALIDATION_FILE
                try:
                    with open(target, "w", encoding="utf-8") as fh:
                        json.dump(fallback, fh, indent=2, ensure_ascii=False)
                except IOError:
                    pass

            # Esteriliza arquivos active*.robot pra remover tokens do disco
            _sterilize_active_robots()

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return jsonify({"status": "started", "mode": mode, "run_id": run_id, "config": config})


@app.route("/api/run/cancel", methods=["POST"])
def cancel_run():
    """Mata o subprocess do Robot em curso. Marca _state["cancelled"]=True
    pra o frontend distinguir cancel manual de falha real."""
    proc = _state.get("process")
    if not _state.get("running") or not proc:
        return jsonify({"ok": False, "error": "Nenhuma run em execução"}), 404
    try:
        _state["cancelled"] = True
        proc.terminate()
        # Dá 2s pro processo encerrar limpo, depois mata forçado
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
        return jsonify({"ok": True, "run_id": _state.get("run_id")})
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@app.route("/api/status")
def get_status():
    """Retorna progresso atual."""
    progress = None
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE) as f:
                progress = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, encoding="utf-8") as f:
                logs = f.readlines()
        except IOError:
            pass

    elapsed = None
    if _state["started_at"]:
        # Enquanto rodando, elapsed é "agora - inicio". Depois de terminar, usa elapsed_final fixo.
        if _state["running"]:
            elapsed = round(time.time() - _state["started_at"], 1)
        else:
            elapsed = _state.get("elapsed_final")

    return jsonify({
        "running": _state["running"],
        "finished": _state["finished"],
        "exit_code": _state["exit_code"],
        "cancelled": _state.get("cancelled", False),
        "elapsed": elapsed,
        "elapsed_final": _state.get("elapsed_final"),
        "progress": progress,
        "logs": [l.strip() for l in logs if l.strip()],
        # Metadata adicional pra frontend V2 correlacionar
        "run_id": _state.get("run_id"),
        "mode": _state.get("mode"),
        "config": _state.get("config"),
        "started_at_iso": (
            __import__("datetime").datetime.fromtimestamp(_state["started_at"]).isoformat()
            if _state.get("started_at") else None
        ),
    })


@app.route("/api/results")
def get_results():
    """Retorna o relatório de divergências (Pipefy ou iPaaS)."""
    # Tenta iPaaS primeiro (mais recente), depois Pipefy
    for fpath in [IPAAS_VALIDATION_FILE, VALIDATION_FILE]:
        if os.path.exists(fpath):
            try:
                with open(fpath, encoding="utf-8") as f:
                    return jsonify(json.load(f))
            except (json.JSONDecodeError, IOError):
                pass
    return jsonify(None)


if __name__ == "__main__":
    os.makedirs(RESULTS_DIR, exist_ok=True)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
