from dataclasses import dataclass


@dataclass(slots=True)
class PageText:
    page: int
    text: str


@dataclass(slots=True)
class DocumentText:
    name: str
    pages: list[PageText]
    metadata: dict[str, str]


@dataclass(slots=True)
class Chunk:
    document_id: str
    document: str
    page: int
    section: str | None
    clause: str | None
    text: str
