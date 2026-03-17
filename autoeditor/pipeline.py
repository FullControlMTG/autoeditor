from dataclasses import dataclass
from enum import Enum, auto
from math import ceil
from pathlib import Path

from .config import Config
from .project import ProjectFolder


class SegmentType(Enum):
    INTRO = auto()
    OUTRO = auto()
    TRANSITION = auto()
    DECK_TECH = auto()
    GAME = auto()
    MIDROLL_AD = auto()


@dataclass
class Segment:
    type: SegmentType
    path: Path
    label: str


def build_pipeline(project: ProjectFolder, config: Config) -> list[Segment]:
    """Return the ordered list of segments for a project.

    Default order for N games:
      Intro > Transition > Deck Tech > Midroll Ad 1
      > Game 1 > T > ... > Game ceil(N/2) > Midroll Ad 2
      > Game ceil(N/2)+1 > T > ... > Game N > Outro

    Rules:
    - No transition clip before/after midroll ads.
    - Midroll Ad 2 is skipped when there is only 1 game.
    - Any asset not configured (path is None) is simply omitted.
    """
    segments: list[Segment] = []

    if config.intro_path:
        segments.append(Segment(SegmentType.INTRO, config.intro_path, "Intro"))

    if config.transition_path:
        segments.append(Segment(SegmentType.TRANSITION, config.transition_path, "Transition"))

    segments.append(Segment(SegmentType.DECK_TECH, project.deck_tech, "Deck Tech"))

    if config.midroll_ad_path_1 and config.midroll_ad_1_enabled:
        segments.append(Segment(SegmentType.MIDROLL_AD, config.midroll_ad_path_1, "Midroll Ad 1"))

    games = project.games
    num_games = len(games)
    # Midroll Ad 2 is inserted after the first ceil(num_games/2) games.
    # Only meaningful when there are at least 2 games.
    midroll2_after = ceil(num_games / 2)

    for i, game_path in enumerate(games):
        game_num = i + 1
        is_last = game_num == num_games

        segments.append(Segment(SegmentType.GAME, game_path, f"Game {game_num}"))

        if game_num == midroll2_after and config.midroll_ad_path_2 and config.midroll_ad_2_enabled and num_games >= 2:
            # No transition on either side of a midroll ad.
            segments.append(Segment(SegmentType.MIDROLL_AD, config.midroll_ad_path_2, "Midroll Ad 2"))
        elif not is_last and config.transition_path:
            segments.append(Segment(SegmentType.TRANSITION, config.transition_path, "Transition"))

    if config.outro_path:
        segments.append(Segment(SegmentType.OUTRO, config.outro_path, "Outro"))

    return segments


def describe_pipeline(segments: list[Segment]) -> str:
    """Return a human-readable summary of the pipeline order."""
    return " > ".join(s.label for s in segments)
