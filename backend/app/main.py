from fastapi import FastAPI
from backend.app.api.routes import router
app = FastAPI(
    title="Sentinel GRC",
    description="Security Configuration & Compliance Platform",
    version="1.0.0", 
)

@app.get("/health")
def health_check():
    return {
        "status":"ok",
        "service":"sentinel-grc",
    }
app.include_router(router)