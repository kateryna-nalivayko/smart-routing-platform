"""
adapters/repositories/service_request.py
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.orm import ServiceSite as ServiceRequestORM
from app.adapters.ports import AbstractServiceRequestRepository
from app.domain.aggregates import ServiceRequest


class SqlAlchemyServiceRequestRepository(AbstractServiceRequestRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, request_id: UUID) -> ServiceRequest | None:
        result = await self.session.execute(
            select(ServiceRequestORM).where(ServiceRequestORM.id == request_id)
        )
        return result.scalar_one_or_none()

    async def get_by_ids(self, ids: list[UUID]) -> list[ServiceRequest]:
        result = await self.session.execute(
            select(ServiceRequestORM).where(ServiceRequestORM.id.in_(ids))
        )
        return list(result.scalars().all())

    async def get_pending(self) -> list[ServiceRequest]:
        from app.adapters.orm.base import ServiceStatus
        result = await self.session.execute(
            select(ServiceRequestORM).where(
                ServiceRequestORM.status == ServiceStatus.PENDING
            )
        )
        return list(result.scalars().all())

    async def update(self, service_request: ServiceRequest) -> None:
        # SQLAlchemy tracks changes automatically
        pass
