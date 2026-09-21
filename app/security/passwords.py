"""Password hashing via PBKDF2-HMAC-SHA256 (hashlib.pbkdf2_hmac), deliberately
using only the Python standard library rather than adding bcrypt/passlib/argon2
to requirements.txt -- those are better algorithms for this purpose, but this
environment has no way to verify a new pip dependency actually installs
cleanly before it ships. PBKDF2 with a high iteration count is still a
legitimate, NIST-recommended choice; if you want to move to bcrypt/argon2
later, only this file and its two functions need to change.
"""
import hashlib
import hmac
import os

_ITERATIONS = 260_000
_ALGO = "sha256"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2_{_ALGO}${_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo_label, iterations_str, salt_hex, hash_hex = stored.split("$")
        algo = algo_label.removeprefix("pbkdf2_")
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    candidate = hashlib.pbkdf2_hmac(algo, password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)
