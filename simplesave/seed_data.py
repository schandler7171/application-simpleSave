"""One-time seeding of the bundled sample snippets on first launch."""
from __future__ import annotations

from simplesave import config, io_formats
from simplesave.db import Database


def seed_sample_snippets_if_needed(db: Database, prefs: dict) -> int:
    """Import the bundled sample-snippets/*.csv exactly once per install.

    Controlled by prefs["seeded_sample_snippets"] rather than "is the
    database empty" so that a user who deletes the samples later doesn't
    get them silently re-added on next launch. Mutates and saves `prefs`
    on success. Returns the number of snippets created (0 if already
    seeded, the folder is missing, or nothing was found).
    """
    if prefs.get("seeded_sample_snippets"):
        return 0

    folder = config.resource_path("sample-snippets")
    if not folder.is_dir():
        return 0

    total_created = 0
    for csv_path in sorted(folder.glob("*.csv")):
        result = io_formats.import_csv(db, csv_path)
        total_created += result.created

    prefs["seeded_sample_snippets"] = True
    config.save_prefs(prefs)
    return total_created
