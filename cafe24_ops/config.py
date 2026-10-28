"""설정 로더: config/*.yaml + 환경변수(config/secrets.env)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"

_loaded = False


def load_env() -> None:
    """config/secrets.env 를 1회 로드. 이미 설정된 환경변수는 덮어쓰지 않음."""
    global _loaded
    if _loaded:
        return
    env_file = CONFIG_DIR / "secrets.env"
    if env_file.exists():
        load_dotenv(env_file, override=False)
    _loaded = True


def env(name: str, default: str = "") -> str:
    load_env()
    return (os.environ.get(name) or default).strip()


def env_all(*names: str) -> bool:
    """모든 환경변수가 채워져 있으면 True (채널 활성 판단)."""
    return all(env(n) for n in names)


def _read_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def sources() -> dict[str, Any]:
    cfg = _read_yaml("sources.yaml")
    shop = cfg.setdefault("shop", {})
    shop["mall_id"] = shop.get("mall_id") or env("CAFE24_MALL_ID")
    shop.setdefault("platform", "cafe24")
    shop.setdefault("api_version", "2025-06-01")
    cfg.setdefault("brand", "내 쇼핑몰")
    cfg.setdefault("ads", [])
    cfg.setdefault("competitors", [])
    return cfg


def metrics() -> dict[str, Any]:
    return _read_yaml("metrics.yaml")


def mode() -> str:
    """live | demo"""
    return env("CAFE24_OPS_MODE", "live").lower()


def database_url() -> str:
    return env("DATABASE_URL")
