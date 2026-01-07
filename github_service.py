
# github_service.py
import base64
import json
import requests
from typing import Tuple, Any, Optional

class GitHubService:
    """
    Integração mínima com GitHub para usar o repositório como “banco de dados”.
    Lê e grava arquivos JSON em uma branch específica usando a Contents API.
    """

    def __init__(self, token: str, repo_full_name: str, branch: str = "main"):
        """
        :param token: GitHub Personal Access Token (PAT) com escopo 'repo'.
        :param repo_full_name: "usuario/nome-repositorio".
        :param branch: branch alvo (ex.: 'main').
        """
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "financeiro-familiar-streamlit"
        })
        self.api_base = "https://api.github.com"
        self.repo = repo_full_name
        self.branch = branch

    def _contents_url(self, path: str) -> str:
        return f"{self.api_base}/repos/{self.repo}/contents/{path}"

    def get_json(self, path: str, default: Optional[Any] = None) -> Tuple[Any, Optional[str]]:
        """
        Lê um arquivo JSON do GitHub.
        :return: (objeto_json, sha) — sha é necessário para updates concorrentes.
        """
        url = self._contents_url(path)
        params = {"ref": self.branch}
        r = self.session.get(url, params=params)
        if r.status_code == 200:
            data = r.json()
            content_b64 = data.get("content", "")
            decoded = base64.b64decode(content_b64)
            obj = json.loads(decoded.decode("utf-8"))
            return obj, data.get("sha")
        elif r.status_code == 404:
            # Se não existir e houver default, cria o arquivo.
            if default is not None:
                self.put_json(path, default, f"Inicializa {path}")
                # Lê novamente para obter sha atualizado
                obj, sha = self.get_json(path, default=None)
                return obj, sha
            return default, None
        else:
            raise RuntimeError(f"Erro ao ler {path}: {r.status_code} {r.text}")

    def put_json(self, path: str, obj: Any, message: str, sha: Optional[str] = None) -> str:
        """
        Cria/atualiza um arquivo JSON. Retorna o novo SHA do conteúdo.
        """
        url = self._contents_url(path)
        content_str = json.dumps(obj, ensure_ascii=False, indent=2)
        b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
        payload = {
            "message": message,
            "content": b64,
            "branch": self.branch
        }
        if sha:
            payload["sha"] = sha

        r = self.session.put(url, json=payload)
        if r.status_code in (200, 201):
            return r.json()["content"]["sha"]
        elif r.status_code == 409:
            # Conflito: recarrega sha e tenta novamente uma vez
            current, current_sha = self.get_json(path, default=obj)
            payload["sha"] = current_sha
            r2 = self.session.put(url, json=payload)
            if r2.status_code in (200, 201):
                return r2.json()["content"]["sha"]
            raise RuntimeError(f"Conflito ao salvar {path}: {r2.status_code} {r2.text}")
        else:
            raise RuntimeError(f"Erro ao salvar {path}: {r.status_code} {r.text}")

    def ensure_file(self, path: str, default: Any) -> Tuple[Any, Optional[str]]:
        """
        Garante que o arquivo exista (cria com default se necessário) e retorna seu conteúdo e sha.
        """
        return self.get_json(path, default=default)
