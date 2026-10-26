"""Portable, offline HTML presentation of an exact audit report."""

import json
from importlib.resources import files


def render_html(report: dict) -> str:
    """Embed an audit result without allowing identifiers to become HTML."""
    payload = json.dumps(report, ensure_ascii=True, allow_nan=False, separators=(',', ':'))
    for character, escaped in (('<', '\\u003c'), ('>', '\\u003e'), ('&', '\\u0026')):
        payload = payload.replace(character, escaped)
    template = files('unscored').joinpath('report.html').read_text(encoding='utf-8')
    return template.replace('__REPORT_JSON__', payload)
