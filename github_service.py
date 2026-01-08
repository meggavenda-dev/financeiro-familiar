
# github_service.py
import base64
import json
import requests
import logging
from time import sleep
from typing import Tuple, Any, Optional, Callable

logger = logging.getLogger("financeiro")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

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
        user_agent: str = "financeiro-familiar-streamlit",
        api_base: str = "https://api.github.com",
    ):
        """
        :param token: PAT com escopo 'repo' (para leitura/escrita).
        :param repo_full_name: "owner/repo".
        :param branch: branch alvo (ex.: 'main').
        :param request_timeout: timeout (segundos) por requisição.
        :param max_retries: tentativas em erros transitórios (timeout/conexão).
        :param user_agent: header de identificação do cliente.
        :param api_base: base da API (permite GitHub Enterprise).
        """
        if not token or not repo_full_name:
            raise ValueError("Token e repo_full_name são obrigatórios.")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": user_agent,
        })

        self.api_base = api_base.rstrip("/")
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
                # Diagnóstico de rate limit
                remaining = int(resp.headers.get("X-RateLimit-Remaining", "1"))
                if remaining <= 0:
                    reset = resp.headers.get("X-RateLimit-Reset", "desconhecido")
                    logger.warning(f"Rate limit atingido; reseta em {reset}")
                    raise RuntimeError(f"Rate limit atingido. Reseta em {reset}.")

                # 429 (se ocorrer) com Retry-After
                if resp.status_code == 429:
                    ra = int(resp.headers.get("Retry-After", "1"))
                    logger.warning(f"429 recebido. Aguardando {ra}s antes de tentar novamente.")
                    sleep(ra)
                    continue
                return resp
            except requests.exceptions.Timeout:
                if attempt < self.max_retries:
                    sleep(0.8)
                    continue
                logger.error("Timeout ao chamar GitHub API.")
                raise
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries:
                    sleep(0.8)
                    continue
                logger.error(f"Erro de requisição: {e}")
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
            logger.info(f"GET {path} (sha={data.get('sha')[:7] if data.get('sha') else '—'})")
            return obj, data.get("sha")

        if r.status_code == 404:
            if default is not None:
                logger.info(f"{path} inexistente. Inicializando com default.")
                self.put_json(path, default, f"Inicializa {path}")
                obj, sha = self.get_json(path, default=None)
                return obj, sha
            return default, None

        if r.status_code in (401, 403):
            logger.error(f"Acesso negado ao ler {path}: {r.status_code}")
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
            new_sha = r.json()["content"]["sha"]
            logger.info(f"PUT {path} OK (nova sha={new_sha[:7]})")
            return new_sha

        if r.status_code == 409:
            logger.warning(f"409 em {path}. Recarregando e tentando novamente.")
            current, current_sha = self.get_json(path, default=obj)
            payload["sha"] = current_sha
            r2 = self._request("PUT", url, json=payload)
            if r2.status_code in (200, 201):
                new_sha = r2.json()["content"]["sha"]
                logger.info(f"PUT {path} após 409 OK (sha={new_sha[:7]})")
                return new_sha
            raise RuntimeError(f"Conflito ao salvar {path}: {r2.status_code}\n{r2.text}")

        if r.status_code in (401, 403):
            logger.error(f"Acesso negado ao salvar {path}: {r.status_code}")
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
        """
        Atualiza campo 'status' de um item em lista JSON pelo ID.
        Nota: status é idealmente derivado no UI. Use apenas se quiser persistir.
        """
        arr, sha = self.get_json(path, default=[])
        found = False
        if isinstance(arr, list):
            for it in arr:
                if isinstance(it, dict) and it.get("id") == item_id:
                    it["status"] = new_status  # se optar por persistir
                    found = True
                    break
        if not found:
            return False
        self.put_json(path, arr, f"{commit_message_prefix}: {item_id} -> {new_status}", sha=sha)
        return True

    # ---------------- Diagnóstico ----------------
    def ping(self) -> bool:
        """Verifica se consegue listar o repositório (diagnóstico rápido)."""
        url = f"{self.api_base}/repos/{self.repo}"
        r = self._request("GET", url)
        return r.status_code == 200
