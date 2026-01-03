import jwt
import datetime
from pathlib import Path
from django.conf import settings

# Load transfer configuration
TRANSFER_CONF = settings.TRANSFER_TOKEN


# -------------------------------------------
# LOAD PRIVATE KEY (for signing tokens)
# -------------------------------------------
def load_private_key():
    """
    Reads the RSA private key used to sign transfer tokens.
    """
    private_path = Path(TRANSFER_CONF["PRIVATE_KEY_PATH"])
    return private_path.read_text()


# -------------------------------------------
# LOAD PUBLIC KEY (for verifying tokens)
# -------------------------------------------
def load_public_key():
    """
    Reads the RSA public key used to verify transfer tokens.
    """
    public_path = Path(TRANSFER_CONF["PUBLIC_KEY_PATH"])
    return public_path.read_text()


# -------------------------------------------
# GENERATE TRANSFER TOKEN
# -------------------------------------------
def generate_transfer_token(session_id: str, from_mirror_id: str, to_mirror_id: str, exp_seconds=None):
    """
    Create an RS256-signed token authorizing a session transfer between mirrors.
    Token includes:
      - session ID
      - source mirror ID
      - target mirror ID
      - expiration time
      - purpose: 'session_transfer'
    """
    exp_seconds = exp_seconds or TRANSFER_CONF.get("EXP_SECONDS", 120)
    now = datetime.datetime.utcnow()

    payload = {
        "sub": str(session_id),
        "from": str(from_mirror_id),
        "to": str(to_mirror_id),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + datetime.timedelta(seconds=exp_seconds)).timestamp()),
        "purpose": "session_transfer",
    }

    private_key = load_private_key()

    token = jwt.encode(
        payload,
        private_key,
        algorithm=TRANSFER_CONF["ALGORITHM"]
    )

    return token


# -------------------------------------------
# VALIDATE TRANSFER TOKEN
# -------------------------------------------
def validate_transfer_token(token: str, expected_session=None, expected_to=None):
    """
    Validates RS256-signed transfer token.
    Raises jwt exceptions automatically on failure.

    Optional:
      expected_session: enforce correct session ID
      expected_to: ensure destination mirror matches
    """
    public_key = load_public_key()

    payload = jwt.decode(
        token,
        public_key,
        algorithms=[TRANSFER_CONF["ALGORITHM"]],
    )

    # Ensure token is correct purpose
    if payload.get("purpose") != "session_transfer":
        raise jwt.InvalidTokenError("Invalid token purpose")

    # Enforce session match
    if expected_session and payload.get("sub") != str(expected_session):
        raise jwt.InvalidTokenError("Token session mismatch")

    # Enforce destination match
    if expected_to and payload.get("to") != str(expected_to):
        raise jwt.InvalidTokenError("Token destination mismatch")

    return payload
