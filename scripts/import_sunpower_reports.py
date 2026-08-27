#!/usr/bin/env python3
"""Import daily energy and summary values from SunPower PDF reports."""

from __future__ import annotations

import argparse
import asyncio
import re
from datetime import datetime
from pathlib import Path

import asyncpg
from pypdf import PdfReader


DATE_PATTERN = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}"
DAY_RE = re.compile(rf"(?P<day>{DATE_PATTERN})\s+(?P<energy>\d+(?:\.\d+)?)\s+(?P<max>\d+(?:\.\d+)?)")


def number_after_label(text: str, label: str) -> list[float]:
    number = r"[\d,]+(?:\.\d+)?"
    match = re.search(
        rf"{re.escape(label)}\s*((?:{number}\s*){{1,4}})",
        text,
    )
    if not match:
        return []
    return [
        float(value.replace(",", ""))
        for value in re.findall(r"[\d,]+(?:\.\d+)?", match.group(1))
    ]


def parse_report(path: Path) -> dict:
    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    period = re.search(
        rf"Period Start:\s*(?P<start>{DATE_PATTERN})\s*Period End:\s*(?P<end>{DATE_PATTERN})",
        text,
        re.DOTALL,
    )
    if not period:
        raise ValueError(f"{path.name}: missing period start/end")

    start = datetime.strptime(period["start"], "%b %d, %Y").date()
    end = datetime.strptime(period["end"], "%b %d, %Y").date()
    energy = number_after_label(text, "Energy (kWh)")
    max_power = number_after_label(text, "Max AC Power (kW)")
    days = [
        {
            "local_date": datetime.strptime(match["day"], "%b %d, %Y").date(),
            "energy_kwh": float(match["energy"]),
            "max_power_kw": float(match["max"]),
        }
        for match in DAY_RE.finditer(text)
    ]
    if not days:
        raise ValueError(f"{path.name}: no daily production rows found")
    if not energy:
        raise ValueError(f"{path.name}: missing Energy (kWh) summary")

    return {
        "period_start": start,
        "period_end": end,
        "source_file": path.name,
        "this_period_kwh": energy[0],
        "last_period_kwh": energy[1] if len(energy) > 1 else None,
        "last_year_kwh": energy[2] if len(energy) > 2 else None,
        "lifetime_kwh": energy[3] if len(energy) > 3 else None,
        "this_period_max_kw": max_power[0] if max_power else None,
        "days": days,
    }


def report_warnings(reports: list[dict]) -> list[str]:
    warnings: list[str] = []
    by_period = {
        (report["period_start"], report["period_end"]): report
        for report in reports
    }
    for report in reports:
        daily_total = sum(day["energy_kwh"] for day in report["days"])
        if abs(daily_total - report["this_period_kwh"]) > 0.1:
            warnings.append(
                f"{report['source_file']}: daily sum {daily_total:.2f} differs "
                f"from period total {report['this_period_kwh']:.2f} kWh"
            )

        prior_key = (
            report["period_start"].replace(year=report["period_start"].year - 1),
            report["period_end"].replace(year=report["period_end"].year - 1),
        )
        prior = by_period.get(prior_key)
        if prior and report["last_year_kwh"] is not None:
            difference = abs(report["last_year_kwh"] - prior["this_period_kwh"])
            if difference > 0.1:
                warnings.append(
                    f"{report['source_file']}: last-year total differs from "
                    f"{prior['source_file']} by {difference:.2f} kWh"
                )
    return warnings


async def import_reports(database_url: str, reports: list[dict]) -> None:
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                for report in reports:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO historical_reports (
                            period_start, period_end, source_file, this_period_kwh,
                            last_period_kwh, last_year_kwh, lifetime_kwh, this_period_max_kw
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (period_start, period_end) DO UPDATE SET
                            source_file = EXCLUDED.source_file,
                            this_period_kwh = EXCLUDED.this_period_kwh,
                            last_period_kwh = EXCLUDED.last_period_kwh,
                            last_year_kwh = EXCLUDED.last_year_kwh,
                            lifetime_kwh = EXCLUDED.lifetime_kwh,
                            this_period_max_kw = EXCLUDED.this_period_max_kw,
                            imported_at = now()
                        RETURNING id
                        """,
                        report["period_start"], report["period_end"], report["source_file"],
                        report["this_period_kwh"], report["last_period_kwh"],
                        report["last_year_kwh"], report["lifetime_kwh"], report["this_period_max_kw"],
                    )
                    assert row is not None
                    await conn.execute(
                        "DELETE FROM historical_report_days WHERE report_id = $1",
                        row["id"],
                    )
                    await conn.executemany(
                        """
                        INSERT INTO historical_report_days (report_id, local_date, energy_kwh, max_power_kw)
                        VALUES ($1, $2, $3, $4)
                        """,
                        [
                            (row["id"], day["local_date"], day["energy_kwh"], day["max_power_kw"])
                            for day in report["days"]
                        ],
                    )
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports_dir", type=Path)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    paths = sorted(args.reports_dir.glob("*.pdf"))
    if not paths:
        raise SystemExit(f"No PDF files found in {args.reports_dir}")
    reports = [parse_report(path) for path in paths]
    for warning in report_warnings(reports):
        print(f"WARNING: {warning}")
    asyncio.run(import_reports(args.database_url, reports))
    total_days = sum(len(report["days"]) for report in reports)
    print(f"Imported {len(reports)} reports and {total_days} daily rows")


if __name__ == "__main__":
    main()