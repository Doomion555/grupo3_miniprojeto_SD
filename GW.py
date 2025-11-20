from flask import Flask, request
import requests

app = Flask(__name__)

ORDERS_URL = "http://orders:5600"
PAYMENTS_URL = "http://payments:5800"
NOTIFICATIONS_URL = "http://notifications:5900"


@app.route("/")
def boas_vindas():
    return {"mensagem": "Bem-vindo à Loja XPTO"}, 200


@app.route("/orders/new", methods=["POST"])
def criar_pedido():
    try:
        dados_pedido = request.json
        resposta = requests.post(f"{ORDERS_URL}/orders", json=dados_pedido, timeout=2)
        return resposta.json(), resposta.status_code
    except Exception as e:
        return {"erro": str(e)}, 500


@app.route("/orders/products", methods=["GET"])
def listar_produtos():
    try:
        resposta = requests.get(f"{ORDERS_URL}/products", timeout=2)
        return resposta.json(), resposta.status_code
    except Exception as e:
        return {"erro": str(e)}, 500


@app.route("/payments", methods=["POST"])
def processar_pagamento():
    try:
        dados_pagamento = request.json
        resposta = requests.post(f"{PAYMENTS_URL}/payments", json=dados_pagamento, timeout=2)
        return resposta.json(), resposta.status_code
    except Exception as e:
        return {"erro": str(e)}, 500


@app.route("/notifications", methods=["POST"])
def enviar_notificacao():
    try:
        dados = request.json
        resposta = requests.post(f"{NOTIFICATIONS_URL}/notifications", json=dados, timeout=2)
        return resposta.json(), resposta.status_code
    except Exception as e:
        return {"erro": str(e)}, 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5863)
