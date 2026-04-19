from __future__ import annotations

import asyncio
import base64
import os
from io import BytesIO

from fastapi import HTTPException
from google import genai
from google.genai import types as genai_types
from PIL import Image


OCR_PROMPT = (
    "You are a master mathematical OCR engine. Extract the physics or math problem from this image perfectly. "
    "Convert all formulas to standard text or LaTeX. Do not solve the problem. Only return the exact text of the question."
)


def _normalize_base64_image(base64_string: str) -> bytes:
    payload = (base64_string or "").strip()
    if not payload:
        raise HTTPException(status_code=422, detail="image_data cannot be empty.")
    if payload.startswith("data:") and "," in payload:
        payload = payload.split(",", 1)[1].strip()
    try:
        return base64.b64decode(payload, validate=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid Base64 image payload.") from exc


def _decode_image(base64_string: str) -> Image.Image:
    image_bytes = _normalize_base64_image(base64_string)
    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()
        return image
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to decode uploaded image.") from exc


def _create_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is missing for image OCR.")
    return genai.Client(api_key=api_key)


async def extract_text_from_image(base64_string: str) -> str:
    client = _create_gemini_client()
    image = _decode_image(base64_string)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()

    def _run_ocr() -> str:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                genai_types.Part.from_text(text=OCR_PROMPT),
                genai_types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            ],
        )
        return str(getattr(response, "text", "") or "").strip()

    text = await asyncio.to_thread(_run_ocr)
    if not text:
        raise HTTPException(status_code=502, detail="Gemini OCR returned empty text.")
    return text
