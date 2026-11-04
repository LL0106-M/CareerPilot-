import re
from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class SPAStaticFiles(StaticFiles):
    """Serve built assets and fall back to index.html only for browser routes."""

    def __init__(self, directory: Path) -> None:
        super().__init__(directory=str(directory), html=False, check_dir=True)

    @staticmethod
    def _is_versioned_asset(path: str) -> bool:
        stem = Path(path).stem
        if re.search(r"-v\d+$", stem):
            return True
        match = re.search(r"-([A-Za-z0-9_-]{8,})$", stem)
        return bool(
            match
            and any(character.isupper() or character.isdigit() for character in match.group(1))
        )

    async def get_response(self, path: str, scope: Scope) -> Response:
        normalized = path.replace("\\", "/").lstrip("/")
        is_api_path = (
            normalized == "health" or normalized == "ready" or normalized.startswith("v1/")
        )
        looks_like_asset = bool(Path(normalized).suffix)
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404 and not is_api_path and not looks_like_asset:
                response = await super().get_response("index.html", scope)
                response.headers["Cache-Control"] = "no-cache"
                return response
            raise
        if response.status_code == 404 and not is_api_path and not looks_like_asset:
            response = await super().get_response("index.html", scope)
            response.headers["Cache-Control"] = "no-cache"
            return response
        if normalized.startswith("assets/"):
            response.headers["Cache-Control"] = (
                "public, max-age=31536000, immutable"
                if self._is_versioned_asset(normalized)
                else "public, max-age=3600"
            )
        elif response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache"
        return response
