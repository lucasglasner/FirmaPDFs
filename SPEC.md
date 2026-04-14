# PDF Auto-Signer Web App — Specification

## Problem

Manually placing a signature image on PDFs is tedious. The hardest part is finding the correct coordinates and size for the signature. Currently this is done by trial-and-error in a Jupyter notebook using PyMuPDF (`fitz`).

## Goal

A lightweight Python web app with two phases:

1. **Configure** — Load a single PDF and a signature image. Visually preview the PDF and drag/resize the signature to the desired position. Extract exact coordinates and size.
2. **Batch Sign** — Using the configured position, sign multiple PDFs at once and download the results.

---

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Backend | **FastAPI** | Lightweight, async, easy file handling |
| Frontend | **Vanilla HTML/CSS/JS** | No build step, minimal dependencies |
| PDF rendering (backend) | **PyMuPDF (fitz)** | Already used in notebook, fast rasterization |
| PDF signing (backend) | **PyMuPDF (fitz)** | `page.insert_image()` already proven |
| Image handling | **Pillow** | Already used for rotation/conversion |

### Python Dependencies

```
fastapi
uvicorn[standard]
python-multipart
pymupdf
Pillow
```

No JS frameworks. The frontend uses the Canvas API for rendering and interaction.

---

## Architecture

```
Browser                          Server (FastAPI)
───────                          ────────────────
                                 POST /api/upload-pdf
  Upload PDF  ──────────────────►  Store temp PDF
                                   Render page 1 as PNG
  ◄────────────────────────────   Return page image + dimensions

                                 POST /api/upload-signature
  Upload signature ─────────────►  Store temp signature
  ◄────────────────────────────   Return signature image URL

  User drags/resizes signature
  on canvas (client-side only)

                                 POST /api/preview
  Send coords ──────────────────►  Render PDF page with signature overlay
  ◄────────────────────────────   Return preview image (PNG)

                                 POST /api/batch-sign
  Upload N PDFs + coords ───────►  Sign all PDFs with fitz
                                   Package into ZIP
  ◄────────────────────────────   Return ZIP download
```

---

## UI Layout

Single-page app with two sections/tabs:

### Section 1 — Configure Position

```
┌──────────────────────────────────────────────────┐
│  [Upload PDF]  [Upload Signature]                │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │                                            │  │
│  │         PDF Page Preview (canvas)          │  │
│  │                                            │  │
│  │         [ draggable signature ]            │  │
│  │                                            │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  Page: [< 1/N >]                                 │
│  X: ____  Y: ____  W: ____  H: ____             │
│  [Preview Signed]  [Apply to All Pages: ☑]       │
│                                                  │
│  [Confirm Position →]                            │
└──────────────────────────────────────────────────┘
```

- Canvas shows the rasterized PDF page at a fitted scale.
- Signature image is overlaid and **draggable + resizable** via mouse.
- Coordinate inputs update live as user drags; typing in inputs moves the overlay.
- All coordinates are in **PDF points** (not pixel), translated from canvas scale.
- "Preview Signed" calls backend to render the actual signed page as a check.
- Page navigation if the PDF has multiple pages (signature position is per-config, same on every page).

### Section 2 — Batch Sign

```
┌──────────────────────────────────────────────────┐
│  Position: (2050, 1350) Size: 175×175   [Edit]   │
│  Signature: firma1.jpeg                           │
│                                                   │
│  [Upload PDFs]  (drag & drop zone)                │
│  ┌──────────────────────────────────────────────┐ │
│  │  05-PFM-HID-PL-01.pdf          ✓ Ready      │ │
│  │  05-PFM-HID-PL-02.pdf          ✓ Ready      │ │
│  │  05-PFM-HID-PL-03.pdf          ✓ Ready      │ │
│  └──────────────────────────────────────────────┘ │
│                                                   │
│  [Sign All & Download ZIP]                        │
│  Apply to: ○ All pages  ○ First page only         │
│            ○ Last page only                        │
└──────────────────────────────────────────────────┘
```

---

## API Endpoints

### `GET /`
Serve the single-page HTML app.

### `POST /api/upload-pdf`
- **Body**: multipart file (single PDF)
- **Response**: `{ "pages": N, "width": float, "height": float, "page_image": "/api/page-image/{id}/0" }`
- Stores the PDF in a temp directory. Renders page 0 as PNG.

### `GET /api/page-image/{pdf_id}/{page_num}`
- **Response**: PNG image of the requested page (rasterized at ~150 DPI for preview).

### `POST /api/upload-signature`
- **Body**: multipart file (JPG/PNG)
- **Response**: `{ "signature_url": "/api/signature/{id}", "width": int, "height": int }`

### `GET /api/signature/{sig_id}`
- **Response**: The uploaded signature image.

### `POST /api/preview`
- **Body**: `{ "pdf_id": str, "sig_id": str, "page": int, "x": float, "y": float, "w": float, "h": float }`
- **Response**: PNG image of that page with the signature burned in at the given rect.

### `POST /api/batch-sign`
- **Body**: multipart — multiple PDF files + JSON field with `{ "sig_id": str, "x": float, "y": float, "w": float, "h": float, "pages": "all" | "first" | "last" }`
- **Response**: `application/zip` containing all signed PDFs.

---

## Coordinate System

- PyMuPDF uses **points** (1 point = 1/72 inch) with origin at **top-left**.
- The canvas displays the page scaled to fit the viewport.
- A `scale` factor is computed: `scale = canvas_width / pdf_page_width`.
- Mouse positions on canvas are converted: `pdf_x = canvas_x / scale`, `pdf_y = canvas_y / scale`.
- The signature rect in PDF space: `fitz.Rect(x, y, x + w, y + h)`.

---

## File Structure

```
FirmaPlanos/
├── SPEC.md              # This file
├── app.py               # FastAPI application (all backend logic)
├── static/
│   └── index.html       # Single-page app (HTML + JS + CSS inlined)
├── requirements.txt     # Python dependencies
├── sign.ipynb           # Original notebook (kept for reference)
├── planos/              # Input PDFs (user's existing folder)
└── planos_firma/        # Output PDFs (user's existing folder)
```

The app is a **single Python file** (`app.py`) + **single HTML file** (`static/index.html`). No build tools.

---

## Implementation Plan (ordered tasks)

### Phase 1 — Backend Core
1. Create `requirements.txt` with dependencies.
2. Create `app.py` with FastAPI skeleton, temp file management, and CORS.
3. Implement `POST /api/upload-pdf` — accept PDF, store in temp dir, rasterize page 0.
4. Implement `GET /api/page-image/{pdf_id}/{page_num}` — serve rasterized page.
5. Implement `POST /api/upload-signature` — accept image, store, return metadata.
6. Implement `GET /api/signature/{sig_id}` — serve signature image.
7. Implement `POST /api/preview` — render a single page with signature overlay.
8. Implement `POST /api/batch-sign` — sign multiple PDFs, return ZIP.

### Phase 2 — Frontend
9. Create `static/index.html` with basic layout (two tabs).
10. Implement PDF upload + page rendering on canvas.
11. Implement signature upload + overlay on canvas.
12. Implement drag & resize interaction for the signature overlay.
13. Implement coordinate display + manual input fields.
14. Implement preview button (calls `/api/preview`).
15. Implement batch upload UI + file list.
16. Implement "Sign All & Download ZIP" button.

### Phase 3 — Polish
17. Page navigation (prev/next) for multi-page PDFs.
18. "Apply to" radio buttons (all pages / first / last).
19. Drag-and-drop file upload zones.
20. Error handling and loading states.
21. Cleanup temp files on shutdown.

---

## Running

```bash
pip install -r requirements.txt
python app.py
# Opens at http://localhost:8000
```

Or:

```bash
uvicorn app:app --reload --port 8000
```

---

## Security Notes

- Temp files are stored in a system temp directory and cleaned up on shutdown.
- File uploads are validated: only PDF and image MIME types accepted.
- No authentication (local tool only, not exposed to the internet).
- File size limits enforced (e.g., 50 MB per PDF, 5 MB per signature).

---

## Non-Goals

- No database. All state is ephemeral (temp files + in-memory dict).
- No user accounts or multi-user support.
- No OCR or text extraction.
- No digital signatures (cryptographic). This is visual stamp/image placement only.
