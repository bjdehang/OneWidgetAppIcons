"""Unified app IDs derived from Apple bundle IDs."""

import re


def unified_id_from_bundle(bundle_id):
    """Lowercase a bundle ID and replace dots and spaces with underscores.

    Other characters, including hyphens, stay as they are. ``app.imone.OneWidget``
    becomes ``app_imone_onewidget``.
    """
    if not isinstance(bundle_id, str) or not bundle_id or bundle_id.strip() != bundle_id:
        raise ValueError(f"Invalid bundle ID: {bundle_id!r}")
    normalized = bundle_id.lower().replace(".", "_").replace(" ", "_")
    if not re.fullmatch(r"[a-z0-9_-]+", normalized):
        raise ValueError(f"Bundle ID cannot form a unified ID: {bundle_id!r}")
    return normalized


def legacy_id(app_store_id):
    """Return the previous ``app-<App Store ID>`` alias."""
    text = str(app_store_id)
    if not text.isdecimal():
        raise ValueError(f"Invalid App Store ID: {app_store_id!r}")
    return f"app-{text}"
