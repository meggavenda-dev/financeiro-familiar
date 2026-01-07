# github_service.py
import base64
import json
import requests
from time import sleep
from typing import Tuple, Any, Optional

class GitHubService:
    def __init__(self, token: str, repo_full_name: str, branch: str = "main",
                 request_timeout: int = 15, max_retries: int = 2):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "financeiro-familiar-streamlit"
        })
        self.api_base = "https://api.github.com"
        self.repo = repo_full_name
        self.branch = branch
        self.timeout = request_timeout
        self.max_retries = max_retries

    def _contents_url(self, path: str) -> str:
        return f"{self.api_base}/repos/{self.repo}/contents/{path}"

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        # retry básico em erros transitórios
        for attempt in range(self.max_retries + 1):
            try:
                return self.session.request(method, url, timeout=self.timeout, **kwargs)
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
        elif r.status_code == 404:
            if default is not None:
                self.put_json(path, default, f"Inicializa {path}")
                obj, sha = self.get_json(path, default=None)
                return obj, sha
            return default, None
        elif r.status_code in (401, 403):
            raise RuntimeError(f"Acesso negado ao {path}. Verifique token e permissões. ({r.status_code})")
        else:
            raise RuntimeError(f"Erro ao ler {path}: {r.status_code} {r.text}")

    def put_json(self, path: str, obj: Any, message: str, sha: Optional[str] = None) -> str:
        url = self._contents_url(path)
        content_str = json.dumps(obj, ensure_ascii=False, indent=2)
        b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
        payload = {"message": message, "content": b64, "branch": self.branch}
        if sha:
            payload["sha"] = sha

        r = self._request("PUT", url, json=payload)
        if r.status_code in (200, 201):
            return r.json()["content"]["sha"]
        elif r.status_code == 409:
            current, current_sha = self.get_json(path, default=obj)
            payload["sha"] = current_sha
            r2 = self._request("PUT", url, json=payload)
            if r2.status_code in (200, 201):
                return r2.json()["content"]["sha"]
            raise RuntimeError(f"Conflito ao salvar {path}: {r2.status_code} {r2.text}")
        elif r.status_code in (401, 403):
            raise RuntimeError(f"Acesso negado ao salvar {path}. Verifique token e permissões. ({r.status_code})")
        else:
            raise RuntimeError(f"Erro ao salvar {path}: {r.status_code} {r.text}")

    def ensure_file(self, path: str, default: Any) -> Tuple[Any, Optional[str]]:
        return self.get_json(path, default=default)
