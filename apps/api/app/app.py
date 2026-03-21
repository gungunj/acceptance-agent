from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.exports import router as exports_router
from app.routes.fill_results import router as fill_results_router
from app.routes.gaps import router as gaps_router
from app.routes.materials import router as materials_router
from app.routes.resolved_template import router as resolved_template_router
from app.routes.section_drafts import router as section_drafts_router
from app.services.startup_preflight import run_startup_preflight


def create_app() -> FastAPI:
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Keep existing unprefixed routes used by the current frontend.
    app.include_router(materials_router)
    app.include_router(exports_router)
    app.include_router(fill_results_router)
    app.include_router(gaps_router)
    app.include_router(resolved_template_router)
    app.include_router(section_drafts_router)
    # Add /api-prefixed aliases (requested contract).
    app.include_router(materials_router, prefix="/api")
    app.include_router(exports_router, prefix="/api")
    app.include_router(fill_results_router, prefix="/api")
    app.include_router(gaps_router, prefix="/api")
    app.include_router(resolved_template_router, prefix="/api")
    app.include_router(section_drafts_router, prefix="/api")

    @app.on_event("startup")
    def startup_preflight() -> None:
        # Non-blocking config self-check; emits warnings/errors in logs.
        app.state.preflight = run_startup_preflight()

    return app
