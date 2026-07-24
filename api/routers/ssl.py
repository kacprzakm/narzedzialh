import asyncio
import datetime
import ipaddress
import socket
import ssl
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()

ALLOWED_PORTS = {443, 8443, 465, 993, 995, 25, 587}


class SSLCheckError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _resolve_public_ip(host: str) -> str:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise SSLCheckError(f"Nie można rozwiązać hosta: {host}") from e

    for info in infos:
        addr = info[4][0]
        ip = ipaddress.ip_address(addr.split("%")[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise SSLCheckError("Adres docelowy jest niedozwolony")

    return infos[0][4][0]


def _check_ssl_sync(host: str, port: int = 443) -> dict[str, Any]:
    ctx = ssl.create_default_context()

    ip = _resolve_public_ip(host)

    try:
        with socket.create_connection((ip, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                cipher = ssock.cipher()
                version = ssock.version()
    except ssl.SSLCertVerificationError as e:
        raise SSLCheckError(f"Weryfikacja certyfikatu nie powiodła się: {e.reason}") from e
    except socket.gaierror as e:
        raise SSLCheckError(f"Nie można rozwiązać hosta: {host}") from e
    except (TimeoutError, ConnectionRefusedError, OSError) as e:
        raise SSLCheckError(f"Połączenie nie powiodło się: {e}") from e

    if not cert:
        raise SSLCheckError("Serwer nie zwrócił certyfikatu")

    not_after_str = cert.get("notAfter", "")
    not_before_str = cert.get("notBefore", "")
    not_after = datetime.datetime.strptime(
        not_after_str, "%b %d %H:%M:%S %Y %Z"
    ).replace(tzinfo=datetime.UTC)
    days_left = (not_after - datetime.datetime.now(datetime.UTC)).days

    san_list = [v for typ, v in cert.get("subjectAltName", []) if typ == "DNS"]

    subject = dict(x[0] for x in cert.get("subject", []))
    issuer = dict(x[0] for x in cert.get("issuer", []))

    return {
        "host": host,
        "port": port,
        "cn": subject.get("commonName"),
        "sans": san_list,
        "valid_from": not_before_str,
        "valid_to": not_after_str,
        "days_left": days_left,
        "expired": days_left < 0,
        "issuer_cn": issuer.get("commonName"),
        "issuer_org": issuer.get("organizationName"),
        "tls_version": version,
        "cipher_suite": cipher[0] if cipher else None,
    }


@router.get("/{host}")
async def check_ssl(host: str, port: int = 443) -> dict[str, Any]:
    if port not in ALLOWED_PORTS:
        raise HTTPException(status_code=400, detail="Niedozwolony port")
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _check_ssl_sync, host, port)
    except SSLCheckError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
