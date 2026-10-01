def test_health_check():
    from app.routers.health import health_check

    response = health_check()

    assert response.status_code == 200

    assert response.body == b'{"status":"ok","service":"otomatisasi-kisikisi"}'
