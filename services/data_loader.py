
# services/data_loader.py
import streamlit as st
from services.app_context import get_context
from services.finance_core import novo_id
from datetime import datetime

DEFAULTS = {
    "data/usuarios.json": [
        {"id": "u1", "nome": "Administrador", "perfil": "admin", "ativo": True}
    ],
    "data/contas.json": [
        {"id": "c1", "nome": "Conta Corrente", "tipo": "banco", "moeda": "BRL", "saldo_inicial": 0.0, "ativa": True}
    ],
    "data/categorias.json": [
        {"id": "cat1", "nome": "Moradia", "tipo": "despesa"},
        {"id": "cat2", "nome": "Alimentação", "tipo": "despesa"},
        {"id": "cat3", "nome": "Transporte", "tipo": "despesa"},
        {"id": "cat4", "nome": "Educação", "tipo": "despesa"},
        {"id": "cat5", "nome": "Lazer", "tipo": "despesa"},
        {"id": "cat6", "nome": "Salário", "tipo": "receita"},
        {"id": "cat7", "nome": "Freelancer", "tipo": "receita"},
        {"id": "cat8", "nome": "Aluguel Recebido", "tipo": "receita"},
    ],
    "data/transacoes.json": [],
    "data/metas.json": [],
    "data/eventos.json": [],
    # legado opcional (será migrado se existirem):
    "data/despesas.json": [],
    "data/receitas.json": [],
    "data/contas_pagar.json": [],
    "data/contas_receber.json": [],
    "data/orcamentos.json": [],  # se você usa orçamento, mantemos como opcional
}

def _migrar_legado(gh, data_dict: dict):
    """Migra seus arquivos antigos para transacoes.json (executa apenas se transacoes.json estiver vazio)."""
    transacoes = data_dict["data/transacoes.json"]["content"]

    if transacoes:  # já existe base nova → não migra
        return

    despesas = data_dict.get("data/despesas.json", {"content": []})["content"]
    receitas = data_dict.get("data/receitas.json", {"content": []})["content"]
    pagar = data_dict.get("data/contas_pagar.json", {"content": []})["content"]
    receber = data_dict.get("data/contas_receber.json", {"content": []})["content"]

    txs = []

    # despesas antigas
    for d in despesas:
        txs.append({
            "id": d.get("id") or novo_id("tx"),
            "tipo": "despesa",
            "descricao": d.get("descricao", "Despesa"),
            "valor": float(d.get("valor", 0.0)),
            "data_prevista": d.get("data"),
            "data_efetiva": d.get("paga_em"),
            "conta_id": d.get("conta_id", "c1"),
            "categoria_id": d.get("categoria_id"),
            "excluido": d.get("excluido", False),
            "parcelamento": d.get("parcelamento"),
            "recorrente": d.get("recorrente", False),
        })

    # receitas antigas
    for r in receitas:
        txs.append({
            "id": r.get("id") or novo_id("tx"),
            "tipo": "receita",
            "descricao": r.get("descricao", "Receita"),
            "valor": float(r.get("valor", 0.0)),
            "data_prevista": r.get("data"),
            "data_efetiva": r.get("recebido_em"),
            "conta_id": r.get("conta_id", "c1"),
            "categoria_id": r.get("categoria_id"),
            "excluido": r.get("excluido", False),
        })

    # contas a pagar (despesa futura)
    for c in pagar:
        txs.append({
            "id": c.get("id") or novo_id("tx"),
            "tipo": "despesa",
            "descricao": c.get("descricao", "Conta a pagar"),
            "valor": float(c.get("valor", 0.0)),
            "data_prevista": c.get("vencimento"),
            "data_efetiva": c.get("paga_em"),
            "conta_id": c.get("conta_id", "c1"),
            "categoria_id": c.get("categoria_id"),
            "excluido": False,
        })

    # contas a receber (receita futura)
    for c in receber:
        txs.append({
            "id": c.get("id") or novo_id("tx"),
            "tipo": "receita",
            "descricao": c.get("descricao", "Conta a receber"),
            "valor": float(c.get("valor", 0.0)),
            "data_prevista": c.get("previsto"),
            "data_efetiva": c.get("recebido_em"),
            "conta_id": c.get("conta_id", "c1"),
            "categoria_id": c.get("categoria_id"),
            "excluido": False,
        })

    if txs:
        _, sha = gh.ensure_file("data/transacoes.json", [])
        gh.put_json("data/transacoes.json", txs, "Migração automática: unificação em transacoes.json", sha=sha)
        st.cache_data.clear()


@st.cache_data(ttl=60, show_spinner=False)
def load_all(cache_key: tuple[str, str]):
    """
    Lê todos os arquivos via GitHubService presente no contexto.
    A chave do cache é (repo_full_name, branch_name).
    """
    ctx = get_context()
    if not ctx.connected:
        raise RuntimeError("Não conectado ao GitHub. Informe repositório e token na barra lateral.")

    gh = ctx.gh
    data = {}
    for path, default in DEFAULTS.items():
        obj, sha = gh.ensure_file(path, default)
        data[path] = {"content": obj, "sha": sha}

    # migra se necessário
    _migrar_legado(gh, data)

    # recarrega transacoes após eventual migração
    obj, sha = gh.ensure_file("data/transacoes.json", [])
    data["data/transacoes.json"] = {"content": obj, "sha": sha}
    return data
