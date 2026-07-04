from fastapi import FastAPI, Request, Header
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
    allow_origins=[
        "https://exam.sanand.workers.dev",
        "https://tds.s-anand.net",
        "https://tools-in-data-science.pages.dev",
    ],
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
# Fixed Orders
# -----------------------------
orders = [
    {
        "id": i,
        "item": f"Order {i}"
    }
    for i in range(1, TOTAL_ORDERS + 1)
]

# -----------------------------
# Idempotency Store
# -----------------------------
idempotency_store = {}

# -----------------------------
# Rate Limit Store
# -----------------------------
client_requests = defaultdict(list)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    client = request.headers.get("X-Client-Id", "default")

    now = time.time()

    client_requests[client] = [
        t for t in client_requests[client]
        if now - t < WINDOW
    ]

    if len(client_requests[client]) >= RATE_LIMIT:
        retry = int(WINDOW - (now - client_requests[client][0])) + 1

        return JSONResponse(
            status_code=429,
            headers={
                "Retry-After": str(retry)
            },
            content={
                "detail": "Rate limit exceeded"
            },
        )

    client_requests[client].append(now)

    return await call_next(request)


@app.post("/orders")
async def create_order(
    idempotency_key: str = Header(..., alias="Idempotency-Key")
):
    if idempotency_key in idempotency_store:
        return JSONResponse(
            status_code=201,
            content=idempotency_store[idempotency_key]
        )

    order = {
        "id": str(uuid.uuid4()),
        "status": "created"
    }

    idempotency_store[idempotency_key] = order

    return JSONResponse(
        status_code=201,
        content=order
    )


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
        next_cursor = base64.b64encode(
            str(end).encode()
        ).decode()

    return {
        "items": items,
        "next_cursor": next_cursor
    }


@app.get("/")
def root():
    return {
        "message": "Orders API Running"
    }