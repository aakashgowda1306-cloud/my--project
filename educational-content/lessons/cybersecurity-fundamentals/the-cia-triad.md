## The big idea

Security protects three things about information. Together they are called the **CIA triad**:

| Letter | Property | Simple meaning | Everyday example |
|---|---|---|---|
| C | **Confidentiality** | Only the right people can read it | Your exam results are not visible to other students |
| I | **Integrity** | Nobody can change it without permission | Nobody can edit your marks after they are published |
| A | **Availability** | It is there when you need it | The results portal works on results day |

Almost every security incident damages at least one of these.

## Worked example

ExampleCorp (a fictional company) has an online shop.

* A stolen password lets someone **read** customer orders → *confidentiality* is harmed.
* Someone **changes** product prices in the database → *integrity* is harmed.
* The shop is **flooded** with traffic and goes offline → *availability* is harmed.

## Controls for each property

* Confidentiality → encryption, strong authentication, access control.
* Integrity → hashing, digital signatures, change control, audit logs.
* Availability → backups, redundancy, capacity planning, DDoS protection.

## In the lab

In the **Digital Forensics Lab** you will compute a SHA-256 hash of an evidence file. That is an
*integrity* check: if one byte changes, the hash changes.

## Practical outcome

After this lesson you can look at any incident and say which part of the CIA triad it harmed —
the first line of every incident report.
