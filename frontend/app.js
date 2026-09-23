const API_URL = "http://127.0.0.1:8000/api";
const $ = (id) => document.getElementById(id);
const state = { initial: null, selections: [], busy: false };
const format = (value) => value.toFixed(2);
const signed = (value) => `${value > 0 ? "+" : ""}${format(value)}`;
const direction = (value) => value > 0 ? "positive" : value < 0 ? "negative" : "neutral";

function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
}

async function api(path, payload) {
    const response = await fetch(`${API_URL}${path}`, {
        ...(payload === undefined ? {} : {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        }),
        signal: AbortSignal.timeout(15000),
    });
    const data = await response.json();
    if (!response.ok) {
        const details = data.errors || data.detail;
        throw new Error(Array.isArray(details)
            ? details.map((item) => typeof item === "string" ? item : item.msg).join(" ")
            : `API request failed (${response.status}).`);
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
        card.append(element("span", name), element("strong", format(score)),
            element("small", score === weakest ? "Lowest baseline · priority area" : "Initial district score"));
        $("districts").append(card);
    });
}

function renderMeasures() {
    $("measures").replaceChildren();
    const categories = [...new Set(Object.values(state.initial.measures).map((measure) => measure.category))];
    categories.forEach((category) => {
        const section = element("section");
        section.append(element("h3", category, "category-heading"));
        const grid = element("div", undefined, "measure-grid");
        Object.entries(state.initial.measures).filter(([, measure]) => measure.category === category)
            .forEach(([id, measure]) => {
                const card = element("article", undefined, "measure");
                card.id = `card-${id}`;
                const top = element("div", undefined, "card-top");
                top.append(element("strong", id), element("span", measure.type === "city" ? "City-wide" : "District-level"));
                const details = element("div", undefined, "cost-lag");
                details.append(element("strong", `${measure.cost} budget points`), element("span", `Lag: ${measure.lag} quarters`));
                const effects = element("div", undefined, "effects");
                Object.entries(measure.effects).forEach(([key, value]) => {
                    const effect = element("span", `${key} ${value > 0 ? "+" : ""}${value}`, `effect${value < 0 ? " negative" : ""}`);
                    effect.title = `${state.initial.indicator_metadata[key]}: ${value > 0 ? "+" : ""}${value} full effect`;
                    effect.setAttribute("aria-label", effect.title);
                    effects.append(effect);
                });
                card.append(top, element("h3", measure.name), details, effects);
                if (measure.type === "district") {
                    const label = element("label", "Target district");
                    const select = element("select");
                    select.id = `district-${id}`;
                    label.htmlFor = select.id;
                    const placeholder = element("option", "Choose a district");
                    placeholder.value = "";
                    select.append(placeholder);
                    Object.keys(state.initial.districts).forEach((district) => {
                        const option = element("option", district);
                        option.value = district;
                        select.append(option);
                    });
                    label.append(select);
                    card.append(label);
                } else card.append(element("p", "City-wide · All five districts", "scope"));
                const button = element("button", "Add to plan");
                button.type = "button";
                button.id = `add-${id}`;
                button.addEventListener("click", () => addMeasure(id));
                card.append(button);
                grid.append(card);
            });
        section.append(grid);
        $("measures").append(section);
    });
}

function addMeasure(id) {
    if (state.busy) return;
    if (state.selections.some((selection) => selection.measure_id === id)) return feedback([`${id} is already in your plan.`]);
    if (state.selections.length >= state.initial.required_decisions) return feedback(["Your plan already has 5 decisions. Remove one before adding another."]);
    const measure = state.initial.measures[id];
    if (budgetUsed() + measure.cost > state.initial.budget) return feedback([`Adding ${id} would exceed your ${state.initial.budget}-point budget.`]);
    const district = measure.type === "district" ? $(`district-${id}`).value : null;
    if (measure.type === "district" && !district) return feedback([`Choose a district for ${id} first.`]);
    state.selections.push({ measure_id: id, district });
    planChanged();
}

function planChanged() {
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
    if (!state.selections.length) $("plan-list").append(element("p", "Your next five decisions start here.", "empty"));
    state.selections.forEach((selection) => {
        const measure = state.initial.measures[selection.measure_id];
        const row = element("div", undefined, "plan-item");
        const text = element("div");
        text.append(element("strong", `${selection.measure_id} · ${measure.name}`), element("small", `${selection.district || "City-wide"} · ${measure.cost} points`));
        const remove = element("button", "Remove");
        remove.type = "button";
        remove.setAttribute("aria-label", `Remove ${selection.measure_id}`);
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
        $(`add-${id}`).textContent = selected ? "Added to plan ✓" : "Add to plan";
        $(`add-${id}`).disabled = state.busy;
        if ($(`district-${id}`)) $(`district-${id}`).disabled = selected || state.busy;
    });
    $("simulate").disabled = state.busy || state.selections.length !== state.initial.required_decisions;
    $("simulate").textContent = state.busy ? "SIMULATING…" : "SIMULATE 2 YEARS";
    $("simulate-hint").textContent = state.selections.length === state.initial.required_decisions
        ? "Your plan is ready for official validation." : "Select exactly 5 decisions to simulate.";
}

function renderResults(result) {
    $("result-summary").replaceChildren();
    [["Before", result.baseline_score], ["After", result.final_score], ["Delta", result.score_delta]].forEach(([label, value]) => {
        const block = element("div");
        block.append(element("small", label), element("strong", label === "Delta" ? signed(value) : format(value), label === "Delta" ? direction(value) : ""));
        $("result-summary").append(block);
    });
    $("result-budget").textContent = `Budget used: ${result.total_cost} · Budget remaining: ${result.remaining_budget}`;
    $("district-results").replaceChildren();
    Object.entries(result.district_scores_before).forEach(([district, before]) => {
        const after = result.district_scores_after[district];
        const row = element("tr");
        row.append(element("td", district), element("td", format(before)), element("td", format(after)), element("td", signed(after - before), direction(after - before)));
        $("district-results").append(row);
    });
    $("critical-results").replaceChildren();
    [["Before", result.critical_indicators_before], ["After", result.critical_indicators_after]].forEach(([label, entries]) => {
        $("critical-results").append(element("h4", `${label}: ${entries.length}`));
        const list = element("ul");
        entries.forEach((entry) => list.append(element("li", `${entry.district} · ${state.initial.indicator_metadata[entry.indicator]} (${entry.indicator}): ${format(entry.value)}`)));
        if (!entries.length) list.append(element("li", "No critical indicators.", "positive"));
        $("critical-results").append(list);
    });
    $("synergy-results").replaceChildren();
    if (!result.applied_synergies.length) $("synergy-results").append(element("p", "No synergies applied.", "muted"));
    result.applied_synergies.forEach((synergy) => {
        const bonuses = Object.entries(synergy.effects).map(([key, value]) => `${key} ${value > 0 ? "+" : ""}${value}`).join(", ");
        $("synergy-results").append(element("p", `${synergy.measures.join(" + ")} → ${synergy.district}: ${bonuses}`, "positive"));
    });
    $("results").hidden = false;
    $("results").focus({ preventScroll: true });
    $("results").scrollIntoView({ block: "start" });
}

async function simulate() {
    if (state.busy || state.selections.length !== state.initial.required_decisions) return;
    state.busy = true;
    feedback();
    $("results").hidden = true;
    renderPlan();
    try {
        const result = await api("/simulate", { selections: state.selections });
        if (!result.valid) feedback(result.errors);
        else renderResults(result);
    } catch (error) {
        feedback([`Simulation failed. Check the backend connection and retry. ${error.message}`]);
    } finally {
        state.busy = false;
        renderPlan();
    }
}

async function loadDashboard() {
    $("retry").hidden = true;
    $("load-status").hidden = false;
    $("load-status").className = "";
    $("load-status").textContent = "Connecting to the city dashboard…";
    try {
        // Initial-state has no district scores. An empty plan returns the
        // engine's baseline fields, without calculating a final scenario score.
        const [initial, baseline] = await Promise.all([
            api("/initial-state"), api("/simulate", { selections: [] }),
        ]);
        state.initial = initial;
        $("baseline-score").textContent = format(initial.baseline_score);
        renderDistricts(baseline.district_scores_before);
        renderMeasures();
        renderPlan();
        $("load-status").hidden = true;
        $("dashboard").hidden = false;
    } catch (error) {
        $("load-status").className = "error";
        $("load-status").textContent = `Cannot load city data. Start the API at ${API_URL}. ${error.message}`;
        $("retry").hidden = false;
    }
}

$("simulate").addEventListener("click", simulate);
$("retry").addEventListener("click", loadDashboard);
loadDashboard();
