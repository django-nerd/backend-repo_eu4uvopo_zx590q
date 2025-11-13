import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="TRI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "TRI Backend Running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from TRI backend API!"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "❌ Unknown"
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    return response


# Models mirroring schemas
class CartItem(BaseModel):
    product_id: str
    title: str
    quantity: int
    price: float

class OrderIn(BaseModel):
    user_email: str
    items: List[CartItem]

class VerifyPaymentIn(BaseModel):
    order_id: str
    payment_id: Optional[str] = None
    signature: Optional[str] = None


def _generate_invoice_number() -> str:
    seq = db["invoicesequence"].find_one_and_update(
        {"_id": "seq"},
        {"$inc": {"last_number": 1}},
        upsert=True,
        return_document=True,
    )
    num = seq.get("last_number", 1)
    year = datetime.now().year
    return f"TRI/{year}/{num:05d}"


def _order_total(items: List[CartItem]) -> float:
    return float(sum(i.price * i.quantity for i in items))


@app.post("/api/orders")
def create_order(payload: OrderIn):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    amount = _order_total(payload.items)
    doc = {
        "user_email": payload.user_email,
        "items": [i.model_dump() for i in payload.items],
        "amount": amount,
        "status": "created",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = db["order"].insert_one(doc)

    # Simulate gateway order id
    gateway_order_id = f"order_{str(result.inserted_id)[-8:]}"
    db["order"].update_one({"_id": result.inserted_id}, {"$set": {"order_id": gateway_order_id}})

    return {
        "_id": str(result.inserted_id),
        "order_id": gateway_order_id,
        "amount": amount,
        "currency": "INR",
        "status": "created",
    }


@app.post("/api/payments/verify")
def verify_payment(payload: VerifyPaymentIn):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    order = db["order"].find_one({"order_id": payload.order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Demo verification: treat any request with order_id as success
    invoice_number = _generate_invoice_number()
    db["order"].update_one(
        {"_id": order["_id"]},
        {"$set": {
            "status": "paid",
            "payment_id": payload.payment_id or f"pay_{str(order['_id'])[-6:]}",
            "invoice_number": invoice_number,
            "updated_at": datetime.now(timezone.utc)
        }}
    )

    return {"status": "paid", "invoice_number": invoice_number}


@app.get("/api/orders")
def list_orders(email: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    cur = db["order"].find({"user_email": email}).sort("created_at", -1).limit(50)
    orders = []
    for o in cur:
        o["_id"] = str(o["_id"])  # make JSON serializable
        orders.append(o)
    return {"orders": orders}


@app.get("/api/invoice/{order_id}")
def get_invoice(order_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    order = db["order"].find_one({"order_id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    inv = order.get("invoice_number", "PENDING")
    items_html = "".join([
        f"<tr><td>{i['title']}</td><td style='text-align:center'>{i['quantity']}</td><td style='text-align:right'>₹{i['price']:.2f}</td><td style='text-align:right'>₹{i['price']*i['quantity']:.2f}</td></tr>"
        for i in order.get("items", [])
    ])
    html = f"""
    <html>
      <head>
        <meta charset='utf-8' />
        <title>Invoice {inv}</title>
        <style>
          body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; padding: 24px; }}
          .card {{ max-width: 720px; margin: 0 auto; border: 1px solid #eee; border-radius: 10px; overflow: hidden; }}
          .header {{ background: #0ea5e9; color: white; padding: 16px 20px; }}
          .section {{ padding: 16px 20px; }}
          table {{ width: 100%; border-collapse: collapse; }}
          th, td {{ padding: 8px; border-bottom: 1px solid #f1f5f9; }}
          th {{ text-align: left; background:#f8fafc; }}
          .right {{ text-align:right; }}
        </style>
      </head>
      <body>
        <div class="card">
          <div class="header">
            <h2>TRI Invoice</h2>
            <div>{inv}</div>
          </div>
          <div class="section">
            <div><strong>Billed To:</strong> {order.get('user_email')}</div>
            <div><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d')}</div>
          </div>
          <div class="section">
            <table>
              <thead>
                <tr><th>Description</th><th style='text-align:center'>Qty</th><th class='right'>Rate</th><th class='right'>Amount</th></tr>
              </thead>
              <tbody>
                {items_html}
                <tr><td colspan="3" class='right'><strong>Total</strong></td><td class='right'><strong>₹{order.get('amount', 0):.2f}</strong></td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </body>
    </html>
    """
    return html


class EmailIn(BaseModel):
    to: str
    subject: str
    html: Optional[str] = None
    text: Optional[str] = None


@app.post("/api/send-email")
def send_email(payload: EmailIn):
    # Demo email sender: In a real system, integrate with SendGrid or similar
    # Here, we just simulate success
    return {"status": "queued", "to": payload.to}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
