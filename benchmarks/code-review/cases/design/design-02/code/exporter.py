import csv
import io
import smtplib
import sqlite3
from decimal import Decimal


class LedgerReportExporter:
    def __init__(self, db_path):
        self._db = sqlite3.connect(db_path)
        self._locale = "en"
        self._rows = None

    def set_locale(self, locale):
        self._locale = locale

    def connection(self):
        return self._db

    def load(self, batch_id):
        cur = self._db.execute(
            "SELECT account, amount, currency FROM ledger WHERE batch = ?",
            (batch_id,),
        )
        self._rows = cur.fetchall()
        return len(self._rows)

    def format_amount(self, value):
        text = f"{Decimal(value):,.2f}"
        if self._locale == "de":
            return text.replace(",", "#").replace(".", ",").replace("#", ".")
        return text

    def export_csv(self):
        buf = io.StringIO()
        writer = csv.writer(buf)
        for account, amount, currency in self._rows or []:
            writer.writerow([account, self.format_amount(amount), currency])
        return buf.getvalue()

    def notify(self, recipient, body):
        smtp = smtplib.SMTP("mail.internal.example", 25)
        smtp.sendmail("reports@example", [recipient], body)
        smtp.quit()
