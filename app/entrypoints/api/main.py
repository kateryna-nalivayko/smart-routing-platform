
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .v1 import optimization

app = FastAPI(
    title="Smart Routing Platform API",
    description="Route optimization for field technicians",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(optimization.router, prefix="/api/v1", tags=["optimization"])


@app.get("/")
async def root():
    return {
        "message": "Smart Routing Platform API",
        "docs": "/docs",
        "version": "0.1.0"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}