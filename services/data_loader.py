
# services/data_loader.py
import streamlit as st
from services.app_context import get_context
from services.finance_core import novo_id

# ---------------------------------------------------------
# Defaults para os arquivos usados pelo app
# ---------------------------------------------------------
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
            "ativa": True,
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
    # legado
    "data/despesas.json": [],
    "data/receitas.json": [],
    "data/contas_pagar.json": [],
    "data/contas_receber.json": [],
    "data/orcamentos.json": [],
}


# ---------------------------------------------------------
# CHANGE: sanitização genérica sem commit desnecessário
# ---------------------------------------------------------
def _sanitizar_lista(gh, path: str, obj, sha: str, commit_msg: str):
    if not isinstance(obj, list):
        clean = []
    else:
        clean = [x for x in obj if isinstance(x, dict)]

    if clean != obj:
        new_sha = gh.put_json(path, clean, commit_msg, sha=sha)
        st.cache_data.clear()
        return clean, new_sha

    return obj, sha


# ---------------------------------------------------------
# CHANGE: garante códigos somente se houver alteração
# ---------------------------------------------------------
def _garantir_codigos(gh, path: str, items: list, sha: str):
    changed = False
    cods = [x.get("codigo") for x in items if isinstance(x.get("codigo"), int)]
    next_code = max(cods) + 1 if cods else 1
    usados = set(cods)

    for it in items:
        if not isinstance(it.get("codigo"), int):
            while next_code in usados:
                next_code += 1
            it["codigo"] = next_code
            usados.add(next_code)
            next_code += 1
            changed = True

    if changed:
        new_sha = gh.put_json(path, items, f"Normaliza códigos em {path}", sha=sha)
        st.cache_data.clear()
        return items, new_sha

    return items, sha


# ---------------------------------------------------------
# Migração legada (executa uma única vez)
# ---------------------------------------------------------
def _migrar_legado(gh, data: dict):
    transacoes = data["data/transacoes.json"]["content"]
    sha = data["data/transacoes.json"]["sha"]

    if transacoes:
        return

    txs = []

    for d in data.get("data/despesas.json", {}).get("content", []):
        if isinstance(d, dict):
            txs.append({
                "id": d.get("id") or novo_id("tx"),
                "tipo": "despesa",
                "descricao": d.get("descricao", "Despesa"),
                "valor": float(d.get("valor", 0)),
                "data_prevista": d.get("data"),
                "data_efetiva": d.get("paga_em"),
                "conta_id": d.get("conta_id", "c1"),
                "categoria_id": d.get("categoria_id"),
                "excluido": bool(d.get("excluido", False)),
            })

    for r in data.get("data/receitas.json", {}).get("content", []):
        if isinstance(r, dict):
            txs.append({
                "id": r.get("id") or novo_id("tx"),
                "tipo": "receita",
                "descricao": r.get("descricao", "Receita"),
                "valor": float(r.get("valor", 0)),
                "data_prevista": r.get("data"),
                "data_efetiva": r.get("recebido_em"),
                "conta_id": r.get("conta_id", "c1"),
                "categoria_id": r.get("categoria_id"),
                "excluido": bool(r.get("excluido", False)),
            })

    if txs:
        new_sha = gh.put_json(
            "data/transacoes.json",
            txs,
            "Migração automática legado → transacoes.json",
            sha=sha,
        )
        data["data/transacoes.json"] = {"content": txs, "sha": new_sha}
        st.cache_data.clear()


# ---------------------------------------------------------
# Loader principal (cacheado)
# ---------------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def load_all(cache_key: tuple):
    ctx = get_context()
    if not ctx.get("connected"):
        raise RuntimeError("Não conectado ao GitHub.")

    gh = ctx.get("gh")
    data = {}

    # Garantir existência
    for path, default in DEFAULTS.items():
        obj, sha = gh.ensure_file(path, default)
        data[path] = {"content": obj, "sha": sha}

    # Migração legado
    _migrar_legado(gh, data)

    # Transações
    txs, sha = _sanitizar_lista(
        gh,
        "data/transacoes.json",
        data["data/transacoes.json"]["content"],
        data["data/transacoes.json"]["sha"],
        "Sanitiza transacoes.json",
    )
    txs, sha = _garantir_codigos(gh, "data/transacoes.json", txs, sha)
    data["data/transacoes.json"] = {"content": txs, "sha": sha}

    # Categorias
    cats, sha = _sanitizar_lista(
        gh,
        "data/categorias.json",
        data["data/categorias.json"]["content"],
        data["data/categorias.json"]["sha"],
        "Sanitiza categorias.json",
    )
    cats, sha = _garantir_codigos(gh, "data/categorias.json", cats, sha)
    data["data/categorias.json"] = {"content": cats, "sha": sha}

    # Metas
    metas, sha = _sanitizar_lista(
        gh,
        "data/metas.json",
        data["data/metas.json"]["content"],
        data["data/metas.json"]["sha"],
        "Sanitiza metas.json",
    )
    data["data/metas.json"] = {"content": metas, "sha": sha}

    return data


# ---------------------------------------------------------
# Helpers públicos
# ---------------------------------------------------------
def listar_categorias(gh):
    cats, sha = gh.ensure_file("data/categorias.json", DEFAULTS["data/categorias.json"])
    return [c for c in cats if isinstance(c, dict)], sha
