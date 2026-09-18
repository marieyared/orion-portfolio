import {
  DEFAULT_PROFILE,
  LIFE_EVENT_TYPES,
  PLAN_DEFINITIONS,
  comparePlans,
  defaultLifeMap,
  monthLabel,
  normalizeLifeMap,
  normalizeProfile,
  profileSummary,
  projectLifeMap,
  recommendPlan,
  salaryAtAge,
  simulatePlan,
} from "./engine.mjs";

const PROFILE_STORAGE_KEY = "orion.wealth.v1";
const LIFE_MAP_STORAGE_KEY = "orion.wealth.life-map.v1";
const state = {
  profile: loadProfile(),
  lifeMap: null,
  planId: "balanced",
  horizonYears: 10,
  view: "life",
};
state.lifeMap = loadLifeMap(state.profile);
state.planId = recommendPlan(state.profile);

function loadProfile() {
  try {
    const saved = JSON.parse(localStorage.getItem(PROFILE_STORAGE_KEY));
    return normalizeProfile(saved || DEFAULT_PROFILE);
  } catch {
    return normalizeProfile(DEFAULT_PROFILE);
  }
}

function saveProfile() {
  localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(state.profile));
}

function loadLifeMap(profile) {
  try {
    const saved = JSON.parse(localStorage.getItem(LIFE_MAP_STORAGE_KEY));
    return normalizeLifeMap(saved || defaultLifeMap(profile), profile);
  } catch {
    return defaultLifeMap(profile);
  }
}

function saveLifeMap() {
  localStorage.setItem(LIFE_MAP_STORAGE_KEY, JSON.stringify(state.lifeMap));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function money(value, compact = false) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: state.profile.currency,
    maximumFractionDigits: 0,
    notation: compact && Math.abs(value) >= 100000 ? "compact" : "standard",
  }).format(value || 0);
}

function signedMoney(value) {
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${money(value, true)}`;
}

function renderPlanSelector() {
  const container = document.querySelector("#plan-selector");
  container.innerHTML = Object.values(PLAN_DEFINITIONS).map((plan) => `
    <button type="button" class="segment ${plan.id === state.planId ? "active" : ""}" data-plan="${plan.id}">${plan.shortName}</button>
  `).join("");
}

function renderMetrics() {
  const summary = profileSummary(state.profile);
  document.querySelector("#metric-net-worth").textContent = money(summary.netWorth, true);
  document.querySelector("#metric-surplus").textContent = money(summary.monthlySurplus);
  document.querySelector("#metric-surplus").style.color = summary.monthlySurplus < 0 ? "var(--coral)" : "var(--ink)";
  document.querySelector("#metric-surplus-note").textContent = summary.monthlySurplus < 0 ? "Spending exceeds income" : "After current spending";
  document.querySelector("#metric-buffer").textContent = `${summary.emergencyMonths.toFixed(1)} months`;
  document.querySelector("#metric-debt").textContent = `${summary.debtApr.toFixed(1)}% APR`;
  document.querySelector("#metric-debt-note").textContent = `${money(summary.debt)} outstanding`;
}

function chartMarkup(timeline) {
  const width = 760;
  const height = 240;
  const padding = { top: 18, right: 10, bottom: 16, left: 58 };
  const values = timeline.map((point) => point.netWorth);
  const minValue = Math.min(0, ...values);
  const maxValue = Math.max(1, ...values);
  const range = maxValue - minValue || 1;
  const x = (index) => padding.left + (index / Math.max(1, timeline.length - 1)) * (width - padding.left - padding.right);
  const y = (value) => padding.top + (1 - (value - minValue) / range) * (height - padding.top - padding.bottom);
  const path = timeline.map((point, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(point.netWorth).toFixed(1)}`).join(" ");
  const area = `${path} L${x(timeline.length - 1).toFixed(1)},${height - padding.bottom} L${x(0).toFixed(1)},${height - padding.bottom} Z`;
  const ticks = [0, 0.5, 1].map((ratio) => {
    const value = minValue + range * ratio;
    const py = y(value);
    return `<line x1="${padding.left}" y1="${py}" x2="${width - padding.right}" y2="${py}" stroke="#dfe4e0" stroke-width="1" />
      <text x="${padding.left - 9}" y="${py + 4}" text-anchor="end" fill="#8e9791" font-size="10">${money(value, true)}</text>`;
  }).join("");

  return `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
    ${ticks}
    <path d="${area}" fill="#dcebe1" opacity="0.72"></path>
    <path d="${path}" fill="none" stroke="#2c6e49" stroke-width="3" vector-effect="non-scaling-stroke"></path>
    <circle cx="${x(timeline.length - 1)}" cy="${y(values[values.length - 1])}" r="4" fill="#2c6e49"></circle>
  </svg>`;
}

function renderEventRail(projection) {
  const visibleEvents = state.lifeMap.events.filter((event) => event.age <= projection.endAge);
  const grouped = [...visibleEvents.reduce((groups, event) => {
    const existing = groups.get(event.age) || [];
    existing.push(event);
    groups.set(event.age, existing);
    return groups;
  }, new Map()).entries()];
  const span = Math.max(1, projection.endAge - projection.currentAge);
  document.querySelector("#event-rail").innerHTML = grouped.map(([age, events]) => {
    const left = Math.max(0, Math.min(100, (age - projection.currentAge) / span * 100));
    const title = events.map((event) => event.label).join(", ");
    return `<div class="event-marker" style="left:calc(${left}% - 4px)" title="${escapeHtml(title)} at age ${age}">
      <span>${age}</span>
    </div>`;
  }).join("");
}

function renderAnnualLedger(projection) {
  const historyRows = projection.salaryHistory.map((entry) => `
    <tr>
      <td>${entry.age}</td>
      <td>${money(entry.annualIncome)}</td>
      <td class="event-text">Recorded salary</td>
      <td>Actual record</td>
      <td>-</td>
    </tr>
  `).join("");
  const projectedRows = projection.rows.map((row) => {
    const eventText = row.events.length
      ? row.events.map((event) => escapeHtml(event.label)).join(", ")
      : "";
    const freeCash = row.phase === "current" ? "Current" : money(row.annualSurplus);
    return `<tr class="${row.phase === "current" ? "current-row" : ""}">
      <td>${row.age}</td>
      <td>${money(row.annualSalary)}</td>
      <td class="event-text">${eventText || "-"}</td>
      <td class="${row.annualSurplus < 0 ? "negative" : ""}">${freeCash}</td>
      <td>${money(row.netWorth, true)}</td>
    </tr>`;
  }).join("");
  document.querySelector("#annual-body").innerHTML = historyRows + projectedRows;
}

function renderTimelineList(projection) {
  const assessments = new Map(projection.eventAssessments.map((item) => [item.id, item]));
  const salaryItems = state.lifeMap.salaryEntries.map((entry) => ({
    id: entry.id,
    age: entry.age,
    kind: "salary",
    title: entry.note,
    detail: money(entry.annualIncome) + " annual net income",
    status: entry.age < state.profile.age ? "Actual" : entry.age === state.profile.age ? "Current" : "Planned",
  }));
  const eventItems = state.lifeMap.events.map((event) => {
    const assessment = assessments.get(event.id);
    const amount = event.type === "retirement" ? "" : " · " + money(event.amount);
    return {
      id: event.id,
      age: event.age,
      kind: "event",
      title: event.label,
      detail: LIFE_EVENT_TYPES[event.type].name + amount,
      status: assessment?.status || event.certainty,
    };
  });
  const items = [...salaryItems, ...eventItems].sort((a, b) => a.age - b.age || a.kind.localeCompare(b.kind));
  document.querySelector("#timeline-list").innerHTML = items.length ? items.map((item) => `
    <div class="timeline-item">
      <span class="timeline-age">${item.age}</span>
      <div class="timeline-copy">
        <strong>${escapeHtml(item.title)}</strong>
        <span>${escapeHtml(item.detail)}</span>
        <em class="timeline-status">${escapeHtml(item.status)}</em>
      </div>
      <button class="remove-item" type="button" data-remove-kind="${item.kind}" data-remove-id="${escapeHtml(item.id)}" aria-label="Remove ${escapeHtml(item.title)}">x</button>
    </div>
  `).join("") : '<div class="timeline-empty">No salaries or life events have been mapped yet.</div>';
}

function renderLifeMap() {
  const projection = projectLifeMap(state.profile, state.lifeMap, state.profile.age + state.horizonYears);
  const currentRow = projection.rows[0];
  document.querySelector("#life-current-worth").textContent = money(projection.startingNetWorth, true);
  document.querySelector("#life-current-age").textContent = "At age " + projection.currentAge;
  document.querySelector("#life-current-income").textContent = money(currentRow.annualSalary, true);
  document.querySelector("#life-ending-worth").textContent = money(projection.endingNetWorth, true);
  document.querySelector("#life-ending-age").textContent = "Projected at age " + projection.endAge;
  document.querySelector("#life-event-count").textContent = String(state.lifeMap.events.length);
  document.querySelector("#salary-growth").value = state.lifeMap.salaryGrowthPct;
  document.querySelector("#life-chart").innerHTML = chartMarkup(projection.rows);
  document.querySelector("#life-chart-axis").innerHTML = `<span>Age ${projection.currentAge}</span><span>Age ${Math.round((projection.currentAge + projection.endAge) / 2)}</span><span>Age ${projection.endAge}</span>`;
  renderEventRail(projection);
  renderAnnualLedger(projection);
  renderTimelineList(projection);
}

function renderAllocation(plan) {
  const labels = { debt: "Debt payoff", reserve: "Cash reserve", invest: "Investments", rental: "Rental fund" };
  document.querySelector("#action-total").textContent = money(plan.monthlySurplus);
  document.querySelector("#allocation-grid").innerHTML = Object.entries(labels).map(([key, label]) => {
    const amount = plan.firstMonthAllocation[key] || 0;
    return `<div class="allocation-item ${amount < 1 ? "zero" : ""}"><span>${label}</span><strong>${money(amount)}</strong></div>`;
  }).join("");
}

function renderCurrentPlan() {
  const plan = simulatePlan(state.profile, state.planId, state.horizonYears);
  const recommended = recommendPlan(state.profile);
  renderMetrics();
  renderPlanSelector();
  document.querySelector("#recommendation-label").textContent = state.planId === recommended ? "Orion starting point" : `Starting point: ${PLAN_DEFINITIONS[recommended].shortName}`;
  document.querySelector("#projection-title").textContent = money(plan.endingNetWorth, true);
  document.querySelector("#projection-growth").textContent = `${signedMoney(plan.growth)} over ${state.horizonYears} years`;
  document.querySelector("#projection-assumption").textContent = `${(plan.annualReturn * 100).toFixed(1)}% annual market assumption`;
  document.querySelector("#projection-chart").innerHTML = chartMarkup(plan.timeline);
  document.querySelector("#chart-axis").innerHTML = `<span>Today</span><span>Year ${Math.round(state.horizonYears / 2)}</span><span>Year ${state.horizonYears}</span>`;
  document.querySelector("#summary-title").textContent = plan.name;
  document.querySelector("#plan-description").textContent = plan.description;
  document.querySelector("#milestone-reserve").textContent = monthLabel(plan.milestones.reserveReady);
  document.querySelector("#milestone-debt").textContent = monthLabel(plan.milestones.debtFree);
  document.querySelector("#milestone-100k").textContent = monthLabel(plan.milestones.first100k);
  document.querySelector("#milestone-rental-row").style.display = plan.id === "rental" ? "flex" : "none";
  document.querySelector("#milestone-rental").textContent = monthLabel(plan.milestones.rentalReady);
  renderAllocation(plan);
}

function renderComparison() {
  const plans = comparePlans(state.profile, state.horizonYears);
  document.querySelector("#comparison-head").innerHTML = `<tr><th>Measure</th>${plans.map((plan) => `<th class="${plan.id === state.planId ? "selected" : ""}">${plan.shortName}</th>`).join("")}</tr>`;
  const rows = [
    ["Projected net worth", (plan) => `<span class="primary-value">${money(plan.endingNetWorth, true)}</span>`],
    ["Monthly to investments", (plan) => money(plan.firstMonthAllocation.invest)],
    ["Monthly to debt", (plan) => money(plan.firstMonthAllocation.debt)],
    ["Emergency reserve", (plan) => monthLabel(plan.milestones.reserveReady)],
    ["Debt free", (plan) => monthLabel(plan.milestones.debtFree)],
    ["Rental fund ready", (plan) => plan.id === "rental" ? monthLabel(plan.milestones.rentalReady) : "Not targeted"],
    ["Return assumption", (plan) => `${(plan.annualReturn * 100).toFixed(1)}% annually`],
  ];
  document.querySelector("#comparison-body").innerHTML = rows.map(([label, value]) => `<tr><td>${label}</td>${plans.map((plan) => `<td>${value(plan)}</td>`).join("")}</tr>`).join("");
}

function renderPosition() {
  const profile = profileSummary(state.profile);
  const items = [
    ["Monthly income", money(profile.monthlyIncome)],
    ["Monthly spending", money(profile.monthlySpending)],
    ["Monthly free cash", money(profile.monthlySurplus)],
    ["Cash savings", money(profile.cash)],
    ["Investments", money(profile.investments)],
    ["Property equity", money(profile.propertyEquity)],
    ["Debt balance", money(profile.debt)],
    ["Debt APR", `${profile.debtApr.toFixed(1)}%`],
    ["Rental target", money(profile.rentalTarget)],
    ["Current age", profile.age],
    ["Target age", profile.targetAge],
    ["Risk posture", profile.risk[0].toUpperCase() + profile.risk.slice(1)],
  ];
  document.querySelector("#position-grid").innerHTML = items.map(([label, value]) => `<div class="position-item"><span>${label}</span><strong>${value}</strong></div>`).join("");
}

function switchView(view) {
  state.view = view;
  const titles = { life: "Your financial life", plan: "Your path forward", compare: "Strategy comparison", position: "Financial position" };
  document.querySelector("#page-title").textContent = titles[view];
  document.querySelectorAll("[data-view-panel]").forEach((panel) => panel.classList.toggle("active", panel.dataset.viewPanel === view));
  document.querySelectorAll("[data-view]").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  if (view === "life") renderLifeMap();
  if (view === "compare") renderComparison();
  if (view === "position") renderPosition();
}

function populateForm() {
  const form = document.querySelector("#profile-form");
  for (const [key, value] of Object.entries(state.profile)) {
    if (form.elements[key]) form.elements[key].value = value;
  }
}

function openProfile() {
  populateForm();
  document.querySelector("#profile-dialog").showModal();
}

document.addEventListener("click", (event) => {
  const removeButton = event.target.closest("[data-remove-id]");
  if (removeButton) {
    const key = removeButton.dataset.removeKind === "salary" ? "salaryEntries" : "events";
    state.lifeMap[key] = state.lifeMap[key].filter((item) => item.id !== removeButton.dataset.removeId);
    saveLifeMap();
    renderLifeMap();
    return;
  }
  const planButton = event.target.closest("[data-plan]");
  if (planButton) {
    state.planId = planButton.dataset.plan;
    renderCurrentPlan();
    if (state.view === "compare") renderComparison();
    return;
  }
  const viewButton = event.target.closest("[data-view]");
  if (viewButton) switchView(viewButton.dataset.view);
});

document.querySelector("#horizon-select").addEventListener("change", (event) => {
  state.horizonYears = Number(event.target.value);
  renderLifeMap();
  renderCurrentPlan();
  if (state.view === "compare") renderComparison();
});

document.querySelector("#edit-profile").addEventListener("click", openProfile);
document.querySelector("#edit-position").addEventListener("click", openProfile);
document.querySelector("#add-salary").addEventListener("click", () => {
  const form = document.querySelector("#salary-form");
  form.reset();
  form.elements.age.value = state.profile.age;
  form.elements.annualIncome.value = Math.round(salaryAtAge(state.profile, state.lifeMap, state.profile.age));
  form.elements.note.value = "Current income";
  document.querySelector("#salary-dialog").showModal();
});
document.querySelector("#add-event").addEventListener("click", () => {
  const form = document.querySelector("#event-form");
  form.reset();
  form.elements.amount.disabled = false;
  form.elements.amount.required = true;
  form.elements.age.value = Math.min(100, state.profile.age + 3);
  form.elements.certainty.value = "possible";
  document.querySelector("#event-dialog").showModal();
});
document.querySelector("#salary-growth").addEventListener("change", (event) => {
  state.lifeMap.salaryGrowthPct = Number(event.target.value);
  state.lifeMap = normalizeLifeMap(state.lifeMap, state.profile);
  saveLifeMap();
  renderLifeMap();
});
document.querySelector("#salary-form").addEventListener("submit", (event) => {
  if (event.submitter?.value !== "save") return;
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget));
  const entry = {
    id: "salary-" + Date.now(),
    age: Number(data.age),
    annualIncome: Number(data.annualIncome),
    note: data.note || "Salary override",
  };
  state.lifeMap.salaryEntries = state.lifeMap.salaryEntries.filter((item) => item.age !== entry.age);
  state.lifeMap.salaryEntries.push(entry);
  state.lifeMap = normalizeLifeMap(state.lifeMap, state.profile);
  saveLifeMap();
  document.querySelector("#salary-dialog").close();
  renderLifeMap();
});
document.querySelector("#event-form").addEventListener("submit", (event) => {
  if (event.submitter?.value !== "save") return;
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget));
  state.lifeMap.events.push({
    id: "event-" + Date.now(),
    age: Number(data.age),
    type: data.type,
    label: data.label || LIFE_EVENT_TYPES[data.type].name,
    amount: Number(data.amount || 0),
    certainty: data.certainty,
  });
  state.lifeMap = normalizeLifeMap(state.lifeMap, state.profile);
  saveLifeMap();
  document.querySelector("#event-dialog").close();
  renderLifeMap();
});
document.querySelector("#event-form").elements.type.addEventListener("change", (event) => {
  const amount = document.querySelector("#event-form").elements.amount;
  const isRetirement = event.target.value === "retirement";
  amount.disabled = isRetirement;
  amount.required = !isRetirement;
  if (isRetirement) amount.value = 0;
});
document.querySelector("#profile-form").addEventListener("submit", (event) => {
  if (event.submitter?.value !== "save") return;
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget));
  state.profile = normalizeProfile(data);
  state.lifeMap.salaryEntries = state.lifeMap.salaryEntries.filter((entry) => entry.age !== state.profile.age);
  state.lifeMap.salaryEntries.push({
    id: "salary-" + state.profile.age,
    age: state.profile.age,
    annualIncome: state.profile.monthlyIncome * 12,
    note: "Current income",
  });
  state.lifeMap = normalizeLifeMap(state.lifeMap, state.profile);
  state.planId = recommendPlan(state.profile);
  saveProfile();
  saveLifeMap();
  document.querySelector("#profile-dialog").close();
  renderLifeMap();
  renderCurrentPlan();
  renderComparison();
  renderPosition();
});

renderLifeMap();
renderCurrentPlan();
renderComparison();
renderPosition();
