from pathlib import Path
import yaml

APP_ROOT = Path(__file__).resolve().parents[1]
BRAND = yaml.safe_load((APP_ROOT / "config/app_config.yaml").read_text(encoding="utf-8"))
COLORS = BRAND["colors"]
COLORS.update(
    {
        "spatial_panel": "#F8FAFC",
        "spatial_background": "#F0F4F8",
        "spatial_text": "#0D2B38",
        "spatial_heading": "#0D2B38",
        "spatial_grid": "#CBD5E1",
        "spatial_border": "#E2E8F0",
        "spatial_series": "#134E5E",
        "spatial_selected": "#D97706",
        "spatial_agreement": "#7C3AED",
    }
)