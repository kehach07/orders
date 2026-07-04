from fastapi import FastAPI, Request, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from collections import defaultdict
import time
import uuid
import base64

app = FastAPI()

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # If the exam requires a specific origin, replace "*" with it.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
    
# -----------------------------
# Fixed catalog
# -----------------------------
TOTAL_ORDERS = 59

orders = [
    {
        "id": i,
        "item": f"Order {i}"
    }
    for i in range(1, TOTAL_ORDERS + 1)
]

# -----------------------------
# Idempotency
# -----------------------------
idempotency_store = {}

# -----------------------------
# Rate limiting
# -----------------------------
RATE_LIMIT = 18
WINDOW = 10

buckets = defaultdict(list)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    client = request.headers.get("X-Client-Id", "anonymous")

    now = time.time()

    buckets[client] = [
        t for t in buckets[client]
        if now - t < WINDOW
    ]

    if len(buckets[client]) >= RATE_LIMIT:
        retry_after = int(WINDOW - (now - buckets[client][0])) + 1

        return JSONResponse(
            status_code=429,
            headers={
                "Retry-After": str(retry_after)
            },
            content={
                "detail": "Rate limit exceeded"
            },
        )

    buckets[client].append(now)

    return await call_next(request)


# -----------------------------
# Idempotent POST
# -----------------------------
@app.post("/orders", status_code=201)
def create_order(
    idempotency_key: str = Header(..., alias="Idempotency-Key")
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
# Cursor Pagination
# -----------------------------
@app.get("/orders")
def list_orders(
    limit: int = 10,
    cursor: Optional[str] = None,
):
    start = 0

    if cursor:
        start = int(
            base64.b64decode(cursor).decode()
        )

    end = min(start + limit, TOTAL_ORDERS)

    items = orders[start:end]

    next_cursor = None

    if end < TOTAL_ORDERS:
        next_cursor = base64.b64encode(
            str(end).encode()
        ).decode()

    return {
        "items": items,
        "next_cursor": next_cursor,
    }