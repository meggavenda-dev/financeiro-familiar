# services/app_context.py
import streamlit as st
from github_service import GitHubService


def init_context():
    """Inicializa sessão e tenta instanciar GitHubService se houver credenciais."""
    ss = st.session_state

    ss["repo_full_name"] = ss.get("repo_full_name", st.secrets.get("repo_full_name", ""))
    ss["github_token"] = ss.get("github_token", st.secrets.get("github_token", ""))
    ss["branch_name"] = ss.get("branch_name", st.secrets.get("branch_name", "main"))

    ss["usuario_id"] = ss.get("usuario_id", "u1")
    ss["perfil"] = ss.get("perfil", "admin")

    if "gh" not in ss and ss["repo_full_name"] and ss["github_token"]:
        try:
            ss["gh"] = GitHubService(
                token=ss["github_token"],
                repo_full_name=ss["repo_full_name"],
                branch=ss["branch_name"],
            )
        except Exception:
            pass  # UI lidará com erro/aviso

    ss["connected"] = "gh" in ss


def get_context():
    init_context()
    return st.session_state
