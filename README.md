# oyaoya

「投資対象からの収益がなく、新規出資金だけで分配・償還した」という**反実仮想**を月次で計算する再現可能なリサーチ環境です。この仮説が事実だと主張するものではありません。

## 現在のデータ品質

`data/funds.csv` はスキーマと計算・公開基盤を検証する初期台帳です。現時点の1件は `idea.md` のフォーマット例を転記したもので、一次資料未確認のため `estimated` としています。収集環境から公式サイトへの接続が拒否されたため、数値を確定情報として扱わないでください。URLが未確認の値に架空の出典を付けない方針です。

## 実行

Python 3.10+ の標準ライブラリだけで動作します。

```bash
python -m src.simulator --funds data/funds.csv --cutoff 2025-07-31 --rollover-rate 0
python -m unittest discover -v
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
