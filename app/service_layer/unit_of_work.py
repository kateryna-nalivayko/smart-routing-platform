import abc
from abc import ABC

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.adapters.ports import (
    AbstractOptimizationTaskRepository,
    AbstractRouteRepository,
    AbstractServiceRequestRepository,
    AbstractTechnicianRepository,
)
from app.config.database import get_postgres_uri

DEFAULT_SESSION_FACTORY = async_sessionmaker(
    bind=create_async_engine(
        get_postgres_uri(),
        echo=True,
        future=True,
    ),
    class_=AsyncSession,
    expire_on_commit=False,
)


class AbstractUnitOfWork(ABC):
    technicians: AbstractTechnicianRepository
    service_requests: AbstractServiceRequestRepository
    routes: AbstractRouteRepository
    optimization_tasks: AbstractOptimizationTaskRepository

    @abc.abstractmethod
    async def __aenter__(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        raise NotImplementedError

    @abc.abstractmethod
    async def commit(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def rollback(self):
        raise NotImplementedError


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    def __init__(self, session_factory=DEFAULT_SESSION_FACTORY):
        self.session_factory = session_factory

    async def __aenter__(self):
        self.session = self.session_factory()

        from app.adapters.repositories import (
            SqlAlchemyOptimizationTaskRepository,
            SqlAlchemyRouteRepository,
            SqlAlchemyServiceRequestRepository,
            SqlAlchemyTechnicianRepository,
        )

        self.technicians = SqlAlchemyTechnicianRepository(self.session)
        self.service_requests = SqlAlchemyServiceRequestRepository(self.session)
        self.routes = SqlAlchemyRouteRepository(self.session)
        self.optimization_tasks = SqlAlchemyOptimizationTaskRepository(self.session)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.rollback()

        await self.session.close()

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()
