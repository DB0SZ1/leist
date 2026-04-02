"""
Layer 4 — Catch-All Detection
SMTP probe to detect catch-all (accept-all) domains.
Domain-deduplicated: probes once per unique domain, not per email.
"""
import asyncio
import random
import string
from .base import BaseLayer, LayerResult
import structlog

log = structlog.get_logger()


def _random_local() -> str:
    """Generate a random address that almost certainly doesn't exist."""
    return "zzz" + "".join(random.choices(string.ascii_lowercase + string.digits, k=10))


class CatchallLayer(BaseLayer):
    layer_id = "catchall"

    async def bulk_lookup(self, keys: list[str], **kwargs) -> dict[str, tuple[bool | None, str]]:
        """
        Deduplicate SMTP probes by domain.
        keys: list of unique domain strings
        kwargs may include: mx_records_map: dict[domain, list[mx_hostnames]]
        Returns: {domain: (is_catchall, confidence)}
        """
        mx_map = kwargs.get("mx_records_map", {})
        results = {}

        for domain in keys:
            mx_hosts = mx_map.get(domain, [])
            if not mx_hosts:
                results[domain] = (None, "unknown")
                continue
            try:
                is_catchall, confidence = await self._smtp_probe(domain, mx_hosts[0])
                results[domain] = (is_catchall, confidence)
            except Exception as e:
                log.warning("catchall.probe_failed", domain=domain, error=str(e)[:200])
                results[domain] = (None, "unknown")

        return results

    async def run(self, row: dict, context: dict) -> LayerResult:
        try:
            email = row.get("email", "").lower().strip()
            domain = email.split("@")[1] if "@" in email else ""

            # Look up pre-computed result from bulk_lookup
            catchall_results = context.get("catchall_results", {})
            result = catchall_results.get(domain, (None, "unknown"))

            return LayerResult(
                layer_id=self.layer_id,
                success=True,
                is_catchall=result[0],
                catchall_confidence=result[1],
            )
        except Exception as e:
            log.error("layer.catchall.failed", error=str(e)[:200])
            return LayerResult(
                layer_id=self.layer_id, success=False,
                error=str(e)[:200],
            )

    async def _smtp_probe(self, domain: str, mx_host: str) -> tuple[bool | None, str]:
        """
        Send RCPT TO with a random address to detect catch-all.
        Returns (is_catchall, confidence).
        """
        random_email = f"{_random_local()}@{domain}"

        # Try port 25 first, then 587
        for port in (25, 587):
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(mx_host, port),
                    timeout=10,
                )
                try:
                    # Read banner
                    await asyncio.wait_for(reader.readline(), timeout=5)

                    # EHLO
                    writer.write(b"EHLO listintel.io\r\n")
                    await writer.drain()
                    while True:
                        line = await asyncio.wait_for(reader.readline(), timeout=5)
                        if line[3:4] == b" ":
                            break

                    # MAIL FROM
                    writer.write(b"MAIL FROM:<probe@listintel.io>\r\n")
                    await writer.drain()
                    await asyncio.wait_for(reader.readline(), timeout=5)

                    # RCPT TO with random address
                    writer.write(f"RCPT TO:<{random_email}>\r\n".encode())
                    await writer.drain()
                    rcpt_response = await asyncio.wait_for(reader.readline(), timeout=5)

                    code = int(rcpt_response[:3].decode())

                    return (
                        code in (250, 251),                       # accepted = catchall
                        "high" if code in (250, 251, 550, 551, 552, 553, 554) else
                        "medium" if 400 <= code < 500 else        # 4xx = ambiguous
                        "low",
                    )
                finally:
                    try:
                        writer.write(b"QUIT\r\n")
                        await writer.drain()
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass

            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                continue  # try next port

        return (None, "unknown")  # could not reach on either port
