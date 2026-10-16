Intent: remove the patient-id branch in IntakeLookupService.lookup, since parse_payload already validates the request and the branch is dead code.
Scope: cleanup only; the timing log and the not-found path stay as they are.
