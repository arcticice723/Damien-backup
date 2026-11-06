import tempfile
import unittest
import zipfile
from pathlib import Path

from jarvis_assistant.retrieval import ApprovedDocumentRetriever


class RetrievalTests(unittest.TestCase):
    def test_searches_only_supported_docs_under_approved_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "note.txt").write_text("Damien can retrieve approved project notes.", encoding="utf-8")
            (root / "ignored.exe").write_text("Damien secret", encoding="utf-8")

            results = ApprovedDocumentRetriever(root).search("approved notes")

        self.assertEqual(len(results), 1)
        self.assertIn("note.txt", results[0])

    def test_searches_basic_docx_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docx = root / "brief.docx"
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t>Mark 42 suit diagnostics</w:t></w:r></w:p></w:body></w:document>"
            )
            with zipfile.ZipFile(docx, "w") as archive:
                archive.writestr("word/document.xml", xml)

            results = ApprovedDocumentRetriever(root).search("suit diagnostics")

        self.assertEqual(len(results), 1)
        self.assertIn("brief.docx", results[0])


if __name__ == "__main__":
    unittest.main()
