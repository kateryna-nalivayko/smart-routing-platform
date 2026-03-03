from datetime import time
from typing import Optional, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.domain.commands import CreateTechnician, UpdateTechnician, DeactivateTechnician
from app.entrypoints.api.dependencies import get_uow
from app.service_layer.unit_of_work import AbstractUnitOfWork

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════

class TimeWindowSchema(BaseModel):
    start: time
    end: time


class CreateTechnicianRequest(BaseModel):
    """Створення техніка."""
    name: str = Field(..., min_length=1, max_length=255)
    home_latitude: Optional[float] = None
    home_longitude: Optional[float] = None
    office_latitude: Optional[float] = None
    office_longitude: Optional[float] = None

    # Skills
    skills: List[str] = Field(default_factory=list, description="e.g., ['exterior - senior', 'interior - medior']")

    # Capabilities
    can_work_at_heights: bool = False
    can_use_lift: bool = False
    can_apply_pesticides: bool = False
    is_citizen: bool = False
    is_physically_demanding: bool = False
    has_living_walls: bool = False

    # Working hours (опціонально)
    max_hours_per_day: int = Field(default=8, ge=1, le=24)
    max_hours_per_week: int = Field(default=40, ge=1, le=168)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Smith",
                "skills": ["exterior - senior"],
                "can_work_at_heights": True,
                "is_citizen": True,
                "max_hours_per_day": 8
            }
        }


class TechnicianResponse(BaseModel):
    """Відповідь з даними техніка."""
    id: UUID
    name: str
    skills: List[str]
    is_active: bool

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@router.post("/", response_model=TechnicianResponse, status_code=status.HTTP_201_CREATED)
async def create_technician(
        request: CreateTechnicianRequest,
        uow: AbstractUnitOfWork = Depends(get_uow),
):
    """Створити нового техніка."""
    from app.service_layer.handlers import create_technician_handler

    command = CreateTechnician(
        name=request.name,
        home_latitude=request.home_latitude,
        home_longitude=request.home_longitude,
        office_latitude=request.office_latitude,
        office_longitude=request.office_longitude,
        skills=request.skills,
        can_work_at_heights=request.can_work_at_heights,
        can_use_lift=request.can_use_lift,
        can_apply_pesticides=request.can_apply_pesticides,
        is_citizen=request.is_citizen,
        is_physically_demanding=request.is_physically_demanding,
        has_living_walls=request.has_living_walls,
        max_hours_per_day=request.max_hours_per_day,
        max_hours_per_week=request.max_hours_per_week,
    )

    tech_id = await create_technician_handler(command, uow)

    # Повернути створеного техніка
    async with uow:
        tech = await uow.technicians.get(tech_id)
        return TechnicianResponse(
            id=tech.id,
            name=tech.name,
            skills=[str(s) for s in tech.skills],
            is_active=tech.is_active
        )


@router.get("/", response_model=List[TechnicianResponse])
async def list_technicians(
        active_only: bool = True,
        uow: AbstractUnitOfWork = Depends(get_uow),
):
    """Список техніків."""
    async with uow:
        if active_only:
            techs = await uow.technicians.get_active()
        else:
            # TODO: implement get_all()
            techs = await uow.technicians.get_active()

        return [
            TechnicianResponse(
                id=t.id,
                name=t.name,
                skills=[str(s) for s in t.skills],
                is_active=t.is_active
            )
            for t in techs
        ]


@router.get("/{tech_id}", response_model=TechnicianResponse)
async def get_technician(
        tech_id: UUID,
        uow: AbstractUnitOfWork = Depends(get_uow),
):
    """Отримати техніка за ID."""
    async with uow:
        tech = await uow.technicians.get(tech_id)
        if not tech:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Technician {tech_id} not found"
            )

        return TechnicianResponse(
            id=tech.id,
            name=tech.name,
            skills=[str(s) for s in tech.skills],
            is_active=tech.is_active
        )


@router.delete("/{tech_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_technician(
        tech_id: UUID,
        uow: AbstractUnitOfWork = Depends(get_uow),
):
    """Деактивувати техніка."""
    from app.service_layer.handlers import deactivate_technician_handler

    command = DeactivateTechnician(technician_id=tech_id)
    await deactivate_technician_handler(command, uow)
