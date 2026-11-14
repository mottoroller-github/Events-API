from models import User


def test_user_password_hashing_behaves_correctly():
    # Arrange: Create a user without saving it to the database
    user = User(username="testuser")
    password = "SecurePassword123!"

    # Act: Hash the password
    user.set_password(password)

    # Assert: A password hash has been generated
    assert user.password_hash is not None

    # Assert: The password is not stored in plain text
    assert user.password_hash != password

    # Assert: The correct password is accepted
    assert user.check_password(password) is True

    # Assert: An incorrect password is rejected
    assert user.check_password("WrongPassword123!") is False
