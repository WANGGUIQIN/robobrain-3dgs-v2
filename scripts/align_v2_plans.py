#!/usr/bin/env python3
"""Align an existing V1 RoboBrain-3DGS processed dataset to V2 plans in place.

Use case: you already have the V1 dataset (rgb_0.png + depth_0.npy + meta.json +
V1-format plan.json) on a target machine and you don't want to re-download the
~9 GB of binary data. The V2 plans bundle (a ~23 MB .tar.zst from the project's
Google Drive) is enough to upgrade the dataset in place.

What this script does for each (dataset, episode) in the V2 plans bundle:
  1. If the V1 dataset has the same episode directory:
       a. If V1 has plan.json and there is no plan_v1.json yet, rename
          plan.json -> plan_v1.json (preserves the original V1 plan as a
          backup, exactly like the manual rename done in the project).
       b. Copy the V2 plan.json from the bundle into the episode dir.
  2. Otherwise warn and skip (a V2 plan exists for an episode the local V1
     dataset doesn't have; nothing we can do — the binaries aren't here).

Idempotent: a second run sees plan.json already in V2 format (`reasoning`
field present) and skips. No double-rename, no data loss.

Usage:
    python scripts/align_v2_plans.py \\
        --v1-root /path/to/v1/data/processed \\
        --plans-source robobrain-3dgs-v2-plans.tar.zst

    # Or use an already-extracted directory:
    python scripts/align_v2_plans.py \\
        --v1-root /path/to/v1/data/processed \\
        --plans-source /path/to/extracted_plans/

    # Preview without writing anything:
    python scripts/align_v2_plans.py --v1-root ... --plans-source ... --dry-run
"""
import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def _extract_archive(archive_path: Path, dest: Path) -> None:
    """Extract a .tar.zst archive. Uses the zstd binary when available
    (fast, multi-threaded); falls back to the `zstandard` Python module."""
    if shutil.which("zstd"):
        with subprocess.Popen(
            ["zstd", "-d", "-c", str(archive_path)],
            stdout=subprocess.PIPE,
        ) as zp:
            subprocess.check_call(
                ["tar", "-xf", "-", "-C", str(dest)],
                stdin=zp.stdout,
            )
            zp.wait()
            if zp.returncode != 0:
                raise RuntimeError(f"zstd exited {zp.returncode}")
    else:
        try:
            import zstandard  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "Neither the `zstd` binary nor the `zstandard` Python module is "
                "available; install one to extract .tar.zst archives."
            ) from e
        with open(archive_path, "rb") as fh:
            with zstandard.ZstdDecompressor().stream_reader(fh) as reader:
                with tarfile.open(fileobj=reader, mode="r|") as tf:
                    tf.extractall(dest)


def _looks_like_v2(plan_path: Path) -> bool:
    """A V2 plan has a non-empty top-level `reasoning` string."""
    try:
        d = json.loads(plan_path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(d.get("reasoning"), str) and bool(d["reasoning"].strip())


def _normalize_rel(rel: Path) -> Path:
    """Drop a leading './' if tar produced relative paths with it."""
    parts = [p for p in rel.parts if p not in (".", "")]
    return Path(*parts) if parts else rel


def main():
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )
    ap.add_argument("--v1-root", type=Path, required=True,
                    help="Path to existing V1 data/processed (mutated in place)")
    ap.add_argument("--plans-source", type=Path, required=True,
                    help=("Either a V2-plans .tar.zst archive OR an "
                          "already-extracted directory containing "
                          "<dataset>/<episode>/plan.json"))
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would change without modifying anything")
    ap.add_argument("--keep-extracted", type=Path, default=None,
                    help=("Optional: extract the archive here and keep it "
                          "(default: temp dir, removed at end)"))
    args = ap.parse_args()

    if not args.v1_root.is_dir():
        sys.exit(f"--v1-root does not exist: {args.v1_root}")

    cleanup_extract = False
    if args.plans_source.is_dir():
        extracted_dir = args.plans_source
    elif (args.plans_source.is_file()
          and args.plans_source.name.endswith(".tar.zst")):
        if args.keep_extracted:
            extracted_dir = args.keep_extracted
            extracted_dir.mkdir(parents=True, exist_ok=True)
        else:
            extracted_dir = Path(tempfile.mkdtemp(prefix="v2_plans_"))
            cleanup_extract = True
        print(f"[extract] {args.plans_source} -> {extracted_dir}")
        if not args.dry_run:
            _extract_archive(args.plans_source, extracted_dir)
        else:
            print("  (dry-run: skipped extraction)")
    else:
        sys.exit(f"--plans-source must be a .tar.zst archive or a directory: "
                 f"{args.plans_source}")

    # Build (relative_path, absolute_source_path_or_None) pairs.
    # In dry-run with an archive, source_path is None (we only count).
    if args.dry_run and args.plans_source.is_file():
        print("[scan] (dry-run) listing archive members ...")
        listing = subprocess.run(
            ["bash", "-c",
             f"zstd -dc {args.plans_source!s} | tar -tf - | grep '/plan.json$'"],
            capture_output=True, text=True,
        )
        rel_paths = [Path(m.strip()) for m in listing.stdout.splitlines()
                     if m.strip()]
        src_pairs = [(_normalize_rel(p), None) for p in rel_paths]
    else:
        print(f"[scan] looking for V2 plan.json under {extracted_dir} ...")
        abs_paths = list(extracted_dir.rglob("episode_*/plan.json"))
        src_pairs = [(_normalize_rel(p.relative_to(extracted_dir)), p)
                     for p in abs_paths]

    print(f"[scan] found {len(src_pairs)} V2 plan files")
    if not src_pairs:
        sys.exit("No V2 plans found in source; nothing to align.")

    n_aligned = 0
    n_already_v2 = 0
    n_missing_ep = 0
    n_backed_up = 0
    n_no_v1_plan = 0  # episode dir exists but had no V1 plan.json (rare)

    for rel, src_plan in src_pairs:
        dst_dir = args.v1_root / rel.parent

        if not dst_dir.is_dir():
            n_missing_ep += 1
            continue

        dst_plan = dst_dir / "plan.json"
        dst_plan_v1 = dst_dir / "plan_v1.json"

        if dst_plan.exists() and _looks_like_v2(dst_plan):
            n_already_v2 += 1
            continue

        if dst_plan.exists():
            if not dst_plan_v1.exists():
                if not args.dry_run:
                    dst_plan.rename(dst_plan_v1)
                n_backed_up += 1
            else:
                # Stale half-aligned state: plan_v1.json already exists but
                # plan.json is still V1. Drop the stale one to let the V2
                # copy proceed cleanly.
                if not args.dry_run:
                    dst_plan.unlink()
        else:
            n_no_v1_plan += 1

        if not args.dry_run:
            assert src_plan is not None, "real run reached dry-run-only branch"
            shutil.copy2(src_plan, dst_plan)
        n_aligned += 1

    print()
    print("==== Summary ====")
    print(f"  aligned (V2 installed)              : {n_aligned}")
    print(f"  backed up V1 -> plan_v1.json       : {n_backed_up}")
    print(f"  already V2 (idempotent skip)        : {n_already_v2}")
    print(f"  source has plan but V1 lacks ep dir : {n_missing_ep}")
    print(f"  ep dir present but no V1 plan.json  : {n_no_v1_plan}")
    if args.dry_run:
        print("  (DRY RUN — no changes were written)")

    if cleanup_extract and not args.keep_extracted and not args.dry_run:
        shutil.rmtree(extracted_dir, ignore_errors=True)
        print(f"[cleanup] removed {extracted_dir}")


if __name__ == "__main__":
    main()
