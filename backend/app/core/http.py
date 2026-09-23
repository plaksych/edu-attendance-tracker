import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings


class BodyTooLarge(Exception):
    pass


class RequestBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        size = 0
        limit = (settings.recognition_upload_max_size_mb + 1) * 1024 * 1024
        if "/schedule/import" in scope["path"]:
            limit = 10 * 1024 * 1024
        elif "uploads" not in scope["path"]:
            limit = 1024 * 1024
        headers = dict(scope["headers"])
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = limit + 1

        async def bounded_receive():
            nonlocal size
            message = await receive()
            if message["type"] == "http.request":
                size += len(message.get("body", b""))
                if size > limit:
                    raise BodyTooLarge()
            return message

        async def secure_send(message):
            if message["type"] == "http.response.start":
                message["headers"] += [(b"x-request-id", request_id.encode()),
                                       (b"cache-control", b"no-store"),
                                       (b"x-content-type-options", b"nosniff")]
            await send(message)
        try:
            if declared > limit:
                raise BodyTooLarge()
            await self.app(scope, bounded_receive, secure_send)
        except BodyTooLarge:
            response = JSONResponse(status_code=413, content={"detail": "Размер запроса превышает лимит",
                "error": {"code": "payload_too_large", "message": "Размер запроса превышает лимит",
                          "request_id": request_id}})
            await response(scope, receive, secure_send)


async def http_error(request: Request, exc):
    codes = {401: "unauthenticated", 403: "forbidden", 404: "not_found", 409: "conflict",
             422: "validation_error", 429: "rate_limited", 503: "unavailable"}
    return JSONResponse(status_code=exc.status_code, headers=exc.headers,
        content={"detail": exc.detail, "error": {"code": codes.get(exc.status_code, "request_error"),
            "message": exc.detail, "request_id": request.state.request_id}})


async def validation_error(request: Request, exc):
    fields = [{"field": ".".join(str(v) for v in e["loc"]), "code": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "Проверьте поля запроса",
        "error": {"code": "validation_error", "message": "Проверьте поля запроса", "fields": fields,
                  "request_id": request.state.request_id}})
