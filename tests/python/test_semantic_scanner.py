"""Testes da Frente 1 (Fase A) - scanner semantico (Gitleaks/Snyk equivalent).

Cobre:
- semantic_scanner.load_rules: filtra disabled, compila regex, descarta invalido
- semantic_scanner.scan_targets: cada regra default dispara em TP e nao dispara em TN
- semantic_scanner.extract_targets_from_automations: converte formato GraphQL
- semantic_scanner.summarize_findings: agrega por severity/category/rule
- /api/security-scan: gating lideranca, valida body, retorna findings + summary
- /api/security-scan/rules: lista regras sem expor regex
- env_restrict: regra so dispara quando env_label bate
"""
import base64
import importlib
import json
import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _basic(user, pw):
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


@pytest.fixture
def scanner_module():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if "semantic_scanner" in sys.modules:
        del sys.modules["semantic_scanner"]
    return importlib.import_module("semantic_scanner")


@pytest.fixture
def default_rules_path():
    return str(REPO_ROOT / "config" / "semantic_rules.json")


# ============== load_rules ==============

def test_load_rules_carrega_default(scanner_module, default_rules_path):
    rules = scanner_module.load_rules(default_rules_path)
    assert len(rules) >= 7  # 9 regras default
    # Cada uma deve ter _compiled.
    for r in rules:
        assert "_compiled" in r
        assert hasattr(r["_compiled"], "search")


def test_load_rules_filtra_disabled(tmp_path, scanner_module):
    rules_data = {
        "version": "1.0",
        "rules": [
            {"id": "r1", "category": "c", "severity": "high", "fields": ["url"],
             "pattern": "x", "enabled": True, "message": "m"},
            {"id": "r2", "category": "c", "severity": "high", "fields": ["url"],
             "pattern": "y", "enabled": False, "message": "m"},
        ],
    }
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rules_data), encoding="utf-8")
    rules = scanner_module.load_rules(str(p))
    assert len(rules) == 1
    assert rules[0]["id"] == "r1"


def test_load_rules_ignora_regex_invalido(tmp_path, scanner_module):
    rules_data = {
        "version": "1.0",
        "rules": [
            {"id": "bad", "category": "c", "severity": "high", "fields": ["url"],
             "pattern": "[invalido(", "enabled": True, "message": "m"},
            {"id": "ok", "category": "c", "severity": "high", "fields": ["url"],
             "pattern": "x", "enabled": True, "message": "m"},
        ],
    }
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rules_data), encoding="utf-8")
    rules = scanner_module.load_rules(str(p))
    assert len(rules) == 1
    assert rules[0]["id"] == "ok"


# ============== scan_targets - regras default em isolado ==============

def test_scan_detecta_http_sem_tls_em_prd(scanner_module, default_rules_path):
    rules = scanner_module.load_rules(default_rules_path)
    targets = [{
        "kind": "automation", "name": "Notificar", "id": "a1",
        "url": "http://api.exemplo.com/hook", "env_label": "PRD",
    }]
    findings = scanner_module.scan_targets(targets, rules)
    assert any(f["rule_id"] == "url_no_tls_in_prd" for f in findings)


def test_scan_nao_dispara_http_quando_env_label_hmg(scanner_module, default_rules_path):
    """url_no_tls_in_prd tem env_restrict='PRD' - nao deve disparar em HMG."""
    rules = scanner_module.load_rules(default_rules_path)
    targets = [{
        "kind": "automation", "name": "Test", "id": "a1",
        "url": "http://api.exemplo.com/hook", "env_label": "HMG",
    }]
    findings = scanner_module.scan_targets(targets, rules)
    assert not any(f["rule_id"] == "url_no_tls_in_prd" for f in findings)


def test_scan_detecta_localhost(scanner_module, default_rules_path):
    rules = scanner_module.load_rules(default_rules_path)
    targets = [{
        "kind": "automation", "name": "X", "id": "a1",
        "url": "https://localhost:8080/webhook", "env_label": "PRD",
    }]
    findings = scanner_module.scan_targets(targets, rules)
    assert any(f["rule_id"] == "url_internal_ip" for f in findings)


def test_scan_detecta_ip_192(scanner_module, default_rules_path):
    rules = scanner_module.load_rules(default_rules_path)
    targets = [{
        "kind": "automation", "name": "X", "id": "a1",
        "url": "https://192.168.0.1/api", "env_label": "PRD",
    }]
    findings = scanner_module.scan_targets(targets, rules)
    assert any(f["rule_id"] == "url_internal_ip" for f in findings)


def test_scan_detecta_subdominio_hmg_em_prd(scanner_module, default_rules_path):
    rules = scanner_module.load_rules(default_rules_path)
    targets = [{
        "kind": "automation", "name": "X", "id": "a1",
        "url": "https://hmg.api.cliente.com/hook", "env_label": "PRD",
    }]
    findings = scanner_module.scan_targets(targets, rules)
    assert any(f["rule_id"] == "url_with_test_subdomain_in_prd" for f in findings)


def test_scan_nao_dispara_subdominio_hmg_em_hmg(scanner_module, default_rules_path):
    rules = scanner_module.load_rules(default_rules_path)
    targets = [{
        "kind": "automation", "name": "X", "id": "a1",
        "url": "https://hmg.api.cliente.com/hook", "env_label": "HMG",
    }]
    findings = scanner_module.scan_targets(targets, rules)
    assert not any(f["rule_id"] == "url_with_test_subdomain_in_prd" for f in findings)


def test_scan_detecta_token_em_query_string(scanner_module, default_rules_path):
    rules = scanner_module.load_rules(default_rules_path)
    targets = [{
        "kind": "automation", "name": "X", "id": "a1",
        "url": "https://api.cliente.com/hook?token=abc123def456",
    }]
    findings = scanner_module.scan_targets(targets, rules)
    assert any(f["rule_id"] == "token_in_query_string" for f in findings)


def test_scan_detecta_bearer_token_em_header(scanner_module, default_rules_path):
    rules = scanner_module.load_rules(default_rules_path)
    targets = [{
        "kind": "automation", "name": "X", "id": "a1",
        "headers": "Authorization: Bearer abc123def456ghi789jkl012mnop",
    }]
    findings = scanner_module.scan_targets(targets, rules)
    assert any(f["rule_id"] == "bearer_token_in_headers" for f in findings)


def test_scan_detecta_credential_no_body(scanner_module, default_rules_path):
    rules = scanner_module.load_rules(default_rules_path)
    targets = [{
        "kind": "automation", "name": "X", "id": "a1",
        "body": '{"api_key": "sk_live_abc12345xyz"}',
    }]
    findings = scanner_module.scan_targets(targets, rules)
    assert any(f["rule_id"] == "credential_in_body" for f in findings)


def test_scan_detecta_email_de_teste_em_prd(scanner_module, default_rules_path):
    rules = scanner_module.load_rules(default_rules_path)
    targets = [{
        "kind": "automation", "name": "X", "id": "a1",
        "body": '{"to": "qa@cliente.com"}', "env_label": "PRD",
    }]
    findings = scanner_module.scan_targets(targets, rules)
    assert any(f["rule_id"] == "email_de_teste_in_prd" for f in findings)


def test_scan_detecta_email_example_com(scanner_module, default_rules_path):
    rules = scanner_module.load_rules(default_rules_path)
    targets = [{
        "kind": "automation", "name": "X", "id": "a1",
        "body": '{"to": "alguem@example.com"}', "env_label": "PRD",
    }]
    findings = scanner_module.scan_targets(targets, rules)
    assert any(f["rule_id"] == "email_de_teste_in_prd" for f in findings)


def test_scan_detecta_aws_access_key(scanner_module, default_rules_path):
    rules = scanner_module.load_rules(default_rules_path)
    targets = [{
        "kind": "automation", "name": "X", "id": "a1",
        "body": '{"access_key": "AKIAIOSFODNN7EXAMPLE"}',
    }]
    findings = scanner_module.scan_targets(targets, rules)
    assert any(f["rule_id"] == "aws_access_key" for f in findings)


def test_scan_detecta_github_token(scanner_module, default_rules_path):
    rules = scanner_module.load_rules(default_rules_path)
    targets = [{
        "kind": "automation", "name": "X", "id": "a1",
        "headers": "Authorization: token ghp_abc123def456ghi789jkl012mnop345qr678",
    }]
    findings = scanner_module.scan_targets(targets, rules)
    assert any(f["rule_id"] == "github_token" for f in findings)


def test_scan_target_limpo_nao_gera_finding(scanner_module, default_rules_path):
    """True negative: target sem nenhum problema nao deve gerar findings."""
    rules = scanner_module.load_rules(default_rules_path)
    targets = [{
        "kind": "automation", "name": "Limpo", "id": "a1",
        "url": "https://api.cliente.com/v1/webhook",
        "headers": '{"Content-Type": "application/json"}',
        "body": '{"order_id": 123, "status": "approved"}',
        "env_label": "PRD",
    }]
    findings = scanner_module.scan_targets(targets, rules)
    assert findings == []


def test_scan_findings_ordenados_por_severidade(scanner_module, default_rules_path):
    rules = scanner_module.load_rules(default_rules_path)
    targets = [{
        "kind": "automation", "name": "Misto", "id": "a1",
        "url": "https://api.cliente.com/v1?token=abcdef123",
        "body": '{"to": "qa@cliente.com"}',
        "env_label": "PRD",
    }]
    findings = scanner_module.scan_targets(targets, rules)
    assert len(findings) >= 2
    # Primeiro deve ser high.
    assert findings[0]["severity"] == "high"


def test_scan_snippet_mascara_secret(scanner_module, default_rules_path):
    """Snippet do finding nao deve expor o segredo completo."""
    rules = scanner_module.load_rules(default_rules_path)
    secret = "Bearer abc123def456ghi789jkl012mnop"
    targets = [{
        "kind": "automation", "name": "X", "id": "a1",
        "headers": f"Authorization: {secret}",
    }]
    findings = scanner_module.scan_targets(targets, rules)
    f = next(x for x in findings if x["rule_id"] == "bearer_token_in_headers")
    assert "***" in f["snippet"]
    assert "abc123def456ghi789jkl012mnop" not in f["snippet"]


# ============== extract_targets_from_automations ==============

def test_extract_targets_automation_http_completa(scanner_module):
    automations = [{
        "id": "auto_1",
        "name": "Webhook ao aprovar",
        "active": True,
        "action_params": {
            "url": "https://api.x.com/hook",
            "headers": '{"X-Token": "abc"}',
            "body": '{"order": 1}',
        },
    }]
    targets = scanner_module.extract_targets_from_automations(automations, env_label="PRD")
    assert len(targets) == 1
    assert targets[0]["kind"] == "automation"
    assert targets[0]["url"] == "https://api.x.com/hook"
    assert targets[0]["env_label"] == "PRD"


def test_extract_targets_automation_sem_http_ignorada(scanner_module):
    """Automation sem url/headers/body (ex: 'mover de fase') nao vira target."""
    automations = [{
        "id": "auto_2",
        "name": "Mover de fase",
        "action_params": {"to_phase_id": "ph_xyz"},
    }]
    targets = scanner_module.extract_targets_from_automations(automations)
    assert targets == []


def test_extract_targets_inclui_conditions_com_value(scanner_module):
    """Conditions com value vao como target separado (pode ter credencial em value)."""
    automations = [{
        "id": "auto_3",
        "name": "Filtro",
        "action_params": {"url": "https://api.x.com"},
        "condition": {
            "expressions": [
                {"field_address": "campo_x", "operation": "equals", "value": "Bearer abcdef123456ghi"},
            ],
        },
    }]
    targets = scanner_module.extract_targets_from_automations(automations, env_label="PRD")
    kinds = [t["kind"] for t in targets]
    assert "automation" in kinds
    assert "condition" in kinds


# ============== summarize_findings ==============

def test_summarize_agrupa_por_severity_e_category(scanner_module):
    findings = [
        {"rule_id": "r1", "category": "secret_leak", "severity": "high"},
        {"rule_id": "r2", "category": "secret_leak", "severity": "high"},
        {"rule_id": "r3", "category": "url_security", "severity": "med"},
    ]
    s = scanner_module.summarize_findings(findings)
    assert s["total"] == 3
    assert s["by_severity"]["high"] == 2
    assert s["by_severity"]["med"] == 1
    assert s["by_category"]["secret_leak"] == 2
    assert s["by_rule"]["r1"] == 1


# ============== Endpoint ==============

def _reload_server(tmp_path, monkeypatch, env=None):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for k in ("APP_PASSWORD", "APP_USERNAME", "LIDERANCA_USERNAME", "LIDERANCA_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    for d in ("config", "results", "snapshots", "tmp"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    # Copia rules e weights pra tmp.
    for f in ("complexity_weights.json", "semantic_rules.json"):
        src = REPO_ROOT / "config" / f
        if src.exists():
            (tmp_path / "config" / f).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for mod in ("server", "semantic_scanner"):
        if mod in sys.modules:
            del sys.modules[mod]
    server = importlib.import_module("server")
    server.app.config["TESTING"] = True
    return server


def test_endpoint_security_scan_gated_demo_recebe_403(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    res = server.app.test_client().post(
        "/api/security-scan",
        headers={"Authorization": _basic("demo", "demosecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"automations": []}),
    )
    assert res.status_code == 403


def test_endpoint_security_scan_happy_path(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    body = {
        "automations": [{
            "id": "a1",
            "name": "Webhook prod",
            "action_params": {"url": "http://api.com/hook"},
        }],
        "env_label": "PRD",
    }
    res = server.app.test_client().post(
        "/api/security-scan",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps(body),
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["targets_count"] == 1
    assert data["summary"]["total"] >= 1
    assert any(f["rule_id"] == "url_no_tls_in_prd" for f in data["findings"])


def test_endpoint_security_scan_aceita_targets_diretos(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    body = {
        "targets": [{
            "kind": "custom", "name": "X", "id": "x1",
            "headers": "Authorization: Bearer abcdefghijklmnop123456789",
        }],
    }
    res = server.app.test_client().post(
        "/api/security-scan",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps(body),
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["targets_count"] == 1


def test_endpoint_security_scan_400_automations_invalido(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().post(
        "/api/security-scan",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"automations": "nao-eh-lista"}),
    )
    assert res.status_code == 400


def test_endpoint_security_scan_targets_invalido_400(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().post(
        "/api/security-scan",
        headers={"Authorization": _basic("lideranca", "ldsecret"),
                 "Content-Type": "application/json"},
        data=json.dumps({"targets": "nao-eh-lista"}),
    )
    assert res.status_code == 400


def test_endpoint_rules_listing_gated_demo(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    res = server.app.test_client().get(
        "/api/security-scan/rules",
        headers={"Authorization": _basic("demo", "demosecret")},
    )
    assert res.status_code == 403


def test_endpoint_rules_listing_nao_expoe_regex(tmp_path, monkeypatch):
    """A listagem de regras pra UI nao deve expor o regex (info sensivel)."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/api/security-scan/rules",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["rules_count"] >= 7
    for r in data["rules"]:
        assert "pattern" not in r
        assert "_compiled" not in r


def test_endpoint_rules_listing_arquivo_inexistente(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    os.remove(tmp_path / "config" / "semantic_rules.json")
    res = server.app.test_client().get(
        "/api/security-scan/rules",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    assert res.get_json()["rules"] == []


def test_v2_security_scan_html_gated_demo(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, env={"APP_PASSWORD": "demosecret"})
    res = server.app.test_client().get(
        "/v2/security-scan",
        headers={"Authorization": _basic("demo", "demosecret")},
    )
    assert res.status_code == 403


def test_v2_security_scan_html_lideranca_recebe_pagina(tmp_path, monkeypatch):
    """Lideranca pega a pagina HTML servida do web/designs."""
    server = _reload_server(tmp_path, monkeypatch, env={
        "APP_PASSWORD": "demosecret",
        "LIDERANCA_PASSWORD": "ldsecret",
    })
    res = server.app.test_client().get(
        "/v2/security-scan",
        headers={"Authorization": _basic("lideranca", "ldsecret")},
    )
    assert res.status_code == 200
    assert b"Security scan" in res.data or b"security-scan" in res.data
