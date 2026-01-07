
import streamlit as st
from services.app_context import get_context

DEFAULTS = {
    "data/usuarios.json": [{"id": "u1", "nome": "Administrador", "perfil": "admin"}],
    "data/contas.json": [{"id": "c1", "nome": "Conta Corrente", "saldo_inicial": 0.0}],
    "data/categorias.json": {
        "receitas": [{"id": "cr1", "nome": "Salário"}],
        "despesas": [{"id": "cd1", "nome": "Alimentação"}],
    },
    "data/receitas.json": [],
    "data/despesas.json": [],
    "data/contas_pagar.json": [],
    "data/contas_receber.json": [],
    "data/metas.json": [],
}

@st.cache_data(ttl=60)
def load_all(cache_key: tuple[str, str]):
    ctx = get_context()
    gh = ctx["gh"]

    data = {}
    for path, default in DEFAULTS.items():
        obj, sha = gh.ensure_file(path, default)
        data[path] = {"content": obj, "sha": sha}

    return data

