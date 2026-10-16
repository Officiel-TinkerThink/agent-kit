# Spec: lab portal sessions and account creation (sec-h2)

- R1 Session tokens are compact HS256 tokens signed with LAB_TOKEN_SECRET; the verifier accepts only HS256 and checks the signature before the payload is trusted.
- R2 Usernames are 3-20 characters from a-z, 0-9 and underscore only; line breaks are never accepted, because the name is written into one audit log line per entry.
- R3 Account creation accepts only username, display_name and role from the client; is_admin is set by administrators only.
- R4 Reset codes and token signatures are compared in constant time.
