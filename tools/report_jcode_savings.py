import csv
from pathlib import Path


CSV_PATH = Path(__file__).with_name("jcode_token_benchmark.csv")


def _to_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def main() -> None:
    if not CSV_PATH.exists():
        raise SystemExit(f"Missing benchmark file: {CSV_PATH}")

    by_task = {}
    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            task = (row.get("task") or "").strip()
            mode = (row.get("mode") or "").strip().lower()
            tok = _to_int(row.get("input_tokens_est") or "0")
            if not task or mode not in {"baseline", "jcode"}:
                continue
            by_task.setdefault(task, {"baseline": 0, "jcode": 0})
            by_task[task][mode] = tok

    total_baseline = 0
    total_jcode = 0
    print("Task savings")
    print("------------")
    for task in sorted(by_task):
        base = by_task[task]["baseline"]
        jcode = by_task[task]["jcode"]
        total_baseline += base
        total_jcode += jcode
        if base > 0:
            saved = base - jcode
            pct = (saved / base) * 100
            print(f"{task}: baseline={base}, jcode={jcode}, saved={saved} ({pct:.1f}%)")
        else:
            print(f"{task}: baseline={base}, jcode={jcode}, saved=n/a")

    print("\nOverall")
    print("-------")
    if total_baseline > 0:
        total_saved = total_baseline - total_jcode
        total_pct = (total_saved / total_baseline) * 100
        print(
            f"baseline={total_baseline}, jcode={total_jcode}, "
            f"saved={total_saved} ({total_pct:.1f}%)"
        )
    else:
        print("No baseline values set yet.")


if __name__ == "__main__":
    main()
