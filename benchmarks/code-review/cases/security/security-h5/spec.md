# Lab profile service: name normalisation, URL import, route access

Scope: change adds (1) profile creation with name validation, (2) import of a profile export from a URL, (3) an audit export route. Files: names.py, fetcher.py, routes.py, auth.py, config.py.

## Requirements

- R1 Profile names are validated on their canonical form. A canonical name (NFKC, trimmed) must not contain any character listed in BANNED_NAME_CHARS, and its length must be between 1 and MAX_NAME_LENGTH characters inclusive.
- R2 Lookup keys are derived from the canonical form with the same checks as R1 applied before the key is returned.
- R3 Profile creation rejects a name that fails R1 with HTTP 400 and does not store anything.
- R4 URL import accepts only the https scheme. The host that the allow-list check accepts must be the host the request is sent to.
- R5 Every route registered in routes.ROUTES requires a valid session token. No route is public.
- R6 A request whose service token is not configured is rejected, never accepted.
- R7 Import size is limited to MAX_IMPORT_BYTES; larger bodies raise FetchError.
