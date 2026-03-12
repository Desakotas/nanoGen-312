import os
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from google import genai
from google.genai.types import GenerateContentConfig, Modality
from PIL import Image, UnidentifiedImageError


PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
DEFAULT_ALLOWED_MODELS = [
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
    "gemini-2.5-flash-image",
]


def parse_allowed_models(raw_value: str | None) -> list[str]:
    if not raw_value:
        return DEFAULT_ALLOWED_MODELS.copy()

    parsed = [item.strip() for item in raw_value.split(",") if item.strip()]
    return parsed or DEFAULT_ALLOWED_MODELS.copy()


ALLOWED_MODELS = parse_allowed_models(os.environ.get("ALLOWED_IMAGE_MODELS"))
DEFAULT_MODEL_ID = os.environ.get("GEMINI_MODEL_ID", ALLOWED_MODELS[0])
if DEFAULT_MODEL_ID not in ALLOWED_MODELS:
    ALLOWED_MODELS = [DEFAULT_MODEL_ID] + ALLOWED_MODELS

if not PROJECT_ID:
    raise RuntimeError("Missing env var GOOGLE_CLOUD_PROJECT")

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
app = FastAPI(title="Vertex Image Edit API", version="1.0.0")
WEB_INDEX = Path(__file__).parent / "web" / "index.html"


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/models")
def get_models():
    return {"default": DEFAULT_MODEL_ID, "models": ALLOWED_MODELS}


@app.get("/")
def index():
    if not WEB_INDEX.exists():
        raise HTTPException(status_code=404, detail="Web UI not found")
    return FileResponse(WEB_INDEX)


@app.post("/edit")
async def edit_image(
    prompt: str = Form(...),
    image: UploadFile = File(...),
    model: str | None = Form(default=None),
):
    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty image file")

    try:
        source_image = Image.open(BytesIO(raw))
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Unsupported image format") from exc

    selected_model = (model or DEFAULT_MODEL_ID).strip()
    if selected_model not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model '{selected_model}'. Allowed: {', '.join(ALLOWED_MODELS)}",
        )

    response = client.models.generate_content(
        model=selected_model,
        contents=[source_image, prompt],
        config=GenerateContentConfig(response_modalities=[Modality.TEXT, Modality.IMAGE]),
    )

    parts = response.candidates[0].content.parts if response.candidates else []
    for part in parts:
        inline_data = getattr(part, "inline_data", None)
        if inline_data and inline_data.data:
            mime_type = inline_data.mime_type or "image/png"
            return StreamingResponse(BytesIO(inline_data.data), media_type=mime_type)

    text_fragments = [getattr(part, "text", "") for part in parts if getattr(part, "text", "")]
    return JSONResponse(
        status_code=502,
        content={
            "error": "Model returned no image data",
            "model_text": "\n".join(text_fragments).strip(),
        },
    )
