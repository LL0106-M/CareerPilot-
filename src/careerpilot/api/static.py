from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class SPAStaticFiles(StaticFiles):
    """Serve built assets and fall back to index.html only for browser routes."""

    def __init__(self, directory: Path) -> None:
        super().__init__(directory=str(directory), html=False, check_dir=True)

    async def get_response(self, path: str, scope: Scope) -> Response:
        normalized = path.lstrip("/")
        is_api_path = normalized == "health" or normalized == "ready" or normalized.startswith(
            "v1/"
        )
        looks_like_asset = bool(Path(normalized).suffix)
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404 and not is_api_path and not looks_like_asset:
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and not is_api_path and not looks_like_asset:
            return await super().get_response("index.html", scope)
        return response
