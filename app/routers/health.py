from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("")
def health_check() -> JSONResponse:
    return JSONResponse(
        content={
            "status": "ok",
            "service": "otomatisasi-kisikisi",
        }
    )