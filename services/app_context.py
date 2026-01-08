
# services/app_context.py
import streamlit as st
from github_service import GitHubService


def init_context():
    """
    Inicializa o estado de sessão do Streamlit.

    - Lê defaults de st.secrets
    - Define usuário e perfil locais
    - Instancia GitHubService se possível
    """

    ss = st.session_state

    # -------------------------------------------------
    # CHANGE: configuração explícita e previsível
    # -------------------------------------------------
    ss.setdefault("repo_full_name", st.secrets.get("repo_full_name", ""))
    ss.setdefault("github_token", st.secrets.get("github_token", ""))
    ss.setdefault("branch_name", st.secrets.get("branch_name", "main"))

    # Usuário local (placeholder para auth futura)
    ss.setdefault("usuario_id", "u1")
    ss.setdefault("perfil", "admin")

    # -------------------------------------------------
    # Inicialização do serviço GitHub
    # -------------------------------------------------
    if "gh" not in ss and ss["repo_full_name"] and ss["github_token"]:
        try:
            ss["gh"] = GitHubService(
                token=ss["github_token"],
                repo_full_name=ss["repo_full_name"],
                branch=ss["branch_name"],
            )
            ss["connected"] = True
            ss.pop("gh_error", None)
        except Exception as e:
            ss["gh"] = None
            ss["connected"] = False
            ss["gh_error"] = str(e)
    else:
        ss["connected"] = ss.get("gh") is not None


def get_context():
    """
    Retorna o session_state sem realizar mutações.

    IMPORTANTE:
    - NÃO chama init_context()
    - Seguro para ser usado em funções cacheadas
    """
    return st.session_state
