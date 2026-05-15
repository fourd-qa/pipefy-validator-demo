"""Engine do email diario do Dashboard de Produtividade (Sprint 4 parte 2).

Funcoes puras que consomem as engines existentes de dashboard_metrics e
produzem um digest pronto pra renderizar como email HTML enxuto.

Separado de dashboard_metrics pra deixar a leitura mais facil — este modulo
agrega e formata, nao calcula scoring.
"""
from __future__ import annotations

import datetime as _dt
import html as _html
from typing import Any, Dict, List, Optional

import dashboard_metrics


def _first_enabled_pipe(monitored: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for p in monitored:
        if p.get("enabled", True) and p.get("id"):
            return p
    return None


def _safe_int(x: Any) -> int:
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def _security_scan_pipes(
    monitored: List[Dict[str, Any]],
    snapshots_root: str,
    semantic_rules_path: Optional[str],
) -> Dict[str, Any]:
    """Roda scan semantico no ultimo snapshot de cada pipe enabled.
    Retorna {by_pipe: [...], total_high, total_med, total_low}.

    Resiliente: se nao tem regras ou nao tem snapshots, retorna estrutura
    vazia (available=False) ao inves de levantar.
    """
    import os as _os
    if not semantic_rules_path or not _os.path.exists(semantic_rules_path):
        return {"available": False, "reason": "Sem arquivo de regras"}
    try:
        import semantic_scanner
        rules = semantic_scanner.load_rules(semantic_rules_path)
    except Exception as ex:
        return {"available": False, "reason": f"Erro carregando regras: {ex}"}
    if not rules:
        return {"available": False, "reason": "Nenhuma regra ativa"}

    by_pipe: List[Dict[str, Any]] = []
    total = {"high": 0, "med": 0, "low": 0}
    for p in monitored:
        if not (p.get("enabled", True) and p.get("id")):
            continue
        import re as _re
        safe_id = _re.sub(r"[^a-zA-Z0-9_-]", "_", p["id"])[:64] or "unknown"
        pipe_dir = _os.path.join(snapshots_root, safe_id)
        if not _os.path.isdir(pipe_dir):
            continue
        files = sorted(f for f in _os.listdir(pipe_dir) if f.endswith(".json"))
        if not files:
            continue
        try:
            import json as _json
            with open(_os.path.join(pipe_dir, files[-1]), "r", encoding="utf-8") as f:
                snapshot = _json.load(f)
        except Exception:
            continue
        env_label = p.get("env_label") or (snapshot.get("metadata") or {}).get("env_label")
        targets = semantic_scanner.extract_targets_from_snapshot(snapshot, env_label=env_label)
        findings = semantic_scanner.scan_targets(targets, rules)
        summary = semantic_scanner.summarize_findings(findings)
        for k in ("high", "med", "low"):
            total[k] += summary["by_severity"].get(k, 0)
        by_pipe.append({
            "pipe_id": p["id"],
            "pipe_name": p.get("name", p["id"]),
            "env_label": env_label,
            "total": summary["total"],
            "by_severity": summary["by_severity"],
            "top_high_findings": [
                {"rule_id": f["rule_id"], "target_name": f.get("target_name"),
                 "field": f.get("field"), "message": f.get("message")}
                for f in findings if f.get("severity") == "high"
            ][:3],
        })

    return {
        "available": bool(by_pipe),
        "reason": None if by_pipe else "Nenhum pipe com snapshot scaneavel",
        "total_findings": sum(total.values()),
        "by_severity": total,
        "by_pipe": by_pipe,
    }


def build_daily_digest(
    validations_path: str,
    weights_path: str,
    snapshots_root: str,
    blueprints_root: str,
    monitored: List[Dict[str, Any]],
    today: Optional[_dt.date] = None,
    semantic_rules_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Monta dict com KPIs e alertas pro email diario.

    Reusa as engines de dashboard_metrics. Pra Burnup e Hot Spots, escolhe o
    primeiro pipe enabled como representativo (poderia ser por pipe, mas o
    email precisa caber em 1 tela).

    Se semantic_rules_path eh passado, roda scan de seguranca em cada pipe
    enabled e adiciona alertas pra findings high.
    """
    today = today or _dt.date.today()

    velocity = dashboard_metrics.compute_velocity(validations_path, weights_path)
    debt = dashboard_metrics.compute_debt(validations_path, weights_path)
    leadtime = dashboard_metrics.compute_leadtime(snapshots_root, monitored)

    # Burnup: percorre pipes ate achar 1 com blueprint marcado.
    burnup_data: Optional[Dict[str, Any]] = None
    for p in monitored:
        if not (p.get("enabled", True) and p.get("id")):
            continue
        b = dashboard_metrics.compute_burnup(snapshots_root, blueprints_root, p["id"])
        if b.get("available"):
            burnup_data = b
            burnup_data["pipe_name"] = p.get("name", p["id"])
            break

    # Hot spots: pega o primeiro pipe enabled (igual ao default do endpoint).
    hotspots_data: Optional[Dict[str, Any]] = None
    repr_pipe = _first_enabled_pipe(monitored)
    if repr_pipe:
        h = dashboard_metrics.compute_hotspots(snapshots_root, repr_pipe["id"], weights_path)
        if h.get("available"):
            hotspots_data = h
            hotspots_data["pipe_name"] = repr_pipe.get("name", repr_pipe["id"])

    alerts: List[Dict[str, Any]] = []

    if debt.get("available") and debt.get("level") == "HIGH":
        alerts.append({
            "kind": "debt_high",
            "severity": "high",
            "message": f"Debito tecnico em nivel HIGH ({_safe_int(debt.get('total_points'))} pts)",
        })

    if leadtime.get("available"):
        for pair in leadtime.get("pairs", []) or []:
            for promoted in (pair.get("promoted") or [])[:3]:
                if (promoted.get("lag_days") or 0) >= 5:
                    alerts.append({
                        "kind": "leadtime_slow",
                        "severity": "med",
                        "message": (
                            f"{pair.get('base_name') or 'par'}: "
                            f"{promoted.get('kind')} {promoted.get('id')} "
                            f"levou {promoted.get('lag_days')}d para promover"
                        ),
                    })

    if hotspots_data:
        for ph in (hotspots_data.get("phases") or [])[:5]:
            if ph.get("level") in ("HIGH", "MEDIUM"):
                alerts.append({
                    "kind": "hotspot",
                    "severity": "high" if ph.get("level") == "HIGH" else "med",
                    "message": (
                        f"Hot spot em {hotspots_data.get('pipe_name')} - "
                        f"{ph.get('phase_name') or ph.get('phase_id')}: "
                        f"{ph.get('level')} ({_safe_int(ph.get('score'))} pts, "
                        f"{ph.get('change_count')} mudancas)"
                    ),
                })

    if burnup_data and burnup_data.get("overall_pct", 100) < 60:
        alerts.append({
            "kind": "burnup_low",
            "severity": "med",
            "message": (
                f"Burnup baixo em {burnup_data.get('pipe_name')}: "
                f"{burnup_data.get('overall_pct')}% "
                f"({burnup_data.get('overall_covered')}/{burnup_data.get('overall_total')} itens)"
            ),
        })

    # Security scan (Pendencia 1 da Fase A resolvida)
    security = _security_scan_pipes(monitored, snapshots_root, semantic_rules_path)
    if security.get("available"):
        for pipe_row in security.get("by_pipe", []):
            for f in pipe_row.get("top_high_findings", [])[:2]:
                alerts.append({
                    "kind": "security_high",
                    "severity": "high",
                    "message": (
                        f"Security: {pipe_row.get('pipe_name')} - "
                        f"{f.get('rule_id')}: {f.get('message')} "
                        f"(automation: {f.get('target_name', '?')})"
                    ),
                })

    return {
        "date": today.isoformat(),
        "kpis": {
            "velocity": {
                "available": bool(velocity.get("available")),
                "total_points": _safe_int(velocity.get("total_points")),
            },
            "debt": {
                "available": bool(debt.get("available")),
                "level": debt.get("level") or "—",
                "total_points": _safe_int(debt.get("total_points")),
            },
            "leadtime": {
                "available": bool(leadtime.get("available")),
                "median_days": leadtime.get("global_median_lag_days") or 0,
                "promoted_count": _safe_int(leadtime.get("total_promoted_elements")),
            },
            "burnup": {
                "available": burnup_data is not None,
                "pct": burnup_data.get("overall_pct") if burnup_data else None,
                "covered": burnup_data.get("overall_covered") if burnup_data else None,
                "total": burnup_data.get("overall_total") if burnup_data else None,
                "pipe_name": burnup_data.get("pipe_name") if burnup_data else None,
            },
        },
        "alerts": alerts[:10],
        "monitored_pipes_count": sum(1 for p in monitored if p.get("enabled", True)),
        "security": security,
    }


def _kpi_card(label: str, value: str, sub: str, color: str) -> str:
    """Bloco HTML pra 1 KPI. CSS inline pra email client compat."""
    return (
        '<td style="padding:0 6px;vertical-align:top;width:25%">'
        '<div style="border:1px solid #1f2a36;border-radius:10px;padding:14px 16px;'
        'background:#0e1620;color:#dfe6ee;font-family:Helvetica,Arial,sans-serif">'
        f'<div style="font-size:10.5px;color:#8a98a7;text-transform:uppercase;'
        f'letter-spacing:.08em;font-weight:600;margin-bottom:6px">{_html.escape(label)}</div>'
        f'<div style="font-size:24px;font-weight:600;color:{color};line-height:1.1">'
        f'{_html.escape(value)}</div>'
        f'<div style="font-size:11px;color:#8a98a7;margin-top:4px">{_html.escape(sub)}</div>'
        '</div></td>'
    )


def _alert_color(severity: str) -> str:
    if severity == "high":
        return "#e56b6b"
    if severity == "med":
        return "#dba844"
    return "#7dd584"


def _format_burnup_value(burnup: Dict[str, Any]) -> str:
    if not burnup.get("available") or burnup.get("pct") is None:
        return "—"
    return f"{burnup['pct']}%"


def render_email_html(digest: Dict[str, Any], dashboard_url: Optional[str] = None) -> str:
    """Renderiza HTML do email diario. CSS 100% inline (email clients
    nao respeitam <style> de forma confiavel)."""
    k = digest.get("kpis", {})
    alerts = digest.get("alerts", []) or []

    velocity = k.get("velocity", {})
    debt = k.get("debt", {})
    leadtime = k.get("leadtime", {})
    burnup = k.get("burnup", {})

    debt_color = {
        "CLEAN": "#7dd584", "LOW": "#dba844",
        "MEDIUM": "#e08a4f", "HIGH": "#e56b6b",
    }.get(debt.get("level"), "#dfe6ee")

    bp_pct = burnup.get("pct") if burnup.get("available") else None
    if bp_pct is None:
        burnup_color = "#8a98a7"
    elif bp_pct >= 90:
        burnup_color = "#7dd584"
    elif bp_pct >= 70:
        burnup_color = "#dba844"
    elif bp_pct >= 50:
        burnup_color = "#e08a4f"
    else:
        burnup_color = "#e56b6b"

    kpis_html = (
        '<table cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%;max-width:640px;border-collapse:separate"><tr>'
        + _kpi_card(
            "Velocity",
            str(velocity.get("total_points", 0)) if velocity.get("available") else "—",
            "pontos da ultima run" if velocity.get("available") else "sem run recente",
            "#dfe6ee",
        )
        + _kpi_card(
            "Debt",
            f"{debt.get('total_points', 0)} pts" if debt.get("available") else "—",
            debt.get("level", "—") if debt.get("available") else "sem dados",
            debt_color,
        )
        + _kpi_card(
            "Lead Time",
            f"{leadtime.get('median_days', 0)}d" if leadtime.get("available") else "—",
            (f"{leadtime.get('promoted_count', 0)} promovidos"
             if leadtime.get("available") else "sem pares HMG/PRD"),
            "#dfe6ee",
        )
        + _kpi_card(
            "Burnup",
            _format_burnup_value(burnup),
            (f"{burnup.get('covered')}/{burnup.get('total')} - {burnup.get('pipe_name')}"
             if burnup.get("available") else "sem blueprint"),
            burnup_color,
        )
        + '</tr></table>'
    )

    if alerts:
        items = []
        for a in alerts:
            color = _alert_color(a.get("severity", ""))
            items.append(
                '<tr><td style="padding:8px 14px;border-bottom:1px solid #1f2a36;'
                'font-family:Helvetica,Arial,sans-serif;font-size:13px;color:#dfe6ee">'
                f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
                f'background:{color};margin-right:10px;vertical-align:middle"></span>'
                f'{_html.escape(a.get("message", ""))}'
                '</td></tr>'
            )
        alerts_html = (
            '<table cellpadding="0" cellspacing="0" border="0" '
            'style="width:100%;max-width:640px;margin-top:14px;'
            'border:1px solid #1f2a36;border-radius:10px;background:#0e1620;'
            'border-collapse:separate">'
            '<tr><td style="padding:12px 14px;font-family:Helvetica,Arial,sans-serif;'
            'font-size:11px;color:#8a98a7;text-transform:uppercase;letter-spacing:.06em;'
            'font-weight:600;border-bottom:1px solid #1f2a36">'
            f'Alertas ({len(alerts)})'
            '</td></tr>'
            + "".join(items)
            + '</table>'
        )
    else:
        alerts_html = (
            '<div style="margin-top:14px;padding:14px;border:1px dashed #1f2a36;'
            'border-radius:10px;color:#8a98a7;font-family:Helvetica,Arial,sans-serif;'
            'font-size:13px;text-align:center">Nenhum alerta hoje.</div>'
        )

    link_html = ""
    if dashboard_url:
        link_html = (
            f'<div style="margin-top:18px;font-family:Helvetica,Arial,sans-serif;'
            f'font-size:12px;color:#8a98a7">'
            f'<a href="{_html.escape(dashboard_url)}" '
            f'style="color:#7aa6d8;text-decoration:none">Abrir dashboard completo &rarr;</a>'
            '</div>'
        )

    return (
        '<!DOCTYPE html><html><body style="margin:0;padding:24px;background:#070b10;'
        'font-family:Helvetica,Arial,sans-serif">'
        '<div style="max-width:640px;margin:0 auto">'
        '<div style="font-size:11px;color:#8a98a7;text-transform:uppercase;'
        'letter-spacing:.08em;font-weight:600;margin-bottom:4px">Pipefy Validator</div>'
        f'<h1 style="margin:0 0 4px;font-size:20px;color:#dfe6ee;font-weight:600;'
        f'letter-spacing:-.02em">Resumo de {_html.escape(digest.get("date", ""))}</h1>'
        f'<div style="color:#8a98a7;font-size:12.5px;margin-bottom:16px">'
        f'{digest.get("monitored_pipes_count", 0)} pipes monitorados</div>'
        + kpis_html
        + alerts_html
        + link_html
        + '</div></body></html>'
    )
