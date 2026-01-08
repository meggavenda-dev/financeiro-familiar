
# services/app_context.py
import streamlit as st
from github_service import GitHubService

def init_context():
    """
    Inicializa o estado de sessão do Streamlit e tenta instanciar o GitHubService
    se houver credenciais disponíveis.

    - Lê valores padrão de st.secrets (repo_full_name, github_token, branch_name).
    - Define usuário e perfil default (u1 / admin).
    - Cria instância de GitHubService caso ainda não exista e haja credenciais.
    - Marca 'connected' no session_state para guiar o fluxo das páginas.
    """
    ss = st.session_state

    # Valores padrão / secrets
    ss["repo_full_name"] = ss.get("repo_full_name", st.secrets.get("repo_full_name", ""))
    ss["github_token"]   = ss.get("github_token",   st.secrets.get("github_token", ""))
    ss["branch_name"]    = ss.get("branch_name",    st.secrets.get("branch_name", "main"))

    # Contexto de usuário local (pode ser ligado a autenticação futuramente)
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
            # Em caso de falha (token inválido, permissão insuficiente, etc.)
            ss["gh"] = None
            ss["connected"] = False
            ss["gh_error"] = str(e)
    else:
        # Se já existe 'gh' no estado, considera conectado quando não é None
        ss["connected"] = "gh" in ss and ss["gh"] is not None

def get_context():
    """
    Retorna o session_state sem mutações.
    NÃO chama init_context() para evitar escrita dentro de funções cacheadas.
    Garanta que init_context() foi chamado no início da execução de cada página/app.
    """
    return st.session_state
