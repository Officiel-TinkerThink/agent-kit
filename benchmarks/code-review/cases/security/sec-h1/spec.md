# Lab document file service: intent (sec-h1)

Scope: files.py, archive.py and fetch.py of the lab document service.

- R1 Downloads: a document is served only when its resolved real path lies under the uploads root /srv/lab/uploads. A sibling directory whose name starts with the same characters is refused.
- R2 Batch archives: archive members are extracted only inside the batch staging directory. A member whose target would land outside that directory causes the archive to be rejected.
- R3 Partner fetch: only allowlisted partner hosts are contacted. A redirect from an allowlisted host must not lead to a host outside the allowlist or to a private network address.
- R4 Refusals are logged with the requester identity or host and the refused value.
