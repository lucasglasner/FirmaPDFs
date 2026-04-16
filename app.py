"""
PDF Auto-Signer — FastAPI Backend
"""

import io
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="PDF Auto-Signer")

# Where we cache uploaded files for the session (cleaned up on shutdown)
TEMP_DIR = Path(tempfile.mkdtemp(prefix="firmaplanox_"))

# In-memory store: id -> absolute path
_pdf_store: dict[str, Path] = {}
_sig_store: dict[str, Path] = {}

ALLOWED_PDF_MIME = {"application/pdf"}
ALLOWED_IMG_MIME = {"image/jpeg", "image/png", "image/jpg"}
MAX_PDF_SIZE = 50 * 1024 * 1024   # 50 MB
MAX_SIG_SIZE = 5 * 1024 * 1024    # 5 MB

PREVIEW_DPI = 150  # dots per inch for page rasterization

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rasterize_page(pdf_path: Path, page_num: int, dpi: int = PREVIEW_DPI) -> bytes:
    """Return PNG bytes for a single PDF page."""
    doc = fitz.open(str(pdf_path))
    if page_num < 0 or page_num >= len(doc):
        raise IndexError(
            f"Page {page_num} out of range (doc has {len(doc)} pages)")
    page = doc[page_num]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    doc.close()
    return pix.tobytes("png")


def _sign_pdf(
    pdf_path: Path,
    sig_path: Path,
    x: float,
    y: float,
    w: float,
    h: float,
    pages: str = "all",   # "all" | "first" | "last" | "specific"
    page_list: str = "",   # comma-separated 1-based page numbers when pages=="specific"
) -> bytes:
    """
    Insert the signature image into the PDF at the given rectangle (PDF points).
    Returns signed PDF bytes.
    """
    # Normalise signature: strip EXIF rotation, convert to RGB JPEG
    img = Image.open(str(sig_path))
    img = img.convert("RGBA")          # keep transparency if any

    # Write normalised signature to a temp file so fitz can read it
    tmp_sig = TEMP_DIR / f"_norm_{sig_path.name}.png"
    img.save(str(tmp_sig), format="PNG")

    doc = fitz.open(str(pdf_path))
    n = len(doc)

    if pages == "first":
        page_indices = [0]
    elif pages == "last":
        page_indices = [n - 1]
    elif pages == "specific":
        page_indices = []
        for token in page_list.split(","):
            token = token.strip()
            if token.isdigit():
                idx = int(token) - 1  # convert 1-based to 0-based
                if 0 <= idx < n:
                    page_indices.append(idx)
        page_indices = sorted(set(page_indices))  # deduplicate & sort
    else:
        page_indices = list(range(n))

    rect = fitz.Rect(x, y, x + w, y + h)

    for i in page_indices:
        page = doc[i]
        page.insert_image(rect, filename=str(tmp_sig))

    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def _validate_upload(file: UploadFile, allowed_mimes: set, max_size: int) -> bytes:
    """Read file content and validate MIME type. Returns raw bytes."""
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in allowed_mimes:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{content_type}'. Allowed: {allowed_mimes}",
        )
    data = file.file.read()
    if len(data) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {max_size // (1024*1024)} MB.",
        )
    return data


# ---------------------------------------------------------------------------
# Routes — PDF
# ---------------------------------------------------------------------------

@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """Accept a PDF, store it, return page count and first page image URL."""
    data = _validate_upload(file, ALLOWED_PDF_MIME, MAX_PDF_SIZE)

    pdf_id = str(uuid.uuid4())
    pdf_path = TEMP_DIR / f"{pdf_id}.pdf"
    pdf_path.write_bytes(data)
    _pdf_store[pdf_id] = pdf_path

    doc = fitz.open(str(pdf_path))
    pages = len(doc)
    first_page = doc[0]
    width = first_page.rect.width
    height = first_page.rect.height
    doc.close()

    return JSONResponse({
        "pdf_id": pdf_id,
        "pages": pages,
        "width": width,
        "height": height,
        "page_image_url": f"/api/page-image/{pdf_id}/0",
    })


@app.get("/api/page-image/{pdf_id}/{page_num}")
async def get_page_image(pdf_id: str, page_num: int):
    """Return a rasterized PNG of the requested page."""
    if pdf_id not in _pdf_store:
        raise HTTPException(
            status_code=404, detail="PDF not found. Please re-upload.")
    try:
        png_bytes = _rasterize_page(_pdf_store[pdf_id], page_num)
    except IndexError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return Response(content=png_bytes, media_type="image/png")


# ---------------------------------------------------------------------------
# Routes — Signature
# ---------------------------------------------------------------------------

@app.post("/api/upload-signature")
async def upload_signature(file: UploadFile = File(...)):
    """Accept a signature image, store it, return its URL and dimensions."""
    data = _validate_upload(file, ALLOWED_IMG_MIME, MAX_SIG_SIZE)

    sig_id = str(uuid.uuid4())
    suffix = Path(file.filename or "sig.png").suffix or ".png"
    sig_path = TEMP_DIR / f"{sig_id}{suffix}"
    sig_path.write_bytes(data)
    _sig_store[sig_id] = sig_path

    img = Image.open(str(sig_path))
    w, h = img.size

    return JSONResponse({
        "sig_id": sig_id,
        "signature_url": f"/api/signature/{sig_id}",
        "width": w,
        "height": h,
    })


@app.get("/api/signature/{sig_id}")
async def get_signature(sig_id: str):
    """Serve the stored signature image."""
    if sig_id not in _sig_store:
        raise HTTPException(
            status_code=404, detail="Signature not found. Please re-upload.")
    sig_path = _sig_store[sig_id]
    media_type = "image/png" if sig_path.suffix.lower() == ".png" else "image/jpeg"
    return Response(content=sig_path.read_bytes(), media_type=media_type)


# ---------------------------------------------------------------------------
# Routes — Preview
# ---------------------------------------------------------------------------

@app.post("/api/preview")
async def preview(
    pdf_id: str = Form(...),
    sig_id: str = Form(...),
    page: int = Form(0),
    x: float = Form(...),
    y: float = Form(...),
    w: float = Form(...),
    h: float = Form(...),
):
    """Render a single page with the signature burned in. Returns PNG."""
    if pdf_id not in _pdf_store:
        raise HTTPException(status_code=404, detail="PDF not found.")
    if sig_id not in _sig_store:
        raise HTTPException(status_code=404, detail="Signature not found.")

    signed_bytes = _sign_pdf(
        _pdf_store[pdf_id],
        _sig_store[sig_id],
        x, y, w, h,
        pages="all",
    )

    # Re-open the signed bytes to rasterize the requested page
    doc = fitz.open(stream=signed_bytes, filetype="pdf")
    if page < 0 or page >= len(doc):
        page = 0
    mat = fitz.Matrix(PREVIEW_DPI / 72, PREVIEW_DPI / 72)
    pix = doc[page].get_pixmap(matrix=mat, alpha=False)
    doc.close()
    return Response(content=pix.tobytes("png"), media_type="image/png")


# ---------------------------------------------------------------------------
# Routes — Batch sign
# ---------------------------------------------------------------------------

@app.post("/api/batch-sign")
async def batch_sign(
    files: List[UploadFile] = File(...),
    sig_id: str = Form(...),
    x: float = Form(...),
    y: float = Form(...),
    w: float = Form(...),
    h: float = Form(...),
    pages: str = Form("all"),
    page_list: str = Form(""),
):
    """
    Sign multiple PDFs with the stored signature at the given rect.
    Returns a ZIP archive containing all signed PDFs.
    """
    if sig_id not in _sig_store:
        raise HTTPException(
            status_code=404, detail="Signature not found. Please re-upload.")
    if pages not in ("all", "first", "last", "specific"):
        raise HTTPException(
            status_code=422, detail="'pages' must be 'all', 'first', 'last' or 'specific'.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for upload in files:
            data = _validate_upload(upload, ALLOWED_PDF_MIME, MAX_PDF_SIZE)

            # Write to temp so fitz can open it by path (stream also works, but path is safer)
            tmp_pdf = TEMP_DIR / f"_batch_{uuid.uuid4()}.pdf"
            tmp_pdf.write_bytes(data)

            try:
                signed_bytes = _sign_pdf(
                    tmp_pdf,
                    _sig_store[sig_id],
                    x, y, w, h,
                    pages=pages,
                    page_list=page_list,
                )
            finally:
                tmp_pdf.unlink(missing_ok=True)

            out_name = upload.filename or "signed.pdf"
            zf.writestr(out_name, signed_bytes)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=signed_pdfs.zip"},
    )


# ---------------------------------------------------------------------------
# Static files (frontend)
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


# ---------------------------------------------------------------------------
# Cleanup on shutdown
# ---------------------------------------------------------------------------

@app.on_event("shutdown")
def cleanup():
    shutil.rmtree(TEMP_DIR, ignore_errors=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
