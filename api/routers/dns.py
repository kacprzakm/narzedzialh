import asyncio
import re
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9_-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9_-]{1,63}(?<!-))*\.?$"
)

DNS_SERVERS = [
    {"name": "Google (1)", "ip": "8.8.8.8"},
    {"name": "Google (2)", "ip": "8.8.4.4"},
    {"name": "Cloudflare (1)", "ip": "1.1.1.1"},
    {"name": "Cloudflare (2)", "ip": "1.0.0.1"},
    {"name": "OpenDNS", "ip": "208.67.222.222"},
    {"name": "Quad9 (CH)", "ip": "9.9.9.9"},
    {"name": "114DNS (CN)", "ip": "114.114.114.114"},
    {"name": "DNS.WATCH (DE)", "ip": "84.200.69.80"},
    {"name": "CZ.NIC (CZ)", "ip": "193.17.47.1"},
    {"name": "UncensoredDNS (DK)", "ip": "91.239.100.100"},
    {"name": "AliDNS (CN)", "ip": "223.5.5.5"},
    {"name": "Yandex (RU)", "ip": "77.88.8.8"},
    {"name": "TENET (ZA)", "ip": "196.216.2.2"},
    {"name": "AdGuard (CY)", "ip": "176.103.130.130"},
    {"name": "NIC.br (BR)", "ip": "200.160.0.8"},
    {"name": "KT (KR)", "ip": "168.126.63.1"},
]

VALID_RECORD_TYPES = {"A", "AAAA", "MX", "TXT", "NS", "CNAME", "SOA", "PTR"}


async def _dig_one(server_ip: str, domain: str, record_type: str) -> list[str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "dig",
            f"@{server_ip}",
            domain,
            record_type,
            "+short",
            "+time=1",
            "+tries=1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=1.0)
        lines = [l for l in stdout.decode().splitlines() if l and not l.startswith(";")]
        return sorted(lines)
    except TimeoutError:
        return []
    except Exception:
        return []


@router.get("/{domain}/{record_type}")
async def check_dns(domain: str, record_type: str) -> dict[str, Any]:
    record_type = record_type.upper()
    if record_type not in VALID_RECORD_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid record type. Valid: {', '.join(sorted(VALID_RECORD_TYPES))}",
        )

    if not DOMAIN_RE.match(domain):
        raise HTTPException(status_code=400, detail="Nieprawidłowa domena")

    tasks = [_dig_one(s["ip"], domain, record_type) for s in DNS_SERVERS]
    results = await asyncio.gather(*tasks)

    servers_with_results = [
        {
            "server": DNS_SERVERS[i]["name"],
            "ip": DNS_SERVERS[i]["ip"],
            "records": results[i],
        }
        for i in range(len(DNS_SERVERS))
    ]

    non_empty = [r for r in results if r]
    unique_answers = {tuple(r) for r in non_empty} if non_empty else set()
    propagated = len(unique_answers) == 1

    return {
        "domain": domain,
        "record_type": record_type,
        "propagated": propagated,
        "unique_answers": len(unique_answers) if unique_answers else 0,
        "servers": servers_with_results,
    }
