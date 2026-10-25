"""PDFium rendering and a bounded, shell-free Tesseract invocation."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading

_PDFIUM_LOCK = threading.Lock()  # PDFium must not run concurrently in different threads.


def tesseract_executable(settings):
    return shutil.which(settings.tesseract_cmd)


def ocr_page(content, page_index, settings):
    import pypdfium2 as pdfium

    executable = tesseract_executable(settings)
    if executable is None:
        raise FileNotFoundError("Tesseract executable is not installed or configured")
    with tempfile.TemporaryDirectory(prefix="alpha-pdf-ocr-") as temporary:
        image_path = Path(temporary) / "page.png"
        output = Path(temporary) / "recognized"
        with _PDFIUM_LOCK:
            with pdfium.PdfDocument(content) as document:
                page = document[page_index]
                try:
                    bitmap = page.render(scale=settings.ocr_dpi / 72)
                    try:
                        with bitmap.to_pil() as image:
                            image.save(image_path, format="PNG", dpi=(settings.ocr_dpi, settings.ocr_dpi))
                    finally:
                        bitmap.close()
                finally:
                    page.close()
        subprocess.run(
            [executable, str(image_path), str(output), "--tessdata-dir", str(settings.tessdata.resolve()),
             "-l", settings.ocr_language, "-c", "tessedit_create_pdf=1"],
            check=True, capture_output=True, timeout=settings.ocr_timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return output.with_suffix(".pdf").read_bytes()
