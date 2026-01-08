
# services/status.py
from datetime import date, datetime

STATUS = ("planejada", "vencendo", "vencida", "paga")

def derivar_status(data_prevista: str | None, data_efetiva: str | None) -> str:
    if data_efetiva:
        return "paga"
    if not data_prevista:
        return "planejada"
    try:
        d = datetime.fromisoformat(str(data_prevista)).date()
    except Exception:
        return "planejada"
    hoje = date.today()
    if d < hoje:
        return "vencida"
    if d == hoje:
        return "vencendo"
    return "planejada"
