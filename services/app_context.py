
# services/app_context.py
import streamlit as st
from github_service import GitHubService


def init_context():
    """Inicializa chaves no session_state e tenta instanciar o GitHubService se houver credenciais."""
    ss = st.session_state

    # Fallback dos secrets para o session_state
    if "repo_full_name" not in ss:
        ss.repo_full_name = st.secrets.get("repo_full_name", "")
    if "github_token" not in ss:
        ss.github_token = st.secrets.get("github_token", "")
    if "branch_name" not in ss:
        ss.branch_name = st.secrets.get("branch_name", "main")

    # Estado do usuário/perfil
    if "usuario_id" not in ss:
        ss.usuario_id = "u1"
    if "perfil" not in ss:
        ss.perfil = "admin"

    # Conexão GitHub (só cria se houver credenciais)
    if "gh" not in ss and ss.repo_full_name and ss.github_token:
        try:
            ss.gh = GitHubService(
                token=ss.github_token,
                repo_full_name=ss.repo_full_name,
                branch=ss.branch_name
            )
        except Exception:
            # não marca como conectado; a UI do app fará o tratamento/alerta
            pass

    ss.connected = "gh" in ss


def get_context():
    """Retorna o session_state (após garantir inicialização)."""
    init_context()
    return st.session_state

