import os
import sqlite3
import streamlit as st
from google import genai
from google.genai import types

DB = "rongtuli.db"

st.set_page_config(page_title="Rong Tuli AI", page_icon="🧵", layout="wide")


# ---------- DATABASE ----------

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def setup():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            customer TEXT,
            quantity INTEGER,
            total REAL,
            status TEXT DEFAULT 'Pending'
        )
    """)

    if con.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        con.executemany(
            "INSERT INTO products(name,price,stock) VALUES(?,?,?)",
            [
                ("Hand Painted Saree", 450, 3),
                ("Hand Painted Dress", 500, 2),
                ("Painted Cotton Dupatta", 250, 5),
                ("Hand Painted Scarf", 150, 6),
            ],
        )

    con.commit()
    con.close()


# ---------- BUSINESS TOOLS ----------

def search_products(query="", max_price=None):
    con = db()
    rows = con.execute("SELECT * FROM products").fetchall()
    con.close()

    results = []
    for p in rows:
        if query.lower() in p["name"].lower() and p["stock"] > 0:
            if max_price is None or p["price"] <= max_price:
                results.append(dict(p))

    return results


def check_stock(product_id):
    con = db()
    row = con.execute(
        "SELECT name, stock FROM products WHERE id=?",
        (product_id,),
    ).fetchone()
    con.close()
    return dict(row) if row else {"error": "Product not found"}


def create_order(product_id, customer, quantity=1):
    con = db()

    product = con.execute(
        "SELECT * FROM products WHERE id=?",
        (product_id,),
    ).fetchone()

    if not product:
        con.close()
        return {"error": "Product not found"}

    if product["stock"] < quantity:
        con.close()
        return {"error": "Not enough stock"}

    total = product["price"] * quantity

    con.execute(
        "UPDATE products SET stock=stock-? WHERE id=?",
        (quantity, product_id),
    )

    cur = con.execute(
        """
        INSERT INTO orders(product_id,customer,quantity,total)
        VALUES(?,?,?,?)
        """,
        (product_id, customer, quantity, total),
    )

    con.commit()
    order_id = cur.lastrowid
    con.close()

    return {
        "success": True,
        "order_id": order_id,
        "product": product["name"],
        "total": total,
    }


def get_business_data():
    con = db()

    products = con.execute("SELECT * FROM products").fetchall()
    orders = con.execute("SELECT * FROM orders").fetchall()

    revenue = sum(o["total"] for o in orders)

    con.close()

    return {
        "products": [dict(p) for p in products],
        "orders": [dict(o) for o in orders],
        "revenue": revenue,
    }


# ---------- GEMINI ----------

@st.cache_resource
def get_client():
    key = os.getenv("GEMINI_API_KEY")

    if not key:
        return None

    return genai.Client(api_key=key)


def ask_ai(message):
    client = get_client()

    if not client:
        return "⚠️ Add your GEMINI_API_KEY to connect Gemini."

    business = get_business_data()

    prompt = f"""
You are Rong Tuli AI, an AI business team for a small handmade
clothing business.

Your job is to help the entrepreneur with:
- customer support
- product discovery
- sales
- inventory
- business insights
- marketing

REAL BUSINESS DATA:
{business}

USER:
{message}

Give a concise, useful answer.
Never invent products, prices, stock, orders, or revenue.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text


# ---------- UI ----------

setup()

st.title("🧵 Rong Tuli AI")
st.caption("Your business. Your decisions. An AI team behind you.")

products, orders = st.columns([2, 1])

with products:
    st.subheader("Products")

    data = get_business_data()

    for p in data["products"]:
        st.write(
            f"**{p['name']}** — ৳{p['price']:.0f} · "
            f"{p['stock']} in stock"
        )

with orders:
    st.subheader("Business")

    data = get_business_data()

    st.metric("Revenue", f"৳{data['revenue']:.0f}")
    st.metric("Orders", len(data["orders"]))


st.divider()

st.subheader("🤖 AI Business Team")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

question = st.chat_input(
    "Ask Rong Tuli AI about customers, products, sales or your business..."
)

if question:
    st.session_state.messages.append(
        {"role": "user", "content": question}
    )

    with st.chat_message("user"):
        st.write(question)

    answer = ask_ai(question)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer}
    )

    with st.chat_message("assistant"):
        st.write(answer)


st.divider()

with st.expander("📦 Orders"):
    data = get_business_data()

    if data["orders"]:
        for o in data["orders"]:
            st.write(
                f"Order #{o['id']} · {o['customer']} · "
                f"৳{o['total']:.0f} · {o['status']}"
            )
    else:
        st.info("No orders yet.")
