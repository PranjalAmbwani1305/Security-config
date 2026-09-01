from fastapi import FastAPI
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