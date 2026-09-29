# 專案流程圖

此圖依據 `src/laya_flow/cli.py`、`src/laya_flow/pipeline.py`、`src/laya_flow/rules.py`、`src/laya_flow/questions.py`、`src/laya_flow/laya.py` 與 `src/laya_flow/policy.py` 的目前實作整理，描述 CLI 到最終 JSON 輸出的主流程。

```mermaid
flowchart TD
    input(["問題參數<br/>或互動式輸入"])

    subgraph cliLayer ["CLI：laya-mre.main()"]
        parseArgs["解析 CLI 參數<br/>backend / threshold / timeout / pretty / laya-only"]
        chooseBackend{"選擇 backend"}
        outputMode{"--laya-only？"}
        layaOnlyOutput["選取 laya_response"]
        fullOutput["選取完整 pipeline result"]
        jsonOutput["json.dumps(..., ensure_ascii=False)"]
    end

    fixtureBackend["FixtureLayaClient<br/>離線 deterministic backend"]
    realBackend["LayaTypedDecisionClient<br/>本機 Laya / local cache"]

    subgraph pipelineLayer ["run_pipeline()"]
        normalize["正規化問題<br/>str(question or '').strip()"]
        ruleParse["parse_rules()<br/>建立 rule_parse、entities 與初始分類"]
        state["建立 Laya state<br/>question + rule_parse 摘要"]
        typedQuestions["build_typed_questions()<br/>primary / tags / needs / flags"]
        typedDecision["backend.decide()<br/>帶入 state、questions、timeout"]
        backendFailure["捕捉 backend 例外<br/>建立 fallback metadata，記錄 backend_error"]
        observableResult["組合可觀測輸出<br/>rule_parse / typed_questions / laya_response / merged / timing"]
    end

    subgraph policyLayer ["政策合併：merge_laya_decision()"]
        responseCheck{"typed response 的 answers 有效？"}
        layaFields["依 threshold 取用 Laya 的<br/>primary / tags / needs / flags"]
        policyOnly["忽略無效 Laya 回應<br/>只使用規則與政策"]
        queryPlan["建立 QueryPlan<br/>candidate needs union<br/>套用 policy_excluded_needs"]
        backendErrorCheck{"有 backend_error？"}
        markBackendError["覆寫 classifier<br/>used=false、reason=backend_error"]
    end

    output(["stdout JSON"])

    input --> parseArgs --> chooseBackend
    chooseBackend -->|"fixture（預設）"| fixtureBackend
    chooseBackend -->|"laya"| realBackend
    fixtureBackend --> normalize
    realBackend --> normalize

    normalize --> ruleParse
    ruleParse --> state
    normalize --> typedQuestions
    state --> typedDecision
    typedQuestions --> typedDecision
    typedDecision -->|"成功"| responseCheck
    typedDecision -->|"失敗 / 例外"| backendFailure --> responseCheck
    responseCheck -->|"是"| layaFields --> queryPlan
    responseCheck -->|"否"| policyOnly --> queryPlan
    queryPlan --> backendErrorCheck
    backendErrorCheck -->|"是"| markBackendError --> observableResult
    backendErrorCheck -->|"否"| observableResult

    observableResult --> outputMode
    outputMode -->|"是"| layaOnlyOutput --> jsonOutput
    outputMode -->|"否"| fullOutput --> jsonOutput
    jsonOutput --> output

    style cliLayer fill:#F5F5F5,stroke:#B3B3B3
    style pipelineLayer fill:#C2E5FF,stroke:#3DADFF
    style policyLayer fill:#E9DDFF,stroke:#874FFF
    style chooseBackend fill:#FFECBD,stroke:#FFC943
    style responseCheck fill:#FFECBD,stroke:#FFC943
    style backendFailure fill:#FFCDC2,stroke:#FF7556
    style markBackendError fill:#FFCDC2,stroke:#FF7556
    style queryPlan fill:#DCCCFF,stroke:#874FFF
    style jsonOutput fill:#CDF4D3,stroke:#66D575
```

## 流程重點

- `parse_rules` 先產生 deterministic 規則解析結果；`state` 與 typed questions 再一併交給選定的 backend。
- `build_typed_questions` 只詢問受限的 intent、need 與 flag，不要求 Laya 生成回答內容。
- backend 可能是離線 fixture 或本機 Laya；backend 失敗時仍會繼續由規則與政策完成合併。
- `merge_laya_decision` 會先檢查 typed response，再依 threshold 驗證 Laya 回應，並以 `laya_needs ∪ rule_based_needs ∪ policy_required_needs` 建立候選 needs，再套用 `policy_excluded_needs` 閘門。
- 預設輸出保留 `rule_parse`、原始 `laya_response`、`merged` 與 `timing`；`--laya-only` 只輸出 Laya 回應。
