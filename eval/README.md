# GrailSeeker Evaluation Harness (PRD §9)

Measures the two §9.2 success criteria against a hand-labeled test set of
200–500 images: (1) segmentation correctly identifies garments, and
(2) visual search returns meaningful matches.

## Workflow

1. **Collect images** into a folder, e.g. `eval/images/` (JPEG/PNG/WebP).
   Standard outfit photos per §9.1 — vary lighting, framing, and category.
2. **Label them**: copy `labels.template.csv` to `labels.csv` and fill in one
   row per garment of interest (a filename may appear on multiple rows if
   you want to evaluate several garments in one photo). Columns follow the
   PRD two-level taxonomy — see the template header comments.
3. **Point the runner at a dev API instance with lifted limits.** The eval
   burns one `/segment` + one `/find` per row, so the daily quotas must be
   raised for the run. In the serving `.env` (dev instance only!):

   ```
   GUEST_DAILY_LIMIT=100000
   FIND_DAILY_LIMIT=100000
   ```

4. **Run:**

   ```bash
   cd ClothingApp
   backend/.venv/bin/python eval/run_eval.py \
       --images eval/images --labels eval/labels.csv \
       --api http://localhost:8000 --out eval/out
   ```

5. **Grade retrieval relevance** (human step): open `eval/out/review.html`,
   look at each query's top results, and fill the `relevant` column
   (`y`/`n`) in `eval/out/grading_sheet.csv` for every listed row.
6. **Score:**

   ```bash
   backend/.venv/bin/python eval/score_grading.py --grading eval/out/grading_sheet.csv
   ```

## What the runner measures automatically (`report.md`)

- **Segmentation** (auto-detectable categories only — top/outerwear/
  bottom/dress; everything else is expected to go through "Search entire
  image" per the Option A decision): detection rate per labeled category,
  boxes per image, confidence distribution.
- **Retrieval health**: results per query, similarity distribution, share
  of queries whose top result clears the 0.7 "match" threshold, and
  category consistency between the label and the returned listings'
  category field.
- **Latency** for `/segment` and `/find`.

Human grading (`score_grading.py`) then adds the §9.2 headline numbers:
precision@1 / precision@5 (share of graded results marked relevant) overall
and per category.

## Notes

- Rows whose `category` is not auto-detectable are searched whole-image
  (bbox omitted), matching what a guest sees in the app.
- If a labeled auto-detectable garment is NOT detected, the runner still
  searches whole-image and flags the row `detected=false`, so segmentation
  misses also show up as retrieval context.
- The runner never writes to the DB; it only calls the public API.
