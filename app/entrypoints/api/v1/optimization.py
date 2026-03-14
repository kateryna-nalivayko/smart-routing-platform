import json
from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.adapters.optimization.excel_oasis_loader import load_oasis_exterior_excel
from app.adapters.optimization.oasis_week_builder import build_week_request_from_oasis
from app.adapters.optimization.or_tools_solver import _eligible_vehicle_ids
from app.adapters.orm import OptimizationTask, Route, RouteStop
from app.config.settings import EXCEL_FILE_PATH, OUTPUT_DIR
from app.domain.commands import OptimizeRoutes
from app.entrypoints.api.dependencies import get_uow
from app.service_layer.handlers import get_task_status_handler, optimize_routes_handler
from app.service_layer.unit_of_work import AbstractUnitOfWork

router = APIRouter()
UoWDep = Annotated[AbstractUnitOfWork, Depends(get_uow)]


class OptimizeRequest(BaseModel):
    target_date: date = Field(..., description="Target date for route optimization", example="2026-02-20")
    timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Timeout for optimization in seconds (5-300)",
        example=30,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "target_date": "2026-02-20",
                "timeout_seconds": 30,
            }
        }


class OptimizeResponse(BaseModel):
    task_id: UUID = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Initial status (always 'queued')")
    message: str = Field(..., description="Instructions for checking status")


class TaskStatusResponse(BaseModel):
    task_id: UUID
    status: str
    target_date: date
    routes_created: int | None = None
    sites_unassigned: int | None = None
    total_distance_km: float | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RouteStopResponse(BaseModel):
    sequence_number: int
    service_site_id: UUID
    site_code: str | None
    site_name: str | None
    arrival_time: datetime
    departure_time: datetime
    travel_time_minutes: int | None
    distance_km: float | None


class RouteResponse(BaseModel):
    route_id: UUID
    technician_id: UUID
    technician_name: str | None
    route_date: date
    stops_count: int
    total_distance_km: float | None
    total_duration_minutes: int | None
    total_travel_time_minutes: int | None
    stops: list[RouteStopResponse]


class TaskRoutesResponse(BaseModel):
    task_id: UUID
    status: str
    target_date: date
    routes_created: int | None
    sites_unassigned: int | None
    routes: list[RouteResponse]


class ExplainReasonItem(BaseModel):
    reason: str
    count: int
    details: str


class TaskExplainResponse(BaseModel):
    task_id: UUID
    target_date: date
    status: str
    total_requested_visits: int
    assigned_estimate: int
    unassigned_count: int
    reasons: list[ExplainReasonItem]


class ScheduleLogItem(BaseModel):
    date: date
    day_of_week: str
    start_time: str
    end_time: str
    technician_name: str
    location_name: str
    location_to: str | None
    activity_type: str


class ConstraintItem(BaseModel):
    name: str
    status: str
    details: str


class ConstraintSummaryResponse(BaseModel):
    accounted_constraints: list[ConstraintItem]
    not_accounted_constraints: list[ConstraintItem]


class TaskArtifactsResponse(BaseModel):
    task_id: UUID
    schedule_json_path: str
    schedule_excel_path: str
    constraints_json_path: str


def _serialize_route(orm_route: Route) -> RouteResponse:
    stops = sorted(orm_route.stops or [], key=lambda x: x.sequence_number)
    return RouteResponse(
        route_id=orm_route.id,
        technician_id=orm_route.technician_id,
        technician_name=orm_route.technician.name if orm_route.technician else None,
        route_date=orm_route.route_date,
        stops_count=orm_route.stops_count,
        total_distance_km=float(orm_route.total_distance_km) if orm_route.total_distance_km is not None else None,
        total_duration_minutes=orm_route.total_duration_minutes,
        total_travel_time_minutes=orm_route.total_travel_time_minutes,
        stops=[
            RouteStopResponse(
                sequence_number=s.sequence_number,
                service_site_id=s.service_site_id,
                site_code=s.service_site.site_code if s.service_site else None,
                site_name=s.service_site.site_name if s.service_site else None,
                arrival_time=s.arrival_time,
                departure_time=s.departure_time,
                travel_time_minutes=s.travel_time_from_previous_minutes,
                distance_km=float(s.distance_from_previous_km) if s.distance_from_previous_km is not None else None,
            )
            for s in stops
        ],
    )


@router.post(
    "/optimize",
    response_model=OptimizeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create optimization task",
)
async def create_optimization_task(
    request: OptimizeRequest,
    uow: UoWDep,
):
    try:
        command = OptimizeRoutes(
            target_date=request.target_date,
            timeout_seconds=request.timeout_seconds,
        )
        task_id = await optimize_routes_handler(command, uow)
        return OptimizeResponse(
            task_id=task_id,
            status="queued",
            message=f"Task queued. Use GET /tasks/{task_id} to check status",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal error: {str(e)}") from e


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
    summary="Get task status",
)
async def get_task_status(
    task_id: UUID,
    uow: UoWDep,
):
    try:
        status_dict = await get_task_status_handler(task_id, uow)
        return TaskStatusResponse(**status_dict)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal error: {str(e)}") from e


@router.get(
    "/tasks/{task_id}/routes",
    response_model=TaskRoutesResponse,
    summary="Get routes for optimization task",
)
async def get_routes_by_task(
    task_id: UUID,
    uow: UoWDep,
):
    async with uow:
        task = await uow.optimization_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

        stmt = (
            select(Route)
            .where(Route.route_date == task.target_date)
            .options(
                selectinload(Route.technician),
                selectinload(Route.stops).selectinload(RouteStop.service_site),
            )
            .order_by(Route.route_date, Route.technician_id)
        )
        result = await uow.session.execute(stmt)
        routes = result.scalars().all()

        return TaskRoutesResponse(
            task_id=task.id,
            status=task.status.value,
            target_date=task.target_date,
            routes_created=task.routes_created,
            sites_unassigned=task.sites_unassigned,
            routes=[_serialize_route(r) for r in routes],
        )


@router.get(
    "/routes",
    response_model=list[RouteResponse],
    summary="Get optimized routes",
)
async def get_routes(
    uow: UoWDep,
    target_date: date | None = None,
    technician_id: UUID | None = None,
    limit: int = 200,
):
    async with uow:
        stmt = (
            select(Route)
            .options(
                selectinload(Route.technician),
                selectinload(Route.stops).selectinload(RouteStop.service_site),
            )
            .order_by(Route.route_date.desc())
            .limit(max(1, min(limit, 1000)))
        )

        if target_date is not None:
            stmt = stmt.where(Route.route_date == target_date)
        if technician_id is not None:
            stmt = stmt.where(Route.technician_id == technician_id)

        result = await uow.session.execute(stmt)
        routes = result.scalars().all()
        return [_serialize_route(r) for r in routes]


@router.get(
    "/tasks",
    response_model=list[TaskStatusResponse],
    summary="List optimization tasks",
)
async def list_tasks(
    uow: UoWDep,
    limit: int = 50,
):
    async with uow:
        stmt = (
            select(OptimizationTask)
            .order_by(OptimizationTask.created_at.desc())
            .limit(max(1, min(limit, 500)))
        )
        result = await uow.session.execute(stmt)
        tasks = result.scalars().all()

        return [
            TaskStatusResponse(
                task_id=t.id,
                status=t.status.value,
                target_date=t.target_date,
                routes_created=t.routes_created,
                sites_unassigned=t.sites_unassigned,
                total_distance_km=float(t.total_distance_km) if t.total_distance_km is not None else None,
                error_message=t.error_message,
                created_at=t.created_at,
                started_at=t.started_at,
                completed_at=t.completed_at,
            )
            for t in tasks
        ]


@router.get(
    "/tasks/{task_id}/explain",
    response_model=TaskExplainResponse,
    summary="Explain why visits were unassigned",
)
async def explain_task(
    task_id: UUID,
    uow: UoWDep,
):
    async with uow:
        task = await uow.optimization_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    try:
        sites, techs = load_oasis_exterior_excel(str(EXCEL_FILE_PATH))
        req = build_week_request_from_oasis(task.target_date, sites, techs)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cannot build explanation dataset: {e}",
        ) from e

    reason_counts = {
        "no_eligible_technician": 0,
        "overflow_guard_limit": 0,
        "optimizer_or_capacity": 0,
    }

    total_requested_visits = 0
    for day_plan in req.day_plans:
        total_requested_visits += len(day_plan.visits)
        max_visits_for_solve = max(30, len(day_plan.technicians) * 8)

        for idx, visit in enumerate(day_plan.visits):
            allowed = _eligible_vehicle_ids(visit, day_plan.technicians)
            if not allowed:
                reason_counts["no_eligible_technician"] += 1
            elif idx >= max_visits_for_solve:
                reason_counts["overflow_guard_limit"] += 1
            else:
                reason_counts["optimizer_or_capacity"] += 1

    unassigned_count = int(task.sites_unassigned or 0)
    assigned_estimate = max(0, total_requested_visits - unassigned_count)

    optimistic_candidates = reason_counts["optimizer_or_capacity"]
    adjusted_optimizer_bucket = min(optimistic_candidates, unassigned_count)
    already_explained = reason_counts["no_eligible_technician"] + reason_counts["overflow_guard_limit"]
    remaining_unassigned = max(0, unassigned_count - already_explained)
    adjusted_optimizer_bucket = max(adjusted_optimizer_bucket, remaining_unassigned)

    reasons = [
        ExplainReasonItem(
            reason="no_eligible_technician",
            count=reason_counts["no_eligible_technician"],
            details="Візит не має жодного техніка, що проходить hard-обмеження (skills/capabilities/preferences).",
        ),
        ExplainReasonItem(
            reason="overflow_guard_limit",
            count=reason_counts["overflow_guard_limit"],
            details="Візит не потрапив у solve-вікно дня через захисний ліміт розміру задачі.",
        ),
        ExplainReasonItem(
            reason="optimizer_or_capacity",
            count=adjusted_optimizer_bucket,
            details="Кандидатні візити, які не вмістилися у часові вікна/змінні ліміти або були відсічені оптимізацією.",
        ),
    ]

    return TaskExplainResponse(
        task_id=task.id,
        target_date=task.target_date,
        status=task.status.value,
        total_requested_visits=total_requested_visits,
        assigned_estimate=assigned_estimate,
        unassigned_count=unassigned_count,
        reasons=reasons,
    )


@router.get(
    "/tasks/{task_id}/schedule-log",
    response_model=list[ScheduleLogItem],
    summary="Get exported schedule log",
)
async def get_schedule_log(task_id: UUID):
    schedule_path = OUTPUT_DIR / str(task_id) / "schedule_log.json"
    if not schedule_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule log not found")
    return json.loads(schedule_path.read_text(encoding="utf-8"))


@router.get(
    "/tasks/{task_id}/constraints",
    response_model=ConstraintSummaryResponse,
    summary="Get accounted and missing constraints",
)
async def get_constraints_summary(task_id: UUID):
    constraints_path = OUTPUT_DIR / str(task_id) / "constraints_summary.json"
    if not constraints_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Constraints summary not found")
    return json.loads(constraints_path.read_text(encoding="utf-8"))


@router.get(
    "/tasks/{task_id}/artifacts",
    response_model=TaskArtifactsResponse,
    summary="Get generated artifact paths",
)
async def get_task_artifacts(task_id: UUID):
    task_dir = OUTPUT_DIR / str(task_id)
    schedule_json_path = task_dir / "schedule_log.json"
    schedule_excel_path = task_dir / "schedule_log.xlsx"
    constraints_json_path = task_dir / "constraints_summary.json"

    if not schedule_json_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifacts not found")

    return TaskArtifactsResponse(
        task_id=task_id,
        schedule_json_path=str(schedule_json_path),
        schedule_excel_path=str(schedule_excel_path),
        constraints_json_path=str(constraints_json_path),
    )
