import ipaddress
import logging
import re
import socket
from html.parser import HTMLParser
from typing import ClassVar
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


class ReferenceContentService:
    max_response_bytes = 2 * 1024 * 1024
    max_redirects = 5
    timeout_seconds = 12
    allowed_content_types: ClassVar[frozenset[str]] = frozenset({"text/html", "text/plain", "application/xhtml+xml"})
    blocked_hosts: ClassVar[frozenset[str]] = frozenset({"localhost", "metadata", "metadata.google", "metadata.google.internal"})

    def __init__(self, *, transport: httpx.BaseTransport | None = None):
        # The optional transport is an injection point for deterministic HTTPX tests.
        self._transport = transport

    @staticmethod
    def safe_log_url(url: str) -> str:
        try:
            parsed = urlparse(url)
            if not parsed.hostname:
                return "invalid-url"
            return f"{parsed.scheme}://{parsed.hostname}{parsed.path}"
        except ValueError:
            return "invalid-url"

    @staticmethod
    def _resolve_public_addresses(url: httpx.URL) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        host = url.host.rstrip(".").casefold()
        if not host or host in ReferenceContentService.blocked_hosts or host.endswith(".localhost"):
            raise ValueError("Host lokal atau metadata tidak diizinkan.")

        expected_port = 443 if url.scheme == "https" else 80
        if url.port not in (None, expected_port):
            raise ValueError("Port URL tidak diizinkan.")

        try:
            literal_ip = ipaddress.ip_address(host)
        except ValueError:
            literal_ip = None
        if literal_ip is not None:
            addresses = {literal_ip}
        else:
            try:
                resolved = socket.getaddrinfo(host, expected_port, type=socket.SOCK_STREAM)
            except socket.gaierror as exc:
                raise ValueError("Host URL referensi tidak valid atau tidak dapat diakses.") from exc
            addresses = {ipaddress.ip_address(item[4][0].split("%", 1)[0]) for item in resolved}

        if not addresses or any(not address.is_global for address in addresses):
            raise ValueError("URL tujuan harus mengarah ke alamat IP publik.")
        return addresses

    @staticmethod
    def _verify_connected_peer(response: httpx.Response, allowed_addresses) -> None:
        network_stream = response.extensions.get("network_stream")
        if network_stream is None:
            return
        peer = network_stream.get_extra_info("server_addr")
        if not peer:
            return
        peer_ip = ipaddress.ip_address(peer[0].split("%", 1)[0])
        if peer_ip not in allowed_addresses or not peer_ip.is_global:
            raise ValueError("Alamat server referensi berubah setelah resolusi DNS.")

    def _open_client(self) -> httpx.Client:
        return httpx.Client(
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=False,
            trust_env=False,
            transport=self._transport,
            headers={"User-Agent": "KisiKisiAI/1.0", "Accept": "text/html,text/plain"},
        )

    def _read_response(self, response: httpx.Response) -> str:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type not in self.allowed_content_types:
            raise ValueError("Tipe konten referensi tidak didukung.")
        declared_size = response.headers.get("content-length")
        if declared_size:
            try:
                if int(declared_size) > self.max_response_bytes:
                    raise ValueError("Konten referensi terlalu besar.")
            except ValueError as exc:
                if str(exc) == "Konten referensi terlalu besar.":
                    raise
                raise ValueError("Ukuran response referensi tidak valid.") from exc

        chunks = bytearray()
        for chunk in response.iter_bytes():
            if len(chunks) + len(chunk) > self.max_response_bytes:
                raise ValueError("Konten referensi terlalu besar.")
            chunks.extend(chunk)
        return bytes(chunks).decode(response.encoding or "utf-8", errors="replace")

    def _fetch_text(self, initial_url: str) -> tuple[str, str]:
        try:
            current_url = httpx.URL(initial_url)
        except (httpx.InvalidURL, ValueError) as exc:
            raise ValueError("URL referensi tidak valid.") from exc

        if current_url.scheme not in {"http", "https"} or not current_url.host:
            raise ValueError("URL referensi harus menggunakan HTTP atau HTTPS.")
        if current_url.username or current_url.password:
            raise ValueError("URL dengan credential tidak diizinkan.")

        visited = set()
        with self._open_client() as client:
            for redirect_count in range(self.max_redirects + 1):
                if current_url in visited:
                    raise ValueError("Redirect referensi berulang.")
                visited.add(current_url)
                allowed_addresses = self._resolve_public_addresses(current_url)
                current_host = current_url.host.rstrip(".").casefold()
                current_port = current_url.port or (443 if current_url.scheme == "https" else 80)

                with client.stream("GET", current_url) as response:
                    # Redirects are handled manually so their targets receive the same
                    # scheme, port, DNS, and address checks before another request.
                    response_host = response.url.host.rstrip(".").casefold()
                    response_port = response.url.port or (443 if response.url.scheme == "https" else 80)
                    if response_host != current_host or response_port != current_port:
                        raise ValueError("Host response tidak sesuai dengan URL yang diminta.")
                    self._verify_connected_peer(response, allowed_addresses)

                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise ValueError("Redirect referensi tidak memiliki tujuan.")
                        if redirect_count >= self.max_redirects:
                            raise ValueError("Referensi melebihi batas jumlah redirect.")
                        try:
                            target = response.url.join(location)
                        except (httpx.InvalidURL, ValueError) as exc:
                            raise ValueError("Tujuan redirect tidak valid.") from exc
                        if target.scheme not in {"http", "https"} or not target.host:
                            raise ValueError("Redirect hanya boleh menuju HTTP atau HTTPS.")
                        if target.username or target.password:
                            raise ValueError("Redirect dengan credential tidak diizinkan.")
                        # The next loop iteration validates DNS/IP before issuing it.
                        current_url = target
                        continue

                    html = self._read_response(response)
                    return html, current_host

        raise ValueError("Referensi melebihi batas jumlah redirect.")

    def fetch(self, url: str, max_characters: int) -> tuple[str | None, str | None, str | None]:
        host = "unknown"
        try:
            try:
                host = httpx.URL(url).host or "unknown"
            except (httpx.InvalidURL, ValueError):
                pass
            html, final_host = self._fetch_text(url)
            parser = _TextParser()
            parser.feed(html)
            content = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()[:max_characters]
            if not content:
                return None, None, "Halaman tidak berisi teks yang dapat digunakan."
            return content, final_host, None
        except (ValueError, OSError, httpx.HTTPError, OverflowError) as exc:
            if isinstance(exc, httpx.TimeoutException):
                reason = "Referensi timeout."
            elif isinstance(exc, httpx.HTTPStatusError):
                reason = f"Server referensi mengembalikan HTTP {exc.response.status_code}."
            elif isinstance(exc, httpx.HTTPError):
                reason = f"Referensi gagal diakses ({type(exc).__name__})."
            else:
                reason = str(exc) or "Referensi gagal diproses."
            logger.warning(
                "reference extraction failed host=%s error_type=%s reason=%s",
                host,
                type(exc).__name__,
                reason,
            )
            return None, None, reason
