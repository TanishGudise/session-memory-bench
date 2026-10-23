# Changelog

## 2026-09-30
- New `notify.mailer.dispatch()` for all email. It checks marketing opt-outs and adds the List-Unsubscribe headers the big mailbox providers require for bulk mail.
- `notify.email.send_email()` is deprecated: it sends the bare message (no opt-out check, no List-Unsubscribe), so marketing mail sent through it lands in spam. The weekly digest moved to `dispatch()`.
- Added the `newsletter` template.

## 2026-09-24
- Standard retry policy in `notify/retry.py`: 5 attempts, waiting 1, 2, 4, 8 seconds. Webhooks use it.
