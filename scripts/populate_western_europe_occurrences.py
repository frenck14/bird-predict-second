"""Populate western_europe_occurrences.csv from the GBIF occurrence API.

Counts are GBIF HUMAN_OBSERVATION, occurrenceStatus=PRESENT records per country
(not rarity-committee-accepted records). Unverifiable species/countries are
left blank with source=manual_review_required.
"""
import csv
import datetime as dt
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "inputs" / "next_dutch_firsts"
API = "https://api.gbif.org/v1"
COUNTRIES = {"GB": "United Kingdom", "IE": "Ireland", "BE": "Belgium",
             "DE": "Germany", "DK": "Denmark"}
TODAY = dt.date.today().isoformat()
SOURCE = f"GBIF occurrence API (HUMAN_OBSERVATION, PRESENT), retrieved {TODAY}"


def get(path, **params):
    url = f"{API}/{path}?{urllib.parse.urlencode(params, doseq=True)}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def main():
    with open(BASE / "species_master.csv", newline="", encoding="utf-8") as f:
        species = list(csv.DictReader(f))
    rows, report = [], []
    for sp in species:
        name, sci = sp["species"], sp["scientific_name"]
        m = get("species/match", name=sci, rank="SPECIES", kingdom="Animalia")
        ok = bool(m) and m.get("matchType") == "EXACT" and m.get("status") == "ACCEPTED" \
            and m.get("canonicalName", "").lower() == sci.lower()
        key = m.get("usageKey") if ok else None
        for code, country in COUNTRIES.items():
            res = None
            if key:
                res = get("occurrence/search", taxonKey=key, country=code, limit=0,
                          basisOfRecord="HUMAN_OBSERVATION", occurrenceStatus="PRESENT",
                          facet="year", facetLimit=500)
            if res is None:
                rows.append([name, country, "", "", "", "manual_review_required"])
                report.append((name, country, None))
                continue
            years = sorted(int(c["name"]) for f_ in res.get("facets", [])
                           for c in f_["counts"])
            n = res["count"]
            if n == 0:
                # Verified zero records in GBIF
                rows.append([name, country, 0, "", "", SOURCE])
            else:
                rows.append([name, country, n, years[0] if years else "",
                             years[-1] if years else "", SOURCE])
            report.append((name, country, n))
    with open(BASE / "western_europe_occurrences.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["species", "country", "record_count", "period_start", "period_end", "source"])
        w.writerows(rows)

    names = [s["species"] for s in species]
    pop = [n for n in names if any(r[0] == n and r[2] != "" for r in rows)]
    missing = [n for n in names if n not in pop]
    nonzero = {n for n in names if any(r[0] == n and r[2] not in ("", 0) for r in rows)}
    lines = ["# Western Europe occurrences completeness report", "",
             f"Source: GBIF occurrence API, retrieved {TODAY}. Counts are GBIF human observations "
             "(not accepted-rarity-committee records).", "",
             f"- Species in master: {len(names)}",
             f"- Species with verified data (any country): {len(pop)}",
             f"- Species with >=1 record in a priority country: {len(nonzero)}",
             f"- Species missing data (manual_review_required): {len(missing)}", "",
             "## Country coverage", "", "| Country | Species verified | Species with records>0 | Total records |",
             "|---|---|---|---|"]
    for country in COUNTRIES.values():
        cr = [r for r in rows if r[1] == country]
        v = [r for r in cr if r[2] != ""]
        lines.append(f"| {country} | {len(v)} | {sum(1 for r in v if r[2] > 0)} | {sum(r[2] for r in v)} |")
    lines += ["", "## Species missing data", ""] + ([f"- {n}" for n in missing] or ["- none"])
    lines += ["", "## Species with zero GBIF records in all priority countries", ""]
    zero = [n for n in pop if n not in nonzero]
    lines += [f"- {n}" for n in zero] or ["- none"]
    (BASE / "western_europe_occurrences_completeness.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
