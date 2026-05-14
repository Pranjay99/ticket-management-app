import csv
import io
import os
import random
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.models.ticket import Ticket
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_SAMPLE_CSV = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "raw", "sample_1000.csv"
)

CATEGORY_KEYWORDS = {
    "Shipping & Delivery":  ["shipping","delivery","deliver","shipment","tracking","arrived","package","parcel","courier","not arrived","late","missing package","lost package"],
    "Billing & Payment":    ["charge","charged","payment","invoice","billing","bill","overcharge","double charge","duplicate","promo","discount","coupon","credit card"],
    "Product Quality":      ["defective","broken","damage","damaged","quality","counterfeit","fake","wrong item","not working","malfunction","poor quality"],
    "Returns & Refunds":    ["refund","return","exchange","money back","give back","send back","reimburs"],
    "Account & Login":      ["login","password","account","sign in","locked","access","username","reset","forgot","unauthorized"],
    "Technical Support":    ["website","app","crash","error","bug","loading","checkout","cart","not loading","page","500","glitch"],
    "Order Management":     ["order","cancel","cancellation","address","confirmation","status","processing","dispatch"],
    "Customer Service":     ["agent","representative","support","rude","unhelpful","unresolved","complaint","callback","no response"],
}

ISSUES_BY_CATEGORY = {
    "Shipping & Delivery":  ["late delivery","missing package","wrong address","no tracking update","lost shipment"],
    "Billing & Payment":    ["double charge","unauthorized charge","promo not applied","refund pending","wrong invoice"],
    "Product Quality":      ["defective item","broken on arrival","wrong color","poor build quality"],
    "Returns & Refunds":    ["refund not received","return label broken","exchange request","policy dispute"],
    "Account & Login":      ["password reset failed","account locked","suspicious login"],
    "Technical Support":    ["checkout crash","app crash","cart broken","500 error"],
    "Order Management":     ["cancel order","address change","no confirmation email","order stuck"],
    "Customer Service":     ["rude agent","unresolved complaint","missed callback"],
    "Other":                ["general question","feedback","other issue"],
}

SUBCATEGORIES = {
    "Shipping & Delivery":  ["Late Delivery","Lost Package","Wrong Address","Tracking Issue"],
    "Billing & Payment":    ["Duplicate Charge","Unauthorized Charge","Promo Code","Refund Delay"],
    "Product Quality":      ["Defective Item","Wrong Item","Damaged Packaging"],
    "Returns & Refunds":    ["Return Request","Refund Status","Exchange Request"],
    "Account & Login":      ["Password Reset","Account Locked","Unauthorized Access"],
    "Technical Support":    ["Website Bug","App Crash","Checkout Error"],
    "Order Management":     ["Cancel Order","Change Address","Missing Confirmation"],
    "Customer Service":     ["Rude Agent","Unresolved Issue","Missed Callback"],
    "Other":                ["General Inquiry","Feedback"],
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
        "word_count": len(message.split()),
        "processed_at": datetime.now(timezone.utc),
    }


def seed_if_empty(db: Session) -> None:
    """Load sample_1000.csv into the DB if the tickets table is empty."""
    if db.query(Ticket.ticket_id).limit(1).first():
        return  # already has data

    if not os.path.isfile(_SAMPLE_CSV):
        logger.warning("Seed file not found: %s — skipping auto-seed", _SAMPLE_CSV)
        return

    logger.info("Database is empty — seeding from %s", _SAMPLE_CSV)

    with open(_SAMPLE_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    inserted = 0
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
    logger.info("Seed complete: %d tickets loaded.", inserted)
