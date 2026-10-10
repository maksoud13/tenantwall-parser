from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from app.models import ModifyRequest, ModifyResponse, HealthResponse
from app.modifier import SqlModifier, SUPPORTED_DIALECTS

app = FastAPI(
    title="tenantwall Parser",
    description="Parses SQL and injects tenant filters.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        service="tenantwall Parser",
        version="1.0.0",
        supported_dialects=SUPPORTED_DIALECTS,
    )


@app.post("/api/modify", response_model=ModifyResponse)
def modify(req: ModifyRequest):
    try:
        modifier = SqlModifier(
            dialect=req.dialect,
            excluded_tables=req.excluded_tables,
        )
        result = modifier.add_filter(req.sql, req.column, req.value)
        return ModifyResponse(
            success=True,
            result=result,
            dialect=req.dialect,
            skipped_tables=list(modifier.excluded_tables) if modifier.excluded_tables else None,
        )
    except ValueError as e:
        return ModifyResponse(success=False, error=str(e))
    except Exception as e:
        return ModifyResponse(success=False, error=f"Unexpected error: {e}")


@app.get("/api/modify-from-file", response_model=ModifyResponse)
def modify_from_file(
    file: str = "complex.sql",
    column: str = "tenant_id",
    value: str = "maksoud",
    dialect: str = "oracle",
    excluded: str = "",
):
    """
    Read SQL from a local file and modify it.
    
    Pass excluded tables as comma-separated: excluded=table1,table2
    """
    base_dir = Path(__file__).resolve().parent.parent
    file_path = base_dir / file

    if not file_path.exists():
        return ModifyResponse(success=False, error=f"File not found: {file_path}")

    try:
        sql = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return ModifyResponse(success=False, error=f"Failed to read file: {e}")

    excluded_tables = [t.strip() for t in excluded.split(",") if t.strip()]

    try:
        modifier = SqlModifier(dialect=dialect, excluded_tables=excluded_tables)
        result = modifier.add_filter(sql, column, value)
        return ModifyResponse(
            success=True,
            result=result,
            dialect=dialect,
            skipped_tables=excluded_tables if excluded_tables else None,
        )
    except ValueError as e:
        return ModifyResponse(success=False, error=str(e))
    except Exception as e:
        return ModifyResponse(success=False, error=f"Unexpected error: {e}")
    
    
# =========================================================
# 🎯 NEW: Accept SQL as raw text (no JSON escaping needed)
# =========================================================
@app.post("/api/modify-text", response_class=PlainTextResponse)
async def modify_text(
    request: Request,
    column: str = "tenant_id",
    value: str = "maksoud",
    dialect: str = "oracle",
    excluded: str = "",
):
    """
    Accepts SQL as raw text in the request body.
    No JSON escaping needed. Just paste the SQL directly.

    Usage:
        POST /api/modify-text?column=tenant_id&value=maksoud&dialect=oracle&excluded=table1,table2
        Body: <raw SQL>
    """
    try:
        # Read raw body as SQL
        sql = (await request.body()).decode("utf-8")
    except Exception as e:
        return PlainTextResponse(
            content=f"ERROR reading body: {e}",
            status_code=400,
        )

    if not sql.strip():
        return PlainTextResponse(
            content="ERROR: Empty SQL body",
            status_code=400,
        )

    # Parse excluded list
    excluded_tables = [t.strip() for t in excluded.split(",") if t.strip()]

    try:
        modifier = SqlModifier(dialect=dialect, excluded_tables=excluded_tables)
        result = modifier.add_filter(sql, column, value)
        return PlainTextResponse(content=result)
    except ValueError as e:
        return PlainTextResponse(
            content=f"ERROR: {e}",
            status_code=400,
        )
    except Exception as e:
        return PlainTextResponse(
            content=f"UNEXPECTED ERROR: {e}",
            status_code=500,
        )