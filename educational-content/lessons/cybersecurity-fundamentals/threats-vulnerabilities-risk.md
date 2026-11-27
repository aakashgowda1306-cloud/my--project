## Three words defenders use every day

* **Asset** — something worth protecting (a server, customer data, a user account).
* **Vulnerability** — a weakness in the asset (SSH accepts passwords; software is out of date).
* **Threat** — someone or something that could exploit the weakness (an automated password-guessing tool).

**Risk** = how *likely* the threat exploits the vulnerability × how bad the *impact* would be.

## Worked example (from our synthetic dataset)

| Piece | ExampleCorp bastion server |
|---|---|
| Asset | `lnx-bastion-01`, the jump server administrators use |
| Vulnerability | It accepted password logins for `root` |
| Threat | An automated tool at `203.0.113.45` trying passwords |
| Impact | Full control of the server if a password is guessed |

## Reducing risk

You can reduce **likelihood** (disable password logins, use keys, block the source) or reduce
**impact** (least privilege, segmentation, backups). In the dataset, an administrator later
applied change ticket `CHG-1038` to set `PasswordAuthentication no` — a likelihood reduction.

## Practical outcome

You can describe a security problem in one clear sentence:
*"A [threat] could exploit [vulnerability] in [asset], causing [impact]; we reduce it by [control]."*
