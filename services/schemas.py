
# services/schemas.py
from dataclasses import dataclass, field
from typing import Optional
from datetime import date

@dataclass
class Transacao:
    id: str
    tipo: str  # "despesa" | "receita"
    descricao: str = ""
    valor: float = 0.0
    data_prevista: Optional[date] = None
    data_efetiva: Optional[date] = None
    conta_id: str = "c1"
    categoria_id: Optional[str] = None
    excluido: bool = False
    parcelamento: Optional[dict] = None
    recorrente: bool = False

def validate_transacao_dict(d: dict) -> bool:
    """Validação leve de transação (tipos e valores mínimos)."""
    if not isinstance(d, dict):
        return False
    tipo = d.get("tipo")
    if tipo not in ("despesa", "receita"):
        return False
    try:
        v = float(d.get("valor", 0.0))
    except Exception:
        return False
    if v < 0:
        return False
    return True
