
# services/app_context.py
import streamlit as st
from dataclasses import dataclass
from github_service import GitHubService

def init_context():
    """Inicializa session_state e tenta instanciar GitHubService se houver credenciais."""
    ss = st.session_state
    ss["repo_full_name"] = ss.get("repo_full_name", st.secrets.get("repo_full_name", ""))
    ss["github_token"] = ss.get("github_token", st.secrets.get("github_token", ""))
    ss["branch_name"]  = ss.get("branch_name",  st.secrets.get("branch_name", "main"))

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
            ss["connected"] = True
        except Exception as e:
            ss["gh"] = None
            ss["connected"] = False
            ss["gh_error"] = str(e)
    else:
        ss["connected"] = "gh" in ss and ss["gh"] is not None

def get_context():
    """Retorna o session_state cru (para casos avançados)."""
    return st.session_state

@dataclass(frozen=True)
class AppConfig:
    connected: bool
    repo_full_name: str
    branch_name: str
    perfil: str

def get_config() -> AppConfig:
    """Retorna uma visão imutável do contexto (evita mutações acidentais nas páginas)."""
    ss = st.session_state
    return AppConfig(
        connected=bool(ss.get("connected")),
        repo_full_name=str(ss.get("repo_full_name", "")),
        branch_name=str(ss.get("branch_name", "main")),
        perfil=str(ss.get("perfil", "comum")),
    )
