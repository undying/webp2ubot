from dataclasses import dataclass


@dataclass(slots=True)
class ImageArtifact:
    url: str
    caption: str | None = None


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
