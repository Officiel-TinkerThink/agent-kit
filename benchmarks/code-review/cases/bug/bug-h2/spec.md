# Spec: reagent lot expiry and nightly inventory job

Scope: schedule.py, expiry.py, notify.py (changed in this release); windows.py and clock.py are shared and unchanged.

- R1. The nightly inventory job runs once per calendar day at 02:00 America/New_York local time. On a day where 02:00 local does not exist (spring forward), the run is at the first instant after the gap. From the next day on, the run is again at 02:00 local.
- R2. next_daily_run(last_run_utc, zone) returns the aware UTC instant of the run that follows last_run_utc.
- R3. A reagent lot is usable on its expiry date inclusive: usable on day D when D <= expiry_date.
- R4. An opened lot is not usable once more than open_life_days have passed since opened_at_utc. Stored timestamps are timezone-aware UTC; the clock supplies the current instant.
- R5. usable(lot, clock) is False when R3 or R4 fails.
- R6. A check that cannot be evaluated (for example a comparison that raises) must fail closed: the lot is not reported usable.
- R7. build_digest lists, for each lot expiring within GRACE_DAYS (today and expiry date both inclusive), a notice when the lot is usable.
- R8. validate_lot rejects an empty lot_id, a non-positive open_life_days and a naive opened_at_utc.
