import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import zipfile

from services import builder_asset_validation


CONTENT_TYPES = (
    '<Types><Override ContentType="application/vnd.openxmlformats-officedocument.'
    'wordprocessingml.document.main+xml"/></Types>'
)


def docx_bytes(*, include_document=True, extra_entries=0, payload="document"):
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", "<Relationships/>")
        if include_document:
            archive.writestr("word/document.xml", payload)
        for index in range(extra_entries):
            archive.writestr(f"word/media/{index}.txt", "x")
    return output.getvalue()


class BuilderAssetValidationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def write(self, name, content):
        path = self.root / name
        path.write_bytes(content)
        return path

    def test_valid_pdf_requires_header_and_eof(self):
        builder_asset_validation.validate_builder_asset_file(
            self.write("valid.pdf", b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"),
            "application/pdf",
        )
        with self.assertRaises(builder_asset_validation.BuilderAssetValidationError):
            builder_asset_validation.validate_builder_asset_file(
                self.write("fake.pdf", b"%PDF-1.7\nno trailer"),
                "application/pdf",
            )

    def test_valid_minimal_docx_is_accepted(self):
        builder_asset_validation.validate_builder_asset_file(
            self.write("valid.docx", docx_bytes()),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    def test_arbitrary_zip_and_missing_document_xml_are_rejected(self):
        output = BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("payload.txt", "not docx")
        for name, content in (
            ("arbitrary.docx", output.getvalue()),
            ("missing-document.docx", docx_bytes(include_document=False)),
        ):
            with self.subTest(name=name), self.assertRaises(
                builder_asset_validation.BuilderAssetValidationError
            ):
                builder_asset_validation.validate_builder_asset_file(
                    self.write(name, content),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )

    def test_docx_entry_and_expansion_bounds_are_enforced(self):
        with patch.object(builder_asset_validation, "DOCX_MAX_ENTRIES", 3):
            with self.assertRaises(builder_asset_validation.BuilderAssetValidationError):
                builder_asset_validation.validate_builder_asset_file(
                    self.write("entries.docx", docx_bytes(extra_entries=1)),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
        with patch.object(builder_asset_validation, "DOCX_MAX_COMPRESSION_RATIO", 2):
            with self.assertRaises(builder_asset_validation.BuilderAssetValidationError):
                builder_asset_validation.validate_builder_asset_file(
                    self.write("ratio.docx", docx_bytes(payload="x" * 10000)),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )

    def test_generic_ole_is_rejected_and_word_streams_are_required(self):
        path = self.write("generic.doc", bytes.fromhex("d0cf11e0a1b11ae1") + bytes(512))
        with self.assertRaises(builder_asset_validation.BuilderAssetValidationError):
            builder_asset_validation.validate_builder_asset_file(path, "application/msword")

        class WordOle:
            def __enter__(self): return self
            def __exit__(self, *_args): return None
            def listdir(self, **_kwargs): return [["WordDocument"], ["1Table"]]

        with patch.object(builder_asset_validation.olefile, "isOleFile", return_value=True), patch.object(
            builder_asset_validation.olefile, "OleFileIO", return_value=WordOle()
        ):
            builder_asset_validation.validate_builder_asset_file(path, "application/msword")


if __name__ == "__main__":
    unittest.main()
