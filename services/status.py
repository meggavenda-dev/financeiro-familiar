
# services/status.py
from datetime import date, datetime

STATUS = (
    "planejada",   # data no futuro e não paga
    "vencendo",    # hoje e não paga
    "vencida",     # passou do prazo e não paga
    "paga",        # liquidada (tem data_efetiva)
)

def derivar_status(data_prevista: str | None, data_efetiva: str | None) -> str:
    """Deriva status: paga se há data_efetiva; senão compara com data_prevista."""
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

def status_badge(st: str) -> str:
    return {
        "planejada": "📝 Planejada",
        "vencendo": "⏳ Vencendo",
        "vencida": "🔴 Vencida",
        "paga": "✅ Paga",
    }.get(st, st)
