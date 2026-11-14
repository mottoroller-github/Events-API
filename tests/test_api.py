import time
from datetime import datetime, timedelta

import requests


def unique_username():
    return f"testuser_{time.time_ns()}"


def register_user(base_url):
    """Registers a user and returns the username and password."""
    username = unique_username()
    password = "SecureTestPassword123!"

    response = requests.post(
        f"{base_url}/api/auth/register",
        json={
            "username": username,
            "password": password,
        },
        timeout=5,
    )

    assert response.status_code == 201, response.text
    assert response.json()["user"]["username"] == username

    return username, password


def get_auth_token(base_url):
    """Registers a user, logs in, and returns the JWT."""
    username, password = register_user(base_url)

    response = requests.post(
        f"{base_url}/api/auth/login",
        json={
            "username": username,
            "password": password,
        },
        timeout=5,
    )

    assert response.status_code == 200, response.text

    data = response.json()
    assert "access_token" in data
    assert data["user"]["username"] == username

    return data["access_token"]


def create_event(base_url, token, **overrides):
    """Creates an event and returns the HTTP response and event data."""
    event_data = {
        "title": "Integration Test Event",
        "description": "Created by an API integration test",
        "date": (
            datetime.now() + timedelta(days=7)
        ).replace(microsecond=0).isoformat(),
        "location": "Test Location",
        "capacity": 20,
        "is_public": True,
        "requires_admin": False,
    }
    event_data.update(overrides)

    return requests.post(
        f"{base_url}/api/events",
        json=event_data,
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    ), event_data


def test_health_endpoint_returns_healthy(base_url):
    response = requests.get(
        f"{base_url}/api/health",
        timeout=5,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_register_user_creates_new_user(base_url):
    username = unique_username()

    response = requests.post(
        f"{base_url}/api/auth/register",
        json={
            "username": username,
            "password": "SecureTestPassword123!",
        },
        timeout=5,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["message"] == "User created successfully"
    assert data["user"]["username"] == username
    assert isinstance(data["user"]["id"], int)
    assert "password_hash" not in data["user"]


def test_login_returns_jwt_token(base_url):
    username, password = register_user(base_url)

    response = requests.post(
        f"{base_url}/api/auth/login",
        json={
            "username": username,
            "password": password,
        },
        timeout=5,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 0
    assert data["user"]["username"] == username


def test_create_public_event_requires_auth_and_succeeds_with_token(base_url):
    # Without a token, the protected endpoint must reject the request.
    _, event_data = create_event_without_token(base_url)

    # With a valid token, event creation must succeed.
    token = get_auth_token(base_url)
    response, _ = create_event(base_url, token, **event_data)

    assert response.status_code == 201, response.text

    event = response.json()

    assert event["title"] == event_data["title"]
    assert event["description"] == event_data["description"]
    assert event["location"] == event_data["location"]
    assert event["capacity"] == event_data["capacity"]
    assert event["is_public"] is True
    assert event["requires_admin"] is False
    assert isinstance(event["id"], int)
    assert event["date"]


def create_event_without_token(base_url):
    """Checks that creating an event without a JWT is not allowed."""
    event_data = {
        "title": "Unauthorized Test Event",
        "description": "This event should not be created",
        "date": (
            datetime.now() + timedelta(days=7)
        ).replace(microsecond=0).isoformat(),
        "location": "Test Location",
        "capacity": 20,
        "is_public": True,
        "requires_admin": False,
    }

    response = requests.post(
        f"{base_url}/api/events",
        json=event_data,
        timeout=5,
    )

    assert response.status_code in (401, 422), response.text

    return response, event_data


def test_rsvp_to_public_event_without_authentication(base_url):
    # First, create a public event using an authenticated user.
    token = get_auth_token(base_url)

    event_response, _ = create_event(base_url, token)

    assert event_response.status_code == 201, event_response.text
    event = event_response.json()
    event_id = event["id"]

    # Anonymous RSVP registration for a public event is allowed.
    rsvp_response = requests.post(
        f"{base_url}/api/rsvps/event/{event_id}",
        json={"attending": True},
        timeout=5,
    )

    assert rsvp_response.status_code == 201, rsvp_response.text

    rsvp = rsvp_response.json()

    assert rsvp["event_id"] == event_id
    assert rsvp["attending"] is True
    assert rsvp["user_id"] is None
    assert isinstance(rsvp["id"], int)


def test_get_rsvps_returns_correct_statistics(base_url):
    token = get_auth_token(base_url)
    event_response, _ = create_event(base_url, token)

    assert event_response.status_code == 201, event_response.text
    event_id = event_response.json()["id"]

    # An anonymous participant registers for the event.
    rsvp_response = requests.post(
        f"{base_url}/api/rsvps/event/{event_id}",
        json={"attending": True},
        timeout=5,
    )

    assert rsvp_response.status_code == 201, rsvp_response.text

    response = requests.get(
        f"{base_url}/api/rsvps/event/{event_id}",
        timeout=5,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["event"]["id"] == event_id
    assert len(data["rsvps"]) == 1
    assert data["stats"]["attending"] == 1
    assert data["stats"]["not_attending"] == 0
    assert data["stats"]["total"] == 1


def test_register_user_with_duplicate_username_returns_400(base_url):
    # Arrange: Register a user successfully for the first time.
    username = unique_username()
    user_data = {
        "username": username,
        "password": "SecureTestPassword123!",
    }

    first_response = requests.post(
        f"{base_url}/api/auth/register",
        json=user_data,
        timeout=5,
    )

    assert first_response.status_code == 201, first_response.text

    # Act: Attempt to register the same username again.
    second_response = requests.post(
        f"{base_url}/api/auth/register",
        json=user_data,
        timeout=5,
    )

    # Assert: Duplicate registration is rejected.
    assert second_response.status_code == 400
    assert second_response.json()["error"] == "Username already exists"


def test_create_event_without_authentication_returns_401(base_url):
    # Arrange: Prepare valid event data without authentication.
    event_data = {
        "title": "Unauthorized Event",
        "description": "This event must not be created",
        "date": (
            datetime.now() + timedelta(days=7)
        ).replace(microsecond=0).isoformat(),
        "location": "Test Location",
        "capacity": 10,
        "is_public": True,
        "requires_admin": False,
    }

    # Act: Send a POST request without an Authorization header.
    response = requests.post(
        f"{base_url}/api/events",
        json=event_data,
        timeout=5,
    )

    # Assert: JWT authentication is required.
    assert response.status_code in (401, 422), response.text


def test_rsvp_to_private_event_without_authentication_returns_401(base_url):
    # Arrange: Use an authenticated user to create the event.
    token = get_auth_token(base_url)

    event_response, _ = create_event(
        base_url,
        token,
        title="Private Event",
        is_public=False,
        requires_admin=False,
    )

    assert event_response.status_code == 201, event_response.text
    event_id = event_response.json()["id"]

    # Act: Attempt to RSVP to the private event without a token.
    response = requests.post(
        f"{base_url}/api/rsvps/event/{event_id}",
        json={"attending": True},
        timeout=5,
    )

    # Assert: Authentication is required for private events.
    assert response.status_code == 401, response.text
    assert response.json()["error"] == (
        "Authentication required for this event"
    )
