from app.core.security import (
    detect_device,
    generate_csrf_token,
    hash_password,
    sign_csrf_token,
    verify_csrf_token,
    verify_password,
)


def test_password_hash():
    password = "Password123!"

    password_hash = hash_password(
        password
    )

    assert password_hash != password
    assert verify_password(
        password,
        password_hash,
    )

    assert not verify_password(
        "WrongPassword123!",
        password_hash,
    )


def test_csrf():
    token = generate_csrf_token()

    signature = sign_csrf_token(
        token
    )

    assert verify_csrf_token(
        token,
        signature,
    )

    assert not verify_csrf_token(
        "wrong-token",
        signature,
    )


def test_device_detection():
    assert (
        detect_device(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )
        == "Windows PC"
    )

    assert (
        detect_device(
            "Mozilla/5.0 (Linux; Android 14; Mobile)"
        )
        == "Android Mobile"
    )

    assert (
        detect_device(
            "Mozilla/5.0 (iPhone; CPU iPhone OS)"
        )
        == "iPhone"
    )