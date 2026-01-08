
# services/app_context.py
"""
Contexto e estado da aplicação (Streamlit Session State).

- Lê defaults de st.secrets
- Define usuário/perfil locais
- Controla o modo mobile (toggle global)
- Instancia GitHubService quando possível
- Expõe get_context() para uso em páginas e serviços
"""

import streamlit as st
from github_service import GitHubService


def init_context():
    """
    Inicializa o estado de sessão do Streamlit.

    Comportamento:
    - Carrega valores padrão de st.secrets (repo, token, branch)
    - Define chaves estáveis de usuário/perfil
    - Define 'modo_mobile' (toggle global de UI)
    - Instancia GitHubService se há credenciais
    - Sinaliza 'connected' e 'gh_error' conforme resultado
    """
    ss = st.session_state

    # -------------------------------------------------
    # Defaults vindos de st.secrets (se presentes)
    # -------------------------------------------------
    ss.setdefault("repo_full_name", st.secrets.get("repo_full_name", ""))
    ss.setdefault("github_token", st.secrets.get("github_token", ""))
    ss.setdefault("branch_name", st.secrets.get("branch_name", "main"))

    # -------------------------------------------------
    # Identidade local (placeholder para auth futura)
    # -------------------------------------------------
    ss.setdefault("usuario_id", "u1")
    ss.setdefault("perfil", "admin")

    # -------------------------------------------------
    # UI global — modo mobile (controlado pelo sidebar)
    # -------------------------------------------------
    ss.setdefault("modo_mobile", False)

    # -------------------------------------------------
    # Inicialização do serviço GitHub (se possível)
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
        # Se já existe 'gh' em sessão, considera conectado
        ss["connected"] = ss.get("gh") is not None


def get_context():
    """
    Retorna o session_state sem realizar mutações.

    IMPORTANTE:
    - NÃO chama init_context()
    - Seguro para uso em funções cacheadas e páginas
    """
    return st.session_state
