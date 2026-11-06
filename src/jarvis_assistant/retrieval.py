from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree


class ApprovedDocumentRetriever:
    SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf", ".docx", ".pptx", ".xlsx"}

    def __init__(self, root: Path) -> None:
        self.root = root

    def search(self, query: str, limit: int = 3) -> list[str]:
        if not self.root.exists():
            return []
        terms = {term.lower() for term in query.split() if len(term) > 2}
        if not terms:
            return []
        scored: list[tuple[int, Path, str]] = []
        for path in self.root.rglob("*"):
            if path.suffix.lower() not in self.SUPPORTED_SUFFIXES or not path.is_file():
                continue
            text = self._read_text(path)
            score = sum(text.lower().count(term) for term in terms)
            if score:
            lowered = text.lower()
            offsets = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
            start = max(0, min(offsets) - 300) if offsets else 0
            snippet = text[start : start + 1200].replace("\n", " ").strip()
                scored.append((score, path, snippet))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [f"{path.name}: {snippet}" for _score, path, snippet in scored[:limit]]

    def _read_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".pdf":
            return self._read_pdf(path)
        if suffix in {".docx", ".pptx", ".xlsx"}:
            return self._read_office_zip(path)
        return ""

    def _read_pdf(self, path: Path) -> str:
        for module_name in ("pypdf", "PyPDF2"):
            try:
                module = __import__(module_name)
                reader = module.PdfReader(str(path))
                return "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception:
                continue
        return ""

    def _read_office_zip(self, path: Path) -> str:
        try:
            with zipfile.ZipFile(path) as archive:
                xml_files = [
                    name
                    for name in archive.namelist()
                    if name.endswith(".xml")
                    and (
                        name.startswith("word/")
                        or name.startswith("ppt/slides/")
                        or name.startswith("xl/sharedStrings")
                    )
                ]
                parts: list[str] = []
                for name in xml_files:
                    parts.append(_xml_text(archive.read(name)))
                return "\n".join(parts)
        except Exception:
            return ""


def _xml_text(data: bytes) -> str:
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError:
        return ""
    values = [node.text for node in root.iter() if node.text]
    return re.sub(r"\s+", " ", " ".join(values)).strip()
