import base64
import hashlib
import secrets
from db_folder.db_connection import ConnectionDB


class APIKeyManager:

    def __init__(self, db_conn: ConnectionDB):
        self.db_conn = db_conn

    @staticmethod
    def generate_api_key() -> tuple:
        raw_key = f"tm_{secrets.token_urlsafe(32)}"
        prefix = raw_key[:10]
        salt = secrets.token_hex(32)
        key_hash = hashlib.pbkdf2_hmac(
            'sha256',
            raw_key.encode(),
            salt.encode(),
            100000,
            dklen=64
        ).hex()
        return raw_key, key_hash, salt, prefix

    @staticmethod
    def verify_api_key(raw_key: str, stored_hash: str, salt: str) -> bool:
        computed_hash = hashlib.pbkdf2_hmac(
            'sha256',
            raw_key.encode(),
            salt.encode(),
            100000,
            dklen=64
        ).hex()
        return secrets.compare_digest(computed_hash, stored_hash)

    @staticmethod
    def _verify_scrypt_password(password: str, stored_hash: str) -> bool:
        """BrAIniac password format: s:<saltBase64>:<hashBase64> (Node.js crypto.scrypt)."""
        parts = stored_hash.split(':', 2)
        if len(parts) != 3 or parts[0] != 's':
            return False
        try:
            salt = base64.b64decode(parts[1])
            expected = base64.b64decode(parts[2])
        except Exception:
            return False
        keylen = len(expected)
        derived = hashlib.scrypt(
            password.encode(), salt=salt, n=16384, r=8, p=1, dklen=keylen
        )
        return secrets.compare_digest(derived, expected)

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        """Поддерживает BrAIniac (scrypt s:…) и legacy (pbkdf2_sha256$…)."""
        if stored_hash.startswith('s:'):
            return APIKeyManager._verify_scrypt_password(password, stored_hash)
        # Legacy pbkdf2_sha256$salt$digest format (test DB)
        try:
            algo, salt, digest = stored_hash.split('$', 2)
        except ValueError:
            return False
        if algo != 'pbkdf2_sha256':
            return False
        computed = hashlib.pbkdf2_hmac(
            'sha256', password.encode(), salt.encode(), 100000, dklen=32
        ).hex()
        return secrets.compare_digest(computed, digest)

    async def get_user_by_api_key(self, auth_key: str):
        prefix = auth_key[:10]
        candidates = await self.db_conn.fetch(
            """
            SELECT u.user_id AS id, u.email, ak.key_hash, ak.key_salt, ak.key_name
            FROM "User" u
            JOIN api_keys ak ON ak.user_id = u.user_id
            WHERE ak.key_prefix = $1 AND ak.is_active = true
            """,
            prefix,
        )
        for candidate in candidates:
            if self.verify_api_key(auth_key, candidate['key_hash'], candidate['key_salt']):
                await self.db_conn.execute(
                    "UPDATE api_keys SET last_used_at = NOW() WHERE key_hash = $1",
                    candidate['key_hash'],
                )
                return {
                    'id': candidate['id'],
                    'email': candidate['email'],
                    'key_name': candidate['key_name'],
                }
        return None

    async def create_api_key(self, user_id: int, key_name: str) -> str:
        raw_key, key_hash, salt, prefix = self.generate_api_key()
        await self.db_conn.execute(
            """
            INSERT INTO api_keys (user_id, key_name, key_hash, key_salt, key_prefix, is_active)
            VALUES ($1, $2, $3, $4, $5, true)
            """,
            user_id, key_name, key_hash, salt, prefix,
        )
        return raw_key

    async def revoke_api_key(self, user_id: int, key_name: str):
        await self.db_conn.execute(
            """
            UPDATE api_keys SET is_active = false
            WHERE user_id = $1 AND key_name = $2 AND is_active = true
            """,
            user_id, key_name,
        )

    async def revoke_api_key_by_id(self, user_id: int, key_id: int):
        await self.db_conn.execute(
            """
            UPDATE api_keys SET is_active = false
            WHERE user_id = $1 AND id = $2 AND is_active = true
            """,
            user_id, key_id,
        )

    async def list_user_keys(self, user_id: int):
        return await self.db_conn.fetch(
            """
            SELECT id, key_name, key_prefix, is_active, created_at, last_used_at
            FROM api_keys
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user_id,
        )
