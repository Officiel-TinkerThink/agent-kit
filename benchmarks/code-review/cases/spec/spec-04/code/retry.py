import time


class TransientError(Exception):
    """Raised by fn when the failure is safe to retry."""


def call_with_retry(fn, audit, max_attempts=3, base_delay_s=0.5):
    """Call fn, retrying on TransientError with exponential backoff."""
    attempt = 0
    while True:
        attempt += 1
        try:
            result = fn()
        except TransientError:
            audit.append({"attempt": attempt, "outcome": "transient_error"})
            if attempt >= max_attempts:
                raise
            time.sleep(base_delay_s * 2 ** (attempt - 1))
            continue
        except Exception:
            audit.append({"attempt": attempt, "outcome": "fatal_error"})
            raise
        audit.append({"attempt": attempt, "outcome": "success"})
        return result


if __name__ == "__main__":
    log = []
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise TransientError("temporary")
        return "ok"

    print(call_with_retry(flaky, log, base_delay_s=0.01), log)
