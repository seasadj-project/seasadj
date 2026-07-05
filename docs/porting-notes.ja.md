# 移植ノート（開発者向け・日本語）

Fortran90版（Ver16_00）から本パッケージ（`seasadj`）への移植の設計判断・移植規約・回帰テストの回し方の記録。利用者向けの使い方は [README.ja.md](../README.ja.md) を参照。

| 項目 | 内容 |
|---|---|
| 状態 | **Phase B 完了**：Pythonic API（`decompose()`）・パッケージ公開整備が完了。Phase Aで G1〜G7 全合格・全数値出力がFortran版とビット単位一致を確認済み |
| 要件 | Python 3.10以上。**コアは標準ライブラリのみ**（依存ゼロ）。テスト実行のみ pytest |

## ゴールデンテストについて（非公開）

移植合否判定の基準入出力（G1〜G7、`04_検証データ/`）はこの公開リポジトリには**含まれない**。`tests/test_golden.py` はそのデータと Fortran 版の `para/` 参照コピーが見つからない環境では自動的に skip される（`pytest.skip(..., allow_module_level=True)`）。公開リポで走るのは `tests/test_api.py`（人工データ＋API/ファイルモード同値性）のみ。

手元でゴールデンテストを回す場合（データを持っている開発者のみ）：

```bash
cd 05_Python
python -m pytest tests/ -v
```

- G1〜G7 それぞれ：一時ディレクトリに `in_data/`＋リポジトリの `para/` をコピー → 実行 → `expected/` と比較（**参照元は読み取り専用**）
- 合否基準：数値系列は `|a−b| ≤ 1e-10 + 1e-10|b|`、埋め値（0.0／−999.0／重みの1.0）と o21 整数項目・コンソール離散値は完全一致、o20_SUM は行数のみ
- ハーネスの検出力は負対照（G1 expected と G2 expected の比較で903/903行が閾値超過）で確認済み

実測（2026年7月4日、Python 3.14.2 / Windows、Phase A）：**7ケース全合格、全数値出力がFortran出力とビット単位一致**（純Python逐次ループがFortranと同一順序のIEEE754演算になるため。exp/log/sqrt を含む対数変換モードのケースも一致）。

## モジュール対応（Fortranと1:1）

| Python | Fortran | 内容 |
|---|---|---|
| `main.py` | 01_main.f90 | 処理フロー（`run()`＝ファイルI/O、`_pipeline()`＝計算本体。両方とも呼出順はFortranと同一） |
| `var.py` | 02_var.f90 | 定数（max_t=7300, rwm_term, pad_val）・ファイル名・同梱para解決（`bundled_para_dir`） |
| `reg.py` | 03_reg.f90 | read_para/read_data/det_hol・det_ao・det_ls（ファイル層＋`*_core`計算層）/check_inputs/adj_org/week |
| `wma.py` | 04_wma.f90 | wm_ave（3x3/3x5/3x9 季節加重移動平均） |
| `st1.py` | 05_st1.f90 | mov_ave/Ini_SI/Ini_S/std_sf |
| `st2.py` | 06_st2.f90 | hmv_ave/dev_dat/det_het/det_swm（MSR） |
| `out.py` | 07_out.f90 | o01〜o25 出力（o20/o21はラベル・桁揃えもFortranに一致） |
| `rep.py` | 08_rep.f90 | rep_ext（極端SI比の置換） |
| `trb.py` | 09_trb.f90 | hend_w/trb_cor/exp_dat（対数変換モードのバイアス補正） |
| `api.py` | — | `decompose()`／`Decomposition`（Phase B新設。`_pipeline()` をメモリ入力で呼ぶ） |
| `ftn.py` | — | Fortran意味論ヘルパー（idiv/imod/1始まり配列/重み行列読込） |

## 移植規約（厳守。変更時は必ずゴールデンテスト再実行）

1. **1始まり添字**：系列配列は長さ `max_t+1`（index 0 未使用）。Fortranの添字式を無変換で保持
2. **整数演算**：生の `//`・`%` は禁止。`ftn.idiv`（0方向切捨て）・`ftn.imod`（被除数の符号）を使う
3. **累積和の順序**：Fortranのループ順のまま逐次加算（`sum()`・`math.fsum()` 禁止）
4. **重みファイル**：`para/` の同一ファイルを読む（trb_cor の hend_w のみ閉形式、Fortranと同じ）。APIモード（`decompose()`）はパッケージ同梱の `para/`（`src/seasadj/para/`）を使うが、ファイルモード（`run()`／CLI）は従来どおり作業ディレクトリの `para/` を読む
5. 出力の**バイト一致は仕様外**（実数は `repr` の17桁往復精度で出力、比較は数値パース）

## Phase B（公開整備）で行ったこと

- `main.py`：`run()` から計算本体を `_pipeline()` として抽出（コード移動のみ）。`run()`（ファイルモード）と `api.decompose()`（メモリモード）が同一の `_pipeline()` を呼ぶ
- `reg.py`：`det_hol`/`det_ao`/`det_ls` をファイル読み層＋計算層（`det_hol_core` 等）に分離。例外 `AbortRun` を `SeasadjError` に改名（`AbortRun` は互換エイリアスとして残置）
- `para/` を `src/seasadj/para/` に同梱し、`decompose()` はこれを使う（ファイルモードは変わらず作業ディレクトリの `para/` を読む）
- `api.py` 新設：`decompose()` と `Decomposition`（詳細はREADME参照）
- 公開用テスト：`tests/test_api.py`（人工データ＋API/ファイルモード同値性）。`tests/test_golden.py` はゴールデンデータ不在時に自動skip
- パッケージング：`pyproject.toml`（PEP 639 license式・`para/*.dat`同梱・`seasadj`コンソールスクリプト）、`python -m build`・`twine check`・別venvへのインストールで検証済み
