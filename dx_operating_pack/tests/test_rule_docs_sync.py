from __future__ import annotations

from pathlib import Path


START = "<!-- SYNC_BLOCK_START -->"
END = "<!-- SYNC_BLOCK_END -->"


def _extract_sync_block(path: str) -> str:
    text = Path(path).read_text(encoding="utf-8")
    s = text.find(START)
    e = text.find(END)
    assert s != -1, f"{path} missing SYNC_BLOCK_START marker"
    assert e != -1, f"{path} missing SYNC_BLOCK_END marker"
    assert s < e, f"{path} has invalid sync marker order"
    return text[s : e + len(END)].strip()


def test_agents_and_cursorrules_sync_block_match() -> None:
    agents = _extract_sync_block("AGENTS.md")
    cursor = _extract_sync_block(".cursorrules")
    assert agents == cursor, "Synced normative block mismatch: AGENTS.md -> .cursorrules"

