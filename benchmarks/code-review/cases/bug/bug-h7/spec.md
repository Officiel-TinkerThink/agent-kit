# Intent

Intent: Enforce expiry for session tokens issued from identity-provider login.
A token is expired when the current time is at or after the expiry instant the identity provider states for it.
A token that has been idle longer than the configured timeout is also expired.
Issuing a token requires the subject and the identity-provider expiry value.
Lookups return None for an expired token and remove it from the store.
