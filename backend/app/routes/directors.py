"""Director style endpoints."""

from fastapi import APIRouter, Request

router = APIRouter()


def _map_palette(color_palette: list[str]) -> dict:
    """Map color palette list to named dict for frontend."""
    defaults = ["#1a1a2e", "#16213e", "#e94560", "#0f3460", "#c4c4c4"]
    colors = color_palette if color_palette else defaults
    return {
        "primary": colors[0] if len(colors) > 0 else defaults[0],
        "secondary": colors[1] if len(colors) > 1 else defaults[1],
        "accent": colors[4] if len(colors) > 4 else defaults[2],
        "shadow": colors[2] if len(colors) > 2 else defaults[3],
        "highlight": colors[5] if len(colors) > 5 else defaults[4],
    }


@router.get("/")
async def list_directors(request: Request):
    """List all available director styles — frontend-compatible format."""
    styles = request.app.state.director_styles
    directors = []
    for key, style in styles.items():
        vs = style.get("visual_style", {})
        directors.append({
            "id": key,
            "name": style["name"],
            "tagline": style["tagline"],
            "palette": _map_palette(vs.get("color_palette", [])),
            "filmography": style.get("filmography_refs", [])[:5],
            "traits": list(style.get("camera_style", {}).keys())[:5],
            "thumbnail_url": "",
        })
    return {"data": directors, "message": "ok", "success": True}


@router.get("/{director_id}")
async def get_director(director_id: str, request: Request):
    """Get full director style profile."""
    styles = request.app.state.director_styles
    if director_id not in styles:
        return {"error": f"Unknown director: {director_id}"}
    return {"data": styles[director_id], "success": True}
