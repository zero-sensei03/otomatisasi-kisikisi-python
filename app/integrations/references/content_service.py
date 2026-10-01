import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx


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

    def fetch(self, url: str, max_characters: int) -> tuple[str | None, str | None, str | None]:
        try:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("URL tidak valid.")
            expected_port = 443 if parsed.scheme == "https" else 80
            if parsed.port not in (None, expected_port):
                raise ValueError("Port URL tidak diizinkan.")
            addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
            if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
                raise ValueError("URL tujuan tidak diizinkan.")
            allowed_addresses = {ipaddress.ip_address(item[4][0]) for item in addresses}
            with httpx.Client(timeout=12, follow_redirects=False, trust_env=False, headers={"User-Agent": "KisiKisiAI/1.0", "Accept": "text/html,text/plain"}) as client:
                with client.stream("GET", url) as response:
                    if response.url.hostname != parsed.hostname:
                        raise ValueError("Host referensi berubah.")
                    network_stream = response.extensions.get("network_stream")
                    if network_stream is not None:
                        peer = network_stream.get_extra_info("server_addr")
                        if peer and ipaddress.ip_address(peer[0]) not in allowed_addresses:
                            raise ValueError("Alamat server referensi berubah setelah resolusi DNS.")
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    if content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
                        raise ValueError("Tipe konten referensi tidak didukung.")
                    declared_size = response.headers.get("content-length")
                    if declared_size and int(declared_size) > self.max_response_bytes:
                        raise ValueError("Konten referensi terlalu besar.")
                    chunks = bytearray()
                    for chunk in response.iter_bytes():
                        if len(chunks) + len(chunk) > self.max_response_bytes:
                            raise ValueError("Konten referensi terlalu besar.")
                        chunks.extend(chunk)
                    html = bytes(chunks).decode(response.encoding or "utf-8", errors="replace")
            parser = _TextParser()
            parser.feed(html)
            content = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()[:max_characters]
            if not content:
                return None, None, "Halaman tidak berisi teks yang dapat digunakan."
            return content, parsed.hostname, None
        except Exception:
            return None, None, "Referensi gagal diambil."
