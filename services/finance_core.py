
from datetime import datetime

def novo_id(prefix):
    return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

def criar(lista, item):
    lista.append(item)

def editar(lista, item_id, novos_dados):
    for x in lista:
        if x["id"] == item_id and not x.get("excluido"):
            x.update(novos_dados)
            return True
    return False

def excluir(lista, item_id):
    for x in lista:
        if x["id"] == item_id:
            x["excluido"] = True
            x["excluido_em"] = datetime.now().isoformat()
            return True
    return False

def baixar(despesa, forma):
    despesa["status"] = "paga"
    despesa["paga_em"] = datetime.now().isoformat()
    despesa["forma_pagamento"] = forma

def estornar(despesa):
    despesa["status"] = "prevista"
    despesa["paga_em"] = None
    despesa["forma_pagamento"] = None

def gerar_recorrentes(lista, ano, mes):
    novos = []
    for l in lista:
        if l.get("recorrente"):
            c = l.copy()
            c["id"] = novo_id("r")
            c["data"] = f"{ano}-{mes:02d}-{l['data'][-2:]}"
            c["status"] = "prevista"
            novos.append(c)
    return novos

