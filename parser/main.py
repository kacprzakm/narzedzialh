import asyncio
import json
import os
import re
import sys
from email.message import Message
from email.parser import BytesParser
from email.policy import default as default_policy
from email.utils import parseaddr
from typing import Any

import httpx
import redis.asyncio as aioredis
from redis.exceptions import RedisError

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
RSPAMD_URL = os.getenv("RSPAMD_URL", "http://rspamd:11333")

EX_NOUSER = 67
EX_TEMPFAIL = 75


async def run(recipient: str, raw_message: bytes) -> int:
    local_part = recipient.split("@")[0]
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)

    try:
        job_id = await redis.get(f"rcpt:{local_part}")
        if not job_id:
            print(f"No job for {local_part}", file=sys.stderr)
            return EX_NOUSER

        msg = BytesParser(policy=default_policy).parsebytes(raw_message)
        analysis = await analyze(msg, raw_message, recipient)

        await redis.hset(
            f"job:{job_id}",
            mapping={"status": "completed", "result": json.dumps(analysis)},
        )
        ttl = int(os.getenv("JOB_TTL", "3600"))
        await redis.expire(f"job:{job_id}", ttl)
        return 0

    except RedisError as e:
        print(f"Redis error: {e}", file=sys.stderr)
        return EX_TEMPFAIL
    finally:
        await redis.aclose()


async def analyze(msg: Message, raw_message: bytes, recipient: str) -> dict[str, Any]:
    headers = {
        "from": str(msg.get("From", "")),
        "to": str(msg.get("To", "")),
        "subject": str(msg.get("Subject", "")),
        "message_id": str(msg.get("Message-ID", "")),
        "date": str(msg.get("Date", "")),
    }

    sender_ip = _extract_sender_ip(msg)
    helo = _extract_helo(msg)

    ptr_task = _ptr_lookup(sender_ip) if sender_ip else _noop(None)
    rbl_task = _check_rbl(sender_ip) if sender_ip else _noop([])
    envelope_from = parseaddr(str(msg.get("Return-Path", "")))[1] or parseaddr(headers["from"])[1]
    rspamd_task = _check_rspamd(raw_message, envelope_from, recipient)

    ptr, rbl, rspamd_raw = await asyncio.gather(ptr_task, rbl_task, rspamd_task)
    rspamd_parsed = parse_rspamd(rspamd_raw)

    return {
        "headers": headers,
        "sender_ip": sender_ip,
        "helo": helo,
        "ptr": ptr,
        "rbl": rbl,
        "recipient": recipient,
        "rspamd": rspamd_parsed,
    }


async def _noop(value: Any) -> Any:
    return value


_IP_RE = re.compile(r"\[(\d{1,3}(?:\.\d{1,3}){3})\]|\((?:.*?[\s\[])?(\d{1,3}(?:\.\d{1,3}){3})")


def _extract_sender_ip(msg: Message) -> str | None:
    received = msg.get_all("Received", [])
    for header in reversed(received):
        m = _IP_RE.search(str(header))
        if m:
            return m.group(1) or m.group(2)
    return None


def _extract_helo(msg: Message) -> str | None:
    received = msg.get_all("Received", [])
    pat = re.compile(r"from\s+(\S+)\s")
    for header in reversed(received):
        m = pat.search(str(header))
        if m:
            return m.group(1)
    return None


async def _ptr_lookup(ip: str) -> str | None:
    def _lookup() -> str | None:
        try:
            import dns.resolver
            import dns.reversename

            rev = dns.reversename.from_address(ip)
            ans = dns.resolver.resolve(rev, "PTR", lifetime=5)
            return str(ans[0]).rstrip(".")
        except Exception:
            return None

    return await asyncio.to_thread(_lookup)


async def _check_rbl(ip: str) -> list[dict[str, Any]]:
    rbls = [
        ("Spamhaus ZEN", "zen.spamhaus.org"),
        ("Barracuda", "b.barracudacentral.org"),
        ("SpamCop", "bl.spamcop.net"),
    ]
    reversed_ip = ".".join(reversed(ip.split(".")))

    def _query(host: str) -> bool | None:
        try:
            import dns.resolver

            dns.resolver.resolve(f"{reversed_ip}.{host}", "A", lifetime=3)
            return True
        except Exception as e:
            import dns.resolver

            if isinstance(e, dns.resolver.NXDOMAIN):
                return False
            return None

    tasks = [asyncio.to_thread(_query, host) for _, host in rbls]
    listed = await asyncio.gather(*tasks)
    return [
        {"rbl": name, "listed": listed[i]}
        for i, (name, _) in enumerate(rbls)
    ]


async def _check_rspamd(raw_message: bytes, sender: str, recipient: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{RSPAMD_URL}/checkv2",
                content=raw_message,
                headers={
                    "Content-Type": "application/octet-stream",
                    "From": sender,
                    "Rcpt": recipient,
                },
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        return {"error": "Rspamd niedostępny"}
    except Exception as e:
        return {"error": str(e)}


def parse_rspamd(r: dict[str, Any]) -> dict[str, Any]:
    if "error" in r:
        return {"error": r["error"]}

    score = r.get("score", 0.0)
    action = r.get("action", "unknown")
    thresholds = r.get("thresholds", {})
    symbols_raw = r.get("symbols", {})

    if action in ("reject", "add header") or score >= thresholds.get("add header", 6.0):
        verdict = "SPAM"
    elif action == "greylist" or score >= thresholds.get("greylist", 4.0):
        verdict = "GREYLIST"
    else:
        verdict = "HAM"

    def sym_score(s: dict[str, Any]) -> float:
        return s.get("metric_score", s.get("score", 0.0))

    triggered = sorted(
        [
            {
                "name": s["name"],
                "score": sym_score(s),
                "description": s.get("description", ""),
                "options": s.get("options", []),
            }
            for s in symbols_raw.values()
            if sym_score(s) != 0.0
        ],
        key=lambda x: abs(x["score"]),
        reverse=True,
    )

    dns: dict[str, Any] = {}
    for s in symbols_raw.values():
        name = s["name"]
        entry = {
            "symbol": name,
            "score": sym_score(s),
            "description": s.get("description", ""),
            "options": s.get("options", []),
        }
        if name.startswith("R_SPF"):
            dns.setdefault("spf", entry)
        elif name.startswith("R_DKIM"):
            dns.setdefault("dkim", entry)
        elif name.startswith("DMARC"):
            dns.setdefault("dmarc", entry)

    return {
        "verdict": verdict,
        "action": action,
        "score": score,
        "required_score": r.get("required_score", 15.0),
        "thresholds": thresholds,
        "dns": dns,
        "triggered_symbols": triggered,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: main.py <recipient_email>", file=sys.stderr)
        sys.exit(EX_TEMPFAIL)

    recipient_arg = sys.argv[1]
    raw = sys.stdin.buffer.read()
    sys.exit(asyncio.run(run(recipient_arg, raw)))
