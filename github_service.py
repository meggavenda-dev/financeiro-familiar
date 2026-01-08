# github_service.py
import base64
import json
import requests
from time import sleep
from typing import Tuple, Any, Optional, Callable

class GitHubService:
    """
    Serviço de integração com a GitHub Contents API para usar arquivos JSON
    como “banco de dados” versionado (commits por alteração).
    """

    def __init__(
        self,
        token: str,
        repo_full_name: str,
        branch: str = "main",
        request_timeout: int = 15,
        max_retries: int = 2,
        user_agent: str = "financeiro-familiar-streamlit"
    ):
        """
        :param token: PAT com escopo 'repo' (para leitura/escrita).
        :param repo_full_name: "owner/repo".
        :param branch: branch alvo (ex.: 'main').
        :param request_timeout: timeout (segundos) por requisição.
        :param max_retries: tentativas em erros transitórios (timeout/conexão).
        :param user_agent: header de identificação do cliente.
        """
        if not token or not repo_full_name:
            raise ValueError("Token e repo_full_name são obrigatórios.")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": user_agent,
        })

        self.api_base = "https://api.github.com"
        self.repo = repo_full_name
        self.branch = branch
        self.timeout = request_timeout
        self.max_retries = max_retries

    # ---------------- Internos ----------------
    def _contents_url(self, path: str) -> str:
        return f"{self.api_base}/repos/{self.repo}/contents/{path}"

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
                # Mensagens mais claras em limite de taxa
                if "X-RateLimit-Remaining" in resp.headers:
                    remaining = resp.headers["X-RateLimit-Remaining"]
                    if remaining == "0":
                        reset = resp.headers.get("X-RateLimit-Reset", "desconhecido")
                        raise RuntimeError(f"Rate limit atingido. Reseta em {reset}.")
                return resp
            except requests.exceptions.Timeout:
                if attempt < self.max_retries:
                    sleep(0.8)
                    continue
                raise
            except requests.exceptions.RequestException:
                if attempt < self.max_retries:
                    sleep(0.8)
                    continue
                raise

    # ---------------- Operações principais ----------------
    def get_json(self, path: str, default: Optional[Any] = None) -> Tuple[Any, Optional[str]]:
        """
        Lê um arquivo JSON do repositório (branch).
        Retorna (objeto, sha). Se não existir e houver default, cria e lê novamente.
        """
        url = self._contents_url(path)
        params = {"ref": self.branch}
        r = self._request("GET", url, params=params)

        if r.status_code == 200:
            data = r.json()
            content_b64 = data.get("content", "")
            decoded = base64.b64decode(content_b64)
            obj = json.loads(decoded.decode("utf-8"))
            return obj, data.get("sha")

        if r.status_code == 404:
            if default is not None:
                self.put_json(path, default, f"Inicializa {path}")
                obj, sha = self.get_json(path, default=None)
                return obj, sha
            return default, None

        if r.status_code in (401, 403):
            raise RuntimeError(
                f"Acesso negado ao ler {path}. Verifique token, escopos e permissões. ({r.status_code})\n{r.text}"
            )

        raise RuntimeError(f"Erro ao ler {path}: {r.status_code}\n{r.text}")

    def put_json(self, path: str, obj: Any, message: str, sha: Optional[str] = None) -> str:
        """
        Cria/atualiza um arquivo JSON com commit. Retorna o novo SHA.
        Usa 'sha' para controle de concorrência; se houver conflito (409),
        recarrega e tenta novamente uma vez.
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

        r = self._request("PUT", url, json=payload)

        if r.status_code in (200, 201):
            return r.json()["content"]["sha"]

        if r.status_code == 409:
            current, current_sha = self.get_json(path, default=obj)
            payload["sha"] = current_sha
            r2 = self._request("PUT", url, json=payload)
            if r2.status_code in (200, 201):
                return r2.json()["content"]["sha"]
            raise RuntimeError(f"Conflito ao salvar {path}: {r2.status_code}\n{r2.text}")

        if r.status_code in (401, 403):
            raise RuntimeError(
                f"Acesso negado ao salvar {path}. Verifique token, escopos e branch (proteções). ({r.status_code})\n{r.text}"
            )

        raise RuntimeError(f"Erro ao salvar {path}: {r.status_code}\n{r.text}")

    def ensure_file(self, path: str, default: Any) -> Tuple[Any, Optional[str]]:
        """Garante que o arquivo exista (cria com default se necessário) e retorna seu conteúdo e sha."""
        return self.get_json(path, default=default)

    # ---------------- Helpers “read-modify-write” ----------------
    def append_json(self, path: str, item: Any, commit_message: str) -> None:
        """Append em lista JSON + commit."""
        arr, sha = self.get_json(path, default=[])
        if not isinstance(arr, list):
            raise ValueError(f"{path} não é uma lista JSON.")
        arr.append(item)
        self.put_json(path, arr, commit_message, sha=sha)

    def update_json(self, path: str, transform: Callable[[Any], Any], commit_message: str) -> None:
        """Atualiza JSON aplicando uma função transformadora."""
        obj, sha = self.get_json(path, default=[])
        new_obj = transform(obj)
        self.put_json(path, new_obj, commit_message, sha=sha)

    def update_status_by_id(self, path: str, item_id: str, new_status: str, commit_message_prefix: str = "Update status") -> bool:
        """Atualiza campo 'status' de um item em lista JSON pelo ID."""
        def _transform(arr):
            found = False
            if isinstance(arr, list):
                for it in arr:
                    if isinstance(it, dict) and it.get("id") == item_id:
                        it["status"] = new_status
                        found = True
                        break
            if not found:
                return arr
            return arr

        before, sha = self.get_json(path, default=[])
        after = _transform(before)
        if before is after:
            return False
        self.put_json(path, after, f"{commit_message_prefix}: {item_id} -> {new_status}", sha=sha)
        return True

    # ---------------- Diagnóstico ----------------
    def ping(self) -> bool:
        """Verifica se consegue listar o repositório (diagnóstico rápido)."""
        url = f"{self.api_base}/repos/{self.repo}"
        r = self._request("GET", url)
        return r.status_code == 200
