const API_URL = "http://127.0.0.1:8000/api";
const $ = (id) => document.getElementById(id);
const state = { initial: null, selections: [], busy: false, lastResult: null, savedPlan: null };
let analysisVersion = 0;
const format = (value) => value.toLocaleString("ru-RU", {minimumFractionDigits: 2, maximumFractionDigits: 2});
const signed = (value) => `${value > 0 ? "+" : ""}${format(value)}`;
const direction = (value) => value > 0 ? "positive" : value < 0 ? "negative" : "neutral";

const districtName = (id) => state.initial.ui_labels.districts[id] || id;
const indicatorName = (id) => state.initial.ui_labels.indicators[id] || id;
const measureName = (id) => state.initial.ui_labels.measures[id] || id;
const categoryName = (id) => state.initial.ui_labels.categories[id] || id;

function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
}

async function api(path, payload, timeout = 15000) {
    const response = await fetch(`${API_URL}${path}`, {
        ...(payload === undefined ? {} : {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        }),
        signal: AbortSignal.timeout(timeout),
    });
    const data = await response.json();
    if (!response.ok) {
        const details = data.errors || data.detail;
        throw new Error(Array.isArray(details)
            ? details.map((item) => typeof item === "string" ? item : item.msg).join(" ")
            : `Ошибка запроса (${response.status}).`);
    }
    return data;
}

function feedback(messages = []) {
    $("feedback").replaceChildren();
    $("feedback").hidden = messages.length === 0;
    const list = element("ul");
    messages.forEach((message) => list.append(element("li", message)));
    $("feedback").append(list);
}

function budgetUsed() {
    return state.selections.reduce((total, selection) => total + state.initial.measures[selection.measure_id].cost, 0);
}

function renderDistricts(scores) {
    const weakest = Math.min(...Object.values(scores));
    $("districts").replaceChildren();
    Object.entries(scores).forEach(([name, score]) => {
        const card = element("article", undefined, `district${score === weakest ? " weakest" : ""}`);
        card.append(element("span", districtName(name)), element("strong", format(score)),
            element("small", score === weakest ? "Самый низкий начальный балл" : "Начальный балл района"));
        $("districts").append(card);
    });
}

function renderMeasures() {
    $("measures").replaceChildren();
    const categories = [...new Set(Object.values(state.initial.measures).map((measure) => measure.category))];
    categories.forEach((category) => {
        const section = element("section");
        section.append(element("h3", categoryName(category), "category-heading"));
        const grid = element("div", undefined, "measure-grid");
        Object.entries(state.initial.measures).filter(([, measure]) => measure.category === category)
            .forEach(([id, measure]) => {
                const card = element("article", undefined, "measure");
                card.id = `card-${id}`;
                const top = element("div", undefined, "card-top");
                top.append(element("strong", id), element("span", measure.type === "city" ? "Весь город" : "Один район"));
                const details = element("div", undefined, "cost-lag");
                details.append(element("strong", `${measure.cost} ед. бюджета`), element("span", `Задержка: ${measure.lag} кварт.`));
                const effects = element("div", undefined, "effects");
                Object.entries(measure.effects).forEach(([key, value]) => {
                    const effect = element("span", `${key} ${value > 0 ? "+" : ""}${value}`, `effect${value < 0 ? " negative" : ""}`);
                    effect.title = `${indicatorName(key)}: ${value > 0 ? "+" : ""}${value} полный эффект`;
                    effect.setAttribute("aria-label", effect.title);
                    effects.append(effect);
                });
                card.append(top, element("h3", measureName(id)), details, effects);
                if (measure.type === "district") {
                    const label = element("label", "Район мероприятия");
                    const select = element("select");
                    select.id = `district-${id}`;
                    select.addEventListener("change", renderPlan);
                    label.htmlFor = select.id;
                    const placeholder = element("option", "Выберите район");
                    placeholder.value = "";
                    select.append(placeholder);
                    Object.keys(state.initial.districts).forEach((district) => {
                        const option = element("option", districtName(district));
                        option.value = district;
                        select.append(option);
                    });
                    label.append(select);
                    card.append(label);
                } else card.append(element("p", "Весь город · Все пять районов", "scope"));
                const hint = element("p", "", "measure-hint");
                hint.id = `hint-${id}`;
                card.append(hint);
                const button = element("button", "Добавить в план");
                button.type = "button";
                button.id = `add-${id}`;
                button.setAttribute("aria-describedby", `hint-${id}`);
                button.addEventListener("click", () => addMeasure(id));
                card.append(button);
                grid.append(card);
            });
        section.append(grid);
        $("measures").append(section);
    });
}

// Fast, local guidance; the backend remains authoritative for full validation.
function additionReasons(id) {
    const measure = state.initial.measures[id];
    if (state.selections.some(s => s.measure_id === id)) return ["Эта мера уже в плане."];
    const reasons = [];
    if (state.selections.length >= state.initial.required_decisions) reasons.push("Уже выбрано 5 решений. Сначала уберите одно.");
    if (budgetUsed() + measure.cost > state.initial.budget) reasons.push(`Не хватает бюджета: нужно ${measure.cost}, осталось ${state.initial.budget - budgetUsed()}.`);
    if (state.selections.filter(s => state.initial.measures[s.measure_id].category === measure.category).length >= state.initial.rules.max_per_category)
        reasons.push(`В направлении «${categoryName(measure.category)}» уже выбраны две меры.`);
    const district = measure.type === "district" ? $(`district-${id}`).value : null;
    if (measure.type === "district" && !district) reasons.push("Сначала выберите район.");
    for (const rule of state.initial.rules.incompatibilities) {
        if (!rule.measures.includes(id)) continue;
        const other = state.selections.find(s => rule.measures.includes(s.measure_id));
        if (other && (rule.scope === "global" || (district && district === other.district)))
            reasons.push(rule.scope === "global" ? `Несовместимо с ${other.measure_id} в любом районе.` : `Конфликт с ${other.measure_id} в районе ${districtName(district)}. Выберите другой район или уберите меру.`);
    }
    return reasons;
}

function addMeasure(id) {
    if (state.busy) return;
    const reasons = additionReasons(id);
    if (reasons.length) return feedback(reasons);
    const district = state.initial.measures[id].type === "district" ? $(`district-${id}`).value : null;
    state.selections.push({measure_id: id, district});
    $("demo-status").textContent = "";
    planChanged();
}

function planChanged() {
    $("demo-status").textContent = "";
    state.lastResult = null;
    analysisVersion += 1;
    $("results").hidden = true;
    feedback();
    renderPlan();
}

function renderPlan() {
    const count = `${state.selections.length} / ${state.initial.required_decisions}`;
    const used = budgetUsed();
    $("decision-count").textContent = count;
    $("budget-remaining").textContent = state.initial.budget - used;
    $("plan-decisions").textContent = count;
    $("plan-used").textContent = used;
    $("plan-remaining").textContent = state.initial.budget - used;
    $("plan-list").replaceChildren();
    if (!state.selections.length) $("plan-list").append(element("p", "Выберите пять мероприятий или загрузите пример.", "empty"));
    state.selections.forEach((selection) => {
        const measure = state.initial.measures[selection.measure_id];
        const row = element("div", undefined, "plan-item");
        const text = element("div");
        text.append(element("strong", `${selection.measure_id} · ${measureName(selection.measure_id)}`), element("small", `${selection.district ? districtName(selection.district) : "Весь город"} · ${measure.cost} ед.`));
        const remove = element("button", "Убрать");
        remove.type = "button";
        remove.setAttribute("aria-label", `Убрать ${selection.measure_id}`);
        remove.disabled = state.busy;
        remove.addEventListener("click", () => {
            state.selections = state.selections.filter((item) => item.measure_id !== selection.measure_id);
            planChanged();
        });
        row.append(text, remove);
        $("plan-list").append(row);
    });
    Object.keys(state.initial.measures).forEach((id) => {
        const selected = state.selections.some((selection) => selection.measure_id === id);
        $(`card-${id}`).classList.toggle("selected", selected);
        $(`add-${id}`).textContent = selected ? "В плане ✓" : "Добавить в план";
        const reasons = additionReasons(id);
        $(`add-${id}`).disabled = state.busy || reasons.length > 0;
        $(`hint-${id}`).textContent = reasons.join(" ");
        if ($(`district-${id}`)) $(`district-${id}`).disabled = selected || state.busy;
    });
    $("demo-official").disabled = state.busy;
    $("demo-cheap").disabled = state.busy;
    $("simulate").disabled = state.busy || state.selections.length !== state.initial.required_decisions;
    $("simulate").textContent = state.busy ? "РАССЧИТЫВАЕМ…" : "РАССЧИТАТЬ · 2 ГОДА";
    $("simulate-hint").textContent = state.selections.length === state.initial.required_decisions
        ? "План готов к проверке и расчёту." : "Выберите ровно 5 решений.";
}

function renderResults(result) {
    state.lastResult = result;
    renderIndicatorChart();
    void renderComparison(result);
    $("result-summary").replaceChildren();
    [["Было", result.baseline_score], ["Стало", result.final_score], ["Изменение", result.score_delta]].forEach(([label, value]) => {
        const block = element("div");
        block.append(element("small", label), element("strong", label === "Изменение" ? signed(value) : format(value), label === "Изменение" ? direction(value) : ""));
        $("result-summary").append(block);
    });
    $("result-budget").textContent = `Потрачено: ${result.total_cost} · Осталось: ${result.remaining_budget}`;
    $("district-results").replaceChildren();
    Object.entries(result.district_scores_before).forEach(([district, before]) => {
        const after = result.district_scores_after[district];
        const row = element("tr");
        row.append(element("td", districtName(district)), element("td", format(before)), element("td", format(after)), element("td", signed(after - before), direction(after - before)));
        $("district-results").append(row);
    });
    $("critical-results").replaceChildren();
    [["Было", result.critical_indicators_before], ["Стало", result.critical_indicators_after]].forEach(([label, entries]) => {
        $("critical-results").append(element("h4", `${label}: ${entries.length}`));
        const list = element("ul");
        entries.forEach((entry) => list.append(element("li", `${districtName(entry.district)} · ${indicatorName(entry.indicator)} (${entry.indicator}): ${format(entry.value)}`)));
        if (!entries.length) list.append(element("li", "Критических показателей нет.", "positive"));
        $("critical-results").append(list);
    });
    $("synergy-results").replaceChildren();
    if (!result.applied_synergies.length) $("synergy-results").append(element("p", "Совместные бонусы не сработали.", "muted"));
    result.applied_synergies.forEach((synergy) => {
        const bonuses = Object.entries(synergy.effects).map(([key, value]) => `${key} ${value > 0 ? "+" : ""}${value}`).join(", ");
        $("synergy-results").append(element("p", `${synergy.measures.join(" + ")} → ${districtName(synergy.district)}: ${bonuses}`, "positive"));
    });
    $("results").hidden = false;
    $("results").focus({ preventScroll: true });
    $("results").scrollIntoView({ block: "start" });
}

async function requestAnalysis(result) {
    const version = ++analysisVersion;
    $("ai-content").replaceChildren();
    $("ai-status").hidden = false;
    $("ai-status").textContent = "AI анализирует ваш план…";
    $("ai-analysis").setAttribute("aria-busy", "true");
    try {
        // Send the exact engine response, without rebuilding or altering values.
        const analysis = await api("/analyze", { simulation_result: result }, 40000);
        if (version !== analysisVersion) return;
        const sections = [
            ["strengths", "Сильные стороны"], ["risks", "Риски"],
            ["tradeoffs", "Компромиссы"], ["consequences", "Последствия в модели"],
            ["recommendations", "Рекомендации"],
        ];
        if (!analysis || analysis.error || typeof analysis.summary !== "string"
            || !sections.every(([key]) => Array.isArray(analysis[key])
                && analysis[key].every((item) => typeof item === "string"))) {
            throw new Error("Analysis unavailable");
        }
        const summary = element("section", undefined, "ai-summary");
        summary.append(element("h3", "Главное"), element("p", analysis.summary));
        $("ai-content").append(summary);
        sections.forEach(([key, title]) => {
            const section = element("section");
            section.append(element("h3", title));
            const list = element("ul");
            analysis[key].forEach((item) => list.append(element("li", item)));
            section.append(list);
            $("ai-content").append(section);
        });
        $("ai-status").hidden = true;
    } catch {
        if (version !== analysisVersion) return;
        $("ai-content").replaceChildren();
        $("ai-status").textContent = "AI-анализ временно недоступен. Расчёт сохранён. Попробуйте рассчитать план ещё раз.";
    } finally {
        if (version === analysisVersion) $("ai-analysis").setAttribute("aria-busy", "false");
    }
}

async function simulate() {
    if (state.busy || state.selections.length !== state.initial.required_decisions) return;
    state.busy = true;
    analysisVersion += 1;
    feedback();
    $("results").hidden = true;
    renderPlan();
    try {
        const result = await api("/simulate", { selections: state.selections });
        if (!result.valid) feedback(["Сервер отклонил план: проверьте количество решений, бюджет, районы и несовместимые меры."]);
        else {
            renderResults(result);
            // Do not block plan controls or official results while AI responds.
            void requestAnalysis(result);
        }
    } catch (error) {
        feedback([`Не удалось выполнить расчёт. Проверьте, запущен ли сервер, и повторите попытку.`]);
    } finally {
        state.busy = false;
        renderPlan();
    }
}

async function loadDashboard() {
    $("retry").hidden = true;
    $("load-status").hidden = false;
    $("load-status").className = "";
    $("load-status").textContent = "Загружаем данные города…";
    try {
        // Initial-state has no district scores. An empty plan returns the
        // engine's baseline fields, without calculating a final scenario score.
        const [initial, baseline] = await Promise.all([
            api("/initial-state"), api("/simulate", { selections: [] }),
        ]);
        state.initial = initial;
        $("baseline-score").textContent = format(initial.baseline_score);
        renderDistricts(baseline.district_scores_before);
        $("chart-district").replaceChildren();
        Object.keys(initial.districts).forEach(district => {
            const option = element("option", districtName(district)); option.value = district;
            $("chart-district").append(option);
        });
        $("chart-district").value = "Nura";
        renderMeasures();
        renderPlan();
        $("load-status").hidden = true;
        $("dashboard").hidden = false;
    } catch (error) {
        $("load-status").className = "error";
        $("load-status").textContent = `Не удалось загрузить данные. Проверьте, запущен ли сервер, и нажмите «Повторить подключение».`;
        $("retry").hidden = false;
    }
}

$("simulate").addEventListener("click", simulate);
$("retry").addEventListener("click", loadDashboard);
loadDashboard();

$("save-plan").addEventListener("click", () => {
    if (!state.lastResult) return;
    state.savedPlan = structuredClone(state.lastResult.selected_measures);
    clearComparison();
    $("comparison-status").textContent = "План А сохранён в этой вкладке. Измените решения и рассчитайте план Б. При обновлении страницы сохранение исчезнет.";
});

async function renderComparison(result) {
    clearComparison();
    if (!state.savedPlan) return;
    const saved = state.savedPlan;
    $("comparison-status").textContent = "Сравниваем планы…";
    try {
        const response = await api("/compare", {selections_a: saved, selections_b: result.selected_measures});
        if (state.lastResult !== result || state.savedPlan !== saved) return;
        if (!response.valid) throw new Error("Invalid comparison");
        const c = response.comparison;
        $("comparison-status").textContent = `План А: ${format(c.score_a)} балла, стоимость ${c.cost_a}. План Б: ${format(c.score_b)} балла, стоимость ${c.cost_b}.`;
        renderComparisonInsights(c, saved, result.selected_measures);
        const table = element("table");
        const header = element("tr");
        ["Район", "План А", "План Б", "Б − А"].forEach(label => header.append(element("th", label)));
        const head = element("thead"); head.append(header); table.append(head);
        const body = element("tbody");
        Object.entries(c.districts).forEach(([district, values]) => {
            const row = element("tr");
            [districtName(district), format(values.a), format(values.b), signed(values.difference)].forEach(value => row.append(element("td", value)));
            body.append(row);
        });
        table.append(body); $("comparison-results").append(table);
    } catch {
        if (state.lastResult === result && state.savedPlan === saved)
            $("comparison-status").textContent = "Не удалось сравнить планы. Проверьте подключение и повторите расчёт.";
    }
}

const DEMO_PLANS = {
    official: [{measure_id: "M7", district: "Nura"}, {measure_id: "M8", district: "Nura"},
        {measure_id: "M10", district: "Nura"}, {measure_id: "M12", district: null}, {measure_id: "M5", district: "Saryarka"}],
    cheap: ["M9", "M11", "M10", "M12", "M4"].map(measure_id => ({measure_id, district: measure_id === "M12" ? null : "Nura"})),
};
function loadExample(name) {
    if (state.busy || !state.initial) return;
    state.selections = structuredClone(DEMO_PLANS[name]);
    Object.keys(state.initial.measures).forEach(id => {
        if ($(`district-${id}`)) $(`district-${id}`).value = state.selections.find(s => s.measure_id === id)?.district || "";
    });
    planChanged();
    $("demo-status").textContent = name === "official"
        ? "Пример из задания загружен: 5 решений, стоимость 95. Нажмите «Рассчитать»."
        : "Экономный план загружен: 5 решений, стоимость 61. Нажмите «Рассчитать».";
}
$("demo-official").addEventListener("click", () => loadExample("official"));
$("demo-cheap").addEventListener("click", () => loadExample("cheap"));
$("chart-district").addEventListener("change", renderIndicatorChart);

function renderIndicatorChart() {
    const result = state.lastResult;
    if (!result) return;
    const district = $("chart-district").value;
    $("indicator-chart").replaceChildren();
    Object.entries(result.indicators_before[district]).forEach(([key, before]) => {
        const after = result.indicators_after[district][key];
        const row = element("div", undefined, "indicator-row");
        row.append(element("strong", `${indicatorName(key)} · ${key}`));
        [["Было", before, "before"], ["Стало", after, "after"]].forEach(([label, value, type]) => {
            const line = element("div", undefined, "bar-line");
            line.append(element("span", label));
            const track = element("div", undefined, "bar-track");
            track.setAttribute("aria-hidden", "true");
            const bar = element("div", undefined, `bar-fill ${type}`);
            bar.style.width = `${value}%`;
            track.append(bar);
            line.append(track, element("span", format(value)));
            row.append(line);
        });
        const note = `${signed(result.indicator_deltas[district][key])}${after < 40 ? " · Критическое значение: ниже 40" : ""}`;
        row.append(element("small", note, after < 40 ? "negative" : direction(after - before)));
        $("indicator-chart").append(row);
    });
}

function clearComparison() {
    $("comparison-results").replaceChildren();
    $("comparison-insights").replaceChildren();
    $("comparison-selections").replaceChildren();
    $("comparison-plans").hidden = true;
}

function renderComparisonInsights(c, planA, planB) {
    // All numbers below are engine results, never estimates from AI.
    const costText = c.cost_difference < 0 ? `План Б дешевле на ${Math.abs(c.cost_difference)} ед.`
        : c.cost_difference > 0 ? `План Б дороже на ${c.cost_difference} ед.` : "Стоимость планов одинакова";
    const scoreText = c.score_difference < 0 ? `его балл ниже на ${format(Math.abs(c.score_difference))}`
        : c.score_difference > 0 ? `его балл выше на ${format(c.score_difference)}` : "итоговые баллы равны";
    $("comparison-insights").append(element("p", `${costText}; ${scoreText}.`, "comparison-verdict"));
    const critical = element("p", `Критических показателей: план А — ${c.critical_a.length}, план Б — ${c.critical_b.length}.`);
    $("comparison-insights").append(critical);
    if (c.critical_b.length) {
        const list = element("ul");
        c.critical_b.forEach(item => list.append(element("li", `В плане Б: ${districtName(item.district)} — ${indicatorName(item.indicator)}: ${format(item.value)}. Значение ниже 40 даёт штраф.`, "negative")));
        $("comparison-insights").append(list);
    }
    $("comparison-insights").append(element("p", "Общий балл не заменяет оценку каждого района. Ниже можно увидеть, где результат стал лучше или хуже. Это сравнение условной модели.", "muted"));
    for (const [name, plan] of [["План А", planA], ["План Б", planB]]) {
        const section = element("section"); section.append(element("h4", name));
        const list = element("ul");
        plan.forEach(item => list.append(element("li", `${item.measure_id} · ${measureName(item.measure_id)} — ${item.district ? districtName(item.district) : "весь город"}`)));
        section.append(list); $("comparison-selections").append(section);
    }
    $("comparison-plans").hidden = false;
}
