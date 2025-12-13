from app.security.api_keys import (
    DEFAULT_KEY_PREFIX,
    generate_api_key,
    hash_api_key,
    is_test_key,
    key_prefix,
)


def test_generate_api_key_format_and_length():
    key = generate_api_key()
    assert key.startswith(f"{DEFAULT_KEY_PREFIX}_")
    random_part = key.rsplit("_", maxsplit=1)[-1]
    assert len(random_part) == 64


def test_hash_api_key_deterministic():
    key = "sk_sentinel_example"
    pepper = "pepper-value"
    assert hash_api_key(key, pepper) == hash_api_key(key, pepper)


def test_key_prefix_extraction():
    key = "sk_sentinel_abcd1234efgh"
    assert key_prefix(key, length=8) == "abcd1234"


def test_is_test_key():
    assert is_test_key("sk_test_sentinel_abcd")
    assert not is_test_key("sk_sentinel_abcd")
