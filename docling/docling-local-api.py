#!/usr/bin/env python3.13
"""
Docling local API server — drop-in replacement for the Unstructured.io Docker
container. Exposes the same endpoint path so the Flogo flow URL needs no change:

    POST /general/v0/general  (multipart/form-data, field: files)
    GET  /healthcheck

Returns JSON: {"text": "<chunk1>\\n\\n<chunk2>\\n\\n..."}
The Flogo fileContent expression uses this directly — no smartChunk() call needed.

Uses Docling + HybridChunker with do_ocr=False (native digital PDFs) and
TableFormer table structure detection. Each chunk carries its section heading
as a prefix, handled natively by HybridChunker's contextualize() method.

Run:
    python3.13 docling-local-api.py [--port 8001]
"""

import argparse
import json
import logging
import os
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("docling-api")

# ---------------------------------------------------------------------------
# Docling conversion + chunking
# ---------------------------------------------------------------------------

def _make_converter():
    """
    Build a DocumentConverter for PDFs that may contain:
      - native text  (always extracted)
      - tables       (TableFormer cell-level structure)
      - images with embedded text  (OCR via EasyOCR)
      - diagrams / flowcharts / screenshots  (VLM caption via Ollama)

    Environment variables (all optional):
      DOCLING_OCR=false          — disable OCR (default: true)
      DOCLING_VLM_URL            — Ollama base URL for picture descriptions
                                   (default: http://host.docker.internal:11434)
      DOCLING_VLM_MODEL          — Ollama vision model (default: llava:7b)
                                   Set to empty string "" to disable VLM.
    """
    import os
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        EasyOcrOptions,
    )

    do_ocr = os.environ.get("DOCLING_OCR", "true").lower() not in ("false", "0", "no")
    vlm_url   = os.environ.get("DOCLING_VLM_URL",   "http://host.docker.internal:11434")
    vlm_model = os.environ.get("DOCLING_VLM_MODEL",  "llava:7b")

    opts = PdfPipelineOptions()

    # Allow Docling to call remote services (e.g. Ollama VLM over HTTP)
    opts.enable_remote_services = True

    # ── Tables ────────────────────────────────────────────────────────────
    opts.do_table_structure = True
    opts.table_structure_options.do_cell_matching = True

    # ── OCR (text inside images / scanned pages) ──────────────────────────
    opts.do_ocr = do_ocr
    if do_ocr:
        opts.ocr_options = EasyOcrOptions(force_full_page_ocr=False)
        log.info("OCR enabled (EasyOCR, selective pages)")
    else:
        log.info("OCR disabled via DOCLING_OCR=false")

    # ── VLM picture descriptions (diagrams, flowcharts, charts) ──────────
    if vlm_model:
        try:
            from docling.datamodel.pipeline_options import (
                PictureDescriptionApiOptions,
            )
            pic_opts = PictureDescriptionApiOptions(
                url=f"{vlm_url.rstrip('/')}/v1/chat/completions",
                params={"model": vlm_model},
                prompt=(
                    "Describe this image in 1-3 concise sentences for a RAG search index. "
                    "Focus on: what type of diagram/image it is, the key entities shown, "
                    "and any labels or data values visible. Be factual and brief."
                ),
                timeout=60,
            )
            opts.do_picture_description = True
            opts.picture_description_options = pic_opts
            log.info(f"VLM picture descriptions enabled: {vlm_url}  model={vlm_model}")
        except (ImportError, AttributeError):
            # Older Docling build without PictureDescriptionApiOptions — skip gracefully
            log.warning("PictureDescriptionApiOptions not available in this Docling version — image captions disabled")
    else:
        log.info("VLM picture descriptions disabled (DOCLING_VLM_MODEL is empty)")

    return DocumentConverter(format_options={"pdf": PdfFormatOption(pipeline_options=opts)})


# Module-level singleton so the heavy model load happens once at startup.
_CONVERTER = None

def get_converter():
    global _CONVERTER
    if _CONVERTER is None:
        log.info("Loading Docling models (first request, one-time cost)…")
        _CONVERTER = _make_converter()
        log.info("Docling models ready.")
    return _CONVERTER


def convert_and_chunk(path: str, filename: str, max_tokens: int = 400) -> str:
    """
    Convert a document with Docling, chunk with HybridChunker, and return
    all chunks joined by double-newlines (the separator the Weaviate ingest
    activity uses to split on 'paragraph' strategy).
    """
    from docling.chunking import HybridChunker

    log.info(f"Converting: {filename}")
    conv = get_converter()
    result = conv.convert(path)
    doc = result.document

    # Count elements for logging
    tables   = len(doc.tables)
    pictures = len(doc.pictures) if hasattr(doc, 'pictures') else 0
    log.info(f"  → tables={tables}  pictures={pictures}")

    chunker = HybridChunker(max_tokens=max_tokens)
    chunks = list(chunker.chunk(doc))
    log.info(f"  → {len(chunks)} chunks (max_tokens={max_tokens})")

    # contextualize() prepends section headings / captions to each chunk text
    texts = []
    for chunk in chunks:
        text = chunker.contextualize(chunk).strip()
        if text:
            texts.append(text)

    joined = "\n\n".join(texts)
    log.info(f"  → total chars: {len(joined)}")
    return joined


def convert_to_markdown(path: str, filename: str) -> str:
    """
    Convert a document with Docling and return full Markdown via
    doc.export_to_markdown(). No HybridChunker — preserves ## headings
    and Markdown tables intact for downstream heading-based chunking.
    """
    log.info(f"Converting (markdown): {filename}")
    conv = get_converter()
    result = conv.convert(path)
    doc = result.document

    tables   = len(doc.tables)
    pictures = len(doc.pictures) if hasattr(doc, 'pictures') else 0
    log.info(f"  → tables={tables}  pictures={pictures}")

    md = doc.export_to_markdown()
    log.info(f"  → markdown chars: {len(md)}")
    return md


# ---------------------------------------------------------------------------
# Minimal multipart parser (no external deps)
# ---------------------------------------------------------------------------

def parse_multipart(data: bytes, boundary: bytes) -> dict:
    """Returns {field_name: (filename_or_None, bytes)}."""
    parts = {}
    delimiter = b"--" + boundary
    segments = data.split(delimiter)
    for seg in segments:
        if seg in (b"", b"--\r\n", b"--\r\n--", b"\r\n"):
            continue
        if b"\r\n\r\n" not in seg:
            continue
        header_part, body = seg.split(b"\r\n\r\n", 1)
        # Strip trailing CRLF
        if body.endswith(b"\r\n"):
            body = body[:-2]
        headers = header_part.decode(errors="replace")
        fname = None
        field_name = None
        for line in headers.splitlines():
            if "Content-Disposition" in line:
                for token in line.split(";"):
                    token = token.strip()
                    if token.startswith("name="):
                        field_name = token[5:].strip('"')
                    elif token.startswith("filename="):
                        fname = token[9:].strip('"')
        if field_name:
            parts[field_name] = (fname, body)
    return parts


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class DoclingHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # suppress default per-request stdout noise
        log.debug(fmt, *args)

    def send_json(self, code: int, obj):
        body = json.dumps(obj).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def do_GET(self):
        if self.path in ("/healthcheck", "/health"):
            self.send_json(200, {"status": "ok", "engine": "docling"})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path not in ("/general/v0/general", "/v0/markdown"):
            self.send_json(404, {"error": "not found"})
            return
        markdown_mode = (self.path == "/v0/markdown")

        # Read body
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        # Parse multipart boundary
        ct = self.headers.get("Content-Type", "")
        boundary = None
        for part in ct.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part[9:].strip('"').encode()
                break

        if not boundary:
            self.send_json(400, {"error": "missing multipart boundary"})
            return

        parts = parse_multipart(body, boundary)
        if "files" not in parts:
            self.send_json(400, {"error": "missing 'files' field in multipart body"})
            return

        fname, file_bytes = parts["files"]
        if not fname:
            fname = "upload.pdf"

        # Write to temp file with correct extension
        ext = os.path.splitext(fname)[1] or ".pdf"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
            tf.write(file_bytes)
            tmp_path = tf.name

        try:
            if markdown_mode:
                md = convert_to_markdown(tmp_path, fname)
                self.send_json(200, {"markdown": md, "filename": fname})
            else:
                text = convert_and_chunk(tmp_path, fname)
                self.send_json(200, {"text": text, "filename": fname})
        except Exception as e:
            log.exception(f"Conversion failed for {fname}: {e}")
            self.send_json(500, {"error": str(e)})
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Docling local API server")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--max-tokens", type=int, default=400,
                        help="HybridChunker max_tokens per chunk (default 400)")
    args = parser.parse_args()

    # Pre-load models so the first ingest request isn't slow
    log.info(f"Pre-loading Docling models…")
    try:
        get_converter()
    except Exception as e:
        log.warning(f"Model pre-load failed (will retry on first request): {e}")

    server = ThreadingHTTPServer((args.host, args.port), DoclingHandler)
    log.info(f"Docling API listening on http://{args.host}:{args.port}")
    log.info(f"  Endpoint: POST /general/v0/general (multipart, field: files)")
    log.info(f"  Health:   GET  /healthcheck")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down.")


if __name__ == "__main__":
    main()
