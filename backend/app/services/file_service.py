"""
File Processing Service
-----------------------
Handles CSV/Excel/PDF uploads, cleans QuickBooks-style GL exports,
and prepares data for GPT analysis.
"""

import pandas as pd
import io
from typing import Tuple


def read_uploaded_file(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Read CSV, Excel, or PDF file from uploaded bytes into a DataFrame."""
    if filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes))
    elif filename.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(file_bytes))
    elif filename.endswith(".pdf"):
        df = read_pdf_tables(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: {filename}")
    return df


def read_pdf_tables(file_bytes: bytes) -> pd.DataFrame:
    """
    Extract tables from a PDF using pdfplumber.
    - Scans all pages for tables
    - Combines all tables into one DataFrame
    - If no tables found, extracts raw text and returns it as a single-column DataFrame
    """
    import pdfplumber

    all_tables = []
    raw_text_pages = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            # Try to extract tables first
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    if len(table) > 1:
                        # First row as header, rest as data
                        header = [str(cell or "").strip() for cell in table[0]]
                        # Make column names unique (fix duplicate headers)
                        seen = {}
                        unique_header = []
                        for h in header:
                            if h in seen:
                                seen[h] += 1
                                unique_header.append(f"{h}_{seen[h]}")
                            else:
                                seen[h] = 0
                                unique_header.append(h)
                        rows = []
                        for row in table[1:]:
                            cleaned_row = [str(cell or "").strip() for cell in row]
                            rows.append(cleaned_row)
                        df = pd.DataFrame(rows, columns=unique_header)
                        all_tables.append(df)
            else:
                # No tables on this page — capture raw text
                text = page.extract_text()
                if text and text.strip():
                    raw_text_pages.append({
                        "page": i + 1,
                        "content": text.strip()
                    })

    if all_tables:
        # Combine all tables — use sort=False to avoid reindex errors
        combined = pd.concat(all_tables, ignore_index=True, sort=False)
        # Drop completely empty rows and columns
        combined = combined.dropna(how="all").dropna(axis=1, how="all")
        return combined
    elif raw_text_pages:
        # No tables found — return raw text as DataFrame
        return pd.DataFrame(raw_text_pages)
    else:
        raise ValueError("No tables or text could be extracted from this PDF.")


def extract_pdf_text(file_bytes: bytes) -> str:
    """
    Extract all text from a PDF (for GPT analysis when no tables are found).
    """
    import pdfplumber

    all_text = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text.append(text)
    return "\n\n".join(all_text)


def clean_gl_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean a QuickBooks-style General Ledger export.
    - Drops spacer columns (all-NaN unnamed columns)
    - Removes section header rows and total rows
    - Renames columns to clean snake_case names
    - Parses dates and amounts
    """
    # Drop columns that are entirely NaN or are unnamed spacers
    cols_to_keep = []
    for col in df.columns:
        if "Unnamed" in str(col):
            if df[col].notna().sum() > 0:
                # Some unnamed cols hold account headers — check if meaningful
                non_null = df[col].dropna().unique()
                if len(non_null) > 2:
                    cols_to_keep.append(col)
            continue
        cols_to_keep.append(col)

    df = df[cols_to_keep].copy()

    # Identify and extract account category from section headers
    # Section headers have a value in Unnamed:1 but NaN in Type
    if "Unnamed: 1" in df.columns:
        account_col = "Unnamed: 1"
        # Forward-fill the account category
        current_account = None
        account_categories = []
        for _, row in df.iterrows():
            if pd.notna(row.get(account_col)) and pd.isna(row.get("Type")):
                val = str(row[account_col]).strip()
                if not val.startswith("Total"):
                    current_account = val
            account_categories.append(current_account)
        df["account_category"] = account_categories
        df = df.drop(columns=[account_col], errors="ignore")

    # Remove header rows (no Type) and total/summary rows
    if "Type" in df.columns:
        df = df[df["Type"].notna()].copy()

    # Remove any "Total" rows that slipped through
    if "Unnamed: 0" in df.columns:
        df = df[df["Unnamed: 0"] != "TOTAL"]
        df = df.drop(columns=["Unnamed: 0"], errors="ignore")

    # Clean column names
    column_map = {
        "Type": "type",
        "Date": "date",
        "Num": "check_num",
        "Name": "name",
        "Memo": "memo",
        "Split": "split_account",
        "Amount": "amount",
        "Balance": "balance",
    }
    # Only rename columns that exist
    rename_dict = {k: v for k, v in column_map.items() if k in df.columns}
    df = df.rename(columns=rename_dict)

    # Drop any remaining unnamed columns
    df = df[[c for c in df.columns if "Unnamed" not in str(c)]]

    # Parse types
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    if "balance" in df.columns:
        df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
    if "check_num" in df.columns:
        df["check_num"] = df["check_num"].apply(
            lambda x: str(int(x)) if pd.notna(x) else ""
        )

    # Fill NaN names with empty string for display
    if "name" in df.columns:
        df["name"] = df["name"].fillna("")

    df = df.reset_index(drop=True)
    return df


def generate_summary(df: pd.DataFrame) -> dict:
    """
    Generate a statistical summary of the cleaned GL data.
    Returns a dict ready to be sent to GPT for analysis.
    """
    summary = {
        "total_transactions": len(df),
        "date_range": {},
        "transaction_types": {},
        "top_vendors": [],
        "account_breakdown": [],
        "anomalies": [],
    }

    # Date range
    if "date" in df.columns:
        dates = df["date"].dropna()
        if len(dates) > 0:
            summary["date_range"] = {
                "start": str(dates.min().date()),
                "end": str(dates.max().date()),
            }

    # Transaction type counts
    if "type" in df.columns:
        summary["transaction_types"] = df["type"].value_counts().to_dict()

    # Top vendors by transaction count
    if "name" in df.columns:
        vendor_counts = (
            df[df["name"] != ""]["name"]
            .value_counts()
            .head(10)
            .to_dict()
        )
        summary["top_vendors"] = [
            {"name": k, "transaction_count": v}
            for k, v in vendor_counts.items()
        ]

    # Account category breakdown with totals
    if "amount" in df.columns:
        if "account_category" in df.columns:
            acct_summary = (
                df.groupby("account_category")["amount"]
                .agg(["sum", "count"])
                .reset_index()
            )
            acct_summary.columns = ["account", "total_amount", "count"]
            acct_summary = acct_summary.sort_values("total_amount")
            summary["account_breakdown"] = acct_summary.to_dict("records")
        elif "split_account" in df.columns:
            acct_summary = (
                df.groupby("split_account")["amount"]
                .agg(["sum", "count"])
                .reset_index()
            )
            acct_summary.columns = ["account", "total_amount", "count"]
            acct_summary = acct_summary.sort_values("total_amount")
            summary["account_breakdown"] = acct_summary.to_dict("records")

    # Anomaly detection
    if "amount" in df.columns:
        amounts = df["amount"].dropna()
        if len(amounts) > 0:
            mean_amt = amounts.mean()
            std_amt = amounts.std()
            threshold = 2.5

            outliers = df[
                (df["amount"].notna())
                & ((df["amount"] - mean_amt).abs() > threshold * std_amt)
            ]

            for _, row in outliers.iterrows():
                anomaly = {
                    "date": str(row.get("date", "N/A")),
                    "amount": float(row["amount"]),
                    "name": str(row.get("name", "")),
                    "memo": str(row.get("memo", "")),
                    "reason": f"Amount ${row['amount']:,.2f} is more than {threshold} std deviations from mean (${mean_amt:,.2f})",
                }
                summary["anomalies"].append(anomaly)

    # Duplicate vendor name detection (fuzzy)
    if "name" in df.columns:
        names = df[df["name"] != ""]["name"].unique()
        similar_pairs = _find_similar_names(names)
        if similar_pairs:
            summary["duplicate_vendors"] = similar_pairs

    return summary


def _find_similar_names(names: list) -> list:
    """Find vendor names that look like duplicates (simple approach)."""
    pairs = []
    normalized = {}
    for name in names:
        key = name.lower().replace(" ", "").replace(",", "").replace(".", "")
        if key in normalized:
            pairs.append({
                "name_1": normalized[key],
                "name_2": name,
                "issue": "Possible duplicate — same name with different formatting",
            })
        else:
            normalized[key] = name
    return pairs


def df_to_preview(df: pd.DataFrame, max_rows: int = 50) -> list:
    """Convert DataFrame to list of dicts for JSON response (preview)."""
    preview = df.head(max_rows).copy()
    # Convert dates to strings for JSON serialization
    for col in preview.columns:
        if pd.api.types.is_datetime64_any_dtype(preview[col]):
            preview[col] = preview[col].dt.strftime("%Y-%m-%d").fillna("")
    preview = preview.fillna("")
    return preview.to_dict("records")
