"""Resolve a platform identifier to one unified app ID and icon path."""


PLATFORMS = {
    "apple-bundle": "bundleId",
    "apple-store": "appleAppStoreId",
    "android": "androidPackageName",
    "harmony": "harmonyBundleName",
    "huawei": "huaweiAppGalleryId",
    "legacy": "legacyId",
    "id": "id",
}


class MappingError(Exception):
    """Base error for a lookup that cannot return an icon."""


class UnknownPlatformError(MappingError):
    """The caller named a platform this table does not support."""


class MissingMappingError(MappingError):
    """No row has this platform identifier."""


class DuplicateMappingError(MappingError):
    """More than one row uses the same platform identifier."""


class MissingImageError(MappingError):
    """The row exists, but the icon file is not in the catalog."""


def _present(value):
    return value is not None and value != ""


def assert_unique_platform_ids(entries):
    """Raise DuplicateMappingError when a non-empty platform ID is reused."""
    seen = {platform: {} for platform in PLATFORMS}
    for entry in entries:
        for platform, field in PLATFORMS.items():
            value = entry.get(field)
            if not _present(value):
                continue
            previous = seen[platform].get(value)
            if previous is not None:
                raise DuplicateMappingError(
                    f"Duplicate mapping: {platform} {value!r} is used by "
                    f"{previous['id']} and {entry['id']}"
                )
            seen[platform][value] = entry
    return seen


def lookup(entries, platform, identifier, root, style=None, assets=None):
    """Map one platform ID to a unified ID and an existing image.

    ``style`` selects a generated icon under ``styles/<style>/<id>.png``.
    Without it, the official icon path on the mapping row is used.
    """
    if platform not in PLATFORMS:
        known = ", ".join(PLATFORMS)
        raise UnknownPlatformError(f"Unknown platform: {platform}. Expected one of: {known}")
    if not _present(identifier):
        raise MissingMappingError(f"Missing mapping: empty {platform} identifier")

    field = PLATFORMS[platform]
    matches = [entry for entry in entries if entry.get(field) == identifier]
    if not matches:
        raise MissingMappingError(f"Missing mapping: no {platform} entry for {identifier!r}")
    if len(matches) > 1:
        ids = ", ".join(entry["id"] for entry in matches)
        raise DuplicateMappingError(
            f"Duplicate mapping: {platform} {identifier!r} matches {ids}"
        )

    entry = matches[0]
    if style:
        path = f"styles/{style}/{entry['id']}.png"
        if assets is not None and not any(asset.get("path") == path for asset in assets):
            raise MissingImageError(f"Missing image: {path} is not a published asset")
        if not (root / path).is_file():
            raise MissingImageError(f"Missing image: {path}")
    else:
        path = entry.get("iconPath")
        if not path:
            raise MissingImageError(f"Missing image: {entry['id']} has no official icon")
        if not (root / path).is_file():
            raise MissingImageError(f"Missing image: {path}")

    return {
        "found": True,
        "id": entry["id"],
        "legacyId": entry.get("legacyId"),
        "name": entry.get("name"),
        "iconAvailable": True,
        "iconPath": path,
    }
