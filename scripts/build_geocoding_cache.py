import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.geocoding import CachedGeocoder
from app.adapters.optimization.excel_oasis_loader import load_oasis_exterior_excel
from app.config.settings import GEOCODING_CACHE_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Populate geocoding cache for routing workbook")
    parser.add_argument(
        "--excel",
        type=Path,
        default=Path("data/Routing_pilot_data_input_FINAL.xlsx"),
        help="Path to Excel workbook",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.excel.exists():
        raise FileNotFoundError(f"Excel file not found: {args.excel}")

    sites, techs = load_oasis_exterior_excel(str(args.excel))
    addresses = {
        site.address.strip()
        for site in sites
        if site.address and site.address.strip()
    }
    addresses.update(
        tech.office_address.strip()
        for tech in techs
        if tech.office_address and tech.office_address.strip()
    )

    geocoder = CachedGeocoder(GEOCODING_CACHE_PATH)
    resolved = geocoder.geocode_many(sorted(addresses))
    print(f"Cached coordinates for {len(resolved)} addresses in {GEOCODING_CACHE_PATH}")


if __name__ == "__main__":
    main()
