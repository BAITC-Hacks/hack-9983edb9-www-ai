# Scenario Validation and Scoring Engine

Модуль для детерминированной валидации, симуляции и оценки сценариев развития города на основе официальных данных.

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
