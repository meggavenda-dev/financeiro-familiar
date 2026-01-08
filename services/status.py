
# services/status.py
from datetime import date, datetime

STATUS = (
    "planejada",   # data no futuro e não paga
    "vencendo",    # hoje e não paga
    "vencida",     # passou do prazo e não paga
    "paga",        # liquidada (tem data_efetiva)
)

# ---------------------------------------------------------
# CHANGE: derivação de status explícita e imutável
# ---------------------------------------------------------
def derivar_status(data_prevista: str | None, data_efetiva: str | None) -> str:
    """
    Deriva o status de uma transação.
    Regra:
    - Se data_efetiva existe → paga
    - Senão, compara data_prevista com hoje
    """
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


# ---------------------------------------------------------
# CHANGE: badges mantidos apenas como representação visual
# ---------------------------------------------------------
def status_badge(sts: str) -> str:
    """Representação visual do status (somente UI)."""
    return {
        "planejada": "📝 Planejada",
        "vencendo": "⏳ Vencendo",
        "vencida": "🔴 Vencida",
        "paga": "✅ Paga",
    }.get(sts, sts)
