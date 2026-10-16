"""HTML rendering for batch record reports."""

import json
from jinja2 import Environment, FileSystemLoader, Template

TEMPLATE_DIR = "/srv/lab/templates"
REPORT_TEMPLATE = "report.html"


def _environment():
    """Create the Jinja2 environment for fixed report templates."""
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
    )


def render_report(title, rows):
    """Render the fixed report template with the title as a plain variable."""
    template = _environment().get_template(REPORT_TEMPLATE)
    return template.render(title=title, rows=rows)


def render_title(title):
    """Render the report heading for a user-supplied title."""
    template = Template("<h1>" + title + "</h1>", autoescape=True)
    return template.render()


def embed_json_for_script(data):
    """Serialise data for embedding in an inline script element."""
    text = json.dumps(data, separators=(",", ":"), sort_keys=True)
    return (
        text.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def render_embedded_report(title, rows):
    """Render the report page with its rows embedded as JSON data."""
    html = render_report(title, rows)
    data_json = embed_json_for_script(rows)
    return html + "\n<script>var reportRows = " + data_json + ";</script>"
