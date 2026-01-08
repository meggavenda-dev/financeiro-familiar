
# services/finance_core.py
from datetime import datetime, date
import uuid
import copy
import calendar
from services.status import derivar_status

def add_months(d: date, months: int) -> date:
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    last = calendar.monthrange(year, month)[1]
    day = min(d.day, last)
    return date(year, month, day)

def novo_id(prefix: str) -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = uuid.uuid4().hex[:4]
    return f"{prefix}-{ts}-{rand}"

def criar(lista: list, item: dict):
    lista.append(item)
    return item

def atualizar(lista: list, item_atualizado: dict) -> bool:
    for i, x in enumerate(lista):
        if x.get("id") == item_atualizado.get("id"):
            lista[i] = item_atualizado
            lista[i]["atualizado_em"] = datetime.now().isoformat()
            return True
    return False

def excluir(lista: list, item_id: str) -> bool:
    for x in lista:
        if x.get("id") == item_id and not x.get("excluido", False):
            x["excluido"] = True
            x["excluido_em"] = datetime.now().isoformat()
            return True
    return False

def baixar(tx: dict, forma_pagamento: str | None = None):
    tx["data_efetiva"] = datetime.now().date().isoformat()
    if forma_pagamento:
        tx["forma_pagamento"] = forma_pagamento

def estornar(tx: dict):
    tx["data_efetiva"] = None
    tx.pop("forma_pagamento", None)

def gerar_parcelas(item_base: dict, qtd_parcelas: int, intervalo_meses: int = 1) -> list:
    if qtd_parcelas < 1:
        raise ValueError("Qtd de parcelas deve ser >= 1")
    total = float(item_base["valor"])
    base = round(total / qtd_parcelas, 2)
    valores = [base] * qtd_parcelas
    ajuste = round(total - sum(valores), 2)
    valores[-1] = round(valores[-1] + ajuste, 2)

    group_id = item_base.get("parcelamento", {}).get("grupo_id") or f"parc-{uuid.uuid4().hex[:8]}"
    data_ref = datetime.fromisoformat(item_base["data_prevista"]).date()

    parcelas = []
    for i in range(qtd_parcelas):
        p = copy.deepcopy(item_base)
        p["id"] = novo_id("tx")
        p["valor"] = valores[i]
        p["parcelamento"] = {"grupo_id": group_id, "parcela": i + 1, "total_parcelas": qtd_parcelas}
        p["data_prevista"] = add_months(data_ref, i * intervalo_meses).isoformat()
        p["data_efetiva"] = None
        parcelas.append(p)
    return parcelas

def saldo_atual(conta: dict, transacoes: list) -> float:
    saldo = float(conta.get("saldo_inicial", 0.0))
    for tx in transacoes:
        if tx.get("conta_id") != conta.get("id"):
            continue
        if tx.get("excluido"):
            continue
        if tx.get("data_efetiva"):
            v = float(tx.get("valor", 0.0))
            if tx.get("tipo") == "receita":
                saldo += v
            else:
                saldo -= v
    return round(saldo, 2)

def normalizar_tx(d):
    if not isinstance(d, dict):
        return None
    d = d.copy()
    d.setdefault("id", "")
    d.setdefault("tipo", "despesa")
    d.setdefault("descricao", "")
    d.setdefault("valor", 0.0)
    d.setdefault("data_prevista", None)
    d.setdefault("data_efetiva", None)
    d.setdefault("conta_id", "c1")
    d.setdefault("categoria_id", None)
    d.setdefault("excluido", False)
    d.setdefault("parcelamento", None)
    d.setdefault("recorrente", False)
    d["status"] = derivar_status(d.get("data_prevista"), d.get("data_efetiva"))
    return d

def ativos(lista: list) -> list:
    return [x for x in lista if isinstance(x, dict) and not x.get("excluido")]

def filtrar_periodo(lista: list, ini: date, fim: date) -> list:
    out = []
    for x in lista:
        try:
            d = datetime.fromisoformat((x.get("data_efetiva") or x.get("data_prevista"))).date()
            if ini <= d <= fim and not x.get("excluido"):
                out.append(x)
        except Exception:
            pass
    return out

