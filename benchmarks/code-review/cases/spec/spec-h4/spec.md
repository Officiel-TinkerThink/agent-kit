# Release version and timestamp rules

Scope: release-check gate for component manifests (versions.py, timestamps.py, manifest.py, release_check.py, cli.py).

R1 Version components compare numerically per component (1.10.0 is higher than 1.9.0).
R2 A pre-release has lower precedence than its release (1.0.0-rc1 is lower than 1.0.0).
R3 Build metadata after + is ignored in precedence.
R4 RFC 3339 timestamps accept lower-case t and z.
R5 A timestamp must carry an offset or Z.
R6 Manifest entries are sorted ascending by precedence.
