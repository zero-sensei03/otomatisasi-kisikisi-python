import re

from app.core.security import hash_password
from app.models import User, UserRole
from app.services.auth import authenticate_user


def create_user(
    db_session,
    *,
    username="testuser",
    email="test@example.com",
    password="Password@123",
    role=UserRole.GURU,
    is_active=True,
):
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        full_name="Test User",
        role=role,
        is_active=is_active,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


def get_csrf_token(response):
    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        response.text,
    )

    assert match is not None

    return match.group(1)


def test_hash_password():
    from app.core.security import verify_password

    password = "Password@123"

    hashed_password = hash_password(password)

    assert hashed_password != password
    assert verify_password(password, hashed_password) is True
    assert verify_password("WrongPassword", hashed_password) is False


def test_authenticate_user_success(db_session):
    create_user(
        db_session,
        username="testuser",
        email="test@example.com",
    )

    user = authenticate_user(
        db=db_session,
        username_or_email="testuser",
        password="Password@123",
    )

    assert user is not None
    assert user.username == "testuser"
    assert user.email == "test@example.com"


def test_authenticate_user_using_email(db_session):
    create_user(
        db_session,
        username="emailuser",
        email="email@example.com",
    )

    user = authenticate_user(
        db=db_session,
        username_or_email="email@example.com",
        password="Password@123",
    )

    assert user is not None
    assert user.username == "emailuser"


def test_authenticate_user_wrong_password(db_session):
    create_user(
        db_session,
        username="wrongpassword",
        email="wrongpassword@example.com",
    )

    user = authenticate_user(
        db=db_session,
        username_or_email="wrongpassword",
        password="WrongPassword@123",
    )

    assert user is None


def test_authenticate_user_not_found(db_session):
    user = authenticate_user(
        db=db_session,
        username_or_email="notfound",
        password="Password@123",
    )

    assert user is None


def test_authenticate_inactive_user(db_session):
    create_user(
        db_session,
        username="inactive",
        email="inactive@example.com",
        is_active=False,
    )

    user = authenticate_user(
        db=db_session,
        username_or_email="inactive",
        password="Password@123",
    )

    assert user is None


def test_login_page(client):
    response = client.get(
        "/login",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "Tesis Evaluasi" in response.text
    assert 'name="username"' in response.text
    assert 'name="password"' in response.text
    assert 'name="csrf_token"' in response.text


def test_login_success(client, db_session):
    create_user(
        db_session,
        username="endpointlogin",
        email="endpoint@example.com",
    )

    login_page = client.get("/login")

    assert login_page.status_code == 200

    csrf_token = get_csrf_token(login_page)

    response = client.post(
        "/login",
        data={
            "username": "endpointlogin",
            "password": "Password@123",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_login_wrong_password(client, db_session):
    create_user(
        db_session,
        username="wronglogin",
        email="wronglogin@example.com",
    )

    login_page = client.get("/login")

    assert login_page.status_code == 200

    csrf_token = get_csrf_token(login_page)

    response = client.post(
        "/login",
        data={
            "username": "wronglogin",
            "password": "WrongPassword@123",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert "Username/email atau password salah." in response.text


def test_login_inactive_user(client, db_session):
    create_user(
        db_session,
        username="inactiveendpoint",
        email="inactiveendpoint@example.com",
        is_active=False,
    )

    login_page = client.get("/login")

    assert login_page.status_code == 200

    csrf_token = get_csrf_token(login_page)

    response = client.post(
        "/login",
        data={
            "username": "inactiveendpoint",
            "password": "Password@123",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert "Username/email atau password salah." in response.text


def test_logout(client, db_session):
    user = create_user(
        db_session,
        username="logoutuser",
        email="logout@example.com",
    )

    login_page = client.get("/login")

    assert login_page.status_code == 200

    csrf_token = get_csrf_token(login_page)

    login_response = client.post(
        "/login",
        data={
            "username": "logoutuser",
            "password": "Password@123",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/dashboard"

    logout_response = client.post(
        "/logout",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/login"

    dashboard_response = client.get(
        "/dashboard",
        follow_redirects=False,
    )

    assert dashboard_response.status_code == 303
    assert dashboard_response.headers["location"] == "/login"

    assert user.id is not None