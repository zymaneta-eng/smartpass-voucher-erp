import os
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime

import database

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app = FastAPI(title="SmartPass Admin Portal", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@app.on_event("startup")
def on_startup():
    database.init_db()
    database.seed_demo_data()

def get_common_counts():
    conn = database.get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM orders WHERE status = 'PAID_REPORTED'")
    pending_orders = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM vouchers WHERE status = 'AVAILABLE'")
    active_vouchers = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM checkins WHERE status = 'PENDING'")
    pending_checkins = c.fetchone()[0]
    
    conn.close()
    return pending_orders, active_vouchers, pending_checkins

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, msg: str = None):
    pending_orders_count, active_vouchers_count, pending_checkins_count = get_common_counts()
    
    conn = database.get_connection()
    c = conn.cursor()
    
    # Pending orders
    c.execute("""
    SELECT o.*, u.full_name, u.phone, p.service_name, p.network_name, p.denomination
    FROM orders o
    JOIN users u ON o.user_id = u.id
    JOIN products p ON o.product_id = p.id
    WHERE o.status = 'PAID_REPORTED'
    ORDER BY o.id DESC
    """)
    pending_orders = c.fetchall()
    
    # Active checkins
    c.execute("""
    SELECT ch.*, u.full_name, v.voucher_code, v.denomination
    FROM checkins ch
    JOIN users u ON ch.user_id = u.id
    JOIN vouchers v ON ch.voucher_id = v.id
    WHERE ch.status = 'PENDING'
    ORDER BY ch.id DESC
    """)
    checkins = c.fetchall()
    
    # Recent vouchers
    c.execute("""
    SELECT v.*, u.full_name
    FROM vouchers v
    JOIN users u ON v.user_id = u.id
    ORDER BY v.id DESC LIMIT 5
    """)
    recent_vouchers = c.fetchall()
    
    # Recent audit
    c.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 5")
    recent_audit = c.fetchall()
    
    # Calculate separate turnovers for UAH and USDT
    c.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE currency = 'UAH'")
    uah_total = c.fetchone()[0] or 0.0
    c.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE currency = 'USDT'")
    usdt_total = c.fetchone()[0] or 0.0
    
    turnover_uah = f"{uah_total:,.0f} ₴".replace(",", " ")
    turnover_usdt = f"{usdt_total:,.2f} USDT"
    
    conn.close()
    
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "active_tab": "dashboard",
            "page_title": "Головний дашборд операцій",
            "page_subtitle": "Оперативний огляд замовлень, оплат і талонів",
            "pending_orders_count": pending_orders_count,
            "active_vouchers_count": active_vouchers_count,
            "pending_checkins_count": pending_checkins_count,
            "turnover_uah": turnover_uah,
            "turnover_usdt": turnover_usdt,
            "admin_name": "Олександр В.",
            "admin_role": "Адміністратор",
            "pending_orders": pending_orders,
            "checkins": checkins,
            "recent_vouchers": recent_vouchers,
            "recent_audit": recent_audit,
            "message": msg
        }
    )

@app.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request):
    pending_orders_count, active_vouchers_count, pending_checkins_count = get_common_counts()
    conn = database.get_connection()
    c = conn.cursor()
    c.execute("""
    SELECT o.*, u.full_name, u.phone, p.service_name, p.network_name, p.denomination
    FROM orders o
    JOIN users u ON o.user_id = u.id
    JOIN products p ON o.product_id = p.id
    ORDER BY o.id DESC
    """)
    orders = c.fetchall()
    conn.close()
    
    return templates.TemplateResponse(
        request=request,
        name="orders.html",
        context={
            "active_tab": "orders",
            "page_title": "Журнал замовлень та оплат",
            "pending_orders_count": pending_orders_count,
            "pending_checkins_count": pending_checkins_count,
            "orders": orders
        }
    )

@app.post("/orders/approve/{order_id}")
def approve_order_route(order_id: int):
    database.approve_order(order_id, admin_name="Головний Адміністратор")
    return RedirectResponse(url="/?msg=Замовлення_успішно_схвалено_талони_випущено", status_code=303)

@app.post("/orders/reject/{order_id}")
def reject_order_route(order_id: int):
    database.reject_order(order_id, reason="Некоректний платіж", admin_name="Головний Адміністратор")
    return RedirectResponse(url="/?msg=Замовлення_відхилено", status_code=303)

@app.get("/vouchers", response_class=HTMLResponse)
def vouchers_page(request: Request):
    pending_orders_count, active_vouchers_count, pending_checkins_count = get_common_counts()
    conn = database.get_connection()
    c = conn.cursor()
    c.execute("""
    SELECT v.*, u.full_name, u.phone
    FROM vouchers v
    JOIN users u ON v.user_id = u.id
    ORDER BY v.id DESC
    """)
    vouchers = c.fetchall()
    conn.close()
    
    return templates.TemplateResponse(
        request=request,
        name="vouchers.html",
        context={
            "active_tab": "vouchers",
            "page_title": "Склад талонів та абонементів",
            "pending_orders_count": pending_orders_count,
            "pending_checkins_count": pending_checkins_count,
            "vouchers": vouchers
        }
    )

@app.get("/checkins", response_class=HTMLResponse)
def checkins_page(request: Request, msg: str = None):
    pending_orders_count, active_vouchers_count, pending_checkins_count = get_common_counts()
    conn = database.get_connection()
    c = conn.cursor()
    c.execute("""
    SELECT ch.*, u.full_name, v.voucher_code, v.denomination
    FROM checkins ch
    JOIN users u ON ch.user_id = u.id
    JOIN vouchers v ON ch.voucher_id = v.id
    WHERE ch.status = 'PENDING'
    ORDER BY ch.id DESC
    """)
    checkins = c.fetchall()
    conn.close()
    
    return templates.TemplateResponse(
        request=request,
        name="checkins.html",
        context={
            "active_tab": "checkins",
            "page_title": "Черга чек-іну (валідація QR)",
            "pending_orders_count": pending_orders_count,
            "pending_checkins_count": pending_checkins_count,
            "checkins": checkins,
            "message": msg
        }
    )

@app.post("/checkins/confirm/{checkin_id}")
def confirm_checkin_route(checkin_id: int):
    database.confirm_checkin(checkin_id, admin_name="Адміністратор рецепції")
    return RedirectResponse(url="/checkins?msg=Талон_успішно_погашено", status_code=303)

@app.post("/checkins/cancel/{checkin_id}")
def cancel_checkin_route(checkin_id: int):
    database.cancel_checkin(checkin_id, admin_name="Адміністратор рецепції")
    return RedirectResponse(url="/checkins?msg=Чек-ін_скасовано_талон_повернуто", status_code=303)

@app.post("/checkins/manual-redeem")
def manual_redeem_route(code: str = Form(...)):
    conn = database.get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM vouchers WHERE voucher_code = ? AND status = 'AVAILABLE'", (code.strip().upper(),))
    v = c.fetchone()
    if v:
        c.execute("UPDATE vouchers SET status = 'USED', used_at = ? WHERE id = ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), v["id"]))
        conn.commit()
        database.log_audit("Адміністратор рецепції", "РУЧНЕ_ПОГАШЕННЯ", f"Талон {code.strip().upper()} успішно погашено через ручний термінал.")
        conn.close()
        return RedirectResponse(url="/checkins?msg=Талон_успішно_знайдено_та_погашено", status_code=303)
    conn.close()
    return RedirectResponse(url="/checkins?msg=Помилка:_Талон_не_знайдено_або_вже_використано", status_code=303)

@app.get("/prices", response_class=HTMLResponse)
def prices_page(request: Request):
    pending_orders_count, active_vouchers_count, pending_checkins_count = get_common_counts()
    conn = database.get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM products ORDER BY id ASC")
    products = c.fetchall()
    conn.close()
    
    return templates.TemplateResponse(
        request=request,
        name="prices.html",
        context={
            "active_tab": "prices",
            "page_title": "Прайс-лист на 3 рівні цін (ТОВ / ФОП / USDT)",
            "pending_orders_count": pending_orders_count,
            "pending_checkins_count": pending_checkins_count,
            "products": products
        }
    )

@app.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request):
    pending_orders_count, active_vouchers_count, pending_checkins_count = get_common_counts()
    conn = database.get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM audit_logs ORDER BY id DESC")
    logs = c.fetchall()
    conn.close()
    
    return templates.TemplateResponse(
        request=request,
        name="audit.html",
        context={
            "active_tab": "audit",
            "page_title": "Незмінний журнал дій адміністраторів",
            "pending_orders_count": pending_orders_count,
            "pending_checkins_count": pending_checkins_count,
            "logs": logs
        }
    )

@app.get("/export/excel")
def export_excel():
    excel_stream = database.generate_excel_report()
    filename = f"SmartPass_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app:app", host="127.0.0.1", port=8000, reload=True)
