from __future__ import annotations

import asyncio
import base64
import os
from io import BytesIO

import google.generativeai as genai
from fastapi import HTTPException
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


def _create_ocr_model() -> genai.GenerativeModel:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is missing for image OCR.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")


async def extract_text_from_image(base64_string: str) -> str:
    model = _create_ocr_model()
    image = _decode_image(base64_string)

    response = await asyncio.to_thread(model.generate_content, [OCR_PROMPT, image])
    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        raise HTTPException(status_code=502, detail="Gemini OCR returned empty text.")
    return text