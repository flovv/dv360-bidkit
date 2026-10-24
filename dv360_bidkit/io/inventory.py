"""Customer inventory policy loader, normalizer, and conflict validator.

Parses customer-supplied CSV or JSON domain/site lists, enforces strict hostname
normalization and boundary-aware parent domain matching, and detects policy conflicts.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from dv360_bidkit.contracts.exceptions import InventoryPolicyError
from dv360_bidkit.contracts.schemas import (
    InventoryAction,
    InventoryEntityType,
    InventoryPolicy,
    InventoryPolicyConfig,
    InventoryPolicyEntry,
)


def normalize_domain(domain_str: str, *, strip_www: bool = True) -> str:
    """Normalizes a hostname string according to RFC standards.

    Strips schemes/ports, converts IDNA to punycode / lowercase,
    and rejects URLs containing paths, queries, or fragments.
    """
    raw = domain_str.strip()
    if not raw:
        raise InventoryPolicyError("Domain value cannot be empty.")

    # Reject full URLs containing schemes or paths
    if "://" in raw:
        parsed = urlparse(raw)
        if parsed.path and parsed.path != "/":
            raise InventoryPolicyError(f"Domain '{raw}' contains URL paths, which are invalid in inventory policies.")
        raw = parsed.netloc or parsed.path

    if "/" in raw:
        parts = raw.split("/", 1)
        if parts[1].strip():
            raise InventoryPolicyError(f"Domain '{raw}' contains path '{parts[1]}'. Only hostnames are accepted.")
        raw = parts[0]

    # Strip port if present
    if ":" in raw:
        raw = raw.split(":", 1)[0]

    # Strip trailing dot
    raw = raw.rstrip(".")

    # Convert IDNA (internationalized domain names) to ascii
    try:
        raw = raw.encode("idna").decode("ascii").lower()
    except Exception as exc:
        raise InventoryPolicyError(f"Invalid domain hostname '{domain_str}': {exc}") from exc

    # Optional www strip
    if strip_www and raw.startswith("www."):
        raw = raw[4:]

    # Basic hostname regex check
    hostname_regex = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$")
    if not hostname_regex.match(raw):
        raise InventoryPolicyError(f"Malformed domain hostname: '{raw}'")

    return raw


def is_entry_expired(
    entry: InventoryPolicyEntry,
    *,
    reference_date: str | None = None,
) -> bool:
    """Checks whether an inventory policy entry has expired.

    Compares ISO-8601 date strings (YYYY-MM-DD) against `reference_date` (if supplied)
    or the current UTC date.
    """
    if not entry.expiry or not str(entry.expiry).strip():
        return False
    exp_str = str(entry.expiry).strip()[:10]
    if reference_date is not None and str(reference_date).strip():
        ref_str = str(reference_date).strip()[:10]
    else:
        ref_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return exp_str < ref_str


def extract_targeting_block_requests(policy: InventoryPolicy) -> list[InventoryPolicyEntry]:
    """Extracts active `targeting_block_request` entries from an InventoryPolicy.

    Per Spec Section 5.1 & 5.2, custom bidding scripts do not perform ad-serving blocks;
    these entries are exported as an explicit DV360 targeting block checklist artifact.
    """
    return [
        entry
        for entry in policy.entries
        if entry.action == InventoryAction.TARGETING_BLOCK_REQUEST and not is_entry_expired(entry)
    ]


def match_inventory_entity(
    target_value: str,
    target_type: InventoryEntityType,
    policy: InventoryPolicy,
    *,
    reference_date: str | None = None,
) -> InventoryPolicyEntry | None:
    """Matches a target entity (domain or site_id) against an InventoryPolicy.

    Respects action precedence:
    EXCLUDE_FROM_TRAINING > SET_SCORE > ANNOTATE / TARGETING_BLOCK_REQUEST.
    Skips expired entries.
    """
    if target_type == InventoryEntityType.DOMAIN:
        try:
            norm_target = normalize_domain(target_value, strip_www=policy.config.strip_www)
        except Exception:
            return None
    else:
        norm_target = target_value.strip()

    matched_entries: list[InventoryPolicyEntry] = []

    for entry in policy.entries:
        if entry.entity_type != target_type:
            continue
        if is_entry_expired(entry, reference_date=reference_date):
            continue

        if target_type == InventoryEntityType.DOMAIN:
            entry_val = entry.entity_value
            if norm_target == entry_val:
                matched_entries.append(entry)
            elif policy.config.allow_subdomains:
                # Boundary-aware check: norm_target must end with .entry_val
                if norm_target.endswith("." + entry_val):
                    matched_entries.append(entry)
        else:
            if norm_target == entry.entity_value:
                matched_entries.append(entry)

    if not matched_entries:
        return None

    # Sort by precedence: EXCLUDE_FROM_TRAINING > SET_SCORE > TARGETING_BLOCK_REQUEST > ANNOTATE
    precedence = {
        InventoryAction.EXCLUDE_FROM_TRAINING: 0,
        InventoryAction.SET_SCORE: 1,
        InventoryAction.TARGETING_BLOCK_REQUEST: 2,
        InventoryAction.ANNOTATE: 3,
    }
    matched_entries.sort(key=lambda e: precedence.get(e.action, 99))
    return matched_entries[0]


def load_inventory_policy(
    path: str | Path,
    *,
    config: InventoryPolicyConfig | None = None,
    reference_date: str | None = None,
) -> InventoryPolicy:
    """Loads and validates a customer inventory policy CSV or JSON file.

    Parameters
    ----------
    path : str | Path
        Path to inventory policy file.
    config : InventoryPolicyConfig | None
        Configuration options for domain matching and fallback actions.
    reference_date : str | None
        Optional ISO date (YYYY-MM-DD) used to filter out expired policy entries.

    Returns
    -------
    InventoryPolicy
        Normalized and validated policy entries.
    """
    config = config or InventoryPolicyConfig()
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Inventory policy file not found: {path}")

    raw_entries: list[dict[str, Any]] = []

    if path_obj.suffix.lower() == ".json":
        with open(path_obj, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                raw_entries = data
            elif isinstance(data, dict) and "entries" in data:
                raw_entries = data["entries"]
                if "config" in data and isinstance(data["config"], dict):
                    config = InventoryPolicyConfig(**data["config"])
            else:
                raise InventoryPolicyError("JSON policy must be a list or dict with 'entries' key.")
    else:
        # Default CSV
        with open(path_obj, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_entries.append(row)

    entries: list[InventoryPolicyEntry] = []
    seen_entities: dict[tuple[str, str], list[InventoryPolicyEntry]] = {}
    expired_skipped = 0

    for row in raw_entries:
        entity_type_raw = str(row.get("entity_type", "domain")).strip().lower()
        entity_type = (
            InventoryEntityType.DOMAIN if entity_type_raw == "domain" else InventoryEntityType.SITE_ID
        )

        val = str(row.get("entity_value", "")).strip()
        if entity_type == InventoryEntityType.DOMAIN:
            val = normalize_domain(val, strip_www=config.strip_www)

        action_raw = str(row.get("action", "annotate")).strip().lower()
        try:
            action = InventoryAction(action_raw)
        except ValueError:
            raise InventoryPolicyError(f"Unsupported inventory action '{action_raw}'.")

        source = str(row.get("source", "customer_list")).strip()
        as_of = str(row.get("as_of", "2026-01-01")).strip()
        label = row.get("label")
        expiry = str(row["expiry"]).strip() if row.get("expiry") not in (None, "") else None
        score_val = float(row["score"]) if row.get("score") not in (None, "") else None
        notes = row.get("notes")

        entry = InventoryPolicyEntry(
            entity_type=entity_type,
            entity_value=val,
            action=action,
            source=source,
            as_of=as_of,
            label=label,
            expiry=expiry,
            score=score_val,
            notes=notes,
        )

        if is_entry_expired(entry, reference_date=reference_date):
            expired_skipped += 1
            continue

        key = (entity_type.value, val)
        if key not in seen_entities:
            seen_entities[key] = []
        seen_entities[key].append(entry)
        entries.append(entry)

    # Validate conflicts: check if the same entity has contradictory actions
    for key, item_list in seen_entities.items():
        if len(item_list) > 1:
            actions = {e.action for e in item_list}
            scores = {e.score for e in item_list if e.score is not None}
            # Contradictory if conflicting score overrides
            if len(scores) > 1:
                raise InventoryPolicyError(
                    f"Conflicting score overrides for entity {key}: scores {scores}"
                )
            # Contradictory if both exclude_from_training and set_score
            if InventoryAction.EXCLUDE_FROM_TRAINING in actions and InventoryAction.SET_SCORE in actions:
                raise InventoryPolicyError(
                    f"Conflicting policy actions for entity {key}: cannot have both 'set_score' and 'exclude_from_training'."
                )

    return InventoryPolicy(
        entries=entries,
        config=config,
        normalization_metadata={
            "total_entries": len(entries),
            "unique_entities": len(seen_entities),
            "expired_entries_skipped": expired_skipped,
            "strip_www": config.strip_www,
            "allow_subdomains": config.allow_subdomains,
        },
    )
