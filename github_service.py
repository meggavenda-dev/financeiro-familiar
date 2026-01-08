
# github_service.py
import base64
import json
import requests
import logging
import time
import random
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

    # ------------------------------------------------------------------
    # CHANGE: rate limit com backoff + jitter + secondary limit
    # ------------------------------------------------------------------
    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)

                remaining = int(resp.headers.get("X-RateLimit-Remaining", "1"))

                # CHANGE: espera até reset em vez de falhar
                if remaining <= 0:
                    reset = int(resp.headers.get("X-RateLimit-Reset", "0"))
                    wait = max(0, reset - int(time.time()))
                    jitter = random.uniform(0.3, 0.9)
                    logger.warning(f"Rate limit atingido. Aguardando {wait + jitter:.1f}s.")
                    time.sleep(wait + jitter)
                    continue

                # 429 → retry-after
                if resp.status_code == 429:
                    ra = int(resp.headers.get("Retry-After", "1"))
                    logger.warning(f"429 recebido. Aguardando {ra}s.")
                    time.sleep(ra)
                    continue

                # CHANGE: secondary rate limit (GitHub)
                if resp.status_code == 403 and "rate limit" in resp.text.lower():
                    t = 3 + random.uniform(0.4, 1.1)
                    logger.warning(f"Secondary rate limit. Sleep {t:.1f}s.")
                    time.sleep(t)
                    continue

                return resp

            except requests.exceptions.Timeout:
                if attempt < self.max_retries:
                    sleep(0.8 + random.uniform(0.2, 0.6))
                    continue
                raise

            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries:
                    sleep(0.8)
                    continue
                raise e

    # ------------------------------------------------------------------
    # Conteúdo continua igual (API estável)
    # ------------------------------------------------------------------
    def _contents_url(self, path: str) -> str:
        return f"{self.api_base}/repos/{self.repo}/contents/{path}"

    def get_json(self, path: str, default: Optional[Any] = None) -> Tuple[Any, Optional[str]]:
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
                return self.get_json(path, default=None)
            return default, None

        raise RuntimeError(f"Erro ao ler {path}: {r.status_code}\n{r.text}")

    def put_json(self, path: str, obj: Any, message: str, sha: Optional[str] = None) -> str:
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
            return r2.json()["content"]["sha"]

        raise RuntimeError(f"Erro ao salvar {path}: {r.status_code}\n{r.text}")
