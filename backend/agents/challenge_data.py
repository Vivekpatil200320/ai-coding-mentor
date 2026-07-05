"""Shared file-loading helpers for reading challenge content off disk."""

import json
from pathlib import Path

CHALLENGES_DIR = Path(__file__).resolve().parents[2] / "challenges"


def load_metadata(challenge_id: str) -> dict:
    path = CHALLENGES_DIR / challenge_id / "metadata.json"
    return json.loads(path.read_text())


def load_broken_code(challenge_id: str) -> str:
    path = CHALLENGES_DIR / challenge_id / "broken_code" / "main.py"
    return path.read_text()


def load_rubric(challenge_id: str) -> dict:
    path = CHALLENGES_DIR / challenge_id / "rubric.json"
    return json.loads(path.read_text())


def list_challenges() -> list[dict]:
    """All challenges with a valid metadata.json, sorted by id."""
    challenges = []
    for entry in sorted(CHALLENGES_DIR.iterdir()):
        if not entry.is_dir():
            continue
        metadata_path = entry / "metadata.json"
        if metadata_path.is_file():
            challenges.append(json.loads(metadata_path.read_text()))
    return challenges
