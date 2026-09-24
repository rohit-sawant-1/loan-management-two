"""
One lock for every use of PDFium (the library behind pypdfium2).

PDFium is not thread-safe. pypdfium2's own documentation says it must never
be called from two threads at the same time, not even on two different
documents. In other projects, doing so has corrupted memory and killed the
whole server process.

Our upload routes are plain `def` functions, so FastAPI runs them in parallel
threads: two people uploading a PDF at the same moment, or one person
uploading several at once (Piece 35), would call PDFium twice at once. So
every PDFium call in the app goes inside `with PDFIUM_LOCK:`, and only one
runs at a time.

The lock is held only while PDFium itself is working (reading text, drawing
pages), which takes well under a second a page. The slow part of an upload,
waiting for Gemini to confirm a SPECIMEN document, happens outside it, so two
uploads still overlap where it matters.

Any new code that uses pypdfium2 must take this lock too (T-129).
"""

import threading

PDFIUM_LOCK = threading.Lock()
