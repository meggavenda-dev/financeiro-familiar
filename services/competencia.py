
from datetime import date

def competencia_from_date(d: date) -> str:
    return f"{d.year}-{d.month:02d}"

def label_competencia(comp: str) -> str:
    y, m = comp.split("-")
    meses = ["JAN","FEV","MAR","ABR","MAI","JUN",
             "JUL","AGO","SET","OUT","NOV","DEZ"]
    return f"{meses[int(m)-1]}/{y[-2:]}"

