# oyaoya

「投資対象からの収益がなく、新規出資金だけで分配・償還した」という**反実仮想**を月次で計算する再現可能なリサーチ環境です。この仮説が事実だと主張するものではありません。

## 現在のデータ品質

`data/funds.csv` は公式商品一覧・商品詳細ページから再収集した台帳です。募集総口数、1口100万円、想定利回り、運用実績または商品条件の日付を確認できた69商品を収録しています。金額は **募集総口数×100万円の募集予定額** であり、実際の出資額ではありません。募集総口数を確認できないシリーズ1～12号は計算から除外しているため、結果は全シリーズの完全な再構築ではありません。

## 実行

Python 3.10+ の標準ライブラリだけで動作します。

```bash
python -m src.simulator --funds data/funds.csv --cutoff 2025-07-31 --rollover-rate 0
python -m unittest discover -v
```

公式ページから台帳を再取得する場合（取得先への負荷を避けるため既定でリクエスト間隔を設けています）:

```bash
python -m src.collector --output data/funds.csv
```

出力は `output/monthly_cashflow.csv` と `output/simulation.json`。静的ダッシュボードは `docs/` を配信します。

```bash
python -m http.server 8000 --directory docs
```

## 台帳の確度

- `confirmed`: 一次資料で項目を確認済み
- `estimated`: 二次情報または資料中の例など、要再確認
- `unknown`: 値または根拠が不足

列定義、モデルの制約、今後の収集優先順位は [`idea.md`](idea.md) を参照してください。
