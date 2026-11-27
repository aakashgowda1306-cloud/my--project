## DNS: the phone book

Computers connect to **IP addresses**, people remember **names**. DNS (UDP port 53) answers the question
"what is the address of `lnx-web-01.corp.example`?" Defenders love DNS logs because nearly every
connection starts with a lookup.

## HTTP: the request and the response

A browser sends a request such as:

```
GET /api/products HTTP/1.1
Host: lnx-web-01.corp.example
```

The server replies with a **status code**: `200` OK, `304` not modified, `404` not found, `500` server error.
Our application logs contain these codes — a sudden burst of 404s can mean someone is probing for files.

## HTTPS: HTTP inside TLS

HTTPS wraps HTTP in **TLS encryption**.

| An observer on the network… | HTTP | HTTPS |
|---|---|---|
| can see the destination IP | yes | yes |
| can see the page content and passwords | **yes** | no |

So HTTPS protects *confidentiality* of the content, but defenders can still analyse *who talks to whom*.

## Practical outcome

You can explain what evidence is available from DNS, HTTP and HTTPS traffic — and what is hidden.
