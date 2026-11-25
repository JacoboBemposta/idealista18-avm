"""Build the table the project starts from, data/idealista18_listings.parquet, from the idealista18 source.

    python build_dataset.py

It runs the ETL pipeline of docs/building-the-dataset/etl_pipeline.ipynb without the explanations, and writes the
same two files: the table, one row per sale listing of Madrid, Barcelona and Valencia, and a data-quality report.
The source files are downloaded once, into data/raw_rda/, and reused by later runs and by the notebooks.

Source: idealista18 (Rey-Blanco, Arbués, López & Páez, 2024, Environment and Planning B,
doi:10.1177/23998083241242844), licensed ODbL v1.0.
"""

import shutil
import sys
import time
import urllib.error
import urllib.request
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import rdata
import shapely

REPOSITORY = Path(__file__).resolve().parent
DATA_DIR = REPOSITORY / "data"
RAW_DIR = DATA_DIR / "raw_rda"
OUTPUT_PARQUET = DATA_DIR / "idealista18_listings.parquet"
QUALITY_REPORT = DATA_DIR / "idealista18_quality_report.csv"

CITIES = ("Madrid", "Barcelona", "Valencia")
OBJECT_KINDS = ("Sale", "Polygons", "POIS")
SOURCE_URL_TEMPLATE = "https://github.com/paezha/idealista18/raw/master/data/{file_name}"
# A server has several addresses, tried in turn. Without a timeout, an address that never answers holds a download
# for about two minutes before the next one is tried; with it, ten seconds.
DOWNLOAD_TIMEOUT_SECONDS = 10
DOCUMENTED_ROWS = {"Madrid": 94_815, "Barcelona": 61_486, "Valencia": 33_622}

SHARED_COLUMN_NAMES = {
    "ASSETID": "asset_id",
    "PERIOD": "period",
    "PRICE": "price_eur",
    "UNITPRICE": "unit_price_eur_m2",
    "CONSTRUCTEDAREA": "built_area_m2",
    "ROOMNUMBER": "bedrooms",
    "BATHNUMBER": "bathrooms",
    "HASTERRACE": "has_terrace",
    "HASLIFT": "has_lift",
    "HASAIRCONDITIONING": "has_air_conditioning",
    "HASPARKINGSPACE": "has_parking_space",
    "ISPARKINGSPACEINCLUDEDINPRICE": "parking_included_in_price",
    "PARKINGSPACEPRICE": "parking_space_price_eur",
    "HASNORTHORIENTATION": "faces_north",
    "HASSOUTHORIENTATION": "faces_south",
    "HASEASTORIENTATION": "faces_east",
    "HASWESTORIENTATION": "faces_west",
    "HASBOXROOM": "has_box_room",
    "HASWARDROBE": "has_wardrobe",
    "HASSWIMMINGPOOL": "has_swimming_pool",
    "HASDOORMAN": "has_doorman",
    "HASGARDEN": "has_garden",
    "ISDUPLEX": "is_duplex",
    "ISSTUDIO": "is_studio",
    "ISINTOPFLOOR": "is_top_floor",
    "CONSTRUCTIONYEAR": "construction_year",
    "FLOORCLEAN": "floor",
    "CADCONSTRUCTIONYEAR": "cadastre_construction_year",
    "CADMAXBUILDINGFLOOR": "cadastre_building_floors",
    "CADDWELLINGCOUNT": "cadastre_dwellings_in_building",
    "CADASTRALQUALITYID": "cadastre_quality",
    "DISTANCE_TO_CITY_CENTER": "dist_city_centre_km",
    "DISTANCE_TO_METRO": "dist_metro_km",
    "LATITUDE": "latitude",
    "LONGITUDE": "longitude",
}
LANDMARK_COLUMN_NAMES = {
    "Madrid": ("DISTANCE_TO_CASTELLANA", "dist_castellana_km"),
    "Barcelona": ("DISTANCE_TO_DIAGONAL", "dist_diagonal_km"),
    "Valencia": ("DISTANCE_TO_BLASCO", "dist_blasco_km"),
}

CONDITION_COLUMNS = {"BUILTTYPEID_1": "new_development", "BUILTTYPEID_2": "to_restore", "BUILTTYPEID_3": "good"}
CONDITION = pd.CategoricalDtype(list(CONDITION_COLUMNS.values()))
FURNISHING = pd.CategoricalDtype(["none", "kitchen", "kitchen_and_furniture"])
OUTLOOK = pd.CategoricalDtype(["exterior", "interior"])

# Listings in the thin gaps between neighbourhood polygons, up to about 100 m away, take the nearest neighbourhood
GAP_TOLERANCE_DEGREES = 0.001


def relative(path: Path) -> str:
    return path.relative_to(REPOSITORY).as_posix()


def seconds_since(start: float) -> str:
    return f"{time.perf_counter() - start:.0f} s"


def download_source_files() -> None:
    """Download the source files not yet in data/raw_rda/, one line per file."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    source_files = [RAW_DIR / f"{city}_{kind}.rda" for city in CITIES for kind in OBJECT_KINDS]
    missing_files = [path for path in source_files if not path.exists()]
    if not missing_files:
        print(f"      all {len(source_files)} files are already there, from an earlier run")
        return
    for destination in missing_files:
        print(f"      {destination.name:<22}", end="", flush=True)
        download_start = time.perf_counter()
        partial_file = destination.with_suffix(".part")
        try:
            with (urllib.request.urlopen(SOURCE_URL_TEMPLATE.format(file_name=destination.name),
                                         timeout=DOWNLOAD_TIMEOUT_SECONDS) as response,
                  partial_file.open("wb") as file):
                shutil.copyfileobj(response, file)
        except (urllib.error.URLError, TimeoutError) as error:
            partial_file.unlink(missing_ok=True)
            reason = error.reason if isinstance(error, urllib.error.URLError) else "no answer"
            sys.exit(f"\nCould not download {destination.name} ({reason}). Check the internet connection "
                     "and run the script again: the files already downloaded are kept.")
        partial_file.replace(destination)
        print(f"{destination.stat().st_size / 1e6:4.1f} MB ({seconds_since(download_start)})")


def read_r_object(city: str, kind: str) -> object:
    with warnings.catch_warnings():
        # R's spatial (sf) classes have no Python equivalent: rdata converts them to plain data, and warns
        warnings.filterwarnings("ignore", message="Missing constructor for R class")
        converted_objects = rdata.read_rda(RAW_DIR / f"{city}_{kind}.rda", default_encoding="utf8")
    return converted_objects[f"{city}_{kind}"]


def decode_coded_columns(listings: pd.DataFrame) -> pd.DataFrame:
    condition_codes = listings[list(CONDITION_COLUMNS)].to_numpy().argmax(axis=1)
    return pd.DataFrame({
        "condition": pd.Categorical.from_codes(condition_codes, dtype=CONDITION),
        "furnishing": listings["AMENITYID"].map({1: "none", 2: "kitchen", 3: "kitchen_and_furniture"})
                                           .astype(FURNISHING),
        "outlook": listings["FLATLOCATIONID"].map({1: "exterior", 2: "interior"}).astype(OUTLOOK),
    }, index=listings.index)


def to_clean_schema(listings: pd.DataFrame, city: str) -> pd.DataFrame:
    source_landmark_column, landmark_column = LANDMARK_COLUMN_NAMES[city]
    city_table = listings[list(SHARED_COLUMN_NAMES)].rename(columns=SHARED_COLUMN_NAMES)
    city_table["asset_id"] = city_table["asset_id"].astype("str")
    city_table = pd.concat([city_table, decode_coded_columns(listings)], axis="columns")
    city_table[landmark_column] = listings[source_landmark_column]
    city_table["city"] = city.lower()
    return city_table


def to_shapely_multipolygon(polygons: list[list[np.ndarray]]) -> shapely.MultiPolygon:
    return shapely.MultiPolygon([shapely.Polygon(rings[0], holes=rings[1:]) for rings in polygons])


def with_neighbourhoods(listings: pd.DataFrame, polygons_by_city: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Each listing's neighbourhood: the polygon that contains its point, or the nearest one across a thin gap."""
    neighbourhoods = pd.concat(
        [polygons_by_city[city].assign(city=city.lower()) for city in CITIES], ignore_index=True)
    neighbourhood_shapes = [to_shapely_multipolygon(polygons) for polygons in neighbourhoods["geometry"]]
    listing_points = shapely.points(listings["longitude"].to_numpy(), listings["latitude"].to_numpy())
    spatial_index = shapely.STRtree(neighbourhood_shapes)
    point_positions, neighbourhood_positions = spatial_index.query(listing_points, predicate="intersects")

    unmatched_positions = np.flatnonzero(np.bincount(point_positions, minlength=len(listings)) == 0)
    gap_positions, gap_neighbourhood_positions = spatial_index.query_nearest(
        listing_points[unmatched_positions], max_distance=GAP_TOLERANCE_DEGREES, all_matches=False)
    matches = pd.DataFrame({
        "listing": np.concatenate([point_positions, unmatched_positions[gap_positions]]),
        "neighbourhood_position": np.concatenate([neighbourhood_positions, gap_neighbourhood_positions]),
    })
    matches["neighbourhood_id"] = neighbourhoods["LOCATIONID"].to_numpy()[matches["neighbourhood_position"]]
    matches["neighbourhood"] = neighbourhoods["LOCATIONNAME"].to_numpy()[matches["neighbourhood_position"]]
    # A listing on a shared border falls in two neighbourhoods: keep the one with the lowest identifier
    first_match = matches.sort_values("neighbourhood_id").drop_duplicates("listing").set_index("listing")
    return listings.assign(
        neighbourhood_id=first_match["neighbourhood_id"].reindex(listings.index).astype("str"),
        neighbourhood=first_match["neighbourhood"].reindex(listings.index).astype("str"),
    )


def quality_report(listings: pd.DataFrame) -> pd.DataFrame:
    """How many rows break each quality rule. The rows are reported, never removed."""
    asset_rows = listings.groupby(["city", "asset_id"])["period"]
    quality_rules = {
        "price not a multiple of €1,000": listings["price_eur"] % 1000 != 0,
        "built area below 20 m² or above 500 m²": ~listings["built_area_m2"].between(20, 500),
        "construction year before 1500 or after 2018": ~listings["construction_year"].between(1500, 2018)
                                                       & listings["construction_year"].notna(),
        "more than 10 bedrooms": listings["bedrooms"] > 10,
        "more than 10 bathrooms": listings["bathrooms"] > 10,
        "no bedroom, but not a studio": (listings["bedrooms"] == 0) & (listings["is_studio"] == 0),
        "outside every neighbourhood": listings["neighbourhood"].isna(),
        "asset repeated within its quarter": listings.duplicated(["city", "asset_id", "period"], keep=False),
        "asset in more than one quarter": asset_rows.transform("nunique") > 1,
        "parking flags disagree": listings["has_parking_space"] != listings["parking_included_in_price"],
    }
    return pd.DataFrame({
        "rows": {rule: int(broken.sum()) for rule, broken in quality_rules.items()},
        "share (%)": {rule: round(100 * float(broken.mean()), 2) for rule, broken in quality_rules.items()},
    })


def main() -> None:
    if int(pd.__version__.split(".")[0]) < 3:
        sys.exit(f"This script needs pandas 3 or later, and this environment has pandas {pd.__version__}. "
                 "Install the packages of requirements.txt and run it again.")
    start = time.perf_counter()
    print("Building the project's table from idealista18 (Rey-Blanco et al., 2024; licence ODbL v1.0).")
    print("The first run downloads the source data, about 14 MB, which can take a few minutes;")
    print("later runs reuse it, and take less than a minute.\n")

    print(f"[1/5] Extract: the source files, into {relative(RAW_DIR)}/: each city's listings, "
          "neighbourhood polygons and points of interest")
    download_source_files()

    phase_start = time.perf_counter()
    print("[2/5] Extract: reading the R data files (.rda): each city's listings and its neighbourhoods")
    listings_by_city = {city: read_r_object(city, "Sale") for city in CITIES}
    polygons_by_city = {city: read_r_object(city, "Polygons") for city in CITIES}
    row_counts = {city: len(listings) for city, listings in listings_by_city.items()}
    if row_counts != DOCUMENTED_ROWS:
        sys.exit(f"The source has {row_counts} listings, not the documented {DOCUMENTED_ROWS}: it may have changed "
                 "upstream, and the table would differ from the one the project describes.")
    print("      " + ", ".join(f"{city} {count:,}" for city, count in row_counts.items())
          + f" listings, as documented ({seconds_since(phase_start)})")

    phase_start = time.perf_counter()
    print("[3/5] Transform: descriptive column names, explicit types and decoded categories, "
          "into one table for the three cities")
    listings = pd.concat([to_clean_schema(listings_by_city[city], city) for city in CITIES], ignore_index=True)
    listings = listings[["city", *listings.columns.drop("city")]]
    print(f"      {len(listings):,} rows, {listings.shape[1]} columns ({seconds_since(phase_start)})")

    phase_start = time.perf_counter()
    print("[4/5] Transform: the neighbourhood of each listing, the polygon that contains its coordinates")
    listings = with_neighbourhoods(listings, polygons_by_city)
    placed = int(listings["neighbourhood"].notna().sum())
    print(f"      {placed:,} listings placed in a neighbourhood, {len(listings) - placed} outside every one "
          f"({seconds_since(phase_start)})")

    phase_start = time.perf_counter()
    print("[5/5] Load: a data-quality report, and the table as a Parquet file")
    report = quality_report(listings)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    report.to_csv(QUALITY_REPORT)
    listings.to_parquet(OUTPUT_PARQUET, index=False)
    print(f"      {len(report)} quality rules checked: every row is kept, and {relative(QUALITY_REPORT)} counts "
          "the rows that break each rule")
    print(f"      {relative(OUTPUT_PARQUET)}: {len(listings):,} rows, {listings.shape[1]} columns, "
          f"{OUTPUT_PARQUET.stat().st_size / 1e6:.1f} MB ({seconds_since(phase_start)})")

    print(f"\nDone in {seconds_since(start)}. How each step works, and why: docs/building-the-dataset/README.md")


if __name__ == "__main__":
    main()
