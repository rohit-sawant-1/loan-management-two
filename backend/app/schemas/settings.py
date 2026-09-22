"""
Schemas for the system settings (Piece 28).
"""

from pydantic import BaseModel, ConfigDict, StrictBool

from app.schemas.common import UtcDateTime


class SettingsResponse(BaseModel):
    """What every logged-in screen reads, so it knows how to behave."""
    real_uploads_enabled: bool


class SettingResponse(BaseModel):
    """One setting, with what the admin screen shows next to the switch."""
    key: str
    value: bool
    label: str
    # What each position of the switch means, in words, from rules.SETTINGS.
    off_text: str
    on_text: str
    updated_by: str | None = None
    updated_at: UtcDateTime | None = None


class RealUploadsBody(BaseModel):
    # extra="forbid" so a misspelled field is a clear 422 rather than a
    # silently ignored change that looks like it worked.
    model_config = ConfigDict(extra="forbid")

    # StrictBool, not bool: Pydantic would otherwise read "yes", "true" and 1
    # as True. This switch changes how the app behaves for everybody, so it
    # takes true or false and nothing else. The service checks the type again
    # for anything that calls it directly.
    enabled: StrictBool
