from pydantic import BaseModel, Field
from typing import Optional, List


class ModifyRequest(BaseModel):
    sql: str = Field(..., description="The SQL SELECT query to modify")
    column: str = Field(default="tenant_id", description="Column name to filter on")
    value: str = Field(..., description="Value to filter by")
    dialect: str = Field(default="mysql", description="SQL dialect")
    excluded_tables: Optional[List[str]] = Field(
        default=None,
        description="List of table names to skip. No filter will be added to them.",
        examples=[["countries", "currencies", "audit_log"]]
    )


class ModifyResponse(BaseModel):
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    dialect: Optional[str] = None
    skipped_tables: Optional[List[str]] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    supported_dialects: list[str]