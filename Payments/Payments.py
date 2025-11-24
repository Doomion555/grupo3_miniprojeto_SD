from flask import Flask, request, jsonify
import mysql.connector
import json
import os

app = Flask(__name__)  # Corrigi **name** para __name__

# ---- DB CONFIG ----
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "grupo3")
DB_PASSWORD = os.getenv("DB_PASSWORD", "baguette")
DB_NAME = os.getenv("DB_NAME", "servicos")

def get_db():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

@app.route("/payments/me", methods=["GET"])
def pagamentos_do_cliente():
    username = request.headers.get("X-Username")  # username enviado pelo GW
    if not username:
        return jsonify({"erro": "Username não fornecido"}), 401

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Buscar o user_id do username
    cursor.execute("SELECT user_id FROM GW WHERE username=%s", (username,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return jsonify({"erro": "Utilizador não encontrado"}), 404

    user_id = row["user_id"]

    cursor.execute("""
        SELECT 
            Orders.order_id,
            Orders.items,
            Orders.total,
            Orders.status AS order_status,
            Payments.payment_id,
            Payments.status AS payment_status,
            Payments.created_at AS payment_date
        FROM Orders
        LEFT JOIN Payments ON Orders.order_id = Payments.order_id
        WHERE Orders.user_id = %s
        ORDER BY Orders.created_at DESC
    """, (user_id,))

    pagamentos = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(pagamentos), 200


# ------------------------------------
# PROCESS PAYMENT
# ------------------------------------
@app.route("/payments", methods=["POST"])
def process_payment():
    data = request.get_json()

    if not data or "order_id" not in data:
        return jsonify({"error": "Missing order_id"}), 400

    order_id = data["order_id"]

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # 1) Buscar dados da ordem + utilizador
    cursor.execute("""
        SELECT Orders.order_id, Orders.total, Orders.status,
               GW.user_id, GW.wallet, Orders.items
        FROM Orders
        JOIN GW ON Orders.user_id = GW.user_id
        WHERE Orders.order_id = %s
    """, (order_id,))

    row = cursor.fetchone()

    if not row:
        cursor.close()
        conn.close()
        return jsonify({"error": "Order not found"}), 404

    if row["status"] != "pending":
        cursor.close()
        conn.close()
        return jsonify({"error": "Order already processed"}), 400

    total = float(row["total"])
    wallet = float(row["wallet"])
    user_id = row["user_id"]
    items_list = [i.strip() for i in row["items"].split(",")]

    # 2) Verificar wallet
    if wallet >= total:
        payment_status = "Pagamento sucedido"
        new_wallet = wallet - total

        cursor.execute(
            "UPDATE GW SET wallet = %s WHERE user_id = %s",
            (new_wallet, user_id)
        )

        cursor.execute(
            "UPDATE Orders SET status = 'completed' WHERE order_id = %s",
            (order_id,)
        )

    else:
        payment_status = "failed"

        cursor.execute(
            "UPDATE Orders SET status = 'cancelled' WHERE order_id = %s",
            (order_id,)
        )

    # 3) Criar entrada em Payments
    cursor.execute(
        "INSERT INTO Payments (order_id, amount, status) VALUES (%s, %s, %s)",
        (order_id, total, payment_status)
    )
    conn.commit()
    payment_id = cursor.lastrowid

    cursor.close()
    conn.close()

    return jsonify({
        "order_id": order_id,
        "payment_id": payment_id,
        "status": payment_status
    }), 200


@app.route("/")
def home():
    return {"message": "Payments service online"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5700)

