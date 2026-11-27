## Two ways to send data

* **TCP** is like a phone call: both sides agree to talk first, data arrives in order, losses are resent.
* **UDP** is like posting a postcard: fast and simple, no guarantee of delivery.

## The TCP three-way handshake

1. **SYN** — client: "I want to talk. My starting number is 1000."
2. **SYN-ACK** — server: "OK. Mine is 5000. I got your 1000."
3. **ACK** — client: "Got your 5000." → connection established.

The Network Lab shows these packets step by step from pre-generated data.

## Ports

A **port** identifies which program on a host should receive the data.

| Port | Usually |
|---|---|
| 22/tcp | SSH |
| 53/udp | DNS |
| 80/tcp | HTTP |
| 443/tcp | HTTPS |

## Why defenders care

In our synthetic dataset, `ws-fin-02` connects to `203.0.113.200` on **port 4444** five times,
exactly 60 seconds apart. Ordinary business software rarely uses 4444, and humans do not click on a
perfect schedule. That combination suggests **beaconing** — malware checking in with its controller.

## Practical outcome

Given a connection record you can say which protocol and service it likely represents, and spot
patterns (unusual ports, regular timing) worth investigating.
