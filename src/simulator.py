"""Monthly pooled-cash counterfactual simulator (standard library only)."""
from __future__ import annotations
import argparse, calendar, csv, json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

@dataclass(frozen=True)
class Fund:
    name: str; start: date; end: date; amount: float; annual_yield: float
    sales_start: date | None = None; confidence: str = "unknown"

def parse_date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None

def load_funds(path: str | Path) -> list[Fund]:
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    funds=[]
    for r in rows:
        start,end=parse_date(r["operation_start"]),parse_date(r["actual_end"] or r["operation_end"])
        amount=float(r["subscribed_amount"] or r["target_amount"])
        if not start or not end or amount <= 0: raise ValueError(f"invalid fund row: {r.get('fund_name')}")
        funds.append(Fund(r["fund_name"],start,end,amount,float(r["annual_yield"]),parse_date(r["sales_start"]),r["confidence"]))
    return funds

def month_start(d: date) -> date: return d.replace(day=1)
def next_month(d: date) -> date:
    return date(d.year + (d.month == 12), 1 if d.month == 12 else d.month + 1, 1)
def months(a: date,b: date):
    cur=month_start(a)
    while cur <= month_start(b): yield cur; cur=next_month(cur)

def is_narita(fund: Fund) -> bool:
    """Return whether a fund belongs to the Narita series."""
    return fund.name.startswith("成田")

def simulate(funds: list[Fund], cutoff: date, rollover_rate=0.0, achievement_rate=1.0, spread_sales=False,
             funding_stop_date: date | None = None):
    if not 0 <= rollover_rate <= 1 or not 0 <= achievement_rate <= 1: raise ValueError("rates must be between 0 and 1")
    if not funds: return []
    first=min(month_start(f.sales_start or f.start) for f in funds); balance=0.; out=[]
    for m in months(first,cutoff):
        inflow=distribution=redemption=outstanding=annual_burden=0.
        narita_outstanding=narita_annual_burden=0.
        for f in funds:
            amount=f.amount*achievement_rate
            # A fund starting on/after the stop month is treated as never funded.
            funded = funding_stop_date is None or month_start(f.start) < month_start(funding_stop_date)
            if not funded: continue
            if spread_sales and f.sales_start:
                sale_months=list(months(f.sales_start,f.start));
                if m in sale_months: inflow += amount/len(sale_months)
            elif m == month_start(f.start): inflow += amount
            if month_start(f.start) <= m <= month_start(f.end):
                burden=amount*f.annual_yield
                distribution += burden/12; outstanding += amount; annual_burden += burden
                if is_narita(f):
                    narita_outstanding += amount; narita_annual_burden += burden
            if m == month_start(f.end): redemption += amount*(1-rollover_rate)
        required=max(0.,distribution+redemption-balance)
        balance += inflow-distribution-redemption
        obligations=distribution+redemption
        coverage=balance/outstanding if outstanding else None
        out.append({"month":m.isoformat(),"new_investment":round(inflow),"distribution":round(distribution),"redemption":round(redemption),"cash_balance":round(balance),"required_new_money":round(required),"outstanding_principal":round(outstanding),"narita_outstanding_principal":round(narita_outstanding),"other_outstanding_principal":round(outstanding-narita_outstanding),"annual_distribution_burden":round(annual_burden),"narita_annual_distribution_burden":round(narita_annual_burden),"other_annual_distribution_burden":round(annual_burden-narita_annual_burden),"monthly_distribution_burden":round(annual_burden/12),"coverage_ratio":round(coverage,4) if coverage is not None else None,"psr":round(inflow/obligations,3) if obligations else None})
    return out

def annual_obligations(rows):
    """Aggregate scheduled principal and distributions by calendar year."""
    result={}
    for row in rows:
        year=row["month"][:4]
        item=result.setdefault(year,{"year":int(year),"scheduled_redemptions":0,"distributions":0,"required_cash_outflow":0})
        item["scheduled_redemptions"] += row["redemption"]
        item["distributions"] += row["distribution"]
        item["required_cash_outflow"] += row["redemption"]+row["distribution"]
    return list(result.values())

def funding_stop_summary(rows, stop_date: date):
    stop=month_start(stop_date).isoformat()
    at_stop=next((r for r in rows if r["month"] == stop),None)
    shortage=next((r for r in rows if r["month"] >= stop and r["cash_balance"] < 0),None)
    runway=None
    if shortage and at_stop:
        runway=(int(shortage["month"][:4])-int(stop[:4]))*12+int(shortage["month"][5:7])-int(stop[5:7])
    return {"funding_stop_date":stop,"shortage_month":shortage["month"] if shortage else None,"runway_months":runway,"outstanding_principal_at_stop":at_stop["outstanding_principal"] if at_stop else 0,"annual_distribution_burden_at_stop":at_stop["annual_distribution_burden"] if at_stop else 0}

def summarize(rows, funds):
    negative=next((r["month"] for r in rows if r["cash_balance"] < 0),None)
    return {"fund_count":len(funds),"confirmed_funds":sum(f.confidence=="confirmed" for f in funds),"cumulative_investment":sum(r["new_investment"] for r in rows),"cumulative_distribution":sum(r["distribution"] for r in rows),"cumulative_redemption":sum(r["redemption"] for r in rows),"ending_cash":rows[-1]["cash_balance"] if rows else 0,"peak_cash":max((r["cash_balance"] for r in rows),default=0),"first_negative_month":negative}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--funds",default="data/funds.csv"); p.add_argument("--cutoff",default="2025-07-31"); p.add_argument("--rollover-rate",type=float,default=0); p.add_argument("--achievement-rate",type=float,default=1); p.add_argument("--spread-sales",action="store_true"); p.add_argument("--funding-stop-date"); p.add_argument("--output",default="output")
    a=p.parse_args(); funds=load_funds(a.funds); stop=parse_date(a.funding_stop_date); rows=simulate(funds,date.fromisoformat(a.cutoff),a.rollover_rate,a.achievement_rate,a.spread_sales,stop); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    with open(out/"monthly_cashflow.csv","w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys() if rows else ["month"],lineterminator="\n"); w.writeheader(); w.writerows(rows)
    payload={"parameters":{"cutoff":a.cutoff,"rollover_rate":a.rollover_rate,"achievement_rate":a.achievement_rate,"spread_sales":a.spread_sales,"funding_stop_date":a.funding_stop_date},"summary":summarize(rows,funds),"annual_obligations":annual_obligations(rows),"monthly":rows}
    if stop: payload["funding_stop_summary"]=funding_stop_summary(rows,stop)
    (out/"simulation.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(payload["summary"],ensure_ascii=False))
if __name__ == "__main__": main()
