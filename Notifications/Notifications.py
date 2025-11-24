from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# URLs dos serviços internos
ORDERS_URL = os.getenv("ORDERS_URL", "http://orders:5600")
PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://payments:5700")

print("Serviço de notificações online sem acesso direto à DB.")

# ------------------------------
#     NOTIFICATIONS /me
# ------------------------------
@app.route('/notifications/me', methods=['GET'])
def notificacoes_do_cliente():
    username = request.headers.get('X-Username')
    if not username:
        return jsonify({"erro": "Username não fornecido"}), 401

    # 1) Buscar orders do utilizador
    try:
        orders_resp = requests.get(f"{ORDERS_URL}/orders/{username}", timeout=5)
        orders_data = orders_resp.json() if orders_resp.status_code == 200 else []
    except Exception as e:
        orders_data = {"erro": f"Falha ao contactar Orders: {str(e)}"}

    # 2) Buscar payments do utilizador
    try:
        payments_resp = requests.get(
            f"{PAYMENTS_URL}/payments/me",
            headers={"X-Username": username},
            timeout=5
        )
        payments_data = payments_resp.json() if payments_resp.status_code == 200 else []
    except Exception as e:
        payments_data = {"erro": f"Falha ao contactar Payments: {str(e)}"}

    # 3) Resposta final agregada
    return jsonify({
        "username": username,
        "orders": orders_data,
        "payments": payments_data
    }), 200

# ------------------------------
# RUN
# ------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5800)
