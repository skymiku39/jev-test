# StreamSuite Laya MRE

這是一個從 StreamSuite 抽出的最小可重現測試 repository，只保留一條純本機流程：

```text
規則解析 -> Laya typed decision -> 合併政策
```

這裡沒有任何外部事件傳輸、資料庫、直播音訊或問答回答模型整合。預設使用固定的
`fixture` typed backend，因此不需要下載模型、不需要網路，也不需要啟動其他服務。

本專案使用 `uv` 管理環境與依賴；CLI 入口是 `laya-mre`，請透過 `uv run` 執行。

## 快速開始

在 repository 根目錄執行：

```powershell
uv sync --extra test
uv run pytest -q
```

直接跑一題：

```powershell
uv run laya-mre "英雄聯盟的大亂鬥是什麼？"
```

輸出會同時保留 `rule_parse`、原始 `laya_response` 與 `merged`，方便逐步比對。

## 使用真實 Laya

MRE 的 adapter 延續本專案的 typed contract：呼叫 `laya.load(...)`，再以
`agent.predict(state, questions)` 取得 `{ "answers": ... }`。模型依賴是 optional，且只允許
使用本機已有的 checkpoint／cache；MRE 不會在 pipeline 執行期間下載權重。

`model` extra 使用 PyPI 的真實 `laya` 套件，版本解析結果由 `uv.lock` 管理。可用以下命令
確認目前環境載入的是實際套件：

```powershell
# 依目前機器的 Laya 安裝方式準備 optional model dependencies
uv sync --extra model
uv run --extra model python -c "import laya; print(laya.__version__)"
$env:LAYA_MODEL = "multilingual"
$env:LAYA_DEVICE = "auto"
uv run laya-mre --backend laya "如何調整 Ollama 設定？"
```

若模型未安裝或 cache 不存在，請先用預設 `fixture` backend 重現規則與政策行為；這不會
改變規則或合併層。

## 合併契約

Laya 只提供候選 typed labels。最終計畫由程式政策產生：

- `needs = laya_needs ∪ rule_based_needs ∪ policy_required_needs`
- 未知 intent／need／flag 會被丟棄
- 高信心規則（例如噪音、直播標題、明確遊戲事實）不會被低信心 Laya 覆蓋
- commerce／即時資料路由會由政策補上 `evidence_contract`
- `policy_excluded_needs` 是讀取閘門，不能刪掉 union 中的診斷欄位

`tests/` 裡的測試只針對上述三段流程；`fixtures/cases.json` 是可讀的最小 golden cases。

## 目錄對應

- `src/laya_flow/rules.py`：自包含的 deterministic rule parser；已移除原本的外部 entity／儲存依賴。
- `src/laya_flow/questions.py`：Laya role-neutral typed question batch。
- `src/laya_flow/laya.py`：真實 Laya adapter 與離線 `fixture`／scripted backend。
- `src/laya_flow/policy.py`：QueryPlan、三方 needs union、exclusion 與 Laya merge guard。
- `src/laya_flow/pipeline.py`：把三個階段串起來並保留每一階段的可觀測輸出。
