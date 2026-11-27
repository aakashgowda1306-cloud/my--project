## What an IPv4 address is

An IPv4 address is 32 bits, written as four numbers from 0 to 255: `10.20.4.27`.
Each number is called an **octet** (8 bits).

## What "/24" means

The number after the slash is the **prefix length**: how many bits belong to the *network*.
The remaining bits identify *hosts* inside that network.

`10.20.4.27/24` → the first 24 bits (`10.20.4`) are the network; the last 8 bits are for hosts.

## Three values to calculate

| Value | How | For 10.20.4.27/24 |
|---|---|---|
| Network address | Set all host bits to 0 | `10.20.4.0` |
| Broadcast address | Set all host bits to 1 | `10.20.4.255` |
| Usable hosts | 2^(host bits) − 2 | 2^8 − 2 = **254** |

We subtract 2 because the network and broadcast addresses cannot be given to devices.

## Private and documentation ranges

* Private (RFC 1918): `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` — used inside organisations.
* Documentation (RFC 5737): `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24` — reserved for examples.
  Every "external" address in Cybersec Academy comes from these, so no real host is ever involved.

## Practical outcome

You can work out which addresses belong to the same subnet — essential when deciding whether
traffic is internal or crossing a boundary.
