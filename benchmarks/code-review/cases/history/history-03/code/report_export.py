"""Report export: builds CSV or JSON files from report records."""

import csv
import io
import json
import logging

logger = logging.getLogger("reports.export")

SUPPORTED_FORMATS = ("csv", "json")
COLUMNS = ("site_id", "study_code", "visit", "status")


def build_rows(records):
    return [
        {
            "site_id": r.get("site_id", ""),
            "study_code": r.get("study_code", ""),
            "visit": r.get("visit", ""),
            "status": r.get("status", "UNKNOWN"),
        }
        for r in records
    ]


class ReportExporter:
    def __init__(self, sink):
        self._sink = sink

    def export(self, records: list, fmt: str):
        if fmt not in SUPPORTED_FORMATS:
            raise ValueError(f"unsupported format: {fmt}")
        rows = build_rows(records)
        return self._dispatch(rows, fmt)

    def _dispatch(self, rows, fmt):
        if not rows:
            logger.info("no records to export")
            return None
        if fmt == "csv":
            return self.write_csv_rows(rows)
        return self.write_json_rows(rows)

    def write_csv_rows(self, rows):
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
        return self._sink.write("report.csv", buffer.getvalue())

    def write_json_rows(self, rows):
        payload = json.dumps(rows, indent=2, sort_keys=True)
        return self._sink.write("report.json", payload)
