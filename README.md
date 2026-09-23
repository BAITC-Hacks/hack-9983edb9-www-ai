# QalaAI — «Аким на 5 часов»

AI-симулятор управления условными районами Астаны для HackAlem AI.
Пользователь выбирает ровно пять мероприятий в пределах 100 бюджетных единиц
и сравнивает состояние города до и после двух условных лет.

Данные синтетические: это учебная модель по заданию хакатона, не реальные
городские измерения и не прогноз. Персональные данные не используются.
Набор районов, 14 мероприятий и формула сверены с предоставленным заданием.

## Архитектура и роль AI

HTML/CSS/vanilla JavaScript → FastAPI → расчётный движок → результат → OpenAI.

- `backend/data.py`: исходные показатели, мероприятия, веса и ограничения.
- `backend/simulation.py`: валидация, расчёт Score, дельт и вкладов мероприятий.
- `backend/main.py`: HTTP API для интерфейса.
- `backend/ai_service.py`: объяснение готового результата через OpenAI (`gpt-4o-mini`).
- `frontend/`: выбор решений, бюджет, результаты по районам и AI-анализ.
- `tests/`: тесты движка и API на стандартном `unittest`.

Нет базы данных, регистрации или сохранения планов между перезагрузками.
Все пользователи начинают с одного состояния. Сервер не изменяет исходный датасет.

AI объясняет сильные стороны, риски, компромиссы и возможные последствия,
но не считает баллы. Все числа готовит Python. Реальный AI требует ключа
и доступного API-баланса. Без ключа симуляция работает, а интерфейс сообщает
о недоступности анализа. Автотесты заменяют OpenAI подставными ответами:
они не доказывают качество настоящего ответа модели.

## Правила

- Бюджет 100; остаток не даёт бонуса.
- Ровно 5 разных мероприятий, максимум 2 из одного направления.
- Для районной меры нужен один из пяти районов. У городской район отсутствует
  (в JSON допускается `null`, означающий отсутствие района).
- M1 и M3 несовместимы во всём городе.
- M4/M7 и M5/M13 несовместимы при выборе одного района.
- Нарушение правил возвращает причины и `final_score: null`.
- Порядок выбора не влияет на расчёт.

## Формула Astana Quality of Life Score

Горизонт H = 8 кварталов. Для каждого района и показателя:

```text
новый показатель = clip(исходный + сумма(полный эффект × (8 − лаг) / 8)
                        + синергии, 0, 100)
D_района = сумма(вес показателя × новый показатель)
D_avg = сумма(доля населения × D_района)
Score = 0.7 × D_avg + 0.3 × минимальный D_района − N_crit
```

`N_crit` — число пар «район × показатель» строго ниже 40.
Значение ровно 40 не штрафуется. Расчёты не округляются, интерфейс показывает
два знака после запятой. Базовый Score = **52.55768** (на экране **52.56**).

| Показатель | T1 | T2 | E1 | E2 | S1 | S2 | B1 | B2 | C1 | C2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Вес | 0.10 | 0.10 | 0.09 | 0.11 | 0.11 | 0.11 | 0.09 | 0.09 | 0.10 | 0.10 |

Синергии не масштабируются лагом: M1/M2 дают +2 T1 в районе M1,
M10/M12 дают +2 B1 в районе M10, M5/M6 дают +2 E2 в районе M5.

## Что передаётся AI

Ответ симуляции содержит исходные и конечные значения, бюджет, Score,
критические показатели, выбранные меры и синергии. Дополнительно:

- `district_score_deltas`: готовая разница оценок каждого района.
- `indicator_deltas`: готовые изменения всех показателей после ограничения 0–100.
- `measure_contributions`: стоимость, лаг, реализованная доля и эффекты каждой
  меры по районам в `indicator_effects_before_clip` — **до ограничения 0–100**.
- `clipping_adjustments`: поправки, внесённые ограничением 0–100.

Эффекты мер и синергии вместе с поправками объясняют итоговые изменения.
Эффект меры не является её отдельным вкладом в итоговый Score: минимум района,
штрафы и границы делают такое разложение неоднозначным. AI запрещено самому
складывать или придумывать числа. Для невалидного плана дельты и поправки
равны `null`, список вкладов пуст. Старые поля ответа сохранены.

## Быстрый запуск на macOS (zsh)

В терминале откройте корень проекта:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Во втором терминале из той же папки:

```sh
.venv/bin/python -m http.server 5500 --bind 127.0.0.1 --directory frontend
```

Откройте http://127.0.0.1:5500. Документация API: http://127.0.0.1:8000/docs.
Остановка каждого сервера — Ctrl+C в его терминале.

Когда будет ключ, остановите backend и в его терминале выполните:

```zsh
read -rs 'OPENAI_API_KEY?Вставьте ключ OpenAI (ввод скрыт): '
export OPENAI_API_KEY
printf '\n'
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Ключ вводится в скрытое приглашение, не в команду и не в код.
В Linux/bash вместо строки `read` используйте
`read -rsp 'OpenAI API key: ' OPENAI_API_KEY`.
`.env` автоматически не загружается. После работы можно убрать переменную
командой `unset OPENAI_API_KEY`.

Проверка без ключа и платных запросов:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

## Демонстрация и ограничения

Официальный пример ниже: M7/M8/M10 в Nura, M12 по городу, M5 в Saryarka.
Стоимость **95**, Score **56.54307**, прирост **3.98539**.
Дешёвый пример M9/M11/M10/M4 в Nura и M12 по городу стоит **61**,
Score **55.667385**. Районы уточнены для воспроизводимости второго результата.

Покажите исходные показатели → выберите пять мер → нажмите SIMULATE 2 YEARS →
сравните районы и критические показатели → прочитайте AI-анализ, если ключ настроен.

Сравнение команд, случайные события и автоматическая генерация презентаций
пока не реализованы и являются опциональными. Практическая цель — обсуждение
компромиссов в распределении бюджета. Применение к реальному городу потребует
проверенных данных и отдельной валидации модели.


## Возможности

- **Расчет базового состояния (`calculate_baseline`)**: Оценивает исходные показатели по всем районам города, рассчитывает средневзвешенный балл (`D_avg`), минимальный балл (`min_D`), количество критических индикаторов и итоговый скор.
- **Валидация сценария (`validate_scenario`)**: Проверяет список выбранных мер на соответствие бюджету, лимитам по категориям, ограничениям по количеству решений, а также на наличие глобальных и локальных несовместимостей.
- **Симуляция сценария (`simulate_scenario`)**: Применяет валидные меры с учетом временного горизона (`SIMULATION_HORIZON`), лагов внедрения, синергетических эффектов и ограничений индикаторов (от 0 до 100), возвращая детальное сравнение «до/после».

---

## Требования

Для работы модуля необходим Python 3.13 и файл `.data` со следующими структурами:
- `BUDGET` (int/float)
- `DISTRICTS` (dict с данными районов, долями населения и начальными индикаторами)
- `MEASURES` (dict доступных мер с указанием стоимости, категории, типа и эффектов)
- `INCOMPATIBILITIES` (список правил несовместимости мер)
- `SYNERGIES` (список возможных синергетических бонусов)
- `INDICATOR_WEIGHTS` (веса индикаторов для расчета баллов)
- `REQUIRED_DECISIONS` (обязательное количество мер в сценарии)
- `SIMULATION_HORIZON` (горизонт симуляции в условных единицах)

---

## Использование

### 1. Расчет базовой ситуации
```python
from backend.simulation import calculate_baseline

baseline = calculate_baseline()
print("Базовый скор города:", baseline["score"])
```


## Local installation and API verification

Use **Python 3.13**. Run these commands from the repository root.
The deterministic simulation works without an OpenAI key or AI availability.

### Install (Windows PowerShell)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On macOS/Linux, create the environment with `python3.13 -m venv .venv`
and use `.venv/bin/python` in place of `.\.venv\Scripts\python.exe` below.

### Optional AI configuration

The backend reads `OPENAI_API_KEY` from its process environment only.
`.env.example` is a placeholder template. Creating a `.env` file does **not**
automatically load it; no dotenv loader is used. Keep real keys out of source,
frontend code, and version control. `.env` is ignored by Git.

To set the key for the current PowerShell session without entering it into
command history, enter it as the password in the credential prompt:

```powershell
$credential = Get-Credential -UserName "OpenAI" -Message "Enter the API key as the password"
$env:OPENAI_API_KEY = $credential.GetNetworkCredential().Password
Remove-Variable credential
```

Start the backend in this same session. Restart an existing backend after
changing its environment. Without a key, AI returns a controlled error and
simulation remains available. AI explains supplied results; it does not run
or replace the deterministic numerical simulation.

### Run the backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Run the frontend in a second terminal

```powershell
.\.venv\Scripts\python.exe -m http.server 5500 --bind 127.0.0.1 --directory frontend
```

Open http://localhost:5500 (or http://127.0.0.1:5500).
The frontend calls http://127.0.0.1:8000; it is served separately from FastAPI.
Interactive API documentation is at http://127.0.0.1:8000/docs.

### API contracts

| Endpoint | Request | Response |
| --- | --- | --- |
| `GET /api/health` | No body | `{"status":"ok"}` |
| `GET /api/initial-state` | No body | Budget, required decisions, baseline score, districts, measures, indicator metadata |
| `POST /api/simulate` | `{"selections": [...]}` | Structured deterministic result; invalid scenarios return `valid=false`, validation errors, and `final_score=null` |
| `POST /api/analyze` | `{"simulation_result": {...}}` with the complete valid simulation response | `summary`, `strengths`, `risks`, `tradeoffs`, `consequences`, `recommendations`, or `{"error":{"code":"...","message":"..."}}` |

Domain validation and controlled AI errors use HTTP 200 with the above JSON
fields, preserving the frontend contract. Malformed request bodies use HTTP
422 with a `detail` list. AI errors never invalidate a simulation result.
AI error codes include `missing_api_key`, `invalid_simulation`,
`openai_request_failed`, `openai_timeout`, `invalid_ai_response`, and
`analysis_unavailable`. OpenAI requests have a 30-second SDK timeout and no
SDK retries. The analysis endpoint explains the supplied result; it does not
recalculate or independently verify its numerical authenticity.

### Official reference scenario

Submit this JSON to `POST /api/simulate` through `/docs` or an HTTP client:

```json
{
  "selections": [
    {"measure_id": "M7", "district": "Nura"},
    {"measure_id": "M8", "district": "Nura"},
    {"measure_id": "M10", "district": "Nura"},
    {"measure_id": "M12", "district": null},
    {"measure_id": "M5", "district": "Saryarka"}
  ]
}
```

Expected: `valid=true`, `baseline_score` approximately **52.55768**,
`final_score` approximately **56.54307**, `total_cost=95`,
`remaining_budget=5`, and the M10 + M12 synergy in Nura.

### Run the complete automated test suite

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

No running server or API key is needed. API tests use FastAPI TestClient
(`httpx`) and the standard-library `unittest` runner. All external OpenAI calls
are mocked, including success, request failure, and timeout cases.
