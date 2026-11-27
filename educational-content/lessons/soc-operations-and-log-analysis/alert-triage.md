## What a SOC does

A **Security Operations Centre** watches an organisation's systems, investigates alerts and coordinates
the response. The first job of a SOC analyst is **triage**: quickly deciding what each alert really is.

## Three possible verdicts

* **True positive** — malicious activity; escalate to an incident.
* **Benign / expected** — the rule was right, but the activity is authorised (e.g. an approved change).
* **False positive** — the rule fired on something that is not what it looks for.

## The five analyst questions (used by every rule in this platform)

1. What was detected?
2. Why does it matter?
3. What evidence supports the alert?
4. What should I investigate next?
5. What is the appropriate defensive response?

## Worked example (synthetic data)

Two alerts from **CSA-DET-004 (privileged group change)**:

| Alert | Context | Verdict |
|---|---|---|
| r.svensson → Backup Operators, by admin.ops | Ticket **CHG-1042**, approved | Expected activity |
| m.okafor → Domain Admins, by **m.okafor** | No ticket, account added itself, 22 minutes after a suspicious VPN login | True positive |

Same rule, same event type — opposite conclusions. Context is everything.

## Practical outcome

You can triage an alert, choose a verdict and write a short justification another analyst could check.
