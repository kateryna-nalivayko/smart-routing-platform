from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.domain.commands import OptimizeRoutes
from app.entrypoints.api.dependencies import get_uow
from app.service_layer.handlers import get_task_status_handler, optimize_routes_handler
from app.service_layer.unit_of_work import AbstractUnitOfWork

router = APIRouter()


class OptimizeRequest(BaseModel):
    """
    Request to create optimization task.

    Attributes:
        target_date: Date for which to optimize routes
        timeout_seconds: Maximum time for OR-Tools solver (default: 30s)
    """
    target_date: date = Field(
        ...,
        description="Target date for route optimization",
        example="2026-02-20"
    )
    timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Timeout for optimization in seconds (5-300)",
        example=30
    )

    class Config:
        json_schema_extra = {
            "example": {
                "target_date": "2026-02-20",
                "timeout_seconds": 30
            }
        }


class OptimizeResponse(BaseModel):
    """
    Response with task ID.

    Client should poll GET /tasks/{task_id} to check status.
    """
    task_id: UUID = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Initial status (always 'queued')")
    message: str = Field(..., description="Instructions for checking status")


class TaskStatusResponse(BaseModel):
    """
    Task status response.

    Statuses:
    - queued: Task is waiting for processing
    - processing: OR-Tools is solving
    - success: Optimization completed
    - failed: Optimization failed
    """
    task_id: UUID
    status: str
    target_date: date

    # Results (available when status=success)
    routes_created: Optional[int] = None
    sites_unassigned: int | None = None
    total_distance_km: float | None = None

    # Error info (available when status=failed)
    error_message: str | None = None

    # Timestamps
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


# ══════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@router.post(
    "/optimize",
    response_model=OptimizeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create optimization task",
    description="""
    Create a new route optimization task.
    
    The task will be queued and processed asynchronously.
    Use GET /tasks/{task_id} to check the status.
    
    Process:
    1. Creates OptimizationTask record (status=QUEUED)
    2. Returns task_id immediately
    3. Background worker processes the task
    4. Client polls GET /tasks/{task_id} for results
    """,
    responses={
        202: {"description": "Task queued successfully"},
        409: {"description": "Task for this date already in progress"},
        500: {"description": "Internal server error"},
    }
)
async def create_optimization_task(
        request: OptimizeRequest,
        uow: AbstractUnitOfWork = Depends(get_uow),
):
    """Create optimization task."""
    try:
        command = OptimizeRoutes(
            target_date=request.target_date,
            timeout_seconds=request.timeout_seconds,
        )

        task_id = await optimize_routes_handler(command, uow)

        return OptimizeResponse(
            task_id=task_id,
            status="queued",
            message=f"Task queued. Use GET /tasks/{task_id} to check status"
        )

    except ValueError as e:
        # Business rule violation (e.g., task already in progress)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        ) from e

    except Exception as e:
        # Unexpected error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}"
        ) from e


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
    summary="Get task status",
    description="""
    Get the status of an optimization task.
    
    Poll this endpoint every 2-3 seconds until status is 'success' or 'failed'.
    
    Status progression:
    queued → processing → success/failed
    """,
    responses={
        200: {"description": "Task status retrieved"},
        404: {"description": "Task not found"},
        500: {"description": "Internal server error"},
    }
)
async def get_task_status(
        task_id: UUID,
        uow: AbstractUnitOfWork = Depends(get_uow),
):
    """Get optimization task status."""
    try:
        status_dict = await get_task_status_handler(task_id, uow)
        return TaskStatusResponse(**status_dict)

    except ValueError as e:
        # Task not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e

    except Exception as e:
        # Unexpected error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}"
        ) from e


@router.get(
    "/routes",
    summary="Get optimized routes",
    description="Retrieve optimized routes. NOT IMPLEMENTED YET.",
    responses={
        501: {"description": "Not implemented"},
    }
)
async def get_routes(
        date: date | None = None,
        technician_id: UUID | None = None,
):
    """
    Get optimized routes.

    TODO: Implement route retrieval from database.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Route retrieval not implemented yet"
    )
