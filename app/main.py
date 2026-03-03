from uuid import UUID

from fastapi import FastAPI, HTTPException

from app.domain.commands import OptimizeRoutes
from app.entrypoints.api.v1.optimization import OptimizeRequest
from app.service_layer import optimize_routes_handler
from app.service_layer.unit_of_work import SqlAlchemyUnitOfWork

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.post("/optimize")
async def create_optimization(request: OptimizeRequest):
    uow = SqlAlchemyUnitOfWork()

    command = OptimizeRoutes(
        target_date=request.target_date,
        timeout_seconds=30
    )

    task_id = await optimize_routes_handler(command, uow)

    return {"task_id": task_id, "status": "queud"}



@app.get("/tasks/{task_id}")
async def get_status(task_id: UUID):
    uow = SqlAlchemyUnitOfWork()

    async with uow:
        task = await uow.optimization_tasks.get(task_id)
        if not task:
            raise HTTPException(404)


        return {
            "task_id": task.id,
            "status": task.status,
            "target_date": task.target_date
        }