from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from collections import deque
import time
import uuid

app = FastAPI()

EMAIL = "kehachandrakar07@gmail.com"   # Replace with your email

START_TIME = time.time()

# Prometheus Counter
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests"
)

# In-memory logs
logs = deque(maxlen=1000)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    http_requests_total.inc()

    response = await call_next(request)

    logs.append({
        "level": "INFO",
        "ts": time.time(),
        "path": request.url.path,
        "request_id": request_id
    })

    response.headers["X-Request-ID"] = request_id

    return response


@app.get("/")
def root():
    return {"message": "Observable API Running"}


@app.get("/work")
def work(n: int = 1):
    # simulate work
    for _ in range(n):
        pass

    return {
        "email": EMAIL,
        "done": n
    }


@app.get("/metrics")
def metrics():
    return PlainTextResponse(
        generate_latest().decode(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/healthz")
def health():
    return {
        "status": "ok",
        "uptime_s": time.time() - START_TIME
    }


@app.get("/logs/tail")
def tail(limit: int = 10):
    return list(logs)[-limit:]