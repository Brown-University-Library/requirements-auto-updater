"""
Helpers for classifying `uv sync --dry-run --output-format json` output.
"""

import json
from typing import Any, TypedDict


class DryRunClassification(TypedDict):
    """
    Structured result describing whether uv dry-run output indicates a real update.
    """

    has_pending_change: bool
    is_substantive: bool
    is_exclude_newer_only: bool
    summary: str
    sync_action: str
    lock_action: str


def classify_dry_run_output(output_text: str) -> DryRunClassification:
    """
    Classifies uv dry-run output into no-op, metadata-only, or substantive change.

    The primary path parses uv's JSON output. If parsing fails, falls back to a
    conservative text classification.
    """
    parsed_payload: dict[str, Any] | None = _extract_json_payload(output_text)
    if parsed_payload is not None:
        return _classify_json_payload(parsed_payload)
    return _classify_text_output(output_text)


def _extract_json_payload(output_text: str) -> dict[str, Any] | None:
    """
    Extracts the JSON object embedded in uv dry-run output, if present.
    """
    start_index: int = output_text.find('{')
    end_index: int = output_text.rfind('}')
    parsed_payload: dict[str, Any] | None = None
    if start_index == -1 or end_index == -1 or start_index >= end_index:
        return parsed_payload
    json_text: str = output_text[start_index : end_index + 1]
    try:
        loaded_data: Any = json.loads(json_text)
        if isinstance(loaded_data, dict):
            parsed_payload = loaded_data
    except json.JSONDecodeError:
        parsed_payload = None
    return parsed_payload


def _classify_json_payload(parsed_payload: dict[str, Any]) -> DryRunClassification:
    """
    Classifies the parsed uv JSON payload.
    """
    sync_action: str = str(parsed_payload.get('sync', {}).get('action', ''))
    lock_action: str = str(parsed_payload.get('lock', {}).get('action', ''))
    if sync_action == 'check' and lock_action == 'check':
        return DryRunClassification(
            has_pending_change=False,
            is_substantive=False,
            is_exclude_newer_only=False,
            summary='Dry run found no pending changes.',
            sync_action=sync_action,
            lock_action=lock_action,
        )
    if sync_action == 'check' and lock_action != 'check':
        return DryRunClassification(
            has_pending_change=True,
            is_substantive=False,
            is_exclude_newer_only=True,
            summary='Dry run indicates lockfile-only metadata churn; skipping update.',
            sync_action=sync_action,
            lock_action=lock_action,
        )
    return DryRunClassification(
        has_pending_change=True,
        is_substantive=True,
        is_exclude_newer_only=False,
        summary='Dry run indicates a substantive dependency change.',
        sync_action=sync_action,
        lock_action=lock_action,
    )


def _classify_text_output(output_text: str) -> DryRunClassification:
    """
    Conservatively classifies dry-run output when JSON parsing is unavailable.
    """
    normalized_text: str = output_text.lower()
    if 'would make no changes' in normalized_text or 'no lockfile changes detected' in normalized_text:
        return DryRunClassification(
            has_pending_change=False,
            is_substantive=False,
            is_exclude_newer_only=False,
            summary='Dry run found no pending changes.',
            sync_action='',
            lock_action='',
        )
    return DryRunClassification(
        has_pending_change=True,
        is_substantive=True,
        is_exclude_newer_only=False,
        summary='Dry run output could not be parsed; treating as substantive.',
        sync_action='',
        lock_action='',
    )
