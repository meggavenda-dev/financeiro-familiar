
# services/finance_core.py
from datetime import datetime, date
from dataclasses import dataclass
import uuid
import copy
import calendar

# --------------------------------------------------
# 🔧 Utilitário para adicionar meses corretamente
# --------------------------------------------------
def add_months(d: date, months: int) -> date:
    """
    Adiciona 'months' meses à data 'd' mantendo o dia, ajustando para o último dia do mês quando necessário.
    Ex.: 31/01 + 1 mês -> 29/02 (ou 28/02 em ano não bissexto)
    """
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    day = min(d.day, calendar.monthlen(year, month)) if hasattr(calendar, "monthlen") else min(
        d.day, calendar.monthrange(year, month)[1]
    )
    return date(year, month, day)

# --------------------------------------------------
# 🔑 IDs
# --------------------------------------------------
def novo_id(prefix: str) -> str:
    """
    Gera IDs únicos e ordenáveis: <prefix>-YYYYMMDDHHMMSS-XXXX
    Evita colisões quando há múltiplos lançamentos no mesmo segundo.
    """
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = uuid.uuid4().hex[:4]
    return f"{prefix}-{ts}-{rand}"

# --------------------------------------------------
# ➕ CRUD BÁSICO
# --------------------------------------------------
def criar(lista: list, item: dict):
    """
    Adiciona item à lista e retorna o próprio item.
    """
    lista.append(item)
    return item

def editar(lista: list, item_id: str, novos_dados: dict) -> bool:
    """
    Edita parcialmente (soft update) o item pelo ID.
    Compatível com sua versão original.
    """
    for x in lista:
        if x.get("id") == item_id and not x.get("excluido", False):
            x.update(novos_dados)
            x["atualizado_em"] = datetime.now().isoformat()
            return True
    return False

def atualizar(lista: list, item_atualizado: dict) -> bool:
    """
    Substitui o item inteiro pelo ID (usado no módulo avançado).
    """
    for i, x in enumerate(lista):
        if x.get("id") == item_atualizado.get("id"):
            lista[i] = item_atualizado
            lista[i]["atualizado_em"] = datetime.now().isoformat()
            return True
    return False

def excluir(lista: list, item_id: str) -> bool:
    """
    Exclusão lógica (soft delete).
    """
    for x in lista:
        if x.get("id") == item_id and not x.get("excluido", False):
            x["excluido"] = True
            x["excluido_em"] = datetime.now().isoformat()
            return True
    return False

def remover(lista: list, item: dict) -> bool:
    """
    Remove por item (compatibilidade com chamadas do módulo).
    """
    return excluir(lista, item.get("id"))

# --------------------------------------------------
# 💳 BAIXAR / ESTORNAR
# --------------------------------------------------
def baixar(despesa: dict, forma_pagamento: str = None):
    """
    Marca despesa como 'paga'.
    """
    despesa["status"] = "paga"
    despesa["paga_em"] = datetime.now().isoformat()
    despesa["forma_pagamento"] = forma_pagamento

def estornar(despesa: dict):
    """
    Retorna despesa para 'prevista' (estorno).
    """
    despesa["status"] = "prevista"
    despesa["paga_em"] = None
    despesa["forma_pagamento"] = None

# --------------------------------------------------
# 🔁 RECORRÊNCIA (CONTROLADA)
# --------------------------------------------------
def gerar_recorrentes(lista: list, ano: int, mes: int) -> list:
    """
    Gera cópias recorrentes para um (ano, mes) específico.
    - Ignora itens excluídos.
    - Ajusta o dia para mês alvo (evitando datas inválidas).
    - Não grava automaticamente — retorna lista para revisão e persistência externa.
    """
    novos = []

    for l in lista:
        if not l.get("recorrente"):
            continue
        if l.get("excluido"):
            continue

        try:
            # Extrai o dia do item base
            base_data = datetime.fromisoformat(l["data"]).date()
            dia_base = base_data.day
            # Ajusta para o mês/ano desejados
            last_day = calendar.monthrange(ano, mes)[1]
            nova_data = date(ano, mes, min(dia_base, last_day))
        except Exception:
            # Pula itens com datas inválidas
            continue

        c = copy.deepcopy(l)
        c["id"] = novo_id("r")
        c["data"] = nova_data.isoformat()
        c["status"] = "prevista"
        c["gerado_em"] = datetime.now().isoformat()
        c.pop("paga_em", None)  # recorrente gerado não começa como pago

        novos.append(c)

    return novos

# --------------------------------------------------
# 📦 PARCELAMENTO
# --------------------------------------------------
def gerar_parcelas(item_base: dict, qtd_parcelas: int, intervalo_meses: int = 1) -> list:
    """
    Gera parcelas a partir de um item base.
    - Ajuste de centavos para fechar exatamente com o total.
    - Controla datas mensais via add_months()
    - Aplica group_id e metadados de parcelamento (qtd, número da parcela)
    - Saída: lista de itens parcela (status 'prevista')
    """
    if qtd_parcelas < 1:
        raise ValueError("Qtd de parcelas deve ser >= 1")

    total = float(item_base["valor"])
    base = round(total / qtd_parcelas, 2)
    valores = [base] * qtd_parcelas
    ajuste = round(total - sum(valores), 2)
    valores[-1] = round(valores[-1] + ajuste, 2)

    group_id = item_base.get("group_id") or f"parc-{uuid.uuid4().hex[:8]}"
    data_ref = datetime.fromisoformat(item_base["data"]).date()

    parcelas = []
    for i in range(qtd_parcelas):
        p = copy.deepcopy(item_base)
        p["id"] = novo_id("p")
        p["group_id"] = group_id
        p["valor"] = valores[i]
        p["parcelamento"] = {
            "qtd_parcelas": qtd_parcelas,
            "parcela_num": i + 1,
        }
        p["data"] = add_months(data_ref, i * intervalo_meses).isoformat()
        p["status"] = "prevista"
        p["paga_em"] = None
        parcelas.append(p)

    return parcelas

# --------------------------------------------------
# 🧠 UTILITÁRIOS
# --------------------------------------------------
def ativos(lista: list) -> list:
    """
    Retorna itens não excluídos.
    """
    return [x for x in lista if not x.get("excluido")]

def filtrar_periodo(lista: list, ini: date, fim: date) -> list:
    """
    Retorna itens no período [ini, fim], ignorando excluídos e datas inválidas.
    """
    out = []
    for x in lista:
        try:
            d = datetime.fromisoformat(x["data"]).date()
            if ini <= d <= fim and not x.get("excluido"):
                out.append(x)
        except Exception:
            # Ignora registro mal formatado
            pass
    return out

