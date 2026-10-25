"""Unit tests for report loading and real-world number/suppression cleaning."""

import numpy as np
import pandas as pd
import pytest

from dv360_bidkit.contracts.schemas import ReportMapping
from dv360_bidkit.io.reports import _clean_numeric_series, load_report


def test_clean_numeric_series_european_and_privacy():
    raw = pd.Series([
        "1.234.567,89 €",
        "1.234,56",
        "1.234.567",
        "1,234,567.89 $",
        "50,5 %",
        "< 100",
        "<10",
        "*",
        "(not set)",
        "-",
        "1500",
    ])
    cleaned = _clean_numeric_series(raw)

    assert cleaned[0] == pytest.approx(1234567.89)
    assert cleaned[1] == pytest.approx(1234.56)
    assert cleaned[2] == pytest.approx(1234567.0)
    assert cleaned[3] == pytest.approx(1234567.89)
    assert cleaned[4] == pytest.approx(0.505)
    assert np.isnan(cleaned[5])  # "< 100" privacy suppressed
    assert np.isnan(cleaned[6])  # "<10"
    assert np.isnan(cleaned[7])  # "*"
    assert np.isnan(cleaned[8])  # "(not set)"
    assert np.isnan(cleaned[9])  # "-"
    assert cleaned[10] == pytest.approx(1500.0)


def test_load_report_with_european_numbers_and_suppression(tmp_path):
    report_csv = tmp_path / "german_report.csv"
    report_csv.write_text(
        "Domain,Impressions,Active View: Measurable Impressions,Active View: Viewable Impressions,Total Conversions\n"
        "spiegel.de,\"100.000\",\"90.000\",\"75.000\",\"< 100\"\n"
        "zeit.de,\"50.000\",\"40.000\",\"30.000\",\"120\"\n"
        "Total,150.000,130.000,105.000,120\n",
        encoding="utf-8",
    )

    mapping = ReportMapping(
        canonical_field_map={
            "domain": "Domain",
            "impressions": "Impressions",
            "measurable_impressions": "Active View: Measurable Impressions",
            "viewable_impressions": "Active View: Viewable Impressions",
            "conversions": "Total Conversions",
        }
    )

    rep_data = load_report(report_csv, mapping=mapping)
    df = rep_data.df

    # Summary row 'Total' was stripped
    assert len(df) == 2
    assert df.loc[0, "Domain"] == "spiegel.de"
    assert df.loc[0, "Impressions"] == 100000.0
    assert df.loc[0, "Active View: Viewable Impressions"] == 75000.0
    assert np.isnan(df.loc[0, "Total Conversions"])
    assert df.loc[1, "Total Conversions"] == 120.0
