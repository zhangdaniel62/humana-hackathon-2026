"""Shared claim fixtures built from the repository CSV snapshot."""

from __future__ import annotations

import csv
from pathlib import Path

from src.models.claims import ClaimRow, ClaimStatus

CLAIMS_CSV = Path(__file__).resolve().parents[2] / "datasets" / "claims.csv"


def load_claim_rows() -> list[ClaimRow]:
    """Load CSV rows using the same coercions expected from BigQuery rows."""

    with CLAIMS_CSV.open(newline="", encoding="utf-8") as claim_file:
        rows = []
        for raw_row in csv.DictReader(claim_file):
            normalized = {
                key: value if value != "" else None for key, value in raw_row.items()
            }
            rows.append(ClaimRow.model_validate(normalized))
        return rows


def claim_for_status(status: ClaimStatus) -> ClaimRow:
    """Return a stable representative of a status from the CSV snapshot."""

    return next(claim for claim in load_claim_rows() if claim.claim_status == status)
