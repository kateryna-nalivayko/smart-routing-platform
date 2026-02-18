import abc
from abc import ABC
from datetime import datetime, date
from typing import List
from uuid import UUID


class AbstractTechnicianRepository(ABC):

    @abc.abstractmethod
    async def get(self, tech_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_ids(self, ids: List[UUID]):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_active(self):
        raise NotImplementedError


class AbstractServiceRequestRepository(ABC):

    @abc.abstractmethod
    async def get(self, reqeust_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_ids(self, ids: List[UUID]) -> List:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_pending(self) -> List:
        raise NotImplementedError

    @abc.abstractmethod
    async def update(self, service_request) -> None:
        raise NotImplementedError


class AbstractRouteRepository(ABC):

    @abc.abstractmethod
    async def add(self, route) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_technician_and_date(self, tech_id: UUID, target_date: datetime):
        raise NotImplementedError


class AbstractOptimizationTaskRepository(ABC):

    @abc.abstractmethod
    async def add(self, task) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get(self, task_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def find_in_progress(self, target_date: date):
        raise NotImplementedError

    @abc.abstractmethod
    async def update(self, task) -> None:
        raise NotImplementedError


class AbstractOptimizer(ABC):

    @abc.abstractmethod
    async def solve(self, input):
        raise NotImplemented
