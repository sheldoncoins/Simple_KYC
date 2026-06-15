"use client";

/**
 * Render the first page of a PDF to a JPEG Blob, entirely in the browser, so the
 * passport upload accepts PDFs while the server stays image-only. pdf.js is
 * dynamically imported (client-only) and its worker is loaded from a CDN pinned
 * to the installed version.
 */
export async function pdfFirstPageToJpeg(file: Blob): Promise<Blob> {
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc =
    `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

  const data = await file.arrayBuffer();
  const pdf = await pdfjs.getDocument({ data }).promise;
  const page = await pdf.getPage(1);
  const viewport = page.getViewport({ scale: 2 }); // upscale for OCR legibility

  const canvas = document.createElement("canvas");
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas_unavailable");

  await page.render({ canvas, canvasContext: ctx, viewport }).promise;

  return new Promise<Blob>((resolve, reject) =>
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("encode_failed"))),
      "image/jpeg",
      0.92,
    ),
  );
}
