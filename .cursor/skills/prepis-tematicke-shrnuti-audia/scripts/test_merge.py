#!/usr/bin/env python3
"""Kontroly spojování dílů bez stahování modelu."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from transcribe import Segment, chunk_bounds, is_duplicate, mark_segment, merge_chunks


def test_chunk_bounds() -> None:
    assert chunk_bounds(30, 600, 3) == [(0.0, 30)]
    bounds = chunk_bounds(1500, 600, 3)
    assert bounds[0] == (0.0, 600)
    assert abs(bounds[1][0] - 597) < 1e-6
    assert bounds[-1][1] == 1500
    assert bounds[-1][0] < 1500


def test_merge_drops_overlap_and_rebases() -> None:
    first = [
        Segment(0.0, 5.0, "Ahoj"),
        Segment(5.0, 10.0, "světe dnes"),
    ]
    second = [
        Segment(0.2, 2.8, "světe dnes"),
        Segment(3.0, 8.0, "jak se máš"),
    ]
    merged = merge_chunks([(0.0, first), (7.0, second)], overlap=3.0)
    texts = [segment.text for segment in merged]
    assert texts == ["Ahoj", "světe dnes", "jak se máš"], texts
    assert merged[2].start == 10.0
    assert merged[2].end == 15.0


def test_duplicate_text() -> None:
    assert is_duplicate("to je konec věty", "to je konec věty")
    assert not is_duplicate("první věta", "úplně jiná věta")


def test_mark_unintelligible() -> None:
    quiet = mark_segment(Segment(0, 1, "hm", no_speech_prob=0.9))
    assert quiet.unintelligible
    assert quiet.display_text() == "[nesrozumitelné]"
    unsure = mark_segment(Segment(0, 1, "číslo smlouvy 12", avg_logprob=-1.4))
    assert unsure.uncertain
    assert unsure.display_text().startswith("[nejisté]")
    clear = mark_segment(Segment(0, 1, "dočasná ochrana", avg_logprob=-0.2))
    assert clear.display_text() == "dočasná ochrana"


def main() -> int:
    test_chunk_bounds()
    test_merge_drops_overlap_and_rebases()
    test_duplicate_text()
    test_mark_unintelligible()
    print("test_merge: v pořádku")
    return 0


if __name__ == "__main__":
    sys.exit(main())
