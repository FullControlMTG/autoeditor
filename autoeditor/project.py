from dataclasses import dataclass
from pathlib import Path


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi"}


@dataclass
class ProjectFolder:
    name: str
    path: Path
    deck_tech: Path
    games: list[Path]

    @property
    def num_games(self) -> int:
        return len(self.games)


def scan_project(folder: Path) -> ProjectFolder:
    """Scan a single project folder.

    Videos are sorted by modification time then name. The first is the deck
    tech; the rest are game recordings.
    """
    videos = sorted(
        [f for f in folder.iterdir() if f.suffix.lower() in VIDEO_EXTENSIONS],
        key=lambda f: (f.stat().st_mtime, f.name),
    )

    if not videos:
        raise ValueError(f"No video files found in {folder}")

    return ProjectFolder(
        name=folder.name,
        path=folder,
        deck_tech=videos[0],
        games=videos[1:],
    )


def scan_projects_folder(folder: Path) -> list[ProjectFolder]:
    """Return one ProjectFolder per video-containing subdirectory."""
    projects = []
    for subfolder in sorted(folder.iterdir()):
        if subfolder.is_dir():
            try:
                projects.append(scan_project(subfolder))
            except ValueError:
                pass
    return projects
