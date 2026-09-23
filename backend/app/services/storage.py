"""
Where a stored file's bytes actually live (Piece 31).

Two folders, not one — see TRAPS-AND-DECISIONS.md, "Piece 31 — two upload
folders, chosen automatically, never self-declared", for the full reasoning.
In short: `zone="safe"` is `backend/uploads/`, inside the project and
tracked by git; `zone="sensitive"` is a folder outside the project entirely.
Which zone a file goes to is decided once, by `file_service.classify_nature`,
never by whoever is uploading.

Every byte written here is already Fernet-encrypted by the time it arrives —
this module never sees a plain document, only ciphertext going in and coming
out. That is true in both zones, including the safe one: even a confidently-
test file is encrypted, so the git-tracked folder never holds a readable byte
even if the classifier is ever wrong.

`save` / `open_file` / `delete` are the only three operations anything else
in the app is allowed to do with a stored file's bytes (named `open_file`,
not `open`, so it never shadows Python's own builtin). Kept behind this one
small interface so the folder could become S3 or Azure Blob later without
any caller changing.
"""

from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

# The project root: two parents up from this file (app/services/storage.py
# -> app/ -> backend/). Used only to check the sensitive folder is genuinely
# outside it — never to build the safe folder's path, which is already
# relative to backend/ the same way LOG_DIR and CHROMA_PERSIST_DIR are.
_BACKEND_DIR = Path(__file__).resolve().parents[2]


def _fernet() -> Fernet:
    if not settings.upload_encryption_key:
        raise RuntimeError(
            "UPLOAD_ENCRYPTION_KEY is not set. Uploads cannot start without it — "
            "see .env.example for how to generate one."
        )
    return Fernet(settings.upload_encryption_key.encode())


def _safe_dir() -> Path:
    path = (_BACKEND_DIR / settings.upload_dir_safe).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sensitive_dir() -> Path:
    if not settings.upload_dir_sensitive:
        raise RuntimeError(
            "UPLOAD_DIR_SENSITIVE is not set. This is where anything real or "
            "uncertain is stored, so uploads refuse to start without it."
        )
    path = Path(settings.upload_dir_sensitive).resolve()
    # The one check that actually matters: this folder must not be inside
    # the project, or a "sensitive" file would be exactly as exposed to git
    # as a "safe" one — the whole point of having two folders.
    if path == _BACKEND_DIR or _BACKEND_DIR in path.parents:
        raise RuntimeError(
            f"UPLOAD_DIR_SENSITIVE ({path}) is inside the project folder "
            f"({_BACKEND_DIR}). It has to be outside it."
        )
    path.mkdir(parents=True, exist_ok=True)
    return path


def _dir_for(zone: str) -> Path:
    if zone == "safe":
        return _safe_dir()
    if zone == "sensitive":
        return _sensitive_dir()
    raise ValueError(f"'{zone}' is not a storage zone")


def save(zone: str, stored_name: str, plain_bytes: bytes) -> None:
    """Encrypt `plain_bytes` and write it under `stored_name` in `zone`."""
    ciphertext = _fernet().encrypt(plain_bytes)
    (_dir_for(zone) / stored_name).write_bytes(ciphertext)


def open_file(zone: str, stored_name: str) -> bytes:
    """Read `stored_name` from `zone` and decrypt it back to the original bytes."""
    ciphertext = (_dir_for(zone) / stored_name).read_bytes()
    try:
        return _fernet().decrypt(ciphertext)
    except InvalidToken as e:
        # Only ever means the key in .env doesn't match the one the file was
        # written with — never a sign of the file itself being tampered with
        # in a way worth explaining to whoever is looking at the error.
        raise RuntimeError(f"Could not decrypt {stored_name}: wrong key or corrupt file") from e


def delete(zone: str, stored_name: str) -> None:
    """Remove `stored_name` from `zone`, if it exists. Used by Piece 32's purge."""
    (_dir_for(zone) / stored_name).unlink(missing_ok=True)
