#!/usr/bin/env python3
"""GrailSeeker evaluation runner (PRD §9).

Feeds hand-labeled images through /segment + /find on a running API
instance and writes:

  out/results.jsonl     raw per-row records
  out/report.md         automatic metrics (segmentation + retrieval health)
  out/review.html       query image + top results, for human relevance grading
  out/grading_sheet.csv one row per (query, result) to mark relevant y/n

Only stdlib + httpx (installed with the backend requirements).
"""

import argparse
import base64
import csv
import html
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import httpx

AUTO_DETECTABLE = {"top", "outerwear", "bottom", "dress"}
VALID_CATEGORIES = AUTO_DETECTABLE | {
    "footwear", "bag", "headwear", "jewelry", "eyewear", "other",
}
MATCH_THRESHOLD = 0.7
REVIEW_TOP_K = 5


def load_labels(labels_path: Path) -> list[dict]:
    rows = []
    with labels_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(
            line for line in f if not line.lstrip().startswith("#")
        )
        for i, row in enumerate(reader, start=2):
            row = {k: (v or "").strip() for k, v in row.items() if k}
            if not row.get("filename"):
                continue
            category = row.get("category", "").lower()
            if category not in VALID_CATEGORIES:
                sys.exit(
                    f"labels row {i}: category {category!r} is not one of "
                    f"{sorted(VALID_CATEGORIES)}"
                )
            row["category"] = category
            rows.append(row)
    if not rows:
        sys.exit("No labeled rows found — fill in the labels CSV first.")
    return rows


def run_row(client: httpx.Client, images_dir: Path, row: dict) -> dict:
    image_path = images_dir / row["filename"]
    image_bytes = image_path.read_bytes()
    files = {"image": (image_path.name, image_bytes, "image/jpeg")}

    record: dict = {"label": row}

    t0 = time.perf_counter()
    seg = client.post("/api/v1/search/segment", files=files)
    seg.raise_for_status()
    record["segment_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    seg_data = seg.json()
    record["detections"] = seg_data["items"]
    record["image_size"] = [seg_data["image_width"], seg_data["image_height"]]

    # Pick the highest-confidence box whose category matches the label;
    # accessories (and misses) fall back to a whole-image search, exactly
    # like the app's "Search entire image" action.
    bbox = None
    if row["category"] in AUTO_DETECTABLE:
        matching = [d for d in seg_data["items"] if d["category"] == row["category"]]
        if matching:
            best = max(matching, key=lambda d: d["confidence"])
            bbox = best["bbox"]
    record["detected"] = bbox is not None

    params = {"category": row["category"]}
    if bbox:
        params.update(
            bbox_x=bbox["x"], bbox_y=bbox["y"], bbox_w=bbox["w"], bbox_h=bbox["h"]
        )

    t0 = time.perf_counter()
    find = client.post("/api/v1/search/find", params=params, files=files)
    find.raise_for_status()
    record["find_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    record["results"] = find.json()["results"]
    return record


def write_report(records: list[dict], out: Path) -> None:
    lines = ["# GrailSeeker Evaluation Report (automatic metrics)", ""]
    lines.append(f"Queries run: **{len(records)}**")
    lines.append("")

    # --- Segmentation (auto-detectable labels only) ---
    auto = [r for r in records if r["label"]["category"] in AUTO_DETECTABLE]
    lines.append("## Segmentation (PRD §9.2 criterion 1)")
    lines.append("")
    if auto:
        detected = sum(r["detected"] for r in auto)
        lines.append(
            f"- Detection rate (a box of the labeled category exists): "
            f"**{detected}/{len(auto)} = {detected / len(auto):.0%}**"
        )
        per_cat: dict[str, list[bool]] = defaultdict(list)
        for r in auto:
            per_cat[r["label"]["category"]].append(r["detected"])
        for cat in sorted(per_cat):
            hits = per_cat[cat]
            lines.append(f"  - {cat}: {sum(hits)}/{len(hits)} = {sum(hits) / len(hits):.0%}")
        boxes = [len(r["detections"]) for r in records]
        lines.append(f"- Boxes per image: mean {statistics.mean(boxes):.1f}, max {max(boxes)}")
        confs = [d["confidence"] for r in records for d in r["detections"]]
        if confs:
            lines.append(
                f"- Box confidence: mean {statistics.mean(confs):.2f}, "
                f"min {min(confs):.2f}, max {max(confs):.2f}"
            )
    else:
        lines.append("- No auto-detectable categories in the label set.")
    lines.append("")

    # --- Retrieval health ---
    lines.append("## Retrieval health (automatic; relevance needs grading)")
    lines.append("")
    counts = [len(r["results"]) for r in records]
    lines.append(f"- Results per query: mean {statistics.mean(counts):.1f}, min {min(counts)}")
    empty = sum(1 for c in counts if c == 0)
    if empty:
        lines.append(f"- Queries with zero results: **{empty}**")
    top_sims = [r["results"][0]["similarity"] for r in records if r["results"]]
    if top_sims:
        strong = sum(1 for s in top_sims if s >= MATCH_THRESHOLD)
        lines.append(
            f"- Top-1 similarity: mean {statistics.mean(top_sims):.3f}; "
            f"queries whose top result is a confident match (≥{MATCH_THRESHOLD}): "
            f"**{strong}/{len(top_sims)} = {strong / len(top_sims):.0%}**"
        )
    all_sims = [res["similarity"] for r in records for res in r["results"]]
    if all_sims:
        buckets = Counter(
            "match (≥0.7)" if s >= 0.7 else "similar (0.4–0.7)" for s in all_sims
        )
        lines.append(f"- All returned results by confidence label: {dict(buckets)}")

    # --- Latency ---
    lines.append("")
    lines.append("## Latency")
    lines.append("")
    for key, name in [("segment_ms", "/segment"), ("find_ms", "/find")]:
        vals = sorted(r[key] for r in records)
        p95 = vals[int(len(vals) * 0.95) - 1] if len(vals) >= 2 else vals[-1]
        lines.append(f"- {name}: mean {statistics.mean(vals):.0f} ms, p95 {p95:.0f} ms")

    lines.append("")
    lines.append(
        "Next step: grade relevance in grading_sheet.csv (see review.html), "
        "then run score_grading.py for precision@1/@5."
    )
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_review_assets(records: list[dict], images_dir: Path, out: Path) -> None:
    """review.html (visual) + grading_sheet.csv (fill in `relevant`)."""
    with (out / "grading_sheet.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["query_id", "filename", "category", "rank", "listing_id",
             "listing_title", "similarity", "listing_url", "relevant"]
        )
        for qid, r in enumerate(records):
            for rank, res in enumerate(r["results"][:REVIEW_TOP_K], start=1):
                writer.writerow(
                    [qid, r["label"]["filename"], r["label"]["category"], rank,
                     res["id"], res.get("title") or "", res["similarity"],
                     res["listing_url"], ""]
                )

    parts = [
        "<!doctype html><meta charset='utf-8'><title>GrailSeeker eval review</title>",
        "<style>body{font-family:sans-serif;margin:20px} .q{border-top:2px solid #333;"
        "padding:12px 0} .row{display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap}"
        " .card{width:150px;font-size:11px} .card img{width:150px;height:200px;"
        "object-fit:cover;border-radius:6px} .query img{width:200px;max-height:280px;"
        "object-fit:contain;border:3px solid #06c;border-radius:6px}</style>",
        "<h1>GrailSeeker eval review</h1>",
        f"<p>Grade the top {REVIEW_TOP_K} results per query as relevant y/n in "
        "<code>grading_sheet.csv</code> (query_id + rank identify each card).</p>",
    ]
    for qid, r in enumerate(records):
        label = r["label"]
        img_path = images_dir / label["filename"]
        b64 = base64.b64encode(img_path.read_bytes()).decode()
        meta = " · ".join(
            filter(None, [label["category"], label.get("subtype"),
                          label.get("primary_color"), label.get("material")])
        )
        parts.append(f"<div class='q'><h3>#{qid} {html.escape(label['filename'])}"
                     f" — {html.escape(meta)}</h3><div class='row'>")
        parts.append(f"<div class='query'><img src='data:image/jpeg;base64,{b64}'>"
                     f"<br>query{' (whole image)' if not r['detected'] else ''}</div>")
        for rank, res in enumerate(r["results"][:REVIEW_TOP_K], start=1):
            title = html.escape(res.get("title") or "(no title)")
            parts.append(
                f"<div class='card'><img src='{html.escape(res['image_url'])}' "
                f"loading='lazy'><br><b>rank {rank}</b> sim {res['similarity']:.2f}"
                f"<br>{title}</div>"
            )
        parts.append("</div></div>")
    (out / "review.html").write_text("".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", required=True, type=Path)
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--out", default=Path("eval/out"), type=Path)
    parser.add_argument("--token", help="Bearer token (optional; guest works)")
    args = parser.parse_args()

    rows = load_labels(args.labels)
    missing = [r["filename"] for r in rows if not (args.images / r["filename"]).is_file()]
    if missing:
        sys.exit(f"Missing image files: {missing[:10]}{'...' if len(missing) > 10 else ''}")

    args.out.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}

    records = []
    with httpx.Client(base_url=args.api, headers=headers, timeout=120) as client:
        for i, row in enumerate(rows, start=1):
            try:
                record = run_row(client, args.images, row)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    sys.exit(
                        "Rate-limited by the API. Raise GUEST_DAILY_LIMIT and "
                        "FIND_DAILY_LIMIT on the eval instance (see eval/README.md)."
                    )
                raise
            records.append(record)
            print(f"[{i}/{len(rows)}] {row['filename']} ({row['category']}) "
                  f"detected={record['detected']} results={len(record['results'])}")

    with (args.out / "results.jsonl").open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    write_report(records, args.out)
    write_review_assets(records, args.images, args.out)
    print(f"\nWrote {args.out}/report.md, review.html, grading_sheet.csv, results.jsonl")


if __name__ == "__main__":
    main()
