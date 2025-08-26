from __future__ import annotations
import os
import yaml
from typing import List, Dict, Optional, Tuple, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv_list(val: str | None) -> List[str]:
    if not val:
        return []
    return [x.strip() for x in val.split(",") if x.strip()]


def _split_semicolon_list(val: str | None) -> List[str]:
    if not val:
        return []
    return [x.strip() for x in val.split(";") if x.strip()]


class AppConfig(BaseSettings):
    """
    Unified configuration model. Values come from:
      1) Environment variables (.env) — highest precedence
      2) Optional YAML config file (default: config.yaml)
    """
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    # --- Core scanning ---
    city: str = Field(..., alias="CITY")

    # Accept both string and list; normalize to list via validator
    areas: Union[str, List[str]] = Field(default_factory=list, alias="AREAS")

    budget_min: int = Field(..., alias="BUDGET_MIN")
    budget_max: int = Field(..., alias="BUDGET_MAX")

    bhk_in: Union[str, List[int]] = Field(default_factory=list, alias="BHK_IN")
    furnishing_in: Union[str, List[str]] = Field(default_factory=list, alias="FURNISHING_IN")
    property_types_in: Union[str, List[str]] = Field(default_factory=list, alias="PROPERTY_TYPES_IN")

    move_in_by: str = Field(..., alias="MOVE_IN_BY")

    exclude_keywords: Union[str, List[str]] = Field(default_factory=list, alias="EXCLUDE_KEYWORDS")
    required_amenities_any: Union[str, List[str]] = Field(default_factory=list, alias="REQUIRED_AMENITIES_ANY")

    carpet_min_sqft: int = Field(0, alias="CARPET_MIN_SQFT")
    floors_allowed_in: Union[str, List[str]] = Field(default_factory=list, alias="FLOORS_ALLOWED_IN")
    pets_allowed: Optional[bool] = Field(default=None, alias="PETS_ALLOWED")
    listing_age_max_hours: int = Field(48, alias="LISTING_AGE_MAX_HOURS")

    notify_channels: Union[str, List[str]] = Field(default_factory=list, alias="NOTIFY_CHANNELS")
    notify_phone_e164: str = Field(..., alias="NOTIFY_PHONE_E164")
    scan_interval_minutes: int = Field(10, alias="SCAN_INTERVAL_MINUTES")
    soft_match_threshold: int = Field(70, alias="SOFT_MATCH_THRESHOLD")

    # --- Proximity (optional) ---
    # YAML dict: {"Area, City": [lat, lng]} OR env string: "Area, City|12.34|56.78;Another|11.11|22.22"
    area_coords: Union[str, Dict[str, Tuple[float, float]]] = Field(default_factory=dict, alias="AREA_COORDS")
    proximity_km: Optional[float] = Field(default=None, alias="PROXIMITY_KM")

    # --- Politeness & networking ---
    http_min_delay_seconds: float = Field(1.2, alias="HTTP_MIN_DELAY_SECONDS")
    http_max_delay_seconds: float = Field(2.4, alias="HTTP_MAX_DELAY_SECONDS")
    http_timeout_seconds: int = Field(20, alias="HTTP_TIMEOUT_SECONDS")
    max_retries: int = Field(3, alias="MAX_RETRIES")

    # --- WhatsApp Cloud ---
    wa_phone_number_id: Optional[str] = Field(default=None, alias="WA_PHONE_NUMBER_ID")
    wa_access_token: Optional[str] = Field(default=None, alias="WA_ACCESS_TOKEN")

    # --- Twilio ---
    twilio_account_sid: Optional[str] = Field(default=None, alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: Optional[str] = Field(default=None, alias="TWILIO_AUTH_TOKEN")
    twilio_from_number: Optional[str] = Field(default=None, alias="TWILIO_FROM_NUMBER")

    # --- Observability ---
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    health_port: Optional[int] = Field(default=None, alias="HEALTH_PORT")

    # ---------------- Validators ----------------

    @field_validator("areas", mode="before")
    @classmethod
    def parse_areas(cls, v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            s = s.replace("|", ";")  # allow using '|' as a separator too
            return _split_semicolon_list(s)
        return v

    @field_validator("bhk_in", mode="before")
    @classmethod
    def parse_bhk(cls, v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            out: List[int] = []
            for x in _split_csv_list(v):
                try:
                    out.append(int(x))
                except Exception:
                    continue
            return out
        return v

    @field_validator("furnishing_in", "property_types_in", "exclude_keywords",
                     "required_amenities_any", "floors_allowed_in", "notify_channels", mode="before")
    @classmethod
    def parse_csv_style_lists(cls, v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return _split_csv_list(v)
        return v

    @field_validator("area_coords", mode="before")
    @classmethod
    def parse_area_coords(cls, v):
        if not v:
            return {}
        if isinstance(v, dict):
            norm: Dict[str, Tuple[float, float]] = {}
            for name, coords in v.items():
                if isinstance(coords, (list, tuple)) and len(coords) == 2:
                    lat, lng = float(coords[0]), float(coords[1])
                    norm[str(name)] = (lat, lng)
            return norm
        if isinstance(v, str):
            norm: Dict[str, Tuple[float, float]] = {}
            for part in _split_semicolon_list(v):
                bits = [b.strip() for b in part.split("|")]
                if len(bits) != 3:
                    continue
                name, lat_s, lng_s = bits
                try:
                    norm[name] = (float(lat_s), float(lng_s))
                except Exception:
                    continue
            return norm
        return {}

    @field_validator("health_port", mode="before")
    @classmethod
    def parse_health_port(cls, v):
        """
        Allow empty string in .env: HEALTH_PORT=
        Convert "" -> None to satisfy Optional[int].
        """
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            return int(v)  # raises if invalid, which is fine
        return v


# Important for Pydantic v2 when using Union etc.
AppConfig.model_rebuild()


def load_config() -> AppConfig:
    """
    Load config from optional YAML (CONFIG_FILE or ./config.yaml), then overlay env vars.
    """
    yaml_path = os.environ.get("CONFIG_FILE", "config.yaml")
    data = {}
    if os.path.exists(yaml_path):
        with open(yaml_path, "r", encoding="utf-8") as f:
            y = yaml.safe_load(f) or {}
            data.update(y)

    return AppConfig(**data)  # type: ignore[arg-type]
