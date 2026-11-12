"""Configuration loader and schema validator for SellerOps Intelligence Platform."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


class CurrencyConfig(BaseModel):
    code: str = "INR"
    symbol: str = "₹"
    locale: str = "en_IN"
    minor_unit: str = "paise"
    decimal_places: int = 2
    grouping: str = "Indian"
    default_timezone: str = "Asia/Kolkata"


class CategoryConfig(BaseModel):
    name: str
    base_commission_rate: float
    min_commission: float = 0.50
    min_commission_paise: int = 50
    return_window_days: int = 30


class TierConfig(BaseModel):
    commission_discount: float = 0.0
    reserve_rate: float = 0.10
    hold_days: int = 14
    min_volume: float = 0.0
    min_volume_paise: int = 0


class DatasetTarget(BaseModel):
    sellers: int
    customers: int
    listings: int
    orders: int
    disputes: int


class PlatformConfig(BaseModel):
    project_name: str = "SellerOps Intelligence Platform"
    version: str = "1.0.0"
    seed: int = 20261022
    currency: CurrencyConfig = Field(default_factory=CurrencyConfig)
    default_db_path: str = "data/sellerops.db"
    starter_db_path: str = "data/starter/sellerops_starter.db"
    full_db_path: str = "data/full/sellerops_full.db"
    categories: List[CategoryConfig] = Field(default_factory=list)
    seller_tiers: Dict[str, TierConfig] = Field(default_factory=dict)
    business_rules: Dict[str, Any] = Field(default_factory=dict)
    sla_thresholds: Dict[str, Any] = Field(default_factory=dict)
    payout_rules: Dict[str, Any] = Field(default_factory=dict)
    anomalies: Dict[str, Any] = Field(default_factory=dict)
    dataset_targets: Dict[str, DatasetTarget] = Field(default_factory=dict)


def load_config(config_path: Optional[Path] = None) -> PlatformConfig:
    """Load and validate the platform configuration from YAML."""
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    # Normalize structure for Pydantic
    categories = []
    for cat in raw_data.get("categories", []):
        cat_copy = dict(cat)
        if "min_commission_paise" in cat_copy and "min_commission" not in cat_copy:
            cat_copy["min_commission"] = cat_copy["min_commission_paise"] / 100.0
        elif "min_commission" in cat_copy and "min_commission_paise" not in cat_copy:
            cat_copy["min_commission_paise"] = int(cat_copy["min_commission"] * 100)
        categories.append(CategoryConfig(**cat_copy))

    tiers = {}
    for name, cfg in raw_data.get("seller_tiers", {}).items():
        cfg_copy = dict(cfg)
        if "min_volume_paise" in cfg_copy and "min_volume" not in cfg_copy:
            cfg_copy["min_volume"] = cfg_copy["min_volume_paise"] / 100.0
        elif "min_volume" in cfg_copy and "min_volume_paise" not in cfg_copy:
            cfg_copy["min_volume_paise"] = int(cfg_copy["min_volume"] * 100)
        tiers[name] = TierConfig(**cfg_copy)

    targets = {
        name: DatasetTarget(**cfg)
        for name, cfg in raw_data.get("dataset_targets", {}).items()
    }

    currency_dict = raw_data.get("currency", {})
    currency_cfg = CurrencyConfig(**currency_dict) if currency_dict else CurrencyConfig()

    return PlatformConfig(
        project_name=raw_data.get("project", {}).get("name", "SellerOps"),
        version=raw_data.get("project", {}).get("version", "1.0.0"),
        seed=raw_data.get("project", {}).get("seed", 20261022),
        currency=currency_cfg,
        default_db_path=raw_data.get("database", {}).get("default_path", "data/sellerops.db"),
        starter_db_path=raw_data.get("database", {}).get("starter_path", "data/starter/sellerops_starter.db"),
        full_db_path=raw_data.get("database", {}).get("full_path", "data/full/sellerops_full.db"),
        categories=categories,
        seller_tiers=tiers,
        business_rules=raw_data.get("business_rules", {}),
        sla_thresholds=raw_data.get("sla_thresholds", {}),
        payout_rules=raw_data.get("payout_rules", {}),
        anomalies=raw_data.get("anomalies", {}),
        dataset_targets=targets,
    )
