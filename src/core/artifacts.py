import os
import shutil
from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class ImageArtifact:
    url: str
    caption: str | None = None
    file_path: str | None = None


@dataclass(slots=True)
class GalleryArtifact:
    items: list[ImageArtifact]
    caption: str | None = None


@dataclass(slots=True)
class TextArtifact:
    title: str
    body: str
    post_url: str


@dataclass(slots=True)
class VideoArtifact:
    url: str
    caption: str | None = None
    dash_url: str | None = None
    file_path: str | None = None


Artifact = ImageArtifact | GalleryArtifact | TextArtifact | VideoArtifact


TEMP_DIR_PREFIX = "webp2u_"


def remove_temp_file(file_path: str) -> None:
    parent = os.path.dirname(file_path)
    if os.path.basename(parent).startswith(TEMP_DIR_PREFIX):
        remove_temp_dir(parent)
        return
    try:
        os.unlink(file_path)
    except OSError:
        pass


def remove_temp_dir(dir_path: str) -> None:
    if not os.path.basename(dir_path).startswith(TEMP_DIR_PREFIX):
        return
    shutil.rmtree(dir_path, ignore_errors=True)


def cleanup_artifacts(artifacts: Iterable[Artifact]) -> None:
    for artifact in artifacts:
        file_path = getattr(artifact, "file_path", None)
        if file_path:
            remove_temp_file(str(file_path))
