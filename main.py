from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from collections import defaultdict, deque
import time
import uuid
import base64

EMAIL = "22f3001101@ds.study.iitm.ac.in"

TOTAL_ORDERS = 42
RATE_LIMIT = 17
WINDOW = 10  # seconds

app = FastAPI()

# Allow browser-based grader
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Rate Limiting
# -------------------------------
clients = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    client = request.headers.get("X-Client-Id", "anonymous")

    now = time.time()
    q = clients[client]

    while q and now - q[0] >= WINDOW:
        q.popleft()

    if len(q) >= RATE_LIMIT:
        retry_after = max(1, int(WINDOW - (now - q[0])))
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": str(retry_after)},
        )

    q.append(now)

    return await call_next(request)


# -------------------------------
# Idempotent POST
# -------------------------------
orders_by_key = {}


class Order(BaseModel):
    item: str = "default-item"


@app.post("/orders", status_code=201)
def create_order(order: Order, request: Request):
    key = request.headers.get("Idempotency-Key")

    if not key:
        return JSONResponse(
            status_code=400,
            content={"detail": "Missing Idempotency-Key"},
        )

    if key in orders_by_key:
        return orders_by_key[key]

    new_order = {
        "id": str(uuid.uuid4()),
        "item": order.item,
    }

    orders_by_key[key] = new_order

    return new_order


# -------------------------------
# Cursor Pagination
# -------------------------------
@app.get("/orders")
def list_orders(limit: int = 10, cursor: str | None = None):
    start = 1

    if cursor:
        start = int(base64.b64decode(cursor).decode())

    end = min(start + limit - 1, TOTAL_ORDERS)

    items = [{"id": i} for i in range(start, end + 1)]

    next_cursor = None
    if end < TOTAL_ORDERS:
        next_cursor = base64.b64encode(str(end + 1).encode()).decode()

    return {
        "items": items,
        "next_cursor": next_cursor,
    }
