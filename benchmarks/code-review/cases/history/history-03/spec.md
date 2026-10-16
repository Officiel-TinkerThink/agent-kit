Intent: move the empty-records guard from export() into _dispatch() and rename _write_json to write_json_rows to match write_csv_rows.
Scope: refactor only; generated report files must stay byte-identical.
