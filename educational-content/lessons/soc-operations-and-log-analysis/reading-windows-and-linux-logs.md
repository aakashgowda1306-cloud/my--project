## Windows Security event IDs worth memorising

| ID | Meaning | Why it matters |
|---|---|---|
| 4624 | Successful logon | Who signed in, from where, how (logon type) |
| 4625 | Failed logon | Bursts suggest password guessing |
| 4688 | Process created | Shows command lines (e.g. encoded PowerShell) |
| 4698 | Scheduled task created | Common persistence method |
| 4728 / 4732 | Member added to a security group | Privilege changes |
| 4719 | Audit policy changed | Someone may be turning logging off |
| 7045 | Service installed | Another persistence method |
| 1102 | Audit log cleared | Very rarely legitimate |

**Logon types** in 4624/4625: 2 = at the keyboard, 3 = over the network, 5 = service, 10 = Remote Desktop.

## Linux authentication logs

On Debian/Ubuntu, `sshd` writes to `/var/log/auth.log` (or view it with `journalctl -u ssh`):

```
sshd[2140]: Failed password for root from 203.0.113.45 port 40000 ssh2
sshd[2210]: Accepted publickey for admin.ops from 10.20.4.20 port 51022 ssh2
```

Read it left to right: *program* → *result* → *account* → *source address* → *source port*.

## Practical outcome

You can open an unfamiliar log, find the authentication and persistence events, and explain each in plain
language — exactly what the SIEM Investigation Lab asks you to do.
