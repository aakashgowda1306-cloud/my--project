## No single wall is perfect

A castle has a moat, walls, guards and a locked keep. If one fails, the next still helps.
**Defence in depth** applies the same idea to IT: several independent layers of controls.

## Three kinds of control

| Type | Purpose | Example |
|---|---|---|
| **Preventive** | Stop it happening | MFA, firewall rules, disabling password SSH |
| **Detective** | Notice it happening | SIEM detection rules, audit logs |
| **Corrective** | Recover afterwards | Restoring backups, resetting credentials |

## Worked example: the m.okafor case (fictional)

1. MFA on the VPN would have *prevented* the guessed password from being enough.
2. Rule **CSA-DET-003** *detected* the success after failures.
3. Resetting the password and removing the Domain Admins membership *corrects* the damage.

Notice that the attacker also cleared the audit log (event 1102). Sending logs to a central SIEM is a
layer that protects your *detective* controls themselves.

## Practical outcome

For any attack you study, you can list at least one preventive, one detective and one corrective control.
