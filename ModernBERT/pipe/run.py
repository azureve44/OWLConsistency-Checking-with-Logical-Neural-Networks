"""
  1 prepare_modernbert_data.py   labelled_facts.jsonl → JSONL splits
  2 composer main.py             train ModernBERT
  3 evaluate_vs_hermit.py        compare to HermiT benchmark

Requires the HermiT pipeline to have already produced:
  hermit_labels/labelled_facts.jsonl
  hermit_labels/hermit_benchmark.jsonl

Usage
──────
  python modernbert_pipeline/run.py \
      --labelled_facts hermit_labels/labelled_facts.jsonl \
      --benchmark      hermit_labels/hermit_benchmark.jsonl \
      --modernbert_dir /path/to/ModernBERT/repo \
      --out_dir        modernbert_out/ \
      [--skip_prep]          skip Step 1 if splits already exist
      [--skip_train]         skip Step 2 (e.g. evaluate a pre-existing checkpoint)
      [--checkpoint path]    path to checkpoint for evaluation (auto-detected if absent)
      [--device cuda]
      [--batch_size 64]
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
        print(f"\n Step failed (exit {result.returncode}). Aborting.")
        sys.exit(result.returncode)
    print(f" Done")


def find_best_checkpoint(ckpt_dir: Path) -> Path:
    """
Return
the
most
recently
modified
checkpoint in ckpt_dir.
"""
    candidates = list(ckpt_dir.glob("**/*.pt")) + list(ckpt_dir.glob("**/*.ckpt"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def main():
    here = Path(__file__).parent

    parser = argparse.ArgumentParser(
        description="Run the full ModernBERT training + evaluation pipeline."
    )
    parser.add_argument("--labelled_facts", required=True,
                        help="hermit_labels/labelled_facts.jsonl")
    parser.add_argument("--benchmark",      required=True,
                        help="hermit_labels/hermit_benchmark.jsonl")
    parser.add_argument("--modernbert_dir", required=True,
                        help="Path to the cloned ModernBERT repo (contains main.py)")
    parser.add_argument("--out_dir",   default="modernbert_out",
                        help="Root output directory (default: modernbert_out/)")
    parser.add_argument("--yaml",      default=None,
                        help="Composer YAML to use (default: yamls/lubm_consistency.yaml)")
    parser.add_argument("--checkpoint", default=None,
                        help="Checkpoint path for evaluation (auto-detected if omitted)")
    parser.add_argument("--device",     default="cuda")
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--max_tokens", type=int, default=512)
    parser.add_argument("--seed",       type=int, default=42)
    parser.add_argument("--skip_prep",  action="store_true",
                        help="Skip Step 1 if modernbert_data/ splits already exist")
    parser.add_argument("--skip_train", action="store_true",
                        help="Skip Step 2 (go straight to evaluation)")
    args = parser.parse_args()

    out_dir      = Path(args.out_dir)
    data_dir     = out_dir / "modernbert_data"
    ckpt_dir     = out_dir / "checkpoints" / "lubm_consistency"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Prepare data ──────────────────────────────────────────────
    if args.skip_prep and (data_dir / "train.jsonl").exists():
        print(f"  Skipping data prep (using existing splits in {data_dir})")
    else:
        run_step("Step 1 / 3 — Prepare ModernBERT data splits", [
            sys.executable, here / "prepare_modernbert_data.py",
            "--labelled_facts", args.labelled_facts,
            "--out_dir",        data_dir,
            "--max_tokens",     args.max_tokens,
            "--seed",           args.seed,
        ])

    # ── Patch YAML with correct absolute paths ─────────────────────────────
    yaml_src = Path(args.yaml) if args.yaml else here / "yamls" / "lubm_consistency.yaml"
    yaml_out  = out_dir / "lubm_consistency_run.yaml"
    yaml_text = yaml_src.read_text()
    yaml_text = yaml_text.replace("dataset/train.jsonl", str(data_dir / "train.jsonl"))
    yaml_text = yaml_text.replace("dataset/val.jsonl",   str(data_dir / "val.jsonl"))
    yaml_text = yaml_text.replace("checkpoints/lubm_consistency", str(ckpt_dir))
    yaml_out.write_text(yaml_text)

    # ── Step 2: Train ─────────────────────────────────────────────────────
    if args.skip_train:
        print(f"  Skipping training")
    else:
        modernbert_main = Path(args.modernbert_dir) / "main.py"
        if not modernbert_main.exists():
            print(f"\n✗  ModernBERT main.py not found at {modernbert_main}")
            sys.exit(1)

        run_step("Step 2 / 3 — Train ModernBERT (composer)", [
            "composer", str(modernbert_main), str(yaml_out),
        ])

    # ── Step 3: Evaluate ──────────────────────────────────────────────────
    ckpt = args.checkpoint
    if ckpt is None:
        ckpt = find_best_checkpoint(ckpt_dir)
    if ckpt is None:
        print(f"\n⚠  No checkpoint found in {ckpt_dir}. Skipping evaluation.")
        print(f"   Re-run with --checkpoint <path> once training completes.")
    else:
        run_step("Step 3 / 3 — Evaluate vs HermiT benchmark", [
            sys.executable, here / "evaluate_vs_hermit.py",
            "--checkpoint",  ckpt,
            "--test",        data_dir / "test.jsonl",
            "--benchmark",   args.benchmark,
            "--device",      args.device,
            "--batch_size",  args.batch_size,
        ])

    print(f"\n{'═'*65}")
    print(f"  ModernBERT pipeline complete.")
    print(f"  Outputs in: {out_dir.resolve()}/")
    print(f"    modernbert_data/    training splits")
    print(f"    checkpoints/        model checkpoints")
    print(f"    tensorboard_logs/   training curves")
    print(f"{'═'*65}\n")


if __name__ == "__main__":
    main()