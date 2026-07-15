#!/usr/bin/env python3
"""Score a human-graded grading_sheet.csv from run_eval.py.

Prints precision@1 and precision@K (K = deepest graded rank) overall and per
category — the §9.2 headline numbers.
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grading", required=True, type=Path)
    args = parser.parse_args()

    with args.grading.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    graded = [r for r in rows if r["relevant"].strip().lower() in {"y", "n"}]
    ungraded = len(rows) - len(graded)
    if not graded:
        sys.exit("No graded rows — fill the `relevant` column with y/n first.")
    if ungraded:
        print(f"note: {ungraded} rows still ungraded (skipped)\n")

    by_query: dict[str, list[dict]] = defaultdict(list)
    for r in graded:
        by_query[r["query_id"]].append(r)

    def precision_at(k: int, queries: dict[str, list[dict]]) -> tuple[float, int]:
        hits, total = 0, 0
        for results in queries.values():
            top = [r for r in results if int(r["rank"]) <= k]
            hits += sum(r["relevant"].strip().lower() == "y" for r in top)
            total += len(top)
        return (hits / total if total else 0.0), total

    max_rank = max(int(r["rank"]) for r in graded)
    print(f"Queries graded: {len(by_query)}")
    for k in (1, max_rank):
        p, n = precision_at(k, by_query)
        print(f"precision@{k}: {p:.0%}  ({n} graded results)")

    print("\nPer category:")
    by_cat: dict[str, dict[str, list[dict]]] = defaultdict(dict)
    for qid, results in by_query.items():
        by_cat[results[0]["category"]][qid] = results
    for cat in sorted(by_cat):
        p1, _ = precision_at(1, by_cat[cat])
        pk, n = precision_at(max_rank, by_cat[cat])
        print(f"  {cat:10s} p@1 {p1:>4.0%}   p@{max_rank} {pk:>4.0%}   "
              f"({len(by_cat[cat])} queries, {n} graded results)")


if __name__ == "__main__":
    main()
