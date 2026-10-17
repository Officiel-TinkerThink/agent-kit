# Intent

Intent: Send a status notice to every order accepted in a batch, after the batch validation loop has completed.
Each accepted order receives exactly one notice, sent through the notify callable the caller passes in.
Notices are built as zero-argument callables and run by the scheduler after validation.
A failed notice can be resent through a retry path that targets only the orders whose earlier notice failed.
Order ids are validated before any notice is built, and the batch produces exactly one notice per distinct accepted order.
