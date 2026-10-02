def test_health_check():
    from app.routers.health import health_check

    response = health_check()

    assert response.status_code == 200

    assert response.body == b'{"status":"ok","service":"otomatisasi-kisikisi"}'


def test_home_redirects_based_on_login_state():
    from app.routers.pages import home

    assert home(None).headers["location"] == "/auth/login"
    assert home(object()).headers["location"] == "/dashboard"


def test_not_found_uses_html_error_page():
    import asyncio
    from starlette.exceptions import HTTPException
    from starlette.requests import Request

    from app.main import app, handle_http_error

    request = Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": "/route-yang-tidak-ada",
        "raw_path": b"/route-yang-tidak-ada", "query_string": b"",
        "headers": [(b"accept", b"text/html")], "client": ("127.0.0.1", 80),
        "server": ("127.0.0.1", 80), "app": app, "router": app.router,
    })
    response = asyncio.run(handle_http_error(request, HTTPException(404, "Halaman tidak ditemukan.")))
    assert response.status_code == 404
    assert "404 · Terjadi Kesalahan" in response.body.decode()
    assert "tidak ditemukan" in response.body.decode().lower()


def test_unauthenticated_dashboard_redirects_to_login():
    import asyncio
    from starlette.exceptions import HTTPException
    from starlette.requests import Request

    from app.main import app, handle_http_error

    request = Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": "/dashboard",
        "raw_path": b"/dashboard", "query_string": b"",
        "headers": [(b"accept", b"text/html")], "client": ("127.0.0.1", 80),
        "server": ("127.0.0.1", 80), "app": app, "router": app.router,
    })
    response = asyncio.run(handle_http_error(request, HTTPException(401, "Authentication required.")))
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"
