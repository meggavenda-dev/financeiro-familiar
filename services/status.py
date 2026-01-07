
from datetime import date, datetime

def calcular_status(item):
    if item.get("status") == "paga":
        return "paga"
    d = datetime.fromisoformat(item["data"]).date()
    hoje = date.today()
    if d < hoje:
        return "atrasada"
    if d == hoje:
        return "em_aberto"
    return "planejada"

