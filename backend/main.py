from fastapi import FastAPI

app = FastAPI(title="QalaAI — Akim for 5 Hours")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
