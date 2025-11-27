from flask import Flask, request, jsonify
import mysql.connector
import json
import os

app = Flask(__name__)

# Configuração da DB
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "grupo3")
DB_PASSWORD = os.getenv("DB_PASSWORD", "baguette")
DB_NAME = os.getenv("DB_NAME", "servicos")

def get_db_connection():
    print("[DB] Abrindo conexão com a base de dados")
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

# Load dos produtos e preços
with open("Listas/produtos.json", "r") as f:
    items_prices = json.load(f)

items_prices_norm = {k.lower(): v for k, v in items_prices.items()}


# ------------------------------
#        CRIAR ORDER
# ------------------------------
@app.route("/orders", methods=["POST"])
def create_order():
    data = request.get_json()
    print(f"[CREATE ORDER] Received data: {data}")

    if not data or "items" not in data:
        print("[CREATE ORDER] Missing items in request")
        return jsonify({"error": "Missing items"}), 400

    items_input = data["items"]
    items_list = [i.strip() for i in items_input.split(",")] if isinstance(items_input, str) else items_input

    user_id = data.get("user_id")
    if not user_id:
        print("[CREATE ORDER] user_id obrigatório")
        return jsonify({"error": "user_id obrigatório"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    print(f"[CREATE ORDER] Buscando username para user_id: {user_id}")
    cursor.execute("SELECT username FROM GW WHERE user_id=%s", (user_id,))
    user_row = cursor.fetchone()
    if not user_row:
        print("[CREATE ORDER] Utilizador não encontrado")
        cursor.close()
        conn.close()
        return jsonify({"error": "Utilizador não encontrado"}), 404

    username = user_row["username"]
    print(f"[CREATE ORDER] Username encontrado: {username}")

    # Calcular total...
    total = 0
    unknown_items = []
    for item in items_list:
        item_lower = item.lower().strip()
        if item_lower in items_prices_norm:
            total += items_prices_norm[item_lower]
        else:
            unknown_items.append(item)

    if unknown_items:
        print(f"[CREATE ORDER] Itens desconhecidos: {unknown_items}")
        cursor.close()
        conn.close()
        return jsonify({"error": "Unknown items", "items": unknown_items}), 400

    # Inserir order
    cursor.execute(
        "INSERT INTO Orders (user_id, items, total, status) VALUES (%s, %s, %s, %s)",
        (user_id, ",".join(items_list), total, "pending")
    )
    conn.commit()
    order_id = cursor.lastrowid
    cursor.close()
    conn.close()

    print(f"[CREATE ORDER] Order criada com sucesso: {order_id}")
    return jsonify({
        "order_id": order_id,
        "username": username,
        "items": items_list,
        "total": total,
        "status": "pending"
    }), 201


# ------------------------------
#        LISTAR ORDERS
# ------------------------------
@app.route("/orders", methods=["GET"])
def list_orders():
    print("[LIST ORDERS] Fetching all orders")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            Orders.order_id,
            Orders.items,
            Orders.total,
            Orders.status,
            Orders.created_at,
            GW.username
        FROM Orders
        JOIN GW ON Orders.user_id = GW.user_id
    """)

    orders = cursor.fetchall()
    print(f"[LIST ORDERS] Retrieved {len(orders)} orders")

    cursor.close()
    conn.close()

    return jsonify(orders)


# ------------------------------
#      OBTER ORDERS POR USERNAME
# ------------------------------
@app.route("/orders/<username>", methods=["GET"])
def get_orders_by_username(username):
    print(f"[GET ORDERS BY USERNAME] Fetching orders for username: {username}")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            Orders.order_id,
            Orders.items,
            Orders.total,
            Orders.status,
            Orders.created_at,
            GW.username
        FROM Orders
        JOIN GW ON Orders.user_id = GW.user_id
        WHERE GW.username = %s
    """, (username,))

    orders = cursor.fetchall()
    print(f"[GET ORDERS BY USERNAME] Found {len(orders)} orders for {username}")

    cursor.close()
    conn.close()

    if orders:
        return jsonify(orders)

    print(f"[GET ORDERS BY USERNAME] No orders found for {username}")
    return jsonify({"error": "No orders found for this username"}), 404


# ------------------------------
#      CAMPOS DISPONÍVEIS
# ------------------------------
@app.route("/orders/fields", methods=["GET"])
def order_fields():
    print("[ORDER FIELDS] Returning available items")
    return jsonify({
        "items": list(items_prices.keys())
    })

# ------------------------------
#        CANCELAR ORDER
# ------------------------------
@app.route("/orders/cancel", methods=["POST"])
def cancelar_order():
    data = request.get_json()
    print(f"[CANCEL ORDER] Dados recebidos: {data}")
    if not data or "order_id" not in data:
        print("[CANCEL ORDER] order_id obrigatório")
        return jsonify({"error": "order_id obrigatório"}), 400

    order_id = data["order_id"]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    print(f"[CANCEL ORDER] Verificando order_id: {order_id}")
    cursor.execute("SELECT * FROM Orders WHERE order_id=%s", (order_id,))
    order = cursor.fetchone()
    if not order:
        print("[CANCEL ORDER] Order não encontrada")
        cursor.close()
        conn.close()
        return jsonify({"error": "Order não encontrada"}), 404

    if order["status"].lower() != "pending":
        print(f"[CANCEL ORDER] Order não pode ser cancelada, status: {order['status']}")
        cursor.close()
        conn.close()
        return jsonify({
            "error": f"Order não pode ser cancelada porque está '{order['status']}'"
        }), 400

    cursor.execute("UPDATE Orders SET status='cancelled' WHERE order_id=%s", (order_id,))
    conn.commit()
    cursor.close()
    conn.close()

    print(f"[CANCEL ORDER] Order cancelada com sucesso: {order_id}")
    return jsonify({
        "success": True,
        "order_id": order_id,
        "status": "cancelled",
        "message": "Order cancelada com sucesso"
    }), 200


# ------------------------------
#           RUN
# ------------------------------
if __name__ == "__main__":
    print("[STARTING SERVER] Orders service running on port 5600")
    app.run(host="0.0.0.0", port=5600)
