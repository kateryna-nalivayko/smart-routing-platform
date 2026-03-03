from collections.abc import Callable

from app.domain.commands import Command


class MessageBus:
    """Simple message bus for handling commands."""

    def __init__(self):
        self.handlers: dict[type[Command], Callable] = {}

    def register(self, command_type: type[Command], handler: Callable):
        """Register handler for command type."""
        self.handlers[command_type] = handler

    async def handle(self, command: Command):
        """Handle command by calling registered handler."""
        handler = self.handlers.get(type(command))
        if not handler:
            raise ValueError(f"No handler for {type(command)}")

        return await handler(command)
