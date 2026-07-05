# seasadj

X-11の手順を任意周期に一般化した季節調整（周期変動分離）パッケージ。日次データの
曜日周期なら `period=7`、時次データの日周期なら `period=24`、その他任意の周期長を指定
できる — X-13ARIMA-SEATSは月次・四半期データしか扱えないが、本パッケージはその
すき間を埋める。

[English README](README.md)

## なぜこのパッケージが必要か

季節調整の標準ツールはX-13ARIMA-SEATSだが、そのX-11コア部分は月次（周期12）・
四半期（周期4）専用にハードコードされている。日次データの週周期、時次データの
日周期など、その型に収まらない実データが増えている。

本パッケージはX-11の手順を分解する：外れ値調整・休日調整・水準シフト調整・予測延長部分は、任意の周期に対応できるX-13ARIMA-SEATSのRegARIMA事前調整に任せる（すでに十分な実績がある）。周期に縛られるX-11コア部分——移動平均・季節フィルターの自動選択・極端値の置換——を本パッケージで再実装し、任意の周期長に一般化する。

## 特徴

- 乗法型・加法型・対数変換型の3つの分解モード
- 対数変換型は Thomson & Ozaki (2002) のトレンドバイアス補正を内蔵
- SI比を用いた異常値対応（X-11 extreme value replacement）
- MSR（moving seasonality ratio）による季節フィルター（3x3/3x5/3x9）の自動選択
- ヘンダーソン移動平均の項数自動選択
- 依存ゼロ（標準ライブラリのみ）

## インストール

```bash
pip install seasadj
```

## クイックスタート

```python
import math
from seasadj import decompose

# 周期7の仮想系列
data = [100 + 0.05 * i + 20 * math.sin(2 * math.pi * i / 7) for i in range(400)]

result = decompose(data, period=7)

print(result.trend[:5])      # 傾向循環変動
print(result.seasonal[:5])   # 季節変動
print(result.adjusted[:5])   # 季節調整済み系列
print(result.irregular[:5])  # 不規則変動
```

`decompose()` は `trend`・`seasonal`・`adjusted`・`irregular` の各系列（すべて
普通のlist）と、元の `observed` 系列・診断値をまとめた `Decomposition` を返す。
乗法型・対数変換型では `prior_adjusted ≈ trend * seasonal * irregular`、
加法型では `prior_adjusted ≈ trend + seasonal + irregular` が成り立つ。

## X-13ARIMA-SEATSによる入力の準備

`decompose()` は、休日・外れ値・水準シフトの調整が済んだデータ（またはこれらの
要因を直接引数として渡す。下記API仕様を参照）と、任意で予測延長系列を想定して
いる。これらを得る通常の方法は、X-13ARIMA-SEATSでのRegARIMA実行：

- **乗法型・対数変換型の場合**：X-13を変換なし（またはレグレッサーのみ
  `transform function=none`）で実行し、その乗法的な要因推定値（1.0近傍）を
  `holiday_effect`／`ao_effect`／`ls_effect` として使う
- **加法型の場合**：X-13を `transform function=none` で実行し、その加法的な
  要因推定値（0.0近傍＝「引く量」）を同じ引数として使う

この2つを混同する——例えば `model="additive"` に乗法用の要因係数をそのまま
渡す——と、加法モードは要因引数を「割る係数」ではなく「引く量」として扱うため、
誤った調整が黙って行われる点に注意。

## ファイルモード（Fortran互換CLI）

オリジナルのFortranプログラムとの互換性のため、`seasadj` には `in_data/` +
`para/` を持つ作業ディレクトリを読み `out_data/` を書き出すファイルベースの
モードもある：

```bash
seasadj <作業ディレクトリ>
# または
python -m seasadj <作業ディレクトリ>
```

ファイル形式やFortranソースとのモジュール対応表は
[docs/porting-notes.ja.md](docs/porting-notes.ja.md)（開発者向け）を参照。

## API仕様

### `decompose(data, period, **kwargs) -> Decomposition`

| 引数 | 既定値 | 内容 |
|---|---|---|
| `data` | 必須 | 観測値（list/tuple/`np.ndarray`/`pd.Series`のいずれか） |
| `period` | 必須 | 季節周期の長さ（2以上）。例：日次データの曜日周期なら7 |
| `first_position` | `1` | `data[0]` の周期内位置（1..period） |
| `model` | `"multiplicative"` | `"multiplicative"`・`"additive"`・`"log"` のいずれか |
| `forecast` | `None` | 予測延長系列（X-13ARIMA-SEATS等の出力） |
| `holiday_effect` | `None` | 休日要因の事前調整係数（周期ごと） |
| `holiday_regressor` | `None` | 休日回帰変数。`holiday_effect` と `forecast` を両方与える場合は必須 |
| `holiday_coef` | `0.0` | 休日回帰係数 |
| `ao_effect` | `None` | 外れ値（AO）の事前調整係数 |
| `ls_effect` | `None` | 水準シフト（LS）の事前調整係数 |
| `seasonal_ma` | `3` | 初期季節移動平均の項数：3・5・9（3x3/3x5/3x9） |
| `replace_extreme` | `True` | 異常値置換（X-11 extreme value replacement） |
| `sigma` | `(1.5, 2.5)` | 異常値置換の（下限、上限）シグマ |
| `ft_o` | `1` | 先頭観測の通し位置（通常変更不要） |
| `verbose` | `False` | `True` なら進捗行を表示。既定では `diagnostics["log"]` に格納 |

不正な入力に対しては `SeasadjError` を送出する。検証は最初に見つかった
不備を報告する仕様で、データ長のチェックが正値チェック（乗法型・対数
変換型で該当）より先に行われる。

### `Decomposition`

すべての系列は0始まりの普通のlist。`n_total = n_observed + n_forecast`。
index `n_observed` 以降は予測延長期間。

| フィールド | 長さ | 内容 |
|---|---|---|
| `observed` | n_observed | 入力データ |
| `prior_adjusted` | n_total | 休日・外れ値・水準シフト調整後（対数変換型は元スケールに逆変換済み） |
| `trend` | n_total | 傾向循環変動 |
| `seasonal` | n_total | 季節変動 |
| `irregular` | n_total | 不規則変動 |
| `adjusted` | n_total | 季節調整済み系列 |
| `holiday_effect` / `ao_effect` / `ls_effect` | n_total | 実際に適用された要因系列 |
| `n_observed` / `n_forecast` | int | 観測数／予測延長数 |
| `period` | int | `period` 引数のエコーバック |
| `model` | str | `model` 引数のエコーバック |
| `diagnostics` | dict | `h_terms`・`sum_ratios`・`swm_term`・`msr_ratio`・`msr_count`・`si_replaced`・`bias_sig`・`log` |
| `internals` | dict | 中間系列（`TC1`・`SI1`・`w1`・`SI1r`・`S1p`・`S1`・`A1`・`TC2`・`SI2`・`w2`・`SI2r`・`S2p`）と `ft_SI1`。系列端の埋め値（0.0／−999.0／重み1.0）はファイル出力と同じ規約 |

## アルゴリズム

X-11の手順は、傾向循環・季節・不規則の各変動を3段階（初期推定→中間推定→
最終推定）で推定し、各段で前段の季節要因とヘンダーソン・フィルター済みの
トレンドを精緻化する。本パッケージは季節加重移動平均・ヘンダーソン・フィル
ターの項数選択・MSR（moving seasonality ratio）・極端値の置換まで、すべての
ステップをオリジナルX-11の固定周期（12または4）から任意周期に一般化している。

参考文献：Dagum, E. B. (1988), *The X-11-ARIMA/88 Seasonal Adjustment
Method*；[JDemetra+ の X-11理論ドキュメント](https://jdemetradocumentation.github.io/JDemetra-documentation/pages/theory/SA_X11.html)；
Thomson, P. and Ozaki, T. (2002)（対数変換型のトレンドバイアス補正）。

## 開発・テスト

本パッケージはオリジナルのFortran90実装（Ver16_00）からの移植であり、
非公開の凍結ゴールデンテスト7ケース（本パッケージには同梱されない。
[docs/porting-notes.ja.md](docs/porting-notes.ja.md) 参照）でビット単位一致を
検証済み。本パッケージに同梱されるテスト（`tests/test_api.py`）は、人工データ
による分解の恒等式とAPI／ファイルモードの同値性を検証する。

```bash
pip install -e . pytest
python -m pytest tests/ -v
```

## 引用

研究で本パッケージを使う場合は、以下を引用してください：

> Arita, Tetsuma (2022). "Assessment of the spread of COVID-19 in seven
> countries using a seasonal adjustment method." *Statistical Journal of
> the IAOS*. https://doi.org/10.3233/SJI-220932

本パッケージのVer14〜16拡張（極端SI比の置換、加法型・対数変換型モード、
Thomson & Ozaki のトレンドバイアス補正）を扱う論文は準備中（in
preparation）。確定次第この引用を差し替える。

## ライセンス・商用利用について

`seasadj` は GNU Affero General Public License v3.0 以降
（AGPL-3.0-or-later）で提供される — [LICENSE](LICENSE) 参照。

AGPLの条件で利用できない場合（プロプライエタリ製品への組込み等）や共同研究・カスタマイズの相談も歓迎する。連絡はGitHubのIssueから行ってほしい。
