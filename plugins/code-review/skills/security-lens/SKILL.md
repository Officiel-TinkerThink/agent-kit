---
name: security-lens
description: "Focus-mode lens for security defects in Python code: untrusted input to sink paths, authorisation, secrets, audit. Preloaded into security-reviewer; not for direct use."
user-invocable: false
---
LENS-MARKER: security-lens v1

# Security Lens

A defect is untrusted input reaching a dangerous sink, or a control that exists but is wrong.
Report only what a source-to-sink path or a missing required control shows.

## How to look

1. List every entry point (route and HTTP verb, CLI argument, queue consumer, file read). Mark each input untrusted.
2. Trace each untrusted input forward to its sinks: query, file path, outbound request, deserializer, template, shell, log, response, redirect.
3. At each sink find the control and check it is correct for that sink (separator logic, fixed algorithm list, escape context), not merely present.
4. Check the SIBLING: the other verb, route or entry point for the same resource. The one that does it right is evidence the other does not. Check what the change REMOVED (auth decorator, owner filter, timeout, escape, verify flag, audit call) and what it did not touch but depends on.
5. Check object-level authorisation: the query must filter by the caller's identity, not the id alone. For regulated record changes, check the same transaction writes an audit event.
6. Trace with a concrete input and write the outcome at each step. If a step needs code you cannot read, mark UNCLEAR.

## Catalog
### Path prefix check without separator (CWE-22)
- Tell: `startswith(BASE)` on a resolved path used to confine file access.
- Fails when: BASE is `/srv/data` and the request resolves to `/srv/data-old/x.txt`; the prefix passes and a file outside the base is read.
- Bad:
```python
full = os.path.realpath(os.path.join(BASE, name))
if not full.startswith(BASE): raise ValueError("outside base")
```
- Good: `base = os.path.realpath(BASE)`, `full = os.path.realpath(os.path.join(base, name))`, then reject unless `os.path.commonpath([base, full]) == base`.
- Not a defect when: the test uses `commonpath` on the realpath of both base and candidate, or `startswith(base + os.sep)` where `base` is `realpath(BASE)` and `full` is a realpath.

### os.path.join with an absolute second argument (CWE-22)
- Tell: `os.path.join(base, value)` where `value` comes from a request and is not a fixed relative name.
- Fails when: `value` is `/etc/passwd`; `os.path.join` returns it and discards `base`.
- Bad:
```python
path = os.path.join(UPLOAD_DIR, filename)  # filename from request
open(path, "rb")
```
- Good: reject unless `filename not in ("", ".", "..")`, `os.path.basename(filename) == filename` and the name has no NUL byte; or require `re.fullmatch(r"[A-Za-z0-9._-]{1,128}", filename)`. After joining, `realpath` the result and confirm it with `commonpath` against the realpath of the base directory.
- Not a defect when: the second argument is a constant or is already confined by `commonpath`.

### Zip or tar slip (CWE-22)
- Tell: a member name joined to a destination and written with no confinement check; or `tarfile` `extractall(...)` / `extract(...)` called with no `filter=` argument (the default is unsafe before Python 3.14).
- Fails when: a member name with `..` segments or an absolute path resolves outside `dest` and is written there.
- Bad:
```python
target = os.path.join(dest, member.filename)
open(target, "wb").write(zf.read(member))
```
- Good: `zf.extractall(dest)` (zipfile strips `..` and absolute names) or `tarfile` with `filter="data"`.
- Not a defect when: extraction uses `zipfile.extractall` or a tar data filter, which already confine names.

### SSRF via redirect (CWE-918)
- Tell: the host allowlist is checked on the input URL, then `requests.get(url)` runs with default redirects.
- Fails when: an allowlisted host answers 302 to an internal address; requests follows it and returns the internal body.
- Bad:
```python
if urlsplit(url).hostname not in ALLOWED_HOSTS: raise ValueError("host")
resp = requests.get(url, timeout=5)
```
- Good: pass `allow_redirects=False`, then resolve each `Location` (a relative one joined to the current URL) and apply the address check from the alternative-IP entry to every hop, up to a fixed hop limit.
- Not a defect when: redirects are never followed, or each hop is validated before it is taken.

### SSRF via alternative IP forms and internal DNS (CWE-918)
- Tell: the hostname is matched against a string list (`"localhost"`, `"169.254.169.254"`) and the resolved address is never parsed.
- Fails when: a decimal, octal or hex spelling of 127.0.0.1, or a public DNS name resolving to 10.x.x.x, passes the list and reaches an internal host.
- Bad:
```python
host = urlsplit(url).hostname
if host in ("localhost", "169.254.169.254"): raise ValueError("blocked")
```
- Good: resolve with `socket.getaddrinfo` (it accepts legacy IPv4 spellings that `ipaddress.ip_address` rejects); reject the request if any returned address fails `ipaddress.ip_address(a).is_global`; connect to one validated address, keeping the original Host header and TLS server name. Do not substitute `is_private`, `is_loopback` or a string list for `is_global`: carrier-grade NAT `100.64.0.0/10` (for example Alibaba Cloud metadata at `100.100.100.200`) is neither private nor global.
- Not a defect when: the host is a configuration constant that no request data influences.

### JWT algorithm taken from the token (CWE-347)
- Tell: `algorithms=` built from `get_unverified_header(...)`, or signature verification disabled.
- Fails when: a token whose header names `none` or another algorithm is accepted, so any caller can forge claims.
- Bad:
```python
alg = jwt.get_unverified_header(token)["alg"]
claims = jwt.decode(token, KEY, algorithms=[alg])
```
- Good: `jwt.decode(token, KEY, algorithms=["HS256"])` with the algorithm fixed in configuration.
- Not a defect when: the algorithm list is a constant matching the key type (RS256 with a public key).

### Regex anchor $ accepts a trailing newline (CWE-20)
- Tell: `re.match` or `re.search` with `$` used to validate a whole value.
- Fails when: `"alice\n"` matches `^[a-z]+$`, so a value with a trailing newline passes and is stored or sent in a header.
- Bad:
```python
if re.match(r"^[A-Za-z0-9_]{1,32}$", username):
    create_user(username)
```
- Good: `re.fullmatch(r"[A-Za-z0-9_]{1,32}", username)`.
- Not a defect when: the value was stripped first, or the pattern ends with `\Z` or uses `fullmatch`.

### Mass assignment (CWE-915)
- Tell: `Model(**body)` or a `setattr` loop over request keys, where the model has privileged fields.
- Fails when: an update carrying `is_admin: true` is copied onto the model because no field allowlist exists.
- Bad:
```python
user = User(**request.get_json())
db.session.add(user)
```
- Good: copy only allowlisted keys, for example `{k: body[k] for k in ("name", "email") if k in body}`.
- Not a defect when: a schema with only safe fields (Pydantic or marshmallow) is the sole input type.

### Server-side template injection (CWE-1336)
- Tell: user text concatenated into the template source passed to `render_template_string` or `Template()`.
- Fails when: a name containing template syntax is compiled by the engine and evaluates expressions instead of printing text.
- Bad:
```python
tpl = f"<h1>Hello {name}</h1>"
return render_template_string(tpl)
```
- Good: a fixed template file with the value as a variable: `render_template("hello.html", name=name)`.
- Not a defect when: user text is only a render variable and the template source is a constant (SSTI only; check autoescape and `|safe` for XSS).

### Reflected or stored XSS in server-rendered Python HTML (CWE-79)
- Tell: request value in `Markup(...)`, `|safe`, `make_response(f"<...>{value}")`, `HttpResponse(...)` built by f-string, or Jinja2 with autoescape off.
- Fails when: script or event-handler markup in the value is written as HTML and runs in another user's browser when the page renders.
- Bad:
```python
return f"<p>Hello {name}</p>"
```
- Good: `from markupsafe import escape`, then `return f"<p>Hello {escape(name)}</p>"`; or a template file rendered with autoescape on.
- Not a defect when: the value is a validated integer or comes from a closed set of codes.

### CSV or formula injection (CWE-1236)
- Tell: a request-derived string written to a CSV or spreadsheet cell with no check of its first character.
- Fails when: a comment beginning with `=` is written raw; spreadsheet software evaluates it as a formula on open.
- Bad:
```python
for row in rows:
    writer.writerow([row.name, row.comment])
```
- Good: prefix values starting with `=`, `+`, `-`, `@`, tab or CR with a single quote before writing.
- Not a defect when: the export is JSON, or the values come from a closed set of codes.

### SQL built by string for IN lists, ORDER BY and identifiers (CWE-89)
- Tell: an f-string, `%` or `+` building SQL around request values, including ORDER BY and column names.
- Fails when: a value containing a quote closes the literal and changes the statement; a sort parameter injects a clause.
- Bad:
```python
sql = f"SELECT * FROM lot WHERE id IN ({ids})"
cur.execute(sql + f" ORDER BY {sort}")
```
- Good: one placeholder per id with the ids bound as parameters; map `sort` through `{"date": "created_at"}.get(sort, "id")`.
- Not a defect when: values are bound parameters, the fragment comes from a constant allowlist, or ids are cast with `int()` first.

### Timing-unsafe comparison of secrets (CWE-208)
- Tell: `==` or `!=` between a token, signature or API key and the expected value.
- Fails when: response time grows with the matching prefix length, so a client recovers the value one character at a time.
- Bad:
```python
if request.headers["X-Api-Key"] == EXPECTED_KEY:
    allow()
```
- Good: `hmac.compare_digest(provided.encode(), EXPECTED_KEY.encode())`.
- Not a defect when: the value is not secret, such as a public id or a cache key.

### Insecure randomness for tokens (CWE-330)
- Tell: `random.*` used to create a reset token, session id, API key or nonce.
- Fails when: Mersenne Twister output can be predicted from observed values, so the next reset token is guessable.
- Bad:
```python
alphabet = string.ascii_letters + string.digits
token = "".join(random.choice(alphabet) for _ in range(32))
```
- Good: `token = secrets.token_urlsafe(32)`.
- Not a defect when: `random` is used for retry jitter, test data or shuffling a UI list.

### Unsafe yaml.load and pickle.loads on untrusted data (CWE-502)
- Tell: `yaml.load` with `yaml.Loader` or no safe loader, or `pickle.load(s)` on bytes a user can write.
- Fails when: a crafted YAML tag or pickle stream builds arbitrary Python objects during load, which can run code on the server.
- Bad:
```python
config = yaml.load(request.data, Loader=yaml.Loader)
obj = pickle.loads(message.body)
```
- Good: `yaml.safe_load(request.data)`; use JSON or a schema-checked format instead of pickle for untrusted data.
- Not a defect when: pickle reads data this process wrote and verified with an HMAC before load.

### html.escape in a JavaScript context (CWE-79)
- Tell: `html.escape(value)` placed inside a `<script>` block, an `on...=` attribute or a JavaScript string.
- Fails when: a trailing backslash in the value escapes the closing quote, so the JS string does not end and the following script is read as string content. `html.escape` does not escape backslash. Quotes become `&#x27;` and `&quot;`, which are not decoded inside script, so they do not close the string.
- Bad:
```python
name_js = f"var name = '{html.escape(name)}';"
page = f"<script>{name_js}</script>"
```
- Good: embed `json.dumps(value)` with `<`, `>` and `&` replaced by the JavaScript escapes `<`, `>` and `&` (type the backslash-u sequences); or put the value in a `data-` attribute (`html.escape` is valid there) and read it with `el.dataset.name` or `getAttribute`, never `textContent`.
- Not a defect when: `html.escape` is used for HTML text or a quoted HTML attribute value.

### Open redirect with backslash or userinfo tricks (CWE-601)
- Tell: a `next`, `return_to` or `url` parameter checked only with `startswith("/")` or a substring test on the host.
- Fails when: a slash followed by a backslash is treated by browsers as a protocol-relative URL to another host, and the check passes it.
- Bad:
```python
nxt = request.args.get("next", "/")
if nxt.startswith("/"): return redirect(nxt)
```
- Good: parse with `urlsplit`, reject any value with a scheme, a netloc or a backslash, then redirect to a safe default.
- Not a defect when: the target is picked from a fixed set of paths, or built with `url_for` from a route name.

### assert used for authorisation (CWE-285)
- Tell: `assert user.is_admin` or any `assert` guarding a permission or ownership decision.
- Fails when: the process runs with `-O` or `PYTHONOPTIMIZE`; the assert is stripped and the protected action runs for any caller.
- Bad:
```python
assert current_user.role == "qa_approver"
approve_batch(batch_id)
```
- Good: `if current_user.role != "qa_approver": raise PermissionError("role required")`.
- Not a defect when: assert only narrows a type for the checker (`assert isinstance(x, str)`) and no security decision depends on it.

### try/finally that returns and swallows the exception (CWE-391)
- Tell: `return`, `break` or `continue` inside a `finally:` block.
- Fails when: a `SignatureError` raised in the try body is discarded by the finally return, and the function returns `True`.
- Bad:
```python
def verify(sig):
    try: check_signature(sig)
    finally: return True
```
- Good: keep cleanup in `finally` without a return; return from the try body on success.
- Not a defect when: the try body cannot raise a security-relevant exception.

### Missing authentication or object-level authorisation (IDOR) (CWE-639, CWE-862)
- Tell: a handler without an auth decorator for this verb, or a lookup by id with no owner, tenant, site or role check on the handler.
- Fails when: user A sends the id of user B's order; the handler deletes it because the query filters by id only.
- Bad:
```python
@app.delete("/orders/<int:oid>")
def delete_order(oid): Order.query.filter_by(id=oid).delete()
```
- Good: `filter_by(id=oid, owner_id=current_user.id)`, and confirm the auth decorator covers the DELETE verb.
- Not a defect when: the record is a shared reference list that the spec says every authenticated user may change, or the handler enforces a role, site or tenant check that covers this lookup (for example `@require_role("qa_approver")` or `site_id=current_user.site_id` in the same query).

### Secrets or personal data in logs (CWE-532)
- Tell: a `logger` or `print` call receiving a password, token, key, session cookie or a whole request body.
- Fails when: a failed login logs the submitted password, so every operator with log access can read it.
- Bad:
```python
except AuthError:
    logger.info("login failed user=%s password=%s", user, password)
```
- Good: `logger.info("login failed user_id=%s", user_id)`; log identifiers, never values.
- Not a defect when: the logged value is a non-secret identifier or a fingerprint the spec allows.

### Hardcoded credentials (CWE-798)
- Tell: a string literal assigned to `password`, `secret`, `api_key` or `token`, or embedded in a connection string.
- Fails when: the literal is committed and valid in production; rotation needs a code change, and every repository reader holds it.
- Bad:
```python
DB_URL = "postgresql://svc:<password>@db01/qms"
engine = create_engine(DB_URL)
```
- Good: read from the secret store or environment at start (`os.environ["QMS_DB_URL"]`); report the name and location only.
- Not a defect when: the value is an obvious placeholder in an example file, or a fake value under tests or fixtures.

### Debug mode and verbose errors (CWE-489, CWE-209)
- Tell: `debug=True` in application startup, or exception text and stack traces returned in an HTTP response.
- Fails when: any caller who triggers an unhandled error sees the traceback and locals; the Werkzeug debugger is exposed.
- Bad:
```python
app = Flask(__name__)
app.run(host="0.0.0.0", debug=True)
```
- Good: debug read from configuration and off by default; return a generic message with a correlation id and log the traceback server-side.
- Not a defect when: debug is enabled only in a development-only entry point that production never runs.

### TLS verification disabled (CWE-295)
- Tell: `verify=False` on a requests call or session, or `CERT_NONE` or an unverified SSL context.
- Fails when: a man-in-the-middle presents any certificate and the client sends credentials or record data to it.
- Bad:
```python
resp = requests.post(url, data=payload, verify=False)
return resp.json()
```
- Good: keep default verification; for an internal CA pass `verify="/etc/pki/qms-ca.pem"`.
- Not a defect when: a test targets a local self-signed fixture server and the path cannot run in production.

### Missing audit event on a regulated record change (CWE-778)
- Tell: a function changes a regulated record (batch status, deviation, approval, result, signature) with no audit write in the same transaction.
- Fails when: a batch moves from HOLD to RELEASED with no entry recording actor, UTC time, and old and new value; the database holds no record of those facts for the change.
- Bad:
```python
batch.status = "RELEASED"
session.commit()
```
- Good: in the same transaction, add an `AuditEvent` with actor, UTC time, action, old and new value before `commit()`.
- Not a defect when: a database trigger or shared audit wrapper covers this call (confirm by searching the function and the audit module), or the field is not regulated.

### ReDoS from nested quantifiers (CWE-1333)
- Tell: a quantified group that contains its own quantifier, such as `(\w+\s?)+`, applied to request data.
- Fails when: a long run of matching characters followed by one non-matching character makes backtracking time grow exponentially and blocks a worker.
- Bad:
```python
def check(comment):
    return re.match(r"^(\w+\s?)+$", comment)
```
- Good: `re.fullmatch(r"\w+(?:\s\w+)*\s?", comment)`, which matches the same strings as the original (checked on all strings up to length 6 over a word, space, newline and hyphen alphabet) without a nested quantifier; or cap the length before matching.
- Not a defect when: the input length is bounded to a small constant before matching, or the pattern has no nested quantifier.

### OS command injection and eval/exec on request data (CWE-78, CWE-95, CWE-88)
- Tell: `os.system`, `os.popen`, `subprocess.*(..., shell=True)`, `eval` or `exec` with a request-derived string; or a request value passed as an argv element that starts with `-` to a program that accepts options (CWE-88).
- Fails when: shell control characters in the value (for example `;`, `&&` or `$(...)`) run a second command; an option-shaped value changes the program's behaviour.
- Bad:
```python
os.system(f"convert {name} out.png")
```
- Good: `subprocess.run(["convert", name, "out.png"], check=True)` with `shell` omitted, `name` checked against an allowlist, and `--` before user positional arguments where the program supports it; never `eval` on request data (use a parser, or `ast.literal_eval` for literals).
- Not a defect when: the command string is a constant, or the value is a validated integer.

## Traps
- Parameterised query with `?` or `%s` placeholders and a tuple of values: the driver escapes the values, so the statement text is fixed.
- Column or sort fragment picked from a constant allowlist dict: only constants reach the SQL text.
- `subprocess.run([...])` with an argv list and no `shell=True`: no shell parses the arguments.
- `yaml.safe_load` or `json.loads` on untrusted input: they build only plain data types, never objects.
- `hashlib.md5(data, usedforsecurity=False)` as a cache key: not a security use, so MD5 is acceptable here.
- Jinja2 with values passed as variables and a fixed template file: the engine never parses user text as template source. This clears SSTI only: with autoescape off, or with `|safe` or `Markup(value)`, user text is written into HTML as markup (see the XSS entry).

## Do not report
- Style, naming, formatting, or anything a linter, type checker or formatter already reports.
- Behaviour the spec or the change did not ask for, unless it is a security control already in scope.
- Theoretical issues with no source-to-sink path and no missing control shown.
- Pre-existing issues on untouched lines when a diff is given.
- Missing tests, missing docs, general design concerns, or generic hardening (rate limits, CSP, password policy) that no rule or changed code requires.
- Secret values, real or fake: report the file, line and kind only.

## Before you write a finding
1. Quote the exact line and name the sink it reaches.
2. Write the untrusted input and the outcome step by step, with the value at each step.
3. Search the same function, its callers and the sibling route or verb for the control; confirm it is absent or wrong, not merely present.
4. Confirm the line is in scope (diff-added or modified, or whole-file mode), then check the Traps and Do not report sections. If the path cannot be shown, drop the finding or mark it UNCLEAR. Describe any exploit or secret by class and location only.
