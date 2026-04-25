"""Convert centipawn evaluations to win probabilities."""


def centipawns_to_prob(cp: int) -> float:
    """Return White's win probability given a centipawn eval.

    Uses the standard sigmoid formula (same as Lichess and TCEC).
    0 cp → 0.50, +400 cp → ~0.90, -400 cp → ~0.10.
    """
    return 1 / (1 + 10 ** (-cp / 400))
