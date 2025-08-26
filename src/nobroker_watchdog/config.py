from __future__ import annotations
import os
import yaml
from typing import List, Dict, Optional, Tuple, Union
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from datetime import datetime

def _split_csv_list(val: str | None) -> List[str]:
    if not val:
        return []
    return [x.strip() for x in val.split(",") if x.strip()]

def _split_semicolon_pairs(val: str | None) -> List[str]:
    if not val:
        return []
    return [x.strip() for x in val.split(";") if x.strip()]

class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    # Core scanning
    city: str = Field(..., alias="CITY")
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
    notify_channels: Union[str, List[str]] = Field(default_factory=list, alias="NOTIFY_CHANNELS")
    pets_allowed: Optional[bool] = Field(default=None, alias="PETS_ALLOWED")
    listing_age_max_hours: int = Field(48, alias="LISTING_AGE_MAX_HOURS")
    notify_phone_e164: str = Field(..., alias="NOTIFY_PHONE_E164")
    scan_interval_minutes: int = Field(10, alias="SCAN_INTERVAL_MINUTES")
    soft_match_threshold: int = Field(70, alias="SOFT_MATCH_THRESHOLD")

    # Proximity
    area_coords: Dict[str, Tuple[float, float]] = Field(default_factory=dict, alias="AREA_COORDS_MAP")
    proximity_km: Optional[float] = Field(default=None, alias="PROXIMITY_KM")

    # Politeness & networking
    http_min_delay_seconds: float = Field(1.2, alias="HTTP_MIN_DELAY_SECONDS")
    http_max_delay_seconds: float = Field(2.4, alias="HTTP_MAX_DELAY_SECONDS")
    http_timeout_seconds: int = Field(20, alias="HTTP_TIMEOUT_SECONDS")
    max_retries: int = Field(3, alias="MAX_RETRIES")

    # WhatsApp Cloud
    wa_phone_number_id: Optional[str] = Field(default=None, alias="WA_PHONE_NUMBER_ID")
    wa_access_token: Optional[str] = Field(default=None, alias="WA_ACCESS_TOKEN")

    # Twilio
    twilio_account_sid: Optional[str] = Field(default=None, alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: Optional[str] = Field(default=None, alias="TWILIO_AUTH_TOKEN")
    twilio_from_number: Optional[str] = Field(default=None, alias="TWILIO_FROM_NUMBER")

    # Observability
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    health_port: Optional[int] = Field(default=None, alias="HEALTH_PORT")

    @field_validator("areas", mode="before")
    @classmethod
    def parse_areas(cls, v):
        # Support YAML array, or "a;b" (semicolon) or csv with semicolon area contains comma
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Accept both ";" and "|" list styles from example
            parts = [p.strip() for p in v.replace("|", ";").split(";") if p.strip()]
            return parts
        return v

    @field_validator("bhk_in", mode="before")
    @classmethod
    def parse_bhk(cls, v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [int(x.strip()) for x in _split_csv_list(v)]
        return v

    @field_validator("furnishing_in", "property_types_in", "exclude_keywords",
                     "required_amenities_any", "floors_allowed_in", "notify_channels", mode="before")
    @classmethod
    def parse_csv_lists(cls, v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return _split_csv_list(v)
        return v

    @field_validator("area_coords", mode="before")
    @classmethod
    def parse_area_coords(cls, v):
        # env form: "Name|lat|lng;Name2|lat|lng"
        if not v:
            # Also support config.yaml injection handled in load_config()
            return {}
        if isinstance(v, dict):
            return v
        result: Dict[str, Tuple[float, float]] = {}
        parts = _split_semicolon_pairs(v)
        for p in parts:
            name, lat, lng = [t.strip() for t in p.split("|")]
            result[name] = (float(lat), float(lng))
        return result

AppConfig.model_rebuild()


def load_config() -> AppConfig:
    # Merge YAML (if present) under config.sample.yaml / config.yaml with env precedence
    yaml_path = os.environ.get("CONFIG_FILE", "config.yaml")
    data = {}
    if os.path.exists(yaml_path):
        with open(yaml_path, "r", encoding="utf-8") as f:
            y = yaml.safe_load(f) or {}
            data.update(y)

        # Map YAML keys -> env-like keys for pydantic fields
        # Pydantic BaseSettings respects env vars first; we pass yaml data as **kwargs here.
        # Transform to our field aliases if needed:
        if "area_coords" in data and isinstance(data["area_coords"], dict):
            # Keep dict form
            pass

    return AppConfig(**data)  # type: ignore[arg-type]
