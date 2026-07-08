from fastapi import FastAPI, Request, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict, deque
import time
import uuid
import base64

EMAIL = "22f3001101@ds.study.iitm.ac.in"

TOTAL_ORDERS = 42
RATE_LIMIT = 17
WINDOW = 10

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Rate Limiter ----------------

clients = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    # Never rate-limit preflight requests
    if request.method == "OPTIONS":
        return await call_next(request)

    client = request.headers.get("X-Client-Id", "anonymous")

    now = time.time()
    q = clients[client]

    while q and now - q[0] >= WINDOW:
        q.popleft()

    if len(q) >= RATE_LIMIT:
        retry_after = max(1, int(WINDOW - (now - q[0])))
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            content={"detail": "Rate limit exceeded"},
        )

    q.append(now)

    return await call_next(request)


# ---------------- Idempotent Orders ----------------

orders_by_key = {}


@app.post("/orders", status_code=201)
async def create_order(
    request: Request,
    body: dict = Body(default={}),
):
    key = request.headers.get("Idempotency-Key")

    if not key:
        return JSONResponse(
            status_code=400,
            content={"detail": "Missing Idempotency-Key"},
        )

    if key in orders_by_key:
        return JSONResponse(
            status_code=201,
            content=orders_by_key[key],
        )

    order = {"id": str(uuid.uuid4()), **body}

    orders_by_key[key] = order

    return JSONResponse(
        status_code=201,
        content=order,
    )


# ---------------- Pagination ----------------


@app.get("/orders")
async def list_orders(limit: int = 10, cursor: str | None = None):
    if limit < 1:
        limit = 1

    start = 1

    if cursor:
        try:
            start = int(base64.b64decode(cursor).decode())
        except Exception:
            start = 1

    end = min(start + limit - 1, TOTAL_ORDERS)

    items = [{"id": i} for i in range(start, end + 1)]

    next_cursor = None
    if end < TOTAL_ORDERS:
        next_cursor = base64.b64encode(str(end + 1).encode()).decode()

    return {
        "items": items,
        "next_cursor": next_cursor,
    }


@app.get("/")
async def root():
    return {"status": "ok"}
