from fastapi import APIRouter

from app.packs.registry import load_presets_catalog
from app.packs.schemas import PresetsCatalogResponse

router = APIRouter(prefix="/api/presets", tags=["presets"])


@router.get("", response_model=PresetsCatalogResponse)
async def get_presets_catalog():
    return load_presets_catalog()
