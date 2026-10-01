# 完整重做 review ledger

## Accounts design review

- B1：骨架 owner=NULL 充當公開狀態、LearningApp.name 隨 draft.title 重複更新。已改為核准 immutable version＋active pointer；owner 必填，移除重複 name 與草稿同步。正式 fixture 有 owner/version/approved review。native PostgreSQL 7 HTTP tests 已驗證公開 metadata 與舊答案，closed；完整步驟 3 仍待最終驗收。
- reviewer 覆蓋：UUID／FK／unique、Argon2id、DB hash session／idle expiry／rotation、Origin／CSRF、DB throttle、API ownership、DTO、transaction／revision、JSON、private cache。其餘無 design findings。

## Author verification

- Web typecheck 通過。API Ruff check／format 通過。
- API mypy、全 check／真 DB integration 正在執行；登入／草稿 E2E 已加入，尚未執行。
- 測試涵蓋：匿名／跨 owner／CSRF／Origin／revision／logout／rotation／idle timeout／停用／login throttle，採真 PostgreSQL 與 HTTP。

## Accounts correctness review

- C1：admin CLI ValidationError可能輸出password。已改固定安全message／from None，DB engine hide_parameters=True；test_admin_cli短密碼regression通過。
- C2：工作區只顯示20份草稿。已加page/hasMore載入與dedup append；21份草稿E2E加入，runtime待整批。
- C3：私有draft缺response no-store。已覆蓋draft/private/nonGET並測owner/guest/other header，runtime待整批。
- 同一reviewer複核三項修正 NO CODE FINDINGS；主agent不以靜態review代替runtime。
- API Ruff/format/mypy16files與unit9tests已通過，OpenAPI snapshot drift通過。Web check／integration owner mutation／Chromium仍在執行。
- Docker測試container在初始化途中消失；可選TEST_POSTGRES_BIN使用自有臨時native cluster。本機16.15的migration roundtrip/drift及HTTP4 tests通過，CI仍為Docker17，未把16的證據當17 runtime證據。

## 最新runtime證據

- make check：API Ruff/format/mypy、unit9、OpenAPI/TS client drift、Web lint/type/unit2/production build通過。
- native PostgreSQL16.15：migration upgrade/drift/downgrade/recreate、HTTP integration5tests通過，包含真正admin建立／既有帳號不升權。
- owner mutation：temporary source副本移除owner guard後，cross-owner GET由404變200，測試以明確assert200==404拒絕，已通過。
- 最新Chromium整批正在執行，尚未以靜態review或上述HTTP證據替代UI驗收。

## 帳號與草稿驗收結論

- 整批check/integration/E2E exit0；integration5、Chromium3、owner/fixture/API-stopped mutations通過。C1/C2/C3均closed，有具體regression。
- 帳號階段當時 B1 尚 open；已由下方版本切換處置。完整產品仍在實作，不能用帳號階段完成取代 goal。

## Versions / answers review 與驗收

- 獨立 design review：NO DESIGN FINDINGS；覆蓋 UUID/FK/JSON、不可變 trigger、version/review/pointer、答案快照、canonical hash、DB unique/upsert、transaction、受控 DTO、owner/no-store 與 fixture。這是步驟 3 部分範圍審查，未把後續正式發布／AI 功能視為已完成。
- 正確性 P2：公開清單缺 pagination。已加 Query 驗參數／穩定 sort／offset/limit；首頁分頁連結與當頁 refresh 同步。21 筆核准內容與 pending 版本 regression 已加入。
- 正確性 P1：保存 A 期間切換 B，晚到的 A 回應可能讓 editing=A/content=B。已鎖完整 form、edit/new 控制，加 busy submit guard；成功回應同步 editing/content。Promise gate 延遲 PATCH 的 Chromium regression 已加入。
- 第二輪 reviewer 複核 P1/P2：NO CODE FINDINGS；尚須 runtime regression，不以靜態複核代替。
- 第一批 native PostgreSQL 16.15：migration drift/roundtrip、7 HTTP integration 與原 owner mutation通過；版本UPDATE被DB拒絕、非法選項422、兩請求一answer、相同key重放、不同payload409、跨owner404、舊結果在新版切換後仍可回放。
- 新版 OpenAPI/TS client由 make generate-client生成；check（API lint/mypy/unit9、Web lint/type/unit2/production build）已exit0。新增 helper／最後修正後整批仍需重驗。
- Docker PostgreSQL 17：此輪已跑 upgrade/drift/downgrade/recreate，HTTP／三項version mutations與production Chromium仍在執行，不先宣稱通過。
- B1來源核對：rg -n 'owner_id.is_\(None\)|name=body.title|\.values\(name=body.title\)' apps/api/app 無匹配；正式 models/main/drafts/seed及fixture consumers已同批替換。

## 版本切片 runtime 更新

- Docker PostgreSQL17：migration drift/roundtrip、8 HTTP tests、owner mutation通過；首輪version mutation因隔離副本缺scripts/test helpers未到行為斷言，gate正確拒絕，未宣稱該輪完整integration成功。
- 修正source copy：明確複製app/scripts/tests，不把原app加回pythonpath；避免測到原source。native PostgreSQL16.15整批check與8 HTTP tests、owner/latest-draft/pending-version/missing-unique mutations已通過。
- latest-draft：改用可編輯題目後，分類由探索型變交流型；pending-version：未核准detail由404变200；missing-unique：移除owner/key constraint後，正常提交由201變500。各以指定assertion拒絕，不把import/setup失敗當成功。
- Constraint變更只發生於gate自己的temporary database，finally恢復unique；產品source不被mutation改寫。migration0003也測從含原ownerless骨架fixture的0002升級，只清該固定ID且無draft的obsolete fixture，seed再建正式核准version；owned草稿不走清理條件。
- 最新production Chromium仍在執行，尚未以HTTP或mutation結果代替UI驗收。


## 步驟3收尾

最終native PostgreSQL16.15 E2E入口exit0：migration legacyfixture/drift/roundtrip、production build/typecheck、Chromium6tests、fixture-name/API-stopped mutations均通過。註冊waitForResponse確認201再驗畫面；select改explicit label而保留disabled assertion。P1保存鎖與P2分頁runtime closed，step3勾完成，完整產品繼續4。


## Publication 首輪correctness

- P1私有submissions缺no-store：main middleware納入suffix，owner/other header回歸通過。
- P1下架／刪除與新作答race：新key先鎖LearningApp，再查公開version，鎖持有至answer commit；既有key replay保持提前返回。PostgreSQL pg_blocking_pids barrier確認請求真正在等待app lock，再清pointer；新答案回404。native HTTP11通過。
- P2清pointer後舊pending可倒退：審核與明確publish檢查最高核准sequence，不依賴可清空的active pointer；unpublish/restore後舊pending核准409，native HTTP11通過。
- 新增images：upload用途/owner驗證、1MiB上限、Pillow實際decode及重新編碼、serverUUID blob路徑、version reference與private answer image回放；0004 drift/roundtrip、HTTP11及四原mutation已通過。四個image unit通過。
- 新增admin/content/search/share與Web consumers；session creation重新鎖User/recheck active，與停用共用lock。這些後續改動目前整批check/integration/E2E仍在跑，未標整個step4完成；fresh design/correctness reviews進行中。


## 步驟4最終驗收與session收尾

- Fresh design review：NO DESIGN FINDINGS；核對publication、upload retention、admin、共享editor、DTO和可見性機制，沒有搬入舊COS/MD5/Redis/sharding。
- 第二輪correctness P2：studio?app=id刪除後reload仍指向deleted draft而404。已改絕對URL導向/studio?deleted=1；Chromium自動redirect、restore保持unpublished及明確publish已通過。前三項finding與本項均closed。
- 最後bounded review無blocker：owner included_hidden/restore仍限owner並保留答案快照；trash維持scope；ReviewView封面取immutable version；new_session在User row lock後重查active。
- 全套 `TEST_POSTGRES_BIN=/opt/homebrew/bin make check test-integration test-e2e test-faults` exit0：APIunit13、mypy23files、Webunit2/lint/type/production build及OpenAPI/TS drift；nativePG16.15 migration0004/drift/roundtrip、HTTP13；owner/latest-draft/pending-version/missing-unique/private-upload/disabled-session-race六反例。
- Chromium8（15.2秒）含owner答案隱藏恢復、immutable封面審核、搜尋分享QR、刪除導向/restore/再發布、admin題目規則與停用撤session；fixture-name/API-stopped兩反例均拒絕。transport4＋SSE buffering mutation通過。
- source盤點64REST/7tables/20Web declarations及5mutation、actionlint通過。這是本機PG16.15證據，未把Docker17舊0003/HTTP8證據稱為新版runtime；遠端CI尚未執行。
- Will要求關閉session並commit；步驟4完成，5–7未完成。6a須核對補原版userProfile/bio欄位；真provider/品質成本/部署保存仍待決。完整goal未取消。
