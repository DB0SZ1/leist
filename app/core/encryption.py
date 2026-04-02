import os
from cryptography.fernet import Fernet
from app.config import settings
import structlog

logger = structlog.get_logger()

# In a real app this should be defined securely in environment variables. 
# We'll generate one here for the sake of the project or fallback to a hardcoded secure key if missing.
# Fernet keys must be 32 URL-safe base64-encoded bytes.
ENCRYPTION_KEY_FALLBACK = b'aG1ZRE5YcmxMcmJTSURsVG0xRmZ4MjhtMnpzOGM5VzE='
FERNET_KEY = getattr(settings, "FERNET_KEY", ENCRYPTION_KEY_FALLBACK)

try:
    fernet = Fernet(FERNET_KEY)
except Exception as e:
    logger.error("fernet_init_failed", error=str(e))
    # Fallback just so development doesn't crash completely. DO NOT DO THIS IN PRODUCTION.
    fernet = Fernet(ENCRYPTION_KEY_FALLBACK)

def encrypt_data(data: str) -> str:
    """Encrypts string data using Fernet."""
    if not data:
        return None
    return fernet.encrypt(data.encode('utf-8')).decode('utf-8')

def decrypt_data(encrypted_data: str) -> str:
    """Decrypts string data using Fernet."""
    if not encrypted_data:
        return None
    return fernet.decrypt(encrypted_data.encode('utf-8')).decode('utf-8')
