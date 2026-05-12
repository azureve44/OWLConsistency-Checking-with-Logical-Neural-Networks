"""
1 parse_lubm.py        BINARY txts -> facts.jsonl
2 run_hermit.py        facts.jsonl + TBox -> hermit_labels.jsonl
3 prepare_hermit_labels.py  hermit_labels.jsonl -> labelled_facts.jsonl

Out:
    hermit_labels/labelled_facts.jsonl
    hermit_labels/hermit_benchmark.jsonl
    hermit_labels/label_stats.txt
===========================
python
hermit_pipeline / run.py \
- -data_dir / path / to / lubm_txt / \
--tbox / path / to / univ - bench.owl \
- -hermit / path / to / HermiT.jar \
- -out_dir
hermit_labels / \
[--workers 8] \
    [--inject_negatives] \
    [--max_records
5000] \
    [--skip_parse]( if facts.jsonl
already
exists) \
    [--skip_hermit]( if hermit_labels.jsonl
already
exists)
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_step(label: str, cmd: list):
    print(f"\n{'─'*65}")
    print(f"  {label}")
    print(f"{'─'*65}")
    print("  " + " ".join(str(c) for c in cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\n  Step failed (exit {result.returncode}). Aborting.")
        sys.exit(result.returncode)
    print(f" Done")


def main():
    here = Path(__file__).parent

    parser = argparse.ArgumentParser(
        description="Run the full HermiT labelling pipeline."
    )
    parser.add_argument("--data_dir",  required=True,
                        help="Directory containing University*_*.txt files")
    parser.add_argument("--tbox",      required=True,
                        help="Path to univ-bench.owl")
    parser.add_argument("--hermit",    required=True,
                        help="Path to HermiT.jar")
    parser.add_argument("--out_dir",   default="hermit_labels",
                        help="Output directory (default: hermit_labels/)")
    parser.add_argument("--workers",   type=int, default=4)
    parser.add_argument("--timeout",   type=int, default=30)
    parser.add_argument("--java",      default="java")
    parser.add_argument("--inject_negatives", action="store_true",
                        help="Generate synthetic inconsistent examples")
    parser.add_argument("--max_records", type=int, default=None)
    parser.add_argument("--skip_parse",  action="store_true",
                        help="Skip Step 1 if facts.jsonl already exists")
    parser.add_argument("--skip_hermit", action="store_true",
                        help="Skip Step 2 if hermit_labels.jsonl already exists")
    args = parser.parse_args()

    out_dir      = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    facts_path   = out_dir / "facts.jsonl"
    raw_labels   = out_dir / "hermit_raw.jsonl"
    final_labels = out_dir / "labelled_facts.jsonl"

    # ── Step 1: Parse ─────────────────────────────────────────────────────
    if args.skip_parse and facts_path.exists():
        print(f"  Skipping parse  (using existing {facts_path})")
    else:
        run_step("Step 1 / 3 — Parse LUBM BINARY files", [
            sys.executable, here / "parse_lubm.py",
            "--data_dir", args.data_dir,
            "--out",      facts_path,
            "--verbose",
        ])

    # ── Step 2: HermiT ────────────────────────────────────────────────────
    if args.skip_hermit and raw_labels.exists():
        print(f"  Skipping HermiT (using existing {raw_labels})")
    else:
        hermit_cmd = [
            sys.executable, here / "run_hermit.py",
            "--facts",   facts_path,
            "--tbox",    args.tbox,
            "--hermit",  args.hermit,
            "--out",     raw_labels,
            "--workers", args.workers,
            "--timeout", args.timeout,
            "--java",    args.java,
        ]
        if args.inject_negatives:
            hermit_cmd.append("--inject_negatives")
        if args.max_records:
            hermit_cmd += ["--max_records", args.max_records]
        run_step("Step 2 / 3 — Run HermiT consistency checks", hermit_cmd)

    # ── Step 3: Prepare labels ────────────────────────────────────────────
    run_step("Step 3 / 3 — Prepare labelled facts", [
        sys.executable, here / "prepare_hermit_labels.py",
        "--hermit_labels", raw_labels,
        "--out_dir",       out_dir,
    ])

    print(f"\n{'═'*65}")
    print(f"  HermiT pipeline complete.")
    print(f"  Outputs in: {out_dir.resolve()}/")
    print(f"    labelled_facts.jsonl    <- to ModernBERT pipe")
    print(f"    hermit_benchmark.jsonl  <- final comparison")
    print(f"    label_stats.txt")
    print(f"{'═'*65}\n")


if __name__ == "__main__":
    main()