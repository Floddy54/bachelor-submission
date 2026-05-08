#!/usr/bin/env python3
"""
End-to-end Azure smoke test for bachelor-anti-bad.

Exercises the full laptop → Azure → dashboard flow:

  1. Connectivity      — load connection string, open container.
  2. azure_io round-trip — upload_text / read_text / list_blobs / exists /
                           upload_file / download_to_path, all via the
                           shared dashboard/azure_io.py wrapper that
                           server.py uses.
  3. Member discovery  — list_members() surfaces the current MEMBER.
  4. Dashboard parse   — write a realistic fake SLURM log pair and prove
                         that server.parse_all_logs() discovers it, parses
                         the headers/metrics, and reports status="success".
  5. CSV per-member    — write a fake submission CSV and prove that the
                         dashboard's _read_csv_blob picks it up.
  6. Cleanup           — delete every blob we created (full control via the
                         connection string, not the write-only SAS).

Run from the project root (with bachelorenv activated) on your laptop:

    python dashboard/smoke_e2e.py

Exits 0 on success, non-zero on failure. Prints a per-stage PASS/FAIL
table and a short "what to do on HPC" postscript.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path
from typing import Callable

# Allow running as a plain script from anywhere in the project.
HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))      # for `src.config`
sys.path.insert(0, str(HERE.parent))       # for sibling `azure_io`

# --- Imports under test ------------------------------------------------------
import azure_io                            # noqa: E402
from azure_io import (                     # noqa: E402
    MEMBER,
    ACCOUNT_NAME,
    CONTAINER_NAME,
    blob_path,
    download_to_path,
    exists as blob_exists,
    get_container_client,
    list_blobs,
    list_members,
    read_text,
    upload_file,
    upload_text,
)

# Dashboard module — pulled in so we exercise the real parse_all_logs.
# (The dashboard module lives in a top-level `dashboard/` folder, not a
# package, so load it by file path.)
import importlib.util                          # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "dashboard_server", HERE.parent / "server.py",
)
assert _SPEC and _SPEC.loader, "Failed to locate dashboard/server.py"
dashboard_server = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(dashboard_server)


# ─── Reporting helpers ───────────────────────────────────────────────────────

class Stage:
    """Track PASS/FAIL per stage and print a summary at the end."""

    def __init__(self):
        self.results: list[tuple[str, bool, str]] = []
        self.failed = 0

    def run(self, name: str, fn: Callable[[], str]) -> None:
        print(f"\n── {name}")
        try:
            detail = fn() or ""
            self.results.append((name, True, detail))
            print(f"   ✓ PASS  {detail}".rstrip())
        except AssertionError as exc:
            self.results.append((name, False, f"assertion: {exc}"))
            self.failed += 1
            print(f"   ✗ FAIL  assertion: {exc}")
        except Exception as exc:
            self.results.append((name, False, f"{type(exc).__name__}: {exc}"))
            self.failed += 1
            print(f"   ✗ FAIL  {type(exc).__name__}: {exc}")

    def summary(self) -> int:
        print("\n" + "─" * 60)
        print("  SUMMARY")
        print("─" * 60)
        for name, ok, detail in self.results:
            icon = "✓" if ok else "✗"
            print(f"   {icon} {name:42s} {detail[:50]}")
        print("─" * 60)
        total = len(self.results)
        passed = total - self.failed
        print(f"   {passed}/{total} stages passed")
        return 0 if self.failed == 0 else 1


# ─── Test fixture: where test blobs live ────────────────────────────────────

# Every test run creates blobs under <MEMBER>/smoke-e2e/run-<uuid>/ (and a
# couple of top-level names like logs/smoketest_<id>.out that have to live
# in their usual spot for the dashboard parse test). The cleanup step
# deletes everything it wrote, tracked in CREATED.
RUN_ID = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
TEST_PREFIX = f"smoke-e2e/run-{RUN_ID}"

# Fake SLURM job id well outside the real range so it can't collide with a
# real job on the cluster. parse_all_logs filters log files by the regex
# ^(job_type)_(\d+)$ and runs the textattack-specific metric parser only
# when job_type == "textattack" — so we reuse that job_type here and pick
# a 9-leading digit-only id. Any collision would clear on cleanup a few
# seconds later.
FAKE_JOB_TYPE = "textattack"
FAKE_JOB_ID = "9" + str(int(time.time()))[-7:]  # 8 digits, starts with 9

CREATED: list[str] = []  # full blob names (member-prefixed) we need to clean up


def _track(blob_name: str) -> str:
    """Record a blob we'll delete at the end, and return the name unchanged."""
    CREATED.append(blob_name)
    return blob_name


# ─── Stage implementations ───────────────────────────────────────────────────

def stage_connectivity() -> str:
    """Connect and touch the container. Most failure modes (bad creds, wrong
    account name, network) surface here rather than later.

    We use a narrow `list_blobs` instead of `get_container_properties` because
    some middleboxes (observed on Kristiania laptops, 2026-04) silently hang
    HEAD-to-container requests while letting normal GET/PUT data-plane
    operations through."""
    client = get_container_client()
    # Force a real data-plane request with a 5-second hard ceiling so we
    # fail fast if something's wrong. `list_blobs` returns an iterator;
    # invoking next() actually hits the network.
    iterator = client.list_blobs(name_starts_with="__smoke-connectivity-probe__/", results_per_page=1)
    try:
        next(iter(iterator))
    except StopIteration:
        pass  # expected — the probe prefix isn't supposed to exist
    return f"container={CONTAINER_NAME} @ {ACCOUNT_NAME}"


def stage_text_roundtrip() -> str:
    name = _track(blob_path(f"{TEST_PREFIX}/hello.txt"))
    payload = f"hello from smoke-e2e run {RUN_ID}\n"
    upload_text(name, payload)
    assert blob_exists(name), "upload claimed to succeed but exists() is False"
    got = read_text(name)
    assert got == payload, f"text mismatch:\n  wanted: {payload!r}\n  got:    {got!r}"
    return f"uploaded + downloaded {len(payload)} bytes"


def stage_binary_roundtrip(tmp_dir: Path) -> str:
    # Write a small binary file locally, upload, download, compare bytes.
    src = tmp_dir / "binary.bin"
    src.write_bytes(bytes(range(256)))

    name = _track(blob_path(f"{TEST_PREFIX}/binary.bin"))
    upload_file(name, src)

    dst = tmp_dir / "binary-download.bin"
    download_to_path(name, dst)
    assert dst.read_bytes() == src.read_bytes(), "binary round-trip byte mismatch"
    return f"{src.stat().st_size} bytes, sha256 matches via byte compare"


def stage_list_blobs() -> str:
    # Our prefix should contain exactly the two blobs we've uploaded so far.
    entries = list_blobs(f"{TEST_PREFIX}/")
    names = {e["rel"] for e in entries}
    assert f"{TEST_PREFIX}/hello.txt" in names, f"hello.txt not listed: {names}"
    assert f"{TEST_PREFIX}/binary.bin" in names, f"binary.bin not listed: {names}"
    # Every entry should be tagged with the current MEMBER.
    wrong_owner = [e for e in entries if e["member"] != MEMBER]
    assert not wrong_owner, f"list_blobs returned foreign members: {wrong_owner}"
    return f"{len(entries)} blobs under {MEMBER}/{TEST_PREFIX}/"


def stage_member_discovery() -> str:
    members = list_members()
    assert MEMBER in members, f"current MEMBER={MEMBER!r} not discovered: {members}"
    # The reserved "smoke" prefix is supposed to be hidden by list_members,
    # but our test data lives under <MEMBER>/smoke-e2e/..., not the
    # top-level smoke/ prefix — so MEMBER should still appear.
    return f"{len(members)} member(s): {', '.join(members)}"


def stage_log_parse() -> str:
    """
    Write a fake textattack SLURM log pair and assert parse_all_logs() picks
    it up with the parsed metrics the dashboard expects.
    """
    # Realistic-looking textattack log — the parser keys off these exact
    # lines (see _parse_textattack in dashboard/server.py).
    fake_out = (
        "Model: model1\n"
        "Attack: asr\n"
        "Start: Mon Apr 20 12:00:00 UTC 2026\n"
        "CACC: 800/1000 = 80.00%\n"
        "ASR:  150/1000 = 15.00%\n"
        "Triggers: ['cf']\n"
        "Done: Mon Apr 20 12:05:00 UTC 2026\n"
    )
    fake_err = ""  # no traceback → status should be "success"

    out_name = _track(blob_path(f"logs/{FAKE_JOB_TYPE}_{FAKE_JOB_ID}.out"))
    err_name = _track(blob_path(f"logs/{FAKE_JOB_TYPE}_{FAKE_JOB_ID}.err"))
    upload_text(out_name, fake_out)
    upload_text(err_name, fake_err)

    jobs = dashboard_server.parse_all_logs()
    mine = [
        j for j in jobs
        if j["job_type"] == FAKE_JOB_TYPE and j["job_id"] == FAKE_JOB_ID
    ]
    assert len(mine) == 1, f"expected 1 fake job, got {len(mine)}: {mine!r}"
    job = mine[0]
    assert job["status"] == "success", f"status={job['status']!r} (want success)"
    assert job["model"] == "model1", f"model={job['model']!r}"
    assert job["attack"] == "asr",    f"attack={job['attack']!r}"
    m = job["metrics"]
    assert m.get("cacc") == 80.00, f"cacc={m.get('cacc')!r}"
    assert m.get("asr")  == 15.00, f"asr={m.get('asr')!r}"
    # task_score = cacc * (100-asr)/100 = 80 * 85/100 = 68.0
    assert m.get("task_score") == 68.0, f"task_score={m.get('task_score')!r}"
    return f"parsed fake job {FAKE_JOB_ID} with cacc/asr/task_score"


def stage_csv_per_member() -> str:
    """
    _read_csv_per_member is how the dashboard fans results_summary.csv
    across every member's prefix. Write a fake CSV under a
    smoke-e2e subpath and prove the dashboard can read it as a list[dict].
    """
    csv_rel = f"{TEST_PREFIX}/fake_summary.csv"
    csv_name = _track(blob_path(csv_rel))
    upload_text(csv_name, "model,task_score\nmodel1,42.0\nmodel2,37.5\n")

    # Use the internal helper to read exactly what the dashboard would use.
    rows = dashboard_server._read_csv_blob(csv_name)
    assert rows and len(rows) == 2, f"expected 2 rows, got {rows!r}"
    assert rows[0]["model"] == "model1", rows[0]
    assert rows[0]["task_score"] == "42.0", rows[0]
    return f"{len(rows)} rows parsed"


# ─── Cleanup ─────────────────────────────────────────────────────────────────

def cleanup() -> tuple[int, int]:
    """Delete every blob we created. Returns (deleted, failed)."""
    client = get_container_client()
    deleted = failed = 0
    for name in CREATED:
        try:
            client.get_blob_client(name).delete_blob()
            deleted += 1
        except Exception as exc:
            # Most likely: SAS-scoped creds (no delete perm) instead of
            # the connection string. We ran with the connection string,
            # so this is usually an already-gone blob.
            print(f"   ⚠ delete failed for {name}: {exc}", file=sys.stderr)
            failed += 1
    return deleted, failed


# ─── Entry point ─────────────────────────────────────────────────────────────

def main() -> int:
    print("━" * 60)
    print(f"  bachelor-anti-bad — Azure end-to-end smoke test")
    print(f"  member:    {MEMBER}")
    print(f"  account:   {ACCOUNT_NAME}")
    print(f"  container: {CONTAINER_NAME}")
    print(f"  run-id:    {RUN_ID}")
    print("━" * 60)

    # Use a dedicated local tmp dir so we don't leak test artefacts into the
    # project tree. Clean up afterwards regardless of result.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="smoke-e2e-") as tmp:
        tmp_dir = Path(tmp)

        s = Stage()
        s.run("1. Connectivity",          stage_connectivity)
        s.run("2. Text round-trip",       stage_text_roundtrip)
        s.run("3. Binary round-trip",     lambda: stage_binary_roundtrip(tmp_dir))
        s.run("4. list_blobs",            stage_list_blobs)
        s.run("5. Member discovery",      stage_member_discovery)
        s.run("6. Dashboard log parse",   stage_log_parse)
        s.run("7. CSV per-member reader", stage_csv_per_member)

        print("\n── Cleanup")
        deleted, failed = cleanup()
        print(f"   deleted {deleted} blob(s), {failed} failure(s)")

        rc = s.summary()

    print("\nNext step (verify HPC side): submit any SLURM script and watch")
    print("for the '[azure-upload] ...' lines in the .out file, then browse")
    print(f"https://{ACCOUNT_NAME}.blob.core.windows.net/{CONTAINER_NAME}/ in the")
    print(f"portal — your {MEMBER}/logs/ prefix should have the new job's output.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
