# services/app_context.py
import streamlit as st
from github_service import GitHubService


def init_context():
    """Inicializa sessão e tenta instanciar GitHubService se houver credenciais."""
    ss = st.session_state

    # Inicializações idempotentes (podem ser chamadas várias vezes na parte "normal" do app)
    ss["repo_full_name"] = ss.get("repo_full_name", st.secrets.get("repo_full_name", ""))
    ss["github_token"] = ss.get("github_token", st.secrets.get("github_token", ""))
    ss["branch_name"] = ss.get("branch_name", st.secrets.get("branch_name", "main"))

    ss["usuario_id"] = ss.get("usuario_id", "u1")
    ss["perfil"] = ss.get("perfil", "admin")

    # Instancia GitHubService se houver credenciais e ainda não existir
    if "gh" not in ss and ss["repo_full_name"] and ss["github_token"]:
        try:
            ss["gh"] = GitHubService(
                token=ss["github_token"],
                repo_full_name=ss["repo_full_name"],
                branch=ss["branch_name"],
            )
        except Exception:
            # UI lidará com erro/aviso
            pass

    ss["connected"] = "gh" in ss


def get_context():
    """
    Retorna o session_state sem mutações.
    NÃO chama init_context() para evitar escrita dentro de funções cacheadas.
    Garanta que init_context() foi chamado no início da execução de cada página/app.
    """
    return st.session_state
