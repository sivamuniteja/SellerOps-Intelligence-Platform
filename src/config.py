"""Configuration loader and schema validator for SellerOps Intelligence Platform."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


class CategoryConfig(BaseModel):
    name: str
    base_commission_rate: float
    min_commission: float = 0.50
    return_window_days: int = 30


class TierConfig(BaseModel):
    commission_discount: float = 0.0
    reserve_rate: float = 0.10
    hold_days: int = 14
    min_volume: float = 0.0


class DatasetTarget(BaseModel):
    sellers: int
    customers: int
    listings: int
    orders: int
    disputes: int


class PlatformConfig(BaseModel):
    project_name: str = "SellerOps Intelligence Platform"
    version: str = "1.0.0"
    seed: int = 42
    default_db_path: str = "data/sellerops.db"
    starter_db_path: str = "data/starter/sellerops_starter.db"
    full_db_path: str = "data/full/sellerops_full.db"
    categories: List[CategoryConfig] = Field(default_factory=list)
    seller_tiers: Dict[str, TierConfig] = Field(default_factory=dict)
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
    categories = [CategoryConfig(**cat) for cat in raw_data.get("categories", [])]
    tiers = {
        name: TierConfig(**cfg)
        for name, cfg in raw_data.get("seller_tiers", {}).items()
    }
    targets = {
        name: DatasetTarget(**cfg)
        for name, cfg in raw_data.get("dataset_targets", {}).items()
    }

    return PlatformConfig(
        project_name=raw_data.get("project", {}).get("name", "SellerOps"),
        version=raw_data.get("project", {}).get("version", "1.0.0"),
        seed=raw_data.get("project", {}).get("seed", 42),
        default_db_path=raw_data.get("database", {}).get("default_path", "data/sellerops.db"),
        starter_db_path=raw_data.get("database", {}).get("starter_path", "data/starter/sellerops_starter.db"),
        full_db_path=raw_data.get("database", {}).get("full_path", "data/full/sellerops_full.db"),
        categories=categories,
        seller_tiers=tiers,
        sla_thresholds=raw_data.get("sla_thresholds", {}),
        payout_rules=raw_data.get("payout_rules", {}),
        anomalies=raw_data.get("anomalies", {}),
        dataset_targets=targets,
    )
