
# services/data_loader.py
import streamlit as st
from services.app_context import get_context

DEFAULTS = {
    "data/usuarios.json": [{"id": "u1", "nome": "Administrador", "perfil": "admin"}],
    "data/contas.json": [{"id": "c1", "nome": "Conta Corrente", "tipo": "banco", "moeda": "BRL", "saldo_inicial": 0.0}],
    "data/categorias.json": {
        "receitas": [
            {"id": "cr1", "nome": "Salário"},
            {"id": "cr2", "nome": "Freelancer"},
            {"id": "cr3", "nome": "Aluguel Recebido"}
        ],
        "despesas": [
            {"id": "cd1", "nome": "Moradia"},
            {"id": "cd2", "nome": "Alimentação"},
            {"id": "cd3", "nome": "Transporte"},
            {"id": "cd4", "nome": "Educação"},
            {"id": "cd5", "nome": "Lazer"}
        ]
    },
    "data/receitas.json": [],
    "data/despesas.json": [],
    "data/contas_pagar.json": [],
    "data/contas_receber.json": [],
    "data/metas.json": []
}


@st.cache_data(ttl=60, show_spinner=False)
def load_all(cache_key: tuple[str, str]):
    """
    Lê todos os arquivos via GitHubService presente no contexto.
    A chave do cache é (repo_full_name, branch_name) para evitar UnhashableParamError
    e garantir invalidação ao trocar de repositório/branch.
    """
    ctx = get_context()
    if not ctx.connected:
        raise RuntimeError("Não conectado ao GitHub. Informe repositório e token na barra lateral.")

    gh = ctx.gh
    data = {}
    for path, default in DEFAULTS.items():
        obj, sha = gh.ensure_file(path, default)
        data[path] = {"content": obj, "sha": sha}
    return data
