
# services/data_loader.py
import streamlit as st
from services.app_context import get_context
from services.finance_core import novo_id

DEFAULTS = {
    "data/usuarios.json": [
        {"id": "u1", "nome": "Administrador", "perfil": "admin", "ativo": True}
    ],
    "data/contas.json": [
        {
            "id": "c1",
            "nome": "Conta Corrente",
            "tipo": "banco",
            "moeda": "BRL",
            "saldo_inicial": 0.0,
            "ativa": True
        }
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
    "data/despesas.json": [],
    "data/receitas.json": [],
    "data/contas_pagar.json": [],
    "data/contas_receber.json": [],
    "data/orcamentos.json": [],
}

def _sanitizar_lista_de_dicts(gh, path: str, obj, sha: str, commit_msg: str) -> tuple[list, str]:
    """Sanitiza: garante lista de dicts; comita se remover inválidos."""
    if not isinstance(obj, list):
        obj = []
    clean = [x for x in obj if isinstance(x, dict)]
    if len(clean) != len(obj):
        new_sha = gh.put_json(path, clean, commit_msg, sha=sha)
        return clean, new_sha
    return obj, sha

def _migrar_legado(gh, data_dict: dict) -> None:
    """Migra dados legados (despesas/receitas/pagar/receber) para transacoes.json se vazio."""
    transacoes = data_dict["data/transacoes.json"]["content"]
    trans_sha = data_dict["data/transacoes.json"]["sha"]
    if isinstance(transacoes, list) and len(transacoes) > 0:
        return

    despesas = data_dict.get("data/despesas.json", {"content": []})["content"]
    receitas = data_dict.get("data/receitas.json", {"content": []})["content"]
    pagar    = data_dict.get("data/contas_pagar.json", {"content": []})["content"]
    receber  = data_dict.get("data/contas_receber.json", {"content": []})["content"]

    txs = []

    if isinstance(despesas, list):
        for d in despesas:
            if not isinstance(d, dict):
                continue
            txs.append({
                "id": d.get("id") or novo_id("tx"),
                "tipo": "despesa",
                "descricao": d.get("descricao", "Despesa"),
                "valor": float(d.get("valor", 0.0)),
                "data_prevista": d.get("data"),
                "data_efetiva": d.get("paga_em"),
                "conta_id": d.get("conta_id", "c1"),
                "categoria_id": d.get("categoria_id"),
                "excluido": bool(d.get("excluido", False)),
                "parcelamento": d.get("parcelamento"),
                "recorrente": bool(d.get("recorrente", False)),
            })

    if isinstance(receitas, list):
        for r in receitas:
            if not isinstance(r, dict):
                continue
            txs.append({
                "id": r.get("id") or novo_id("tx"),
                "tipo": "receita",
                "descricao": r.get("descricao", "Receita"),
                "valor": float(r.get("valor", 0.0)),
                "data_prevista": r.get("data"),
                "data_efetiva": r.get("recebido_em"),
                "conta_id": r.get("conta_id", "c1"),
                "categoria_id": r.get("categoria_id"),
                "excluido": bool(r.get("excluido", False)),
            })

    if isinstance(pagar, list):
        for c in pagar:
            if not isinstance(c, dict):
                continue
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

    if isinstance(receber, list):
        for c in receber:
            if not isinstance(c, dict):
                continue
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
        new_sha = gh.put_json(
            "data/transacoes.json",
            txs,
            "Migração automática: unificação (despesas/receitas/pagar/receber -> transacoes.json)",
            sha=trans_sha
        )
        data_dict["data/transacoes.json"] = {"content": txs, "sha": new_sha}
        st.cache_data.clear()

# --------- Loaders fragmentados (por recurso) ---------
@st.cache_data(ttl=60, show_spinner=False)
def load_transactions(key: tuple[str, str]):
    ctx = get_context()
    gh = ctx.get("gh")
    # garante existência de todos para migração
    data = {}
    for path, default in DEFAULTS.items():
        obj, sha = gh.ensure_file(path, default)
        data[path] = {"content": obj, "sha": sha}
    _migrar_legado(gh, data)
    # recarrega transacoes e sanitiza
    obj, sha = gh.ensure_file("data/transacoes.json", DEFAULTS["data/transacoes.json"])
    obj, sha = _sanitizar_lista_de_dicts(gh, "data/transacoes.json", obj, sha, "Sanitiza transacoes.json")
    return {"content": obj, "sha": sha}

@st.cache_data(ttl=120, show_spinner=False)
def load_categories(key: tuple[str, str]):
    ctx = get_context()
    gh = ctx.get("gh")
    cats, sha = gh.ensure_file("data/categorias.json", DEFAULTS["data/categorias.json"])
    cats = [c for c in cats if isinstance(c, dict)]
    return {"content": cats, "sha": sha}

@st.cache_data(ttl=120, show_spinner=False)
def load_accounts(key: tuple[str, str]):
    ctx = get_context()
    gh = ctx.get("gh")
    acc, sha = gh.ensure_file("data/contas.json", DEFAULTS["data/contas.json"])
    acc = [a for a in acc if isinstance(a, dict)]
    return {"content": acc, "sha": sha}

@st.cache_data(ttl=120, show_spinner=False)
def load_budgets(key: tuple[str, str]):
    ctx = get_context()
    gh = ctx.get("gh")
    obj, sha = gh.ensure_file("data/orcamentos.json", DEFAULTS["data/orcamentos.json"])
    obj = [o for o in obj if isinstance(o, dict)]
    return {"content": obj, "sha": sha}

@st.cache_data(ttl=120, show_spinner=False)
def load_users(key: tuple[str, str]):
    ctx = get_context()
    gh = ctx.get("gh")
    users, sha = gh.ensure_file("data/usuarios.json", DEFAULTS["data/usuarios.json"])
    users = [u for u in users if isinstance(u, dict)]
    return {"content": users, "sha": sha}

@st.cache_data(ttl=120, show_spinner=False)
def load_goals(key: tuple[str, str]):
    ctx = get_context()
    gh = ctx.get("gh")
    metas, sha = gh.ensure_file("data/metas.json", DEFAULTS["data/metas.json"])
    metas, sha = _sanitizar_lista_de_dicts(gh, "data/metas.json", metas, sha, "Sanitiza metas.json")
    return {"content": metas, "sha": sha}

@st.cache_data(ttl=120, show_spinner=False)
def load_events(key: tuple[str, str]):
    ctx = get_context()
    gh = ctx.get("gh")
    ev, sha = gh.ensure_file("data/eventos.json", DEFAULTS["data/eventos.json"])
    ev = [e for e in ev if isinstance(e, dict)]
    return {"content": ev, "sha": sha}
