"""CSV validation, conservative identity resolution, and auditable cleaning."""

from dataclasses import dataclass
from io import BytesIO
import csv

import numpy as np
import pandas as pd

TIERS = ["Bronze", "Silver", "Gold", "Platinum"]
REQUIRED = [
    "customer_id",
    "first_name",
    "last_name",
    "email",
    "membership_tier",
    "join_date",
    "last_purchase_date",
    "total_spend",
    "purchase_count",
    "marketing_opt_in",
    "updated_at",
]
MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 50_000


@dataclass
class CleanResult:
    clean: pd.DataFrame
    rejected: pd.DataFrame
    duplicates: pd.DataFrame
    input_rows: int
    normalized_cells: int

    @property
    def removed_duplicates(self) -> int:
        return int((self.duplicates["resolution"] == "Removed").sum())


def read_csv(payload: bytes) -> pd.DataFrame:
    """Read bounded UTF-8 CSV without losing leading zeros in IDs."""
    if len(payload) > MAX_BYTES:
        raise ValueError("CSV exceeds the 10 MB limit.")
    try:
        decoded = payload.decode("utf-8-sig")
        headers = next(csv.reader(decoded.splitlines()))
        normalized = [h.strip().lower().replace(" ", "_") for h in headers]
        if len(normalized) != len(set(normalized)):
            raise ValueError("CSV has duplicate column names after normalization.")
        frame = pd.read_csv(
            BytesIO(payload), dtype=str, keep_default_na=False, encoding="utf-8-sig", nrows=MAX_ROWS + 1
        )
    except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError, StopIteration) as exc:
        raise ValueError("Upload a non-empty, valid UTF-8 comma-separated CSV.") from exc
    if len(frame) > MAX_ROWS:
        raise ValueError("CSV exceeds the 50,000-row limit.")
    if not isinstance(frame.index, pd.RangeIndex):
        raise ValueError("CSV rows have more fields than the header. Check delimiters and quoting.")
    return frame


def clean_customers(raw: pd.DataFrame, as_of) -> CleanResult:
    """Keep latest valid snapshot per connected ID/email identity; never sum snapshots."""
    today = pd.Timestamp(as_of).normalize()
    df = raw.copy().reset_index(drop=True)
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    if df.columns.duplicated().any():
        raise ValueError("Duplicate column names after normalization.")
    missing = sorted(set(REQUIRED) - set(df.columns))
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    if len(df) > MAX_ROWS:
        raise ValueError("Dataset exceeds the 50,000-row limit.")
    # Discard unknown columns so uploads cannot inject derived metrics or audit fields.
    df = df[REQUIRED + (["country"] if "country" in df else [])].copy()
    if "country" not in df:
        df["country"] = "Unknown"
    original = df.astype("string").fillna("").astype(str)
    for col in df.columns:
        df[col] = df[col].astype("string").fillna("").astype(str).str.strip()
    df["email"] = df["email"].str.lower()
    df["membership_tier"] = df["membership_tier"].str.title()
    df["country"] = df["country"].replace("", "Unknown")
    changed = int((original != df).sum().sum())
    df["source_row"] = df.index + 2
    errors = pd.Series("", index=df.index, dtype=str)

    def reject(mask, reason):
        errors.loc[mask] += reason + "; "

    for col in ["customer_id", "first_name", "last_name"]:
        reject(df[col].eq(""), f"Missing {col}")
    reject(~df["email"].str.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+"), "Invalid email")
    reject(~df["membership_tier"].isin(TIERS), "Unknown membership tier")
    for col in ["join_date", "last_purchase_date", "updated_at"]:
        blank = df[col].eq("")
        parsed = pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce")
        strict = df[col].str.fullmatch(r"\d{4}-\d{2}-\d{2}")
        optional = blank if col == "last_purchase_date" else pd.Series(False, index=df.index)
        reject((parsed.isna() | ~strict) & ~optional, f"Invalid {col}; use YYYY-MM-DD")
        reject(parsed.gt(today), f"Future {col}")
        df[col] = parsed
    for col in ["total_spend", "purchase_count"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        reject(~np.isfinite(df[col]) | df[col].lt(0), f"Invalid {col}")
    reject(df["total_spend"].gt(1_000_000_000_000), "total_spend exceeds the supported USD 1 trillion maximum")
    reject(df["purchase_count"].gt(1_000_000_000), "purchase_count exceeds the supported 1 billion maximum")
    reject(df["purchase_count"].mod(1).ne(0), "purchase_count must be an integer")
    reject(df["last_purchase_date"].lt(df["join_date"]), "Purchase before signup")
    reject(df["updated_at"].lt(df["join_date"]), "Update before signup")
    reject(df["updated_at"].lt(df["last_purchase_date"]), "Update before purchase")
    reject(df["purchase_count"].gt(0) & df["last_purchase_date"].isna(), "Purchases need a last purchase date")
    reject(
        df["purchase_count"].eq(0) & (df["total_spend"].gt(0) | df["last_purchase_date"].notna()),
        "Zero purchases require zero spend and no last purchase date",
    )
    consent = (
        df["marketing_opt_in"]
        .str.lower()
        .map({"true": True, "false": False, "1": True, "0": False, "yes": True, "no": False})
    )
    reject(consent.isna(), "Invalid marketing_opt_in")
    df["marketing_opt_in"] = consent.astype("boolean").fillna(False).astype(bool)
    rejected = df.loc[errors.ne("")].copy()
    rejected["issues"] = errors[errors.ne("")].str.rstrip("; ")
    valid = df.loc[errors.eq("")].copy()
    valid["purchase_count"] = valid["purchase_count"].astype("int64")

    # Union-find catches transitive collisions (same ID OR normalized email).
    parents = {i: i for i in valid.index}

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    for col in ["customer_id", "email"]:
        seen = {}
        for i, value in valid[col].items():
            if value in seen:
                parents[root(i)] = root(seen[value])
            else:
                seen[value] = i
    valid["identity_group"] = [root(i) for i in valid.index]
    ordered = valid.sort_values(["updated_at", "source_row"], kind="stable")
    kept = ordered.drop_duplicates("identity_group", keep="last").copy()
    # An opt-out on any valid snapshot wins, even if the newest row is opted in.
    consent_by_group = valid.groupby("identity_group")["marketing_opt_in"].all()
    kept["marketing_opt_in"] = kept["identity_group"].map(consent_by_group).astype(bool)
    dup = valid[valid.duplicated("identity_group", keep=False)].copy()
    dup["resolution"] = np.where(dup.index.isin(kept.index), "Kept latest", "Removed")
    dup["identity_group"] = dup["identity_group"].map(lambda i: f"D{i + 1:05d}")
    clean = kept.drop(columns=["identity_group"]).sort_values("customer_id").reset_index(drop=True)
    return CleanResult(clean, rejected, dup.reset_index(drop=True), len(df), changed)


def export_csv(frame: pd.DataFrame) -> bytes:
    """Escape formula-leading strings for safer spreadsheet exports."""
    safe = frame.copy()
    for col in safe.select_dtypes(include=["object", "string"]).columns:
        safe[col] = safe[col].map(
            lambda v: "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v
        )
    return safe.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8-sig")
