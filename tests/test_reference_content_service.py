from __future__ import annotations

import socket

import httpx
import pytest

from app.integrations.references.content_service import ReferenceContentService

PUBLIC_IP = "93.184.216.34"


def public_dns(monkeypatch):
    monkeypatch.setattr(
        "app.integrations.references.content_service.socket.getaddrinfo",
        lambda host, port, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (PUBLIC_IP, port))
        ],
    )


def service_with_responses(monkeypatch, responses):
    public_dns(monkeypatch)
    requests = []

    def handler(request):
        requests.append(request)
        outcome = responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        status, headers, body = outcome
        return httpx.Response(status, headers=headers, content=body, request=request)

    transport = httpx.MockTransport(handler)
    return ReferenceContentService(transport=transport), requests


def ok(body=b"<html><body>Materi sumber</body></html>", *, content_type="text/html"):
    return 200, {"content-type": content_type}, body


def test_public_url_without_redirect_uses_httpx_url_host(monkeypatch):
    service, requests = service_with_responses(monkeypatch, [ok()])

    content, title, error = service.fetch("https://Example.com/materi", 1000)

    assert (content, title, error) == ("Materi sumber", "example.com", None)
    assert len(requests) == 1


def test_public_translate_goog_url_is_allowed(monkeypatch):
    service, _requests = service_with_responses(monkeypatch, [ok()])

    content, title, error = service.fetch("https://example-com.translate.goog/page?_x_tr_sl=auto", 1000)

    assert content == "Materi sumber"
    assert title == "example-com.translate.goog"
    assert error is None


def test_public_redirect_to_a_different_domain_is_revalidated_and_allowed(monkeypatch):
    service, requests = service_with_responses(
        monkeypatch,
        [(302, {"location": "https://translated.example.net/page"}, b""), ok(b"<p>Konten alihan</p>")],
    )

    content, title, error = service.fetch("https://example.com/page", 1000)

    assert (content, title, error) == ("Konten alihan", "translated.example.net", None)
    assert [request.url.host for request in requests] == ["example.com", "translated.example.net"]


def test_malformed_url_returns_failure_without_attribute_error():
    content, title, error = ReferenceContentService().fetch("http://[malformed", 1000)
    assert content is None
    assert title is None
    assert "URL" in error


def test_redirect_loop_is_rejected(monkeypatch):
    service, requests = service_with_responses(
        monkeypatch,
        [(302, {"location": "/same"}, b"")],
    )

    content, title, error = service.fetch("https://example.com/same", 1000)

    assert content is None and title is None
    assert "Redirect" in error
    assert len(requests) == 1


@pytest.mark.parametrize("location", ["http://localhost/private", "http://127.0.0.1/private", "http://10.0.0.1/private", "http://169.254.169.254/latest/meta-data/"])
def test_redirect_to_local_private_or_metadata_target_is_rejected(monkeypatch, location):
    service, requests = service_with_responses(
        monkeypatch,
        [(302, {"location": location}, b"")],
    )

    content, title, error = service.fetch("https://example.com/start", 1000)

    assert content is None and title is None
    assert "tidak diizinkan" in error or "publik" in error
    assert len(requests) == 1


def test_redirect_to_different_public_domain_is_allowed_after_dns_check(monkeypatch):
    service, requests = service_with_responses(
        monkeypatch,
        [(301, {"location": "https://other.example.org/final"}, b""), ok(b"<p>Final</p>")],
    )

    assert service.fetch("https://example.com/start", 1000) == ("Final", "other.example.org", None)
    assert len(requests) == 2


def test_redirect_limit_is_enforced(monkeypatch):
    responses = [(302, {"location": f"/step-{index}"}, b"") for index in range(7)]
    service, requests = service_with_responses(monkeypatch, responses)

    content, title, error = service.fetch("https://example.com/start", 1000)

    assert content is None and title is None
    assert "batas" in error
    assert len(requests) == service.max_redirects + 1


def test_timeout_becomes_reference_failure(monkeypatch):
    service, _requests = service_with_responses(
        monkeypatch,
        [httpx.ReadTimeout("timed out")],
    )

    content, title, error = service.fetch("https://example.com/slow", 1000)

    assert content is None and title is None
    assert error == "Referensi timeout."


@pytest.mark.parametrize("oversized", [True, False])
def test_oversized_response_is_rejected_by_declared_and_streamed_size(monkeypatch, oversized):
    if oversized:
        response = (200, {"content-type": "text/plain", "content-length": "11"}, b"short")
    else:
        response = (200, {"content-type": "text/plain"}, b"01234567890")
    service, _requests = service_with_responses(monkeypatch, [response])
    service.max_response_bytes = 10

    content, title, error = service.fetch("https://example.com/large", 1000)

    assert content is None and title is None
    assert error == "Konten referensi terlalu besar."


def test_non_http_protocol_and_nonstandard_ports_are_rejected():
    service = ReferenceContentService()
    assert service.fetch("file:///etc/passwd", 100)[2]
    assert service.fetch("https://example.com:8443/", 100)[2]
