# Реализация приоритетов MR

этот отчёт относится к реализации v1 из [согласованного плана](automated-mr-priority-system-design.md). исходный baseline — `c6b93dfd1e85d3dafa46f0dfd06ffa5da62b4dc3`. результаты ниже получены локально, отдельно на file SQLite и PostgreSQL 16.15 в disposable контейнере

## Что изменилось

ожидающие MR идут в порядке hotfix → ordinary → automated, внутри каждого класса сохраняется исходный queue row ID. уже работающий MR продолжает свой workflow. automation label сам по себе не добавляет MR в очередь

`automation_labels` задаётся для каждого проекта. совпадение любого имени достаточно, автор MR не участвует. сравнение точное, с учётом регистра, Unicode и внутренних пробелов. пустые имена, внешние пробелы и точные дубликаты отклоняются. пересечение с queue/hotfix labels разрешено, hotfix всегда побеждает. отсутствие настройки и `[]` сохраняют прежнее поведение

новая revision `b8c9d0e1f2a3` после a7 добавляет только active `is_automated`. один resolver и SQL CASE задают общий порядок raw/ORM reads и позиций. активные REST и все полные WS snapshots получают `priority`, старое `is_hotfix` остаётся. history и frozen completion history не расширены. dashboard показывает общие badges и сохраняет серверный порядок

локальная bulk-активация завершает пересчёт сохранённых labels до remote verification и запуска runtime tasks. она сохраняет известный hotfix при неизвестном сохранённом snapshot. remote refresh после этого авторитетно пересчитывает оба flags. недоступный GitLab не превращает local readiness в обещание свежих remote labels

Q/H discovery сначала собирает оба полных списка. только потом разрешены metadata и orphan writes. страницы 100/101/201, overlap и дубликаты покрыты отдельно. malformed labels, частичный fetch, ошибочная progression и достижение cap с оставшимися страницами дают отказ от sweep. последняя принятая полная копия дубликата используется вместе с ID/version CAS, это не обещание атомарного snapshot самого GitLab

## Проверка требований

каждый DB-сценарий нового модуля использует настоящую migrated БД через общий opt-in fixture. GitLab заменён injected HTTP transport, runtime queue/handlers/notifiers остаются настоящими. только миграционные storage/fault/setup проверки используют согласованный raw SQL seam

| Требования | Реализованные сценарии |
| --- | --- |
| T01–T02 | `admission_table.py`, `configuration.py`, `exact_label_names.py` |
| T03–T04 | `ordering.py`, `repository_ordering.py` — literal mixed order, hotfix+automation, равные и обратные timestamps, row ID вместо IID |
| T05–T06 | `relabel.py`, `reclassification.py`, admission table — тот же row/time, две automation labels, last-trigger removal, configured aliases |
| T07–T08 | `startup_activation.py`, `application_startup.py`, `reclassification.py`, `unknown_saved_labels.py` — restart, `[]`, GitLab503, barrier до первого HTTP |
| T09–T10 | `metadata_boundaries.py`, `concurrent_arrivals.py` — stale poll/startup и recreated row, duplicate, два controlled commit schedules |
| T11 | `metadata_boundaries.py` — rebasing/testing/merging fields сохраняются |
| T12–T13 | `execution.py` — настоящий `MergeProcessor.run`, pipeline/rebase/merge/completion без workflow override |
| T14 | `project_isolation.py` и execution — одинаковые IID, разные policies/triggers, scoped notes/WS |
| T15–T16 | `replacement_labels.py`, `replacement_policy.py`, `retry_delivery.py` — final labels/current policy, old requests/receipts, real Retry→DLQ→requeue→processor |
| T17–T19 | `waiting_feedback.py`, `notification_recovery.py`, `metadata_atomicity.py` плюс прежний hotfix suite — fresh comments, failed recipients/reopen, processing/ACK overlap и rollback |
| T20–T21 | `pagination.py`, `paginated_reconciliation.py`, `incomplete_discovery.py`, `processor_incomplete_discovery.py`, `unknown_remote_labels.py`, `unknown_webhook_labels.py` |
| T22–T24 | `automation_helper_identity.py`, `automation_malformed_helper.py`, `automation_roundtrip.py` и прежние migration/archive suites |
| T25–T26 | `wire_contract.py` — authenticated ASGI REST, настоящий initial ASGI WS, полные webhook/poll/startup broadcasts, OpenAPI enum и history boundary |
| T27–T30 | frontend dashboard/hook/API tests и browser QA на disposable HTTP/WS fixture. это не E2E с настоящим GitLab |
| T31 | локальные baseline/candidate SQL/bulk/classifier measurements и EXPLAIN, frontend production bundle sizes. browser timings недоступны |
| T32 | отдельный actual old-binary rehearsal на обеих БД, baseline checkout `c6b93df`, новый downgrade до a7, удаление config key, old startup/read/write и повторный upgrade |

execution oracle для одновременных arrivals — `[1,101,102,2,5,3,4]`, семь merged histories. поздний HF2 после старта следующего ordinary даёт `[1,101,2,102,3]`. отдельный active automated case сохраняет non-preemption. чужой проект с тем же IID не меняется

в первом независимом review найдены и исправлены две границы. admission и полный label snapshot теперь имеют независимые source clocks. sequence `admit t10 → relabel t30 → delayed admit t20` сохраняет labels t30, в том числе при снятии automation. strictly newer snapshot заменяет их. доказанный overlap или неизвестный clock сохраняет enqueue-preserving union и исходную uncertainty, receipt order не объявляется source order

второй случай — missing labels в labeled/unlabeled/update больше не превращается в `[]`. parser отклоняет сообщение до queue/comment changes, существующий webhook route сохраняет его для retry. явный пустой массив и валидный `changes.labels.current` остаются полными snapshots. `replacement_admission_source.py` содержит семь source-order regressions, `missing_webhook_snapshot.py` — три missing cases и четыре положительных controls

## Миграции и эксплуатация

проверены clean upgrade, populated a7 upgrade, повторный downgrade/reupgrade, helper-created schema со старым stamp, empty/deleted-max identity, malformed existing column и interruption после DDL до revision ACK. SQLite schema/data/version/high-water откатываются одним physical transaction. PostgreSQL sequence не перематывается назад

frozen a7 и `retry_archive_v1.py` не изменены. новый head проходит прежний raw retry/DLQ archive roundtrip через f6. старые archive fault oracles привязаны к revision самой archive-фазы, чтобы новая revision не маскировала fault до capture/restore

быстрый fallback остаётся на новом binary — поставить `automation_labels=[]` и перезапустить. для старого binary нужно остановить всех writers, сделать backup, новым checkout откатить **только** новую revision до `a7b8c9d0e1f2`, затем полностью удалить ключ `automation_labels` из project JSON и только после этого запускать старую версию. старый parser отклоняет даже пустой новый ключ

reversal снимает derived automation bit, сохранённые labels и старые durable payloads остаются. новый upgrade и local barrier снова вычисляют текущую policy. более глубокий rollback через f6/base сохраняет прежние archive ограничения, включая maintenance и отсутствие общей lossless гарантии для совместимых live rows при `base`

## Итоговые проверки

итоговые counts и команды будут записаны после завершения текущих общих прогонов и enabled commit hooks. промежуточные targeted результаты не подменяют full suite

## Что реально измерено

сырые measurements и emitted-SQL EXPLAIN сохранены в [JSON отчёте](evidence/automated-mr-priority-performance.json). host macOS 26.0.1 arm64, Python 3.13.7, file SQLite с WAL/FULL и PostgreSQL 16.15 arm64 в Docker. baseline извлечён из точного commit `c6b93df`, candidate — working tree фичи до двух R2 corrections и последующего поведения-сохраняющего выделения pure helpers для обязательного complexity gate. label-source merge и parser corrections лежат вне измеренных read/bulk/feedback workloads

общий read matrix содержит N=0/1/10/100/101/201/1000 при P=1 и N=1000 при P=10, один heavy project и девять с одним MR. на каждую комбинацию active/next/no-op/ORM position собрано по 25 samples. candidate использует `automation_labels=[]` для сопоставления с прежним behavior. startup bulk C=0/1/N и pure classifier L/A=0/1/10/100 измерены отдельно, без выдачи setup/BEGIN/COMMIT за queries операции

для N=1000 дополнительно выполнен конечный ABBA с одинаковой последовательностью common reads без interleaved bulk. SQLite имеет по 50 samples в каждом A/B run, PG по 25. ниже приведены пары A1/A2 и B1/B2, не объединённые выдуманные percentile

| Backend и workload | Baseline median, ms | Candidate median, ms | Baseline p95, ms | Candidate p95, ms |
| --- | --- | --- | --- | --- |
| SQLite active, P=1 | 14.787 / 14.822 | 15.808 / 15.891 | 15.618 / 15.731 | 23.205 / 22.320 |
| SQLite next, P=1 | 14.928 / 14.687 | 15.321 / 15.914 | 21.451 / 15.392 | 16.465 / 16.599 |
| SQLite active, P=10 | 14.667 / 14.556 | 15.473 / 15.982 | 15.695 / 15.673 | 16.366 / 16.837 |
| PG active, P=1 | 14.807 / 14.897 | 15.892 / 15.866 | 16.308 / 17.469 | 17.193 / 17.512 |
| PG next, P=1 | 15.213 / 14.760 | 15.823 / 17.053 | 17.990 / 22.798 | 20.514 / 20.965 |
| PG active, P=10 | 17.142 / 15.159 | 16.669 / 18.001 | 36.991 / 20.061 | 22.614 / 24.007 |

новый active fact добавляет чтение/декодирование одного поля на строку и CASE sort. median active при 1000 rows увеличился примерно на 1 ms в повторённом P=1 workload. SQLite active tail тоже вырос, это явно сохранённый review-trigger, не замаскированный PASS по SLA. PG tail заметно меняется и у baseline. SQLite обе версии используют project index + temporary ORDER BY B-tree, PG обе используют bitmap project scan + memory quicksort. actual PG sort для P=1 занял около 0.8 ms в обеих версиях. из этих локальных данных не следует устойчивое основание добавлять новый index или unrelated LIMIT1 refactor, но и production load SLA они не доказывают

| Локальная активация, N=1000 | SQLite, ms | PG, ms | SQL обеих БД |
| --- | --- | --- | --- |
| C=0 | 9.29 | 11.06 | 2 SELECT, 0 UPDATE |
| C=1, K=1000 | 202.22 | 710.38 | 2 SELECT, 1001 UPDATE |
| C=1000, K=1000 | 523.03 | 1529.88 | 2 SELECT, 2000 UPDATE |

это отдельные actual runs, не распределение latency. постоянные projected reads и O(C+K) writes подтверждены observer. activation не запускает HTTP delivery. no-op refresh без notify делает 1 SELECT и 0 UPDATE, active/next — по 1 SELECT, существующий ORM position — 2 SELECT для непустого проекта. классификация не делает GitLab/author RPC

после выделения pure activation plan этот SQL budget отдельно проверен на окончательном R3 source при N=1000 и C=0/1/1000 на обеих БД. результат остался 2 SELECT и соответственно 0/1001/2000 UPDATE, HTTP delivery по-прежнему не запускается. это отдельная проверка сохранения budget, без повторного заявления baseline latency comparison

synthetic feedback probe использует настоящие queue/updater/notifier и injected HTTP transport. N=K=3, по три samples каждого delay на обе версии/БД. notes requests на refresh остались 6, то есть прежние 2K. при искусственных 500 ms на каждый request median baseline/candidate составил SQLite 3074/3069 ms, PG 3078/3085 ms. это подтверждает, что внешний I/O остаётся основной частью этого workload, а не измеряет latency GitLab. времена project lock и transaction отдельно не профилировались

для WS использован настоящий manager с public authenticated connect и in-process JSON sinks, N=100/1000, subscribers=0/1/10/100, по пять samples. это не TCP/browser benchmark. при N=1000 minimal payload вырос с 81744 до 103744 bytes из-за additive поля, production full item shape здесь не воспроизводился. для 100 subscribers SQLite-run median serialization/broadcast изменился с 65.54 до 72.12 ms. один искусственный slow sink в 50 ms также проверен, `n=1`, без вывода о production backpressure

production frontend builds baseline/candidate выполнены отдельно. JS 844414→847139 bytes, +2725 или +0.323%, gzip 255230→255971, +741 или +0.290%. browser render/reconnect timings недоступны, `n=0`, поэтому React commit/long tasks и browser performance PASS не заявляются. client process CPU и Python traced single-op allocations есть в JSON, это не серверные CPU/RSS. lock contention, event-loop lag и реальная сеть требуют отдельного профиля на согласованном deployment envelope

## Границы результата

strict priority допускает долгое ожидание automated при непрерывном потоке ordinary. aging и редактор настроек в UI не добавлены

browser functional QA выполнена на fixture, browser render/reconnect performance timings имеют `n=0`. реальный GitLab E2E, production capacity, серверные CPU/RSS и distributed exactly-once не заявляются

runtime feedback сохраняет прежние project-lock/HTTP и repeated full-read затраты. локальная bulk-активация не вызывает N отдельных drains. отдельный boolean index и unrelated next-selection refactor не добавлены без устойчивого измеренного основания
