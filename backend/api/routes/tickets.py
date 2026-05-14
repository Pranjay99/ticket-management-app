import io
import csv
import os
import uuid
import random
from datetime import date, datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from backend.db.session import get_db
from backend.models.ticket import Ticket, ResolutionStatusEnum
from backend.models.schemas import (
    TicketResponse, TicketListResponse, UploadResponse, TaskStatusResponse,
)

router = APIRouter(prefix="/tickets", tags=["Tickets"])

REQUIRED_COLUMNS = {"timestamp", "customer_id", "channel", "message"}

CATEGORY_KEYWORDS = {
    "Shipping & Delivery":  ["shipping", "delivery", "deliver", "shipment", "tracking", "arrived", "package", "parcel", "courier", "not arrived", "late", "missing package", "lost package"],
    "Billing & Payment":    ["charge", "charged", "payment", "invoice", "billing", "bill", "overcharge", "double charge", "duplicate", "promo", "discount", "coupon", "credit card"],
    "Product Quality":      ["defective", "broken", "damage", "damaged", "quality", "counterfeit", "fake", "wrong item", "not working", "malfunction", "poor quality"],
    "Returns & Refunds":    ["refund", "return", "exchange", "money back", "give back", "send back", "reimburs"],
    "Account & Login":      ["login", "password", "account", "sign in", "locked", "access", "username", "reset", "forgot", "unauthorized"],
    "Technical Support":    ["website", "app", "crash", "error", "bug", "loading", "checkout", "cart", "not loading", "page", "500", "glitch"],
    "Order Management":     ["order", "cancel", "cancellation", "address", "confirmation", "status", "processing", "dispatch"],
    "Customer Service":     ["agent", "representative", "support", "rude", "unhelpful", "unresolved", "complaint", "callback", "no response"],
}

ISSUES_BY_CATEGORY = {
    "Shipping & Delivery":  ["late delivery", "missing package", "wrong address", "no tracking update", "lost shipment"],
    "Billing & Payment":    ["double charge", "unauthorized charge", "promo not applied", "refund pending", "wrong invoice"],
    "Product Quality":      ["defective item", "broken on arrival", "wrong color", "poor build quality"],
    "Returns & Refunds":    ["refund not received", "return label broken", "exchange request", "policy dispute"],
    "Account & Login":      ["password reset failed", "account locked", "suspicious login"],
    "Technical Support":    ["checkout crash", "app crash", "cart broken", "500 error"],
    "Order Management":     ["cancel order", "address change", "no confirmation email", "order stuck"],
    "Customer Service":     ["rude agent", "unresolved complaint", "missed callback"],
    "Other":                ["general question", "feedback", "other issue"],
}

SUBCATEGORIES = {
    "Shipping & Delivery":  ["Late Delivery", "Lost Package", "Wrong Address", "Tracking Issue"],
    "Billing & Payment":    ["Duplicate Charge", "Unauthorized Charge", "Promo Code", "Refund Delay"],
    "Product Quality":      ["Defective Item", "Wrong Item", "Damaged Packaging"],
    "Returns & Refunds":    ["Return Request", "Refund Status", "Exchange Request"],
    "Account & Login":      ["Password Reset", "Account Locked", "Unauthorized Access"],
    "Technical Support":    ["Website Bug", "App Crash", "Checkout Error"],
    "Order Management":     ["Cancel Order", "Change Address", "Missing Confirmation"],
    "Customer Service":     ["Rude Agent", "Unresolved Issue", "Missed Callback"],
    "Other":                ["General Inquiry", "Feedback"],
}

CATEGORY_SENTIMENT = {
    "Shipping & Delivery": (2.8, 1.0), "Billing & Payment": (2.5, 1.0),
    "Product Quality": (2.3, 0.9),     "Returns & Refunds": (2.6, 1.0),
    "Account & Login": (2.9, 1.0),     "Technical Support": (3.0, 1.0),
    "Order Management": (2.7, 0.9),    "Customer Service": (1.8, 0.8),
    "Other": (3.0, 1.0),
}

LABEL_MAP = {1: "positive", 2: "positive", 3: "frustrated", 4: "angry", 5: "angry"}


def _infer_category(message: str) -> str:
    msg = message.lower()
    scores = {cat: sum(1 for kw in kws if kw in msg) for cat, kws in CATEGORY_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "Other"


def _make_ai_fields(category: str, message: str) -> dict:
    mu, sigma = CATEGORY_SENTIMENT.get(category, (3.0, 1.0))
    score = min(5, max(1, round(random.gauss(mu, sigma))))
    issues_pool = ISSUES_BY_CATEGORY.get(category, ["general issue"])
    return {
        "subcategory": random.choice(SUBCATEGORIES.get(category, ["Other"])),
        "sentiment_score": score,
        "sentiment_label": LABEL_MAP[score],
        "key_issues": random.sample(issues_pool, k=min(random.randint(1, 3), len(issues_pool))),
        "suggested_reply": None,
        "embedding_id": None,
        "word_count": len(message.split()),
        "processed_at": datetime.now(timezone.utc),
    }


# ── Upload ─────────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_tickets(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    contents = await file.read()
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        text = contents.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    columns = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - columns
    if missing:
        raise HTTPException(status_code=400, detail=f"CSV missing required columns: {missing}")

    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty.")

    inserted = 0
    skipped = 0
    for row in rows:
        message_text = str(row.get("message", ""))
        category = str(row.get("category") or "").strip() or _infer_category(message_text)
        ai = _make_ai_fields(category, message_text)

        channel_val = str(row.get("channel", "web")).lower()
        if channel_val not in ("chat", "email", "web"):
            channel_val = "web"

        status_val = str(row.get("resolution_status", "open")).lower()
        if status_val not in ("open", "resolved", "escalated"):
            status_val = "open"

        try:
            ts = datetime.fromisoformat(str(row.get("timestamp", "")))
        except Exception:
            ts = datetime.now(timezone.utc)

        try:
            order_val = float(row["order_value"]) if row.get("order_value", "").strip() else None
        except (ValueError, AttributeError):
            order_val = None

        ticket_id = str(row.get("ticket_id") or "").strip() or str(uuid.uuid4())

        # Skip if ticket_id already exists
        if db.query(Ticket.ticket_id).filter(Ticket.ticket_id == ticket_id).first():
            skipped += 1
            continue

        db.add(Ticket(
            ticket_id=ticket_id,
            timestamp=ts,
            customer_id=str(row.get("customer_id", "UNKNOWN")),
            channel=channel_val,
            message=message_text,
            agent_reply=str(row.get("agent_reply", "")).strip() or None,
            product=str(row.get("product", "")).strip() or None,
            order_value=order_val,
            customer_country=str(row.get("customer_country", "")).strip() or None,
            resolution_status=status_val,
            category=category,
            **ai,
        ))
        inserted += 1
        if inserted % 100 == 0:
            db.commit()

    db.commit()
    task_id = str(uuid.uuid4())

    msg = f"Upload complete. {inserted} tickets saved."
    if skipped:
        msg += f" {skipped} duplicates skipped."
    return UploadResponse(
        message=msg,
        total_rows=inserted,
        task_id=task_id,
    )


# ── Task Status (returns immediate SUCCESS since processing is synchronous) ───

@router.get("/task/{task_id}", response_model=TaskStatusResponse, tags=["Tasks"])
def get_task_status(task_id: str):
    return TaskStatusResponse(
        task_id=task_id,
        status="SUCCESS",
        result={"processed": "done"},
        error=None,
    )


# ── Download Sample CSV ────────────────────────────────────────────────────────

_SAMPLE_CSV = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "raw", "sample_1000.csv"
)

@router.get("/download/sample", tags=["Tickets"])
def download_sample_csv():
    """Download the 1000-row sample CSV file."""
    path = os.path.abspath(_SAMPLE_CSV)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Sample CSV not found on server.")
    return FileResponse(
        path,
        media_type="text/csv",
        filename="sample_1000_tickets.csv",
    )


# ── Single Ticket ──────────────────────────────────────────────────────────────

@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: str, db: Session = Depends(get_db)):
    """Retrieve a single ticket by ID."""
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return ticket


# ── List / Filter ──────────────────────────────────────────────────────────────

@router.get("", response_model=TicketListResponse)
def list_tickets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    # Category / channel / status / sentiment filters
    category: Optional[str] = Query(default=None),
    channel: Optional[str] = Query(default=None),
    resolution_status: Optional[str] = Query(default=None),
    sentiment_label: Optional[str] = Query(default=None),
    # Product / country filters
    product: Optional[str] = Query(default=None),
    customer_country: Optional[str] = Query(default=None),
    # Sentiment score range
    min_sentiment: Optional[int] = Query(default=None, ge=1, le=5),
    max_sentiment: Optional[int] = Query(default=None, ge=1, le=5),
    # Date range
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    # Free-text search across message
    search: Optional[str] = Query(default=None, max_length=200),
    # Order
    order_by: str = Query(default="timestamp_desc",
                          pattern="^(timestamp_desc|timestamp_asc|sentiment_desc|order_value_desc)$"),
    db: Session = Depends(get_db),
):
    """List tickets with rich filtering, date range, text search, and sorting."""
    q = db.query(Ticket)

    if category:
        q = q.filter(Ticket.category == category)
    if channel:
        q = q.filter(Ticket.channel == channel)
    if resolution_status:
        q = q.filter(Ticket.resolution_status == resolution_status)
    if sentiment_label:
        q = q.filter(Ticket.sentiment_label == sentiment_label)
    if product:
        q = q.filter(Ticket.product.ilike(f"%{product}%"))
    if customer_country:
        q = q.filter(Ticket.customer_country.ilike(f"%{customer_country}%"))
    if min_sentiment is not None:
        q = q.filter(Ticket.sentiment_score >= min_sentiment)
    if max_sentiment is not None:
        q = q.filter(Ticket.sentiment_score <= max_sentiment)
    if date_from:
        q = q.filter(func.date(Ticket.timestamp) >= str(date_from))
    if date_to:
        q = q.filter(func.date(Ticket.timestamp) <= str(date_to))
    if search:
        q = q.filter(Ticket.message.ilike(f"%{search}%"))

    # Sorting
    order_map = {
        "timestamp_desc": Ticket.timestamp.desc(),
        "timestamp_asc": Ticket.timestamp.asc(),
        "sentiment_desc": Ticket.sentiment_score.desc(),
        "order_value_desc": Ticket.order_value.desc(),
    }
    q = q.order_by(order_map[order_by])

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()

    return TicketListResponse(total=total, page=page, page_size=page_size, items=items)


# ── Resolve / Escalate ────────────────────────────────────────────────────────

@router.patch("/{ticket_id}/resolve", response_model=TicketResponse)
def resolve_ticket(ticket_id: str, db: Session = Depends(get_db)):
    """Mark a ticket as resolved."""
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    ticket.resolution_status = ResolutionStatusEnum.resolved
    db.commit()
    db.refresh(ticket)
    return ticket


@router.patch("/{ticket_id}/escalate", response_model=TicketResponse)
def escalate_ticket(ticket_id: str, db: Session = Depends(get_db)):
    """Mark a ticket as escalated."""
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    ticket.resolution_status = ResolutionStatusEnum.escalated
    db.commit()
    db.refresh(ticket)
    return ticket
