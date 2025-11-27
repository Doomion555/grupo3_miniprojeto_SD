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
    print("[DB] Abrindo conexão com a base de dados")
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
        print("[AUTH] Token ausente ou inválido no header")
        return None
    token = btoken.split()[1]
    username = tokens_validos.get(token)
    print(f"[AUTH] Token verificado para o username: {username}")
    return username

# ------------------------------
#        BOAS VINDAS
# ------------------------------
@app.route("/", methods=["GET"])
def boas_vindas():
    print("[GW] Requisição de boas-vindas recebida")
    return {"mensagem": "Bem-vindo à Loja XPTO"}, 200

# ------------------------------
#        CRIAR CONTA
# ------------------------------
@app.route("/signup", methods=["POST"])
def criar_conta():
    dados = request.get_json()
    print(f"[SIGNUP] Dados recebidos: {dados}")
    username = dados.get("username")
    password = dados.get("password")

    if not username or not password:
        print("[SIGNUP] Falta username ou password")
        return {"erro": "username e password obrigatórios"}, 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO GW (username, password) VALUES (%s, %s)", (username, password))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[SIGNUP] Conta criada com sucesso para {username}")
        return {"mensagem": f"Conta {username} criada com sucesso"}, 201
    except mysql.connector.errors.IntegrityError:
        print(f"[SIGNUP] Username já existe: {username}")
        return {"erro": "Username já existe"}, 400
    except Exception as e:
        print(f"[SIGNUP] Erro: {e}")
        return {"erro": str(e)}, 500

# ------------------------------
#        COMO CRIAR CONTA
# ------------------------------
@app.route("/XPTO/hub", methods=["GET"])
def xpto_hub():
    print("[GW] /XPTO/hub solicitado")
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
    print(f"[LOGIN] Dados recebidos: {dados}")
    username = dados.get("username")
    password = dados.get("password")

    if not username or not password:
        print("[LOGIN] Falta username ou password")
        return {"erro": "username e password obrigatórios"}, 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM GW WHERE username=%s AND password=%s", (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if not user:
            print(f"[LOGIN] Credenciais inválidas para {username}")
            return {"erro": "Credenciais inválidas"}, 401

        # Gerar token e guardar em memória
        token = str(uuid.uuid4())
        tokens_validos[token] = username
        print(f"[LOGIN] Login bem-sucedido. Token gerado para {username}: {token}")
        return {"token": token}, 200
    except Exception as e:
        print(f"[LOGIN] Erro: {e}")
        return {"erro": str(e)}, 500

# ------------------------------
#        LOGOUT
# ------------------------------
@app.route("/logout", methods=["POST"])
def logout():
    token = verificar_token()
    if not token:
        print("[LOGOUT] Token inválido")
        return {"erro": "Token inválido"}, 401
    # Remove o token da lista de tokens válidos
    for t, user in list(tokens_validos.items()):
        if user == token:
            del tokens_validos[t]
            print(f"[LOGOUT] Token removido para {user}")
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
        print(f"[WALLET] Utilizador não encontrado: {username}")
        return {"erro": "Utilizador não encontrado"}, 404

    print(f"[WALLET] Wallet de {username}: {row['wallet']}")
    return {"username": username, "wallet": float(row["wallet"])}, 200

# ------------------------------
#        ORDERS
# ------------------------------
@app.route("/orders/new", methods=["POST"])
def criar_pedido():
    username = verificar_token()
    print(f"[ORDERS NEW] Username do token: {username}")
    if not username:
        return {"erro": "Token inválido"}, 401

    dados = request.get_json()
    print(f"[ORDERS NEW] Dados recebidos: {dados}")
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
        print(f"[ORDERS NEW] Utilizador não encontrado: {username}")
        return {"erro": "Utilizador não encontrado"}, 404

    dados['user_id'] = row['user_id']
    print(f"[ORDERS NEW] user_id adicionado: {dados['user_id']}")

    try:
        print(f"[ORDERS NEW] Chamando serviço Orders: {ORDERS_URL}/orders")
        resp = requests.post(f"{ORDERS_URL}/orders", json=dados, timeout=5)
        print(f"[ORDERS NEW] Resposta do Orders: {resp.status_code}")
        return resp.json(), resp.status_code
    except Exception as e:
        print(f"[ORDERS NEW] Erro ao chamar Orders: {e}")
        return {"erro": str(e)}, 500

@app.route("/orders/list", methods=["GET"])
def listar_orders():
    username = verificar_token()
    print(f"[ORDERS LIST] Username do token: {username}")
    if not username:
        return {"erro": "Token inválido"}, 401
    try:
        print(f"[ORDERS LIST] Chamando serviço Orders: {ORDERS_URL}/orders")
        resp = requests.get(f"{ORDERS_URL}/orders", timeout=5)
        print(f"[ORDERS LIST] Resposta do Orders: {resp.status_code}")
        return resp.json(), resp.status_code
    except Exception as e:
        print(f"[ORDERS LIST] Erro ao chamar Orders: {e}")
        return {"erro": str(e)}, 500

@app.route("/orders/me", methods=["GET"])
def orders_do_cliente():
    username = verificar_token()
    print(f"[ORDERS ME] Username do token: {username}")
    if not username:
        return {"erro": "Token inválido"}, 401
    try:
        print(f"[ORDERS ME] Chamando serviço Orders: {ORDERS_URL}/orders/{username}")
        resp = requests.get(f"{ORDERS_URL}/orders/{username}", timeout=5)
        print(f"[ORDERS ME] Resposta do Orders: {resp.status_code}")
        return resp.json(), resp.status_code
    except Exception as e:
        print(f"[ORDERS ME] Erro ao chamar Orders: {e}")
        return {"erro": str(e)}, 500

@app.route("/orders/fields", methods=["GET"])
def produtos_disponiveis():
    username = verificar_token()
    print(f"[ORDERS FIELDS] Username do token: {username}")
    if not username:
        return {"erro": "Token inválido"}, 401
    try:
        print(f"[ORDERS FIELDS] Chamando serviço Orders: {ORDERS_URL}/orders/fields")
        resp = requests.get(f"{ORDERS_URL}/orders/fields", timeout=5)
        print(f"[ORDERS FIELDS] Resposta do Orders: {resp.status_code}")
        return resp.json(), resp.status_code
    except Exception as e:
        print(f"[ORDERS FIELDS] Erro ao chamar Orders: {e}")
        return {"erro": str(e)}, 500

@app.route("/orders/cancel", methods=["POST"])
def gw_cancel_order():
    username = verificar_token()
    print(f"[ORDERS CANCEL] Username do token: {username}")
    if not username:
        return {"erro": "Token inválido"}, 401

    dados = request.get_json()
    print(f"[ORDERS CANCEL] Dados recebidos: {dados}")
    if not dados:
        return {"erro": "Corpo da request vazio"}, 400

    try:
        print(f"[ORDERS CANCEL] Chamando serviço Orders: {ORDERS_URL}/orders/cancel")
        resp = requests.post(f"{ORDERS_URL}/orders/cancel", json=dados, timeout=5)
        print(f"[ORDERS CANCEL] Resposta do Orders: {resp.status_code}")
        return resp.json(), resp.status_code
    except Exception as e:
        print(f"[ORDERS CANCEL] Erro ao chamar Orders: {e}")
        return {"erro": str(e)}, 500

# ------------------------------
#        PAYMENTS
# ------------------------------
@app.route("/payments", methods=["POST"])
def processar_pagamento():
    username = verificar_token()
    print(f"[PAYMENTS] Username do token: {username}")
    if not username:
        return {"erro": "Token inválido"}, 401
    dados = request.get_json()
    print(f"[PAYMENTS] Dados recebidos: {dados}")
    try:
        print(f"[PAYMENTS] Chamando serviço Payments: {PAYMENTS_URL}/payments")
        resp = requests.post(f"{PAYMENTS_URL}/payments", json=dados, timeout=5)
        print(f"[PAYMENTS] Resposta do Payments: {resp.status_code}")
        return resp.json(), resp.status_code
    except Exception as e:
        print(f"[PAYMENTS] Erro ao chamar Payments: {e}")
        return {"erro": str(e)}, 500

@app.route("/payments/me", methods=["GET"])
def pagamentos_do_cliente():
    username = verificar_token()
    print(f"[PAYMENTS ME] Username do token: {username}")
    if not username:
        return {"erro": "Token inválido"}, 401

    try:
        print(f"[PAYMENTS ME] Chamando serviço Payments: {PAYMENTS_URL}/payments/me")
        resp = requests.get(f"{PAYMENTS_URL}/payments/me", headers={"X-Username": username}, timeout=5)
        print(f"[PAYMENTS ME] Resposta do Payments: {resp.status_code}")
        return resp.json(), resp.status_code
    except Exception as e:
        print(f"[PAYMENTS ME] Erro ao chamar Payments: {e}")
        return {"erro": str(e)}, 500

# ------------------------------
#      NOTIFICATIONS
# ------------------------------
@app.route("/notifications/me", methods=["GET"])
def notificacoes_do_cliente():
    username = verificar_token()
    print(f"[NOTIFICATIONS ME] Username do token: {username}")
    if not username:
        return {"erro": "Token inválido"}, 401

    try:
        print(f"[NOTIFICATIONS ME] Chamando serviço Notifications: {NOTIFICATIONS_URL}/notifications/me")
        resp = requests.get(
            f"{NOTIFICATIONS_URL}/notifications/me",
            headers={"X-Username": username},
            timeout=5
        )
        print(f"[NOTIFICATIONS ME] Resposta do Notifications: {resp.status_code}")
        return resp.json(), resp.status_code
    except Exception as e:
        print(f"[NOTIFICATIONS ME] Erro ao chamar Notifications: {e}")
        return {"erro": str(e)}, 500

# ------------------------------
# RUN
# ------------------------------
if __name__ == "__main__":
    print("[GW] Iniciando Gateway na porta 5863")
    app.run(host="0.0.0.0", port=5863)
