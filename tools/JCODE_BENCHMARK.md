# JCode Token Benchmark (AC Career Manager)

Use this to measure how much input-token volume JCodeMunch saves versus baseline file reads.

## 1) What to measure

- Measure only repository-inspection input (what you feed the model while exploring code).
- Ignore final answer text; keep focus on code-context intake.
- Run the same task twice:
  - `baseline`: traditional `Get-Content`/full-file reads.
  - `jcode`: JCodeMunch-first flow.

## 2) Fill the CSV

File: `tools/jcode_token_benchmark.csv`

For each row:
- `input_chars`: total characters of code/context passed during exploration.
- `input_tokens_est`: estimated tokens (`round(input_chars / 4)` works well enough for comparisons).
- `notes`: optional (e.g. "2 extra files due to fallback").

## 3) Compute savings

Run:

```bash
python tools/report_jcode_savings.py
```

It prints per-task and overall savings (%).

## 4) Recommended cadence

- First benchmark: 5 tasks (already pre-filled in CSV).
- Re-run monthly after workflow or prompt-policy changes.

## 5) Good target

- If overall savings is below 30%, tighten JCode usage (fewer full-file reads).
- 40-65% is a strong range for this repository.
