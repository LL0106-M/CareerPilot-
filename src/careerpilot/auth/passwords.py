from pwdlib import PasswordHash


class PasswordHasher:
    def __init__(self, password_hash: PasswordHash | None = None) -> None:
        self._password_hash = password_hash or PasswordHash.recommended()

    def hash(self, password: str) -> str:
        return self._password_hash.hash(password)

    def verify(self, password: str, encoded: str) -> bool:
        try:
            return self._password_hash.verify(password, encoded)
        except Exception:
            return False
