
from datetime import datetime, date
import uuid
import copy

# --------------------------------------------------
# 🔑 IDs
# --------------------------------------------------
def novo_id(prefix: str) -> str:
    """
    Gera IDs únicos e ordenáveis.
    Mantém compatibilidade visual com seu padrão atual,
    mas elimina colisões quando há múltimos lançamentos no mesmo segundo.
    """
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    rand = uuid.uuid4().hex[:4]
    return f"{prefix}-{ts}-{rand}"

# --------------------------------------------------
# ➕ CRUD BÁSICO
# --------------------------------------------------
def criar(lista: list, item: dict):
    """
    Adiciona item à lista
    """
    lista.append(item)
    return item

def editar(lista: list, item_id: str, novos_dados: dict) -> bool:
    """
    Edita item existente (soft update)
    """
    for x in lista:
        if x.get("id") == item_id and not x.get("excluido", False):
            x.update(novos_dados)
            x["atualizado_em"] = datetime.now().isoformat()
            return True
    return False

def atualizar(lista: list, item_atualizado: dict) -> bool:
    """
    Atualiza item inteiro pelo ID (usado pelo módulo avançado)
    """
    for i, x in enumerate(lista):
        if x.get("id") == item_atualizado.get("id"):
            lista[i] = item_atualizado
            lista[i]["atualizado_em"] = datetime.now().isoformat()
            return True
    return False

def excluir(lista: list, item_id: str) -> bool:
    """
    Exclusão lógica (soft delete)
    """
    for x in lista:
        if x.get("id") == item_id and not x.get("excluido", False):
            x["excluido"] = True
            x["excluido_em"] = datetime.now().isoformat()
            return True
    return False

def remover(lista: list, item: dict) -> bool:
    """
    Compatibilidade com chamadas do módulo mais novo
    """
    return excluir(lista, item.get("id"))

# --------------------------------------------------
# 💳 BAIXAR / ESTORNAR (FLUXO FINANCEIRO)
# --------------------------------------------------
def baixar(despesa: dict, forma_pagamento: str = None):
    """
    Marca despesa como paga
    """
    despesa["status"] = "paga"
    despesa["paga_em"] = datetime.now().isoformat()
    despesa["forma_pagamento"] = forma_pagamento

def estornar(despesa: dict):
    """
    Retorna despesa para prevista
    """
    despesa["status"] = "prevista"
    despesa["paga_em"] = None
    despesa["forma_pagamento"] = None

# --------------------------------------------------
# 🔁 RECORRÊNCIA (CONTROLADA)
# --------------------------------------------------
def gerar_recorrentes(lista: list, ano: int, mes: int) -> list:
    """
    Gera cópias recorrentes para um mês específico.
    NÃO grava automaticamente — retorna lista para conferência.
    """
    novos = []

    for l in lista:
        if not l.get("recorrente"):
            continue
        if l.get("excluido"):
            continue

        try:
            dia = int(l["data"][-2:])
            nova_data = date(ano, mes, min(dia, 28))  # evita datas inválidas
        except Exception:
            continue

        c = copy.deepcopy(l)
        c["id"] = novo_id("r")
        c["data"] = nova_data.isoformat()
        c["status"] = "prevista"
        c["gerado_em"] = datetime.now().isoformat()
        c.pop("paga_em", None)

        novos.append(c)

    return novos

# --------------------------------------------------
# 📦 PARCELAMENTO
# --------------------------------------------------
def gerar_parcelas(
    item_base: dict,
    qtd_parcelas: int,
    intervalo_meses: int = 1
) -> list:
    """
    Gera lista de parcelas com ajuste de centavos
    """
    assert qtd_parcelas >= 1, "Qtd de parcelas deve ser >= 1"

    total = float(item_base["valor"])
    base = round(total / qtd_parcelas, 2)
    valores = [base] * qtd_parcelas
    ajuste = round(total - sum(valores), 2)
    valores[-1] += ajuste

    group_id = item_base.get("group_id") or f"parc-{uuid.uuid4().hex[:8]}"
    parcelas = []

    data_ref = datetime.fromisoformat(item_base["data"]).date()

    for i in range(qtd_parcelas):
        p = copy.deepcopy(item_base)
        p["id"] = novo_id("p")
        p["group_id"] = group_id
        p["valor"] = valores[i]
        p["parcelamento"] = {
            "qtd_parcelas": qtd_parcelas,
            "parcela_num": i + 1
        }
        p["data"] = (
            (Datetime := (
                data_ref.replace(day=1) +
                timedelta(days=32 * i * intervalo_meses)
            )).replace(day=data_ref.day)
        ).isoformat()
        p["status"] = "prevista"
        p["paga_em"] = None

        parcelas.append(p)

    return parcelas

# --------------------------------------------------
# 🧠 UTILITÁRIOS
# --------------------------------------------------
def ativos(lista: list) -> list:
    """
    Retorna apenas itens não excluídos
    """
    return [x for x in lista if not x.get("excluido")]

def filtrar_periodo(lista: list, ini: date, fim: date) -> list:
    """
    Retorna itens dentro de um período
    """
    out = []
    for x in lista:
        try:
            d = datetime.fromisoformat(x["data"]).date()
            if ini <= d <= fim and not x.get("excluido"):
                out.append(x)
        except Exception:
            pass
    return out
