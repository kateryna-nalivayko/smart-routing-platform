from app.domain.commands import OptimizeRoutes
from app.service_layer.handlers import optimize_routes_handler
from app.service_layer.messagebus import MessageBus
from app.service_layer.unit_of_work import DEFAULT_SESSION_FACTORY, SqlAlchemyUnitOfWork


def get_uow():
    return SqlAlchemyUnitOfWork(DEFAULT_SESSION_FACTORY)


def get_message_bus():
    bus = MessageBus()

    # Register handlers
    bus.register(OptimizeRoutes, optimize_routes_handler)

    return bus
