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

def simulate(funds: list[Fund], cutoff: date, rollover_rate=0.0, achievement_rate=1.0, spread_sales=False):
    if not 0 <= rollover_rate <= 1 or not 0 <= achievement_rate <= 1: raise ValueError("rates must be between 0 and 1")
    if not funds: return []
    first=min(month_start(f.sales_start or f.start) for f in funds); balance=0.; out=[]
    for m in months(first,cutoff):
        inflow=distribution=redemption=outstanding=0.
        for f in funds:
            amount=f.amount*achievement_rate
            if spread_sales and f.sales_start:
                sale_months=list(months(f.sales_start,f.start));
                if m in sale_months: inflow += amount/len(sale_months)
            elif m == month_start(f.start): inflow += amount
            if month_start(f.start) <= m <= month_start(f.end):
                distribution += amount*f.annual_yield/12; outstanding += amount
            if m == month_start(f.end): redemption += amount*(1-rollover_rate)
        required=max(0.,distribution+redemption-balance)
        balance += inflow-distribution-redemption
        obligations=distribution+redemption
        out.append({"month":m.isoformat(),"new_investment":round(inflow),"distribution":round(distribution),"redemption":round(redemption),"cash_balance":round(balance),"required_new_money":round(required),"outstanding_principal":round(outstanding),"psr":round(inflow/obligations,3) if obligations else None})
    return out

def summarize(rows, funds):
    negative=next((r["month"] for r in rows if r["cash_balance"] < 0),None)
    return {"fund_count":len(funds),"confirmed_funds":sum(f.confidence=="confirmed" for f in funds),"cumulative_investment":sum(r["new_investment"] for r in rows),"cumulative_distribution":sum(r["distribution"] for r in rows),"cumulative_redemption":sum(r["redemption"] for r in rows),"ending_cash":rows[-1]["cash_balance"] if rows else 0,"peak_cash":max((r["cash_balance"] for r in rows),default=0),"first_negative_month":negative}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--funds",default="data/funds.csv"); p.add_argument("--cutoff",default="2025-07-31"); p.add_argument("--rollover-rate",type=float,default=0); p.add_argument("--achievement-rate",type=float,default=1); p.add_argument("--spread-sales",action="store_true"); p.add_argument("--output",default="output")
    a=p.parse_args(); funds=load_funds(a.funds); rows=simulate(funds,date.fromisoformat(a.cutoff),a.rollover_rate,a.achievement_rate,a.spread_sales); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    with open(out/"monthly_cashflow.csv","w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys() if rows else ["month"],lineterminator="\n"); w.writeheader(); w.writerows(rows)
    payload={"parameters":{"cutoff":a.cutoff,"rollover_rate":a.rollover_rate,"achievement_rate":a.achievement_rate,"spread_sales":a.spread_sales},"summary":summarize(rows,funds),"monthly":rows}
    (out/"simulation.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(payload["summary"],ensure_ascii=False))
if __name__ == "__main__": main()
