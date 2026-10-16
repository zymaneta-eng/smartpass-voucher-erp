import os
import sys
import uuid
from datetime import datetime, timedelta
import asyncio

# Ensure smartpass directory is in path
sys.path.append(os.path.dirname(__file__))
import database

def simulate_customer_purchase(full_name: str, phone: str, product_id: int, quantity: int, payment_method: str):
    """Simulates a customer creating an order in Telegram and uploading a receipt"""
    database.init_db()
    conn = database.get_connection()
    c = conn.cursor()
    
    # Check or create user
    c.execute("SELECT id FROM users WHERE phone = ?", (phone,))
    u = c.fetchone()
    if not u:
        c.execute("""
        INSERT INTO users (telegram_id, username, full_name, phone, client_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (int(uuid.uuid4().int % 100000000), full_name.lower().replace(" ", "_"), full_name, phone, "individual", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        user_id = c.lastrowid
    else:
        user_id = u["id"]
        
    # Get product
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    prod = c.fetchone()
    if not prod:
        conn.close()
        return None
        
    if payment_method == "USDT":
        total = prod["price_usdt"] * quantity
        currency = "USDT"
    elif payment_method == "FOP":
        total = prod["price_fop"] * quantity
        currency = "UAH"
    else:
        total = prod["price_legal"] * quantity
        currency = "UAH"
        
    order_num = f"ORD-2026-{uuid.uuid4().hex[:4].upper()}"
    sample_receipt = "receipt_sample_1.png" if payment_method == "FOP" else ("receipt_sample_2.png" if payment_method == "USDT" else "receipt_sample_3.png")
    
    c.execute("""
    INSERT INTO orders (order_number, user_id, product_id, quantity, total_amount, currency, payment_method, receipt_file, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PAID_REPORTED', ?)
    """, (order_num, user_id, product_id, quantity, total, currency, payment_method, sample_receipt, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    
    database.log_audit(
        "Telegram Клієнт",
        "НОВЕ_ЗАМОВЛЕННЯ",
        f"Клієнт {full_name} створив замовлення #{order_num} на {quantity} шт. ({prod['service_name']}). Чек завантажено."
    )
    return order_num

def simulate_customer_checkin(voucher_code: str = None):
    """Simulates customer arriving at the location and tapping 'Check-in / Generate QR'"""
    database.init_db()
    conn = database.get_connection()
    c = conn.cursor()
    
    if voucher_code:
        c.execute("SELECT * FROM vouchers WHERE voucher_code = ? AND status = 'AVAILABLE'", (voucher_code,))
    else:
        c.execute("SELECT * FROM vouchers WHERE status = 'AVAILABLE' ORDER BY id DESC LIMIT 1")
    v = c.fetchone()
    
    if not v:
        conn.close()
        return None
        
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    exp_str = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
    token = f"CHK-{uuid.uuid4().hex[:8].upper()}"
    
    c.execute("UPDATE vouchers SET status = 'RESERVED' WHERE id = ?", (v["id"],))
    c.execute("""
    INSERT INTO checkins (voucher_id, user_id, network_name, qr_token, status, created_at, expires_at)
    VALUES (?, ?, ?, ?, 'PENDING', ?, ?)
    """, (v["id"], v["user_id"], v["network_name"], token, now_str, exp_str))
    
    ch_id = c.lastrowid
    conn.commit()
    conn.close()
    
    database.log_audit(
        "Telegram Клієнт",
        "ЗАПИТ_ЧЕКІНУ",
        f"Гість активував талон {v['voucher_code']} для відвідування {v['network_name']}. Згенеровано токен {token}."
    )
    return token

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--order", action="store_true", help="Simulate a new order")
    parser.add_argument("--checkin", action="store_true", help="Simulate a checkin QR request")
    args = parser.parse_args()
    
    if args.order:
        ord_num = simulate_customer_purchase("Андрій Шевченко", "+380997778899", 3, 2, "FOP")
        print(f"Simulated order created: {ord_num}")
    elif args.checkin:
        token = simulate_customer_checkin()
        print(f"Simulated checkin request created with token: {token}")
    else:
        print("SmartPass Simulation Utility. Use --order or --checkin.")
