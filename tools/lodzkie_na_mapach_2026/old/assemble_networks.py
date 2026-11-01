"""E5 prerequisite -- assemble work/networks/<name>/gtfs/ from config.py.

Replaces the one-off `cp` commands used in the first run (2026-09-13) with a
script, so a re-run for a different date/feed-set is a code change here,
not a remembered shell history. Pure file I/O, no QGIS/Java needed.

NETWORK_SPEC below is the single source of truth for "which feed goes in
which network folder" -- it existed only as ad-hoc bash commands before.
Edit this dict (not work/networks/ by hand) when the feed set changes.
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as C

RAW = C.WORK / "gtfs_raw"
RAW_DATED = RAW / C.ANALYSIS_DATE  # everything downloaded via inventory_gtfs.download_feed

# name -> {gtfs_key_in_folder: source_path}
# Two kinds of source: (a) GTFS_FEEDS keys, downloaded live/rolling by
# inventory_gtfs.py and cached under RAW_DATED (re-downloads automatically
# when ANALYSIS_DATE changes -- see download_feed's docstring); (b) pinned
# per-date release filenames (Lodz static+P50/P85 from the gtfs-dashboard
# manifest), fetched once by hand into RAW directly, already date-qualified
# by their own filename. See config.py's NETWORKS_DIR comment block for why
# aleksandrow_lodzki and polish_trains are excluded, and why lka_train.zip
# (not polish_trains.zip) is the ZDiT/LKA feed used for both Lodz variants.
#
# To reproduce for a DIFFERENT date: change config.ANALYSIS_DATE, then
# replace the two "lodz_static_gtfs_<date>..."/"lodz_realized_<date>..."
# paths below with that date's pinned release (or, if no pinned release
# exists for that date/city, point at the live GTFS_FEEDS download instead
# and accept it is NOT guaranteed to match what ran on that historical day
# -- see REPRODUCIBILITY.md).
NETWORK_SPEC = {
    "net_woj_static": {
        "lodz.zip": RAW / "lodz_static_gtfs_2026-09-10.zip",
        "lka_bus.zip": RAW_DATED / "lka_bus.zip",
        "lka_train.zip": RAW_DATED / "lka_train.zip",
        "kutno.zip": RAW_DATED / "kutno.zip",
        "opoczno_mpk.zip": RAW_DATED / "opoczno_mpk.zip",
        "opoczno_pks.zip": RAW_DATED / "opoczno_pks.zip",
        "rozprza.zip": RAW_DATED / "rozprza.zip",
        "tomaszow_mazowiecki.zip": RAW_DATED / "tomaszow_mazowiecki.zip",
    },
    "net_woj_lodzrt": {
        "lodz.zip": RAW / "lodz_realized_2026-09-10_p50.zip",
        "lka_bus.zip": RAW_DATED / "lka_bus.zip",
        "lka_train.zip": RAW_DATED / "lka_train.zip",
        "kutno.zip": RAW_DATED / "kutno.zip",
        "opoczno_mpk.zip": RAW_DATED / "opoczno_mpk.zip",
        "opoczno_pks.zip": RAW_DATED / "opoczno_pks.zip",
        "rozprza.zip": RAW_DATED / "rozprza.zip",
        "tomaszow_mazowiecki.zip": RAW_DATED / "tomaszow_mazowiecki.zip",
    },
    "net_lodz_static": {
        "lodz.zip": RAW / "lodz_static_gtfs_2026-09-10.zip",
        "lka_train.zip": RAW_DATED / "lka_train.zip",
    },
    "net_lodz_p50": {
        "lodz.zip": RAW / "lodz_realized_2026-09-10_p50.zip",
        "lka_train.zip": RAW_DATED / "lka_train.zip",
    },
    # 3-day robustness check for the uniform-negative-delta finding
    # (MULTIDAY_LODZ_NOTES.md) -- static schedule confirmed byte-identical
    # across 09-08/09-09/09-10, so only new realized-day networks are needed;
    # net_lodz_static is reused unchanged as the static side for all 3 days.
    "net_lodz_p50_2026-09-08": {
        "lodz.zip": RAW / "lodz_realized_2026-09-08_p50.zip",
        "lka_train.zip": RAW / "2026-09-10" / "lka_train.zip",
    },
    "net_lodz_p50_2026-09-09": {
        "lodz.zip": RAW / "lodz_realized_2026-09-09_p50.zip",
        "lka_train.zip": RAW / "2026-09-10" / "lka_train.zip",
    },
    # Vacation-vs-school-term robustness check (Michal, 2026-09-14): is the
    # uniform negative delta a September/return-to-school artifact, or a
    # standing Lodz characteristic? Static feed confirmed byte-identical
    # (sha256 e2269d6b...) across all 4 August weekdays below -- edition
    # "11484_11486_11488_11489", feed_start_date 20260810, DISTINCT from
    # September's "11499_11500" edition (feed_start_date 20260901, the actual
    # school-year timetable). 2026-08-12 checked and EXCLUDED: it is an
    # earlier, different edition ("11484_11486", published 08-12 morning,
    # superseded same week) -- mixing it with 08-13/14/17/18 would confound
    # the comparison with an unrelated mid-vacation timetable amendment, not
    # the wakacje-vs-rok-szkolny effect being tested.
    "net_lodz_static_2026-08": {
        "lodz.zip": RAW / "lodz_static_gtfs_2026-08-13.zip",
        "lka_train.zip": RAW / "2026-09-10" / "lka_train.zip",
    },
    "net_lodz_p50_2026-08-13": {
        "lodz.zip": RAW / "lodz_realized_2026-08-13_p50.zip",
        "lka_train.zip": RAW / "2026-09-10" / "lka_train.zip",
    },
    "net_lodz_p50_2026-08-14": {
        "lodz.zip": RAW / "lodz_realized_2026-08-14_p50.zip",
        "lka_train.zip": RAW / "2026-09-10" / "lka_train.zip",
    },
    "net_lodz_p50_2026-08-17": {
        "lodz.zip": RAW / "lodz_realized_2026-08-17_p50.zip",
        "lka_train.zip": RAW / "2026-09-10" / "lka_train.zip",
    },
    "net_lodz_p50_2026-08-18": {
        "lodz.zip": RAW / "lodz_realized_2026-08-18_p50.zip",
        "lka_train.zip": RAW / "2026-09-10" / "lka_train.zip",
    },
}


def assemble(force=False):
    for net_name, files in NETWORK_SPEC.items():
        gtfs_dir = C.NETWORKS_DIR / net_name / "gtfs"
        gtfs_dir.mkdir(parents=True, exist_ok=True)
        if force:
            for old in gtfs_dir.glob("*.zip"):
                old.unlink()
        for dest_name, src in files.items():
            dest = gtfs_dir / dest_name
            if not src.exists():
                raise FileNotFoundError(
                    f"{net_name}: source {src} not found -- run inventory_gtfs.py "
                    f"(or re-download the pinned per-date release) first"
                )
            if dest.exists() and not force:
                continue
            shutil.copy2(src, dest)
        print(f"{net_name}: {len(list(gtfs_dir.glob('*.zip')))} feed(s) in {gtfs_dir}")


if __name__ == "__main__":
    assemble(force="--force" in sys.argv)
