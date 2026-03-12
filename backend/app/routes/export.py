"""Export endpoints — PDF, CBZ, MP4, PPTX.

Turning art into deliverables. Every format a producer might want.
"""

from fastapi import APIRouter, HTTPException

from app.models.schemas import PanelPage
from app.services import firestore
from app.services.export_service import export_pdf, export_cbz, export_pptx

router = APIRouter()


async def _get_project_pages(project_id: str) -> tuple[list[PanelPage], str]:
    """Helper: get project pages and title, or raise 404."""
    project = await firestore.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.pages:
        raise HTTPException(
            status_code=400,
            detail="No panels generated yet. Generate panels first.",
        )
    return project.pages, project.title


@router.post("/pdf/{project_id}")
async def export_pdf_endpoint(project_id: str):
    """Export project as PDF (comics/storyboard)."""
    pages, title = await _get_project_pages(project_id)

    url = await export_pdf(
        pages=pages,
        project_id=project_id,
        title=title,
    )

    return {
        "status": "complete",
        "format": "pdf",
        "project_id": project_id,
        "download_url": url,
    }


@router.post("/cbz/{project_id}")
async def export_cbz_endpoint(project_id: str):
    """Export project as CBZ comic archive."""
    pages, title = await _get_project_pages(project_id)

    url = await export_cbz(
        pages=pages,
        project_id=project_id,
    )

    return {
        "status": "complete",
        "format": "cbz",
        "project_id": project_id,
        "download_url": url,
    }


@router.post("/mp4/{project_id}")
async def export_mp4(project_id: str, resolution: str = "1080p"):
    """Export trailer as MP4.

    Note: This requires the trailer to have been generated first.
    The final assembled MP4 URL comes from the trailer pipeline.
    """
    project = await firestore.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.trailer:
        raise HTTPException(
            status_code=400,
            detail="No trailer generated yet. Generate a trailer first.",
        )

    # Return the trailer's final URL (or individual clips)
    return {
        "status": "complete" if project.trailer.final_video_url else "clips_only",
        "format": "mp4",
        "project_id": project_id,
        "download_url": project.trailer.final_video_url,
        "clips": [
            {"clip_id": c.clip_id, "url": c.video_url, "duration": c.duration}
            for c in project.trailer.clips
            if c.video_url
        ],
        "total_duration": project.trailer.total_duration,
    }


@router.post("/pptx/{project_id}")
async def export_pptx_endpoint(project_id: str):
    """Export storyboard as PowerPoint pitch deck."""
    pages, title = await _get_project_pages(project_id)

    url = await export_pptx(
        pages=pages,
        project_id=project_id,
        title=title,
    )

    return {
        "status": "complete",
        "format": "pptx",
        "project_id": project_id,
        "download_url": url,
    }
