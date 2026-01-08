# services/ui.py
from services.status import derivar_status

def tx_status(tx: dict) -> str:
    """Status derivado (planejada, vencendo, vencida, paga)."""
    return derivar_status(tx.get("data_prevista"), tx.get("data_efetiva"))

def tx_badge(tx: dict) -> str:
    """Badge amigável para exibição de status."""
    st = tx_status(tx)
    return {
        "planejada": "📝 Planejada",
        "vencendo": "⏳ Vencendo",
        "vencida": "🔴 Vencida",
        "paga": "✅ Paga",
    }.get(st, st)
