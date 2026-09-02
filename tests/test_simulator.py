import unittest
from datetime import date
from src.collector import add_years, compact, parse_html
from src.simulator import Fund, annual_obligations, funding_stop_summary, simulate, summarize
class SimulatorTest(unittest.TestCase):
 def test_cash_identity_and_redemption(self):
  f=Fund("test",date(2024,1,1),date(2024,2,28),1200,0.12)
  rows=simulate([f],date(2024,2,29))
  self.assertEqual(rows[0]["cash_balance"],1188)
  self.assertEqual(rows[1]["redemption"],1200)
  self.assertEqual(rows[1]["cash_balance"],-24)
  self.assertEqual(summarize(rows,[f])["first_negative_month"],"2024-02-01")
 def test_rollover_and_sales_spread(self):
  f=Fund("test",date(2024,3,1),date(2024,3,31),300,0,date(2024,1,1))
  rows=simulate([f],date(2024,3,31),rollover_rate=.5,spread_sales=True)
  self.assertEqual([r["new_investment"] for r in rows],[100,100,100])
  self.assertEqual(rows[-1]["redemption"],150)
 def test_outstanding_burden_series_split_and_coverage(self):
  funds=[Fund("成田1号",date(2024,1,1),date(2024,12,31),1000,.12),Fund("その他",date(2024,1,1),date(2024,12,31),500,.06)]
  row=simulate(funds,date(2024,1,31))[0]
  self.assertEqual(row["outstanding_principal"],1500)
  self.assertEqual(row["narita_outstanding_principal"],1000)
  self.assertEqual(row["annual_distribution_burden"],150)
  self.assertEqual(row["monthly_distribution_burden"],12)
  self.assertAlmostEqual(row["coverage_ratio"],.992,places=3)
 def test_funding_stop_and_annual_obligations(self):
  funds=[Fund("old",date(2024,1,1),date(2024,2,29),1200,.12),Fund("new",date(2024,2,1),date(2024,3,31),500,0)]
  rows=simulate(funds,date(2024,3,31),funding_stop_date=date(2024,2,1))
  self.assertEqual(sum(r["new_investment"] for r in rows),1200)
  self.assertEqual(rows[1]["redemption"],1200)
  self.assertEqual(annual_obligations(rows)[0]["required_cash_outflow"],1224)
  stop=funding_stop_summary(rows,date(2024,2,1))
  self.assertEqual(stop["shortage_month"],"2024-02-01")
  self.assertEqual(stop["runway_months"],0)
class CollectorTest(unittest.TestCase):
 def test_parser_ignores_comments_and_normalizes_digits(self):
  root=parse_html('<div><!-- <img alt="完売"> --><h2>成田１２</h2></div>')
  self.assertEqual(compact(root.find("h2")[0].text()),"成田12")
  self.assertEqual(root.find("img"),[])
 def test_add_years_uses_inclusive_period(self):
  self.assertEqual(add_years(date(2024,12,16),1),date(2025,12,15))
if __name__ == '__main__': unittest.main()
