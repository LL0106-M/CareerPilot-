from careerpilot.auth.passwords import PasswordHasher


def test_password_hasher_uses_argon2id_and_verifies_only_the_original_password() -> None:
    hasher = PasswordHasher()

    encoded = hasher.hash("S3cure passphrase!")

    assert encoded.startswith("$argon2id$")
    assert "S3cure passphrase!" not in encoded
    assert hasher.verify("S3cure passphrase!", encoded) is True
    assert hasher.verify("wrong password", encoded) is False
