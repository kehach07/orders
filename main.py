from fastapi import FastAPI, Request, Header, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from collections import defaultdict
import uuid
import time
import base64

app = FastAPI()

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)

# -----------------------------
# CONFIG
# -----------------------------
TOTAL_ORDERS = 59
RATE_LIMIT = 18
WINDOW = 10

# -----------------------------
# Fixed catalog
# -----------------------------
orders = [{"id": i, "item": f"Order {i}"} for i in range(1, TOTAL_ORDERS + 1)]

# -----------------------------
# Stores
# -----------------------------
idempotency_store = {}
client_requests = defaultdict(list)

# -----------------------------
# Rate Limiter
# -----------------------------
@app.middleware("http")
async def rate_limit(request: Request, call_next):
    client = request.headers.get("X-Client-Id", "default")
    now = time.time()

    client_requests[client] = [
        t for t in client_requests[client]
        if now - t < WINDOW
    ]

    if len(client_requests[client]) >= RATE_LIMIT:
        retry = max(1, int(WINDOW - (now - client_requests[client][0])))

        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": str(retry)},
        )

    client_requests[client].append(now)

    return await call_next(request)


# -----------------------------
# Root
# -----------------------------
@app.get("/")
def root():
    return {"message": "Orders API Running"}


# -----------------------------
# POST /orders
# -----------------------------
@app.post("/orders", status_code=201)
async def create_order(
    body: dict = Body(default={}),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid.uuid4()),
        "status": "created",
    }

    idempotency_store[idempotency_key] = order

    return order


# -----------------------------
# GET /orders
# -----------------------------
@app.get("/orders")
async def get_orders(
    limit: int = 10,
    cursor: Optional[str] = None,
):
    start = 0

    if cursor:
        try:
            start = int(base64.b64decode(cursor).decode())
        except Exception:
            start = 0

    end = min(start + limit, TOTAL_ORDERS)

    items = orders[start:end]

    next_cursor = None
    if end < TOTAL_ORDERS:
        next_cursor = base64.b64encode(str(end).encode()).decode()

    return {
        "items": items,
        "next_cursor": next_cursor,
    }