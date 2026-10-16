"""Certificate of Analysis template loading and rendering."""

from pathlib import Path
from string import Template

from common.config import settings
from common.errors import DomainError

TEMPLATE_ROOT = Path(settings.get_str("reports.template_root"))
REQUIRED_COFA_FIELDS = ("lot_code", "assay_pct", "analyst")


def load_template(name: str) -> Template:
    if not name or "/" in name or "\\" in name:
        raise DomainError(f"invalid template name: {name!r}")
    path = TEMPLATE_ROOT / name
    if not path.is_file():
        raise DomainError(f"template not found: {name}")
    return Template(path.read_text(encoding="utf-8"))


def render_cofa(template_name: str, fields: dict) -> str:
    template = load_template(template_name)
    missing = [key for key in REQUIRED_COFA_FIELDS if key not in fields]
    if missing:
        raise DomainError(f"missing fields: {', '.join(missing)}")
    return template.substitute(fields)


def cofa_file_name(lot_code: str, issued_on: str) -> str:
    safe_lot = "".join(ch for ch in lot_code if ch.isalnum() or ch == "-")
    return f"COFA_{safe_lot}_{issued_on}.html"


def cofa_summary_line(fields: dict) -> str:
    lot = fields.get("lot_code", "UNKNOWN")
    assay = fields.get("assay_pct", "n/a")
    return f"{lot} assay={assay}"


def list_templates() -> list:
    return sorted(p.name for p in TEMPLATE_ROOT.glob("*.html"))
