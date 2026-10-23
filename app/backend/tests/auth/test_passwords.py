from smdx_api.auth.passwords import hash_password, verify_password


def test_hash_is_argon2id_and_verifies():
    h = hash_password("secret")
    assert h.startswith("$argon2id$")
    assert verify_password(h, "secret") and not verify_password(h, "wrong")


def test_verify_broken_hash_is_false():
    assert verify_password("not-a-hash", "secret") is False
