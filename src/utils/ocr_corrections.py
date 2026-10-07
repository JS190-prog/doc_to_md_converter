import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

_CORRECTIONS_CACHE: Dict[str, List[Tuple[str, str]]] | None = None
_CORRECTIONS_MTIME: float | None = None


def _corrections_file_path() -> Path:
    # src/utils/ocr_corrections.py -> src/config/ocr_corrections.json
    return Path(__file__).resolve().parents[1] / "config" / "ocr_corrections.json"


def _default_base_rules() -> List[Tuple[str, str]]:
    return []


def _default_profile_name() -> str:
    return "default"


def _default_profiles() -> Dict[str, List[Tuple[str, str]]]:
    return {
        "default": [
            (r"유\s+튜브", "유튜브"),
            (r"도\s+서", "도서"),
            (r"김난도GPT", "김난도 GPT"),
            (r"전미영최지혜", "전미영 최지혜"),
            (r"트렌드코리아TV에참여하고", "트렌드코리아TV에 참여하고"),
            (r"인스타그램\s*계정\s*:\s*", "인스타그램 계정: "),
            (r"유튜브채널\s*:\s*", "유튜브채널: "),
        ],
        "book": [
            (r"Consu-\s*mer", "Consumer"),
        ],
        "invoice": [
            (r"공급\s*가액", "공급가액"),
            (r"부가\s*세", "부가세"),
        ],
    }


def _normalize_rules(raw_rules) -> List[Tuple[str, str]]:
    normalized: List[Tuple[str, str]] = []
    for item in raw_rules or []:
        if not isinstance(item, dict):
            continue
        pattern = item.get("pattern")
        replacement = item.get("replacement", "")
        enabled = item.get("enabled", True)
        if not enabled or not pattern or not isinstance(pattern, str):
            continue
        if not isinstance(replacement, str):
            replacement = str(replacement)
        normalized.append((pattern, replacement))
    return normalized


def _build_profile_rules(config_data) -> Dict[str, List[Tuple[str, str]]]:
    profiles: Dict[str, List[Tuple[str, str]]] = {}
    base_rules = _default_base_rules()
    default_name = _default_profile_name()
    default_profiles = _default_profiles()

    # Backward-compatible format: list or {"rules":[...]}
    if isinstance(config_data, list):
        profiles[default_name] = _normalize_rules(config_data) or default_profiles[default_name]
        return profiles
    if isinstance(config_data, dict) and "profiles" not in config_data:
        root_rules = _normalize_rules(config_data.get("rules"))
        profiles[default_name] = (base_rules + root_rules) if root_rules else default_profiles[default_name]
        return profiles

    if isinstance(config_data, dict):
        base_rules = _normalize_rules(config_data.get("rules"))
        raw_profiles = config_data.get("profiles", {})

        if isinstance(raw_profiles, dict):
            for profile_name, profile_value in raw_profiles.items():
                profile_rules: List[Tuple[str, str]]
                if isinstance(profile_value, dict):
                    profile_rules = _normalize_rules(profile_value.get("rules"))
                elif isinstance(profile_value, list):
                    profile_rules = _normalize_rules(profile_value)
                else:
                    profile_rules = []
                profiles[str(profile_name)] = base_rules + profile_rules

        default_name_from_config = config_data.get("default_profile")
        if isinstance(default_name_from_config, str) and default_name_from_config.strip():
            default_name = default_name_from_config.strip()

    if not profiles:
        profiles = default_profiles
    else:
        # Ensure default profile always exists.
        profiles.setdefault(default_name, profiles.get("default", []) or default_profiles["default"])
        # If user config omitted defaults, merge in built-ins for safer behavior.
        if not profiles.get("default"):
            profiles["default"] = default_profiles["default"]

    profiles["__meta_default_profile__"] = [(default_name, "")]
    return profiles


def _load_rules_from_file() -> Dict[str, List[Tuple[str, str]]]:
    path = _corrections_file_path()
    try:
        if not path.exists():
            profiles = _default_profiles()
            profiles["__meta_default_profile__"] = [(_default_profile_name(), "")]
            return profiles

        raw = json.loads(path.read_text(encoding="utf-8"))
        return _build_profile_rules(raw)
    except Exception as e:
        logger.warning("Failed to load OCR correction rules: %s", e)
        profiles = _default_profiles()
        profiles["__meta_default_profile__"] = [(_default_profile_name(), "")]
        return profiles


def _resolve_profile_name(cached_profiles: Dict[str, List[Tuple[str, str]]], profile: str | None) -> str:
    if profile and profile.strip():
        return profile.strip()
    env_profile = os.getenv("OCR_CORRECTION_PROFILE", "").strip()
    if env_profile:
        return env_profile
    meta = cached_profiles.get("__meta_default_profile__", [])
    if meta and isinstance(meta[0], tuple) and meta[0][0]:
        return meta[0][0]
    return _default_profile_name()


def get_ocr_correction_rules(profile: str | None = None) -> List[Tuple[str, str]]:
    global _CORRECTIONS_CACHE, _CORRECTIONS_MTIME
    path = _corrections_file_path()
    try:
        mtime = path.stat().st_mtime if path.exists() else -1.0
    except Exception:
        mtime = -1.0

    if _CORRECTIONS_CACHE is None or _CORRECTIONS_MTIME != mtime:
        _CORRECTIONS_CACHE = _load_rules_from_file()
        _CORRECTIONS_MTIME = mtime
    profile_name = _resolve_profile_name(_CORRECTIONS_CACHE, profile)
    rules = _CORRECTIONS_CACHE.get(profile_name)
    if rules is None:
        rules = _CORRECTIONS_CACHE.get("default", [])
    return rules


def apply_ocr_corrections(text: str, profile: str | None = None) -> str:
    if not text:
        return ""

    corrected = text
    for pattern, replacement in get_ocr_correction_rules(profile=profile):
        corrected = re.sub(pattern, replacement, corrected)
    return corrected
