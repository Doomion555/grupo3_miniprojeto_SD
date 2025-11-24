from flask import Flask, request, jsonify
import requests
import os
import uuid
import mysql.connector

app = Flask(__name__)

# URLs dos serviços internos (usando variáveis de ambiente do docker-compose)
ORDERS_URL = os.getenv("ORDERS_URL", "http://orders:5600")
PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://payments:5700")
NOTIFICATIONS_URL = os.getenv("NOTIFICATIONS_URL", "http://notifications:5800")

# Lista de tokens válidos em memória
tokens_validos = {}

# ------------------------------
#      FUNÇÕES AUXILIARES
# ------------------------------
def get_db_connection():
    return mysql.connector.connect(
        host="db",
        user="grupo3",
        password="baguette",
        database="servicos",
        auth_plugin='mysql_native_password'
    )
def verificar_token():
    btoken = request.headers.get("Authorization")
    if not btoken or not btoken.startswith("Bearer "):
        return None
    token = btoken.split()[1]
    return tokens_validos.get(token)  # retorna o username se token válido

# ------------------------------
#        BOAS VINDAS
# ------------------------------
@app.route("/", methods=["GET"])
def boas_vindas():
    return {"mensagem": "Bem-vindo à Loja XPTO"}, 200

# ------------------------------
#        CRIAR CONTA
# ------------------------------
@app.route("/signup", methods=["POST"])
def criar_conta():
    dados = request.get_json()
    username = dados.get("username")
    password = dados.get("password")

    if not username or not password:
        return {"erro": "username e password obrigatórios"}, 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO GW (username, password) VALUES (%s, %s)", (username, password))
        conn.commit()
        cursor.close()
        conn.close()
        return {"mensagem": f"Conta {username} criada com sucesso"}, 201
    except mysql.connector.errors.IntegrityError:
        return {"erro": "Username já existe"}, 400
    except Exception as e:
        return {"erro": str(e)}, 500
    
# ------------------------------
#        COMO CRIAR CONTA
# ------------------------------

@app.route("/XPTO/hub", methods=["GET"])
def xpto_hub():
    return ("""\n=== XPTO HUB ===
    Para criar uma conta faça:
    [POST] /signup, no modo raw JSON com as seguintes credenciais: { 'username': 'nome_desejado', 'password': 'senha_desejada' }.
    Para fazer login faça:
    [POST] /login no modo raw JSON, com as credenciais da sua conta.
    O login retorna um token que deve ser usado como header [Authorization: Bearer <token>] para aceder aos serviços.
    """)

# ------------------------------
#        LOGIN
# ------------------------------
@app.route("/login", methods=["POST"])
def login():
    dados = request.get_json()
    username = dados.get("username")
    password = dados.get("password")

    if not username or not password:
        return {"erro": "username e password obrigatórios"}, 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM GW WHERE username=%s AND password=%s", (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if not user:
            return {"erro": "Credenciais inválidas"}, 401

        # Gerar token e guardar em memória
        token = str(uuid.uuid4())
        tokens_validos[token] = username
        return {"token": token}, 200
    except Exception as e:
        return {"erro": str(e)}, 500

# ------------------------------
#        LOGOUT
# ------------------------------
@app.route("/logout", methods=["POST"])
def logout():
    token = verificar_token()
    if not token:
        return {"erro": "Token inválido"}, 401
    # Remove o token da lista de tokens válidos
    for t, user in list(tokens_validos.items()):
        if user == token:
            del tokens_validos[t]
            break
    return {"mensagem": "Sessão terminada"}, 200
    
@app.route("/wallet", methods=["GET"])
def get_wallet():
    username = verificar_token()
    if not username:
        return {"erro": "Token inválido"}, 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT wallet FROM GW WHERE username=%s", (username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return {"erro": "Utilizador não encontrado"}, 404

    return {"username": username, "wallet": float(row["wallet"])}, 200


# ------------------------------
#        ORDERS
# ------------------------------
@app.route("/orders/new", methods=["POST"])
def criar_pedido():
    username = verificar_token()
    if not username:
        return {"erro": "Token inválido"}, 401

    dados = request.get_json()
    if not dados:
        return {"erro": "Corpo da request vazio"}, 400

    # Buscar user_id correto do username do token
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id FROM GW WHERE username=%s", (username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return {"erro": "Utilizador não encontrado"}, 404

    dados['user_id'] = row['user_id']  # envia user_id para o Orders service

    try:
        resp = requests.post(f"{ORDERS_URL}/orders", json=dados, timeout=5)
        return resp.json(), resp.status_code
    except Exception as e:
        return {"erro": str(e)}, 500

@app.route("/orders/list", methods=["GET"])
def listar_orders():
    username = verificar_token()
    if not username:
        return {"erro": "Token inválido"}, 401
    try:
        resp = requests.get(f"{ORDERS_URL}/orders", timeout=5)
        return resp.json(), resp.status_code
    except Exception as e:
        return {"erro": str(e)}, 500

@app.route("/orders/me", methods=["GET"])
def orders_do_cliente():
    username = verificar_token()
    if not username:
        return {"erro": "Token inválido"}, 401

    try:
        resp = requests.get(f"{ORDERS_URL}/orders/{username}", timeout=5)
        return resp.json(), resp.status_code
    except Exception as e:
        return {"erro": str(e)}, 500

@app.route("/orders/fields", methods=["GET"])
def produtos_disponiveis():
    username = verificar_token()
    if not username:
        return {"erro": "Token inválido"}, 401
    try:
        resp = requests.get(f"{ORDERS_URL}/orders/fields", timeout=5)
        return resp.json(), resp.status_code
    except Exception as e:
        return {"erro": str(e)}, 500

# ------------------------------
#        PAYMENTS
# ------------------------------
@app.route("/payments", methods=["POST"])
def processar_pagamento():
    username = verificar_token()
    if not username:
        return {"erro": "Token inválido"}, 401
    dados = request.get_json()
    try:
        resp = requests.post(f"{PAYMENTS_URL}/payments", json=dados, timeout=5)
        return resp.json(), resp.status_code
    except Exception as e:
        return {"erro": str(e)}, 500

# ------------------------------
#      NOTIFICATIONS
# ------------------------------
@app.route("/notifications/payment", methods=["POST"])
def enviar_notificacao_pagamento():
    username = verificar_token()
    if not username:
        return {"erro": "Token inválido"}, 401
    dados = request.get_json()
    try:
        resp = requests.post(f"{NOTIFICATIONS_URL}/notifications/payment", json=dados, timeout=5)
        return resp.json(), resp.status_code
    except Exception as e:
        return {"erro": str(e)}, 500

@app.route("/notifications/contas", methods=["GET"])
def listar_contas():
    username = verificar_token()
    if not username:
        return {"erro": "Token inválido"}, 401
    try:
        resp = requests.get(f"{NOTIFICATIONS_URL}/notifications/contas", timeout=5)
        return resp.json(), resp.status_code
    except Exception as e:
        return {"erro": str(e)}, 500

# ------------------------------
# RUN
# ------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5863)

