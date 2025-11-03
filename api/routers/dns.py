import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()

DNS_SERVERS = [
    {"name": "Google (1)", "ip": "8.8.8.8"},
    {"name": "Google (2)", "ip": "8.8.4.4"},
    {"name": "Cloudflare (1)", "ip": "1.1.1.1"},
    {"name": "Cloudflare (2)", "ip": "1.0.0.1"},
    {"name": "OpenDNS", "ip": "208.67.222.222"},
    {"name": "Quad9", "ip": "9.9.9.9"},
    {"name": "Level3", "ip": "4.2.2.2"},
    {"name": "Comodo", "ip": "8.26.56.26"},
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
            "+time=3",
            "+tries=1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        output = stdout.decode().strip()
        return sorted(output.splitlines()) if output else []
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

    unique_answers = {tuple(r) for r in results}
    propagated = len(unique_answers) == 1

    return {
        "domain": domain,
        "record_type": record_type,
        "propagated": propagated,
        "unique_answers": len(unique_answers),
        "servers": servers_with_results,
    }
