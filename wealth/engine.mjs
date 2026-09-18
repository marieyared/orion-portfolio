const MONTHS_PER_YEAR = 12;

export const PLAN_DEFINITIONS = {
  safety: {
    id: "safety",
    name: "Stabilize first",
    shortName: "Stabilize",
    annualReturn: 0.05,
    emergencyMonths: 6,
    allocation: { debt: 0.5, reserve: 0.3, invest: 0.2, rental: 0 },
    description: "Build a full cash buffer and remove expensive debt before leaning into growth.",
  },
  balanced: {
    id: "balanced",
    name: "Balanced builder",
    shortName: "Balanced",
    annualReturn: 0.065,
    emergencyMonths: 4,
    allocation: { debt: 0.25, reserve: 0.2, invest: 0.55, rental: 0 },
    description: "Grow investments while strengthening liquidity and steadily reducing debt.",
  },
  growth: {
    id: "growth",
    name: "Growth focused",
    shortName: "Growth",
    annualReturn: 0.08,
    emergencyMonths: 3,
    allocation: { debt: 0.1, reserve: 0.1, invest: 0.8, rental: 0 },
    description: "Direct most available cash toward long-term markets and accept wider outcomes.",
  },
  rental: {
    id: "rental",
    name: "Rental runway",
    shortName: "Rental",
    annualReturn: 0.06,
    emergencyMonths: 4,
    allocation: { debt: 0.2, reserve: 0.15, invest: 0.15, rental: 0.5 },
    description: "Build a dedicated property fund without stopping retirement investing entirely.",
  },
};

export const DEFAULT_PROFILE = {
  currency: "USD",
  age: 31,
  targetAge: 50,
  monthlyIncome: 5500,
  essentialExpenses: 2300,
  flexibleExpenses: 900,
  cash: 18000,
  debt: 6000,
  debtApr: 8.5,
  investments: 32000,
  propertyEquity: 0,
  rentalTarget: 65000,
  risk: "balanced",
};

export const LIFE_EVENT_TYPES = {
  inheritance: { name: "Inheritance", direction: "inflow" },
  windfall: { name: "Bonus or business gain", direction: "inflow" },
  major_purchase: { name: "Major purchase", direction: "outflow" },
  property_purchase: { name: "Property contribution", direction: "transfer" },
  retirement: { name: "Retirement", direction: "income_stop" },
};

export function defaultLifeMap(input = DEFAULT_PROFILE) {
  const profile = normalizeProfile(input);
  const promotionAge = Math.min(99, profile.age + 3);
  const propertyAge = Math.min(99, profile.age + 5);
  const inheritanceAge = Math.min(99, profile.age + 10);
  const retirementAge = Math.max(profile.age + 1, profile.targetAge);
  return {
    salaryGrowthPct: 2.5,
    salaryEntries: [
      {
        id: "salary-" + profile.age,
        age: profile.age,
        annualIncome: profile.monthlyIncome * MONTHS_PER_YEAR,
        note: "Current income",
      },
      {
        id: "salary-example-promotion",
        age: promotionAge,
        annualIncome: profile.monthlyIncome * MONTHS_PER_YEAR * 1.15,
        note: "Example promotion",
      },
    ],
    events: [
      {
        id: "event-example-property",
        age: propertyAge,
        type: "property_purchase",
        label: "Example property contribution",
        amount: profile.rentalTarget,
        certainty: "possible",
      },
      {
        id: "event-example-inheritance",
        age: inheritanceAge,
        type: "inheritance",
        label: "Example inheritance",
        amount: 100000,
        certainty: "possible",
      },
      {
        id: "event-example-retirement",
        age: retirementAge,
        type: "retirement",
        label: "Planned retirement",
        amount: 0,
        certainty: "possible",
      },
    ],
  };
}

export function normalizeLifeMap(input = {}, profileInput = DEFAULT_PROFILE) {
  const profile = normalizeProfile(profileInput);
  const fallback = defaultLifeMap(profile);
  const salaryEntries = Array.isArray(input.salaryEntries) ? input.salaryEntries : fallback.salaryEntries;
  const events = Array.isArray(input.events) ? input.events : [];
  return {
    salaryGrowthPct: Math.max(-20, Math.min(30, number(input.salaryGrowthPct, fallback.salaryGrowthPct))),
    salaryEntries: salaryEntries.map((entry, index) => ({
      id: String(entry.id || ("salary-" + index + "-" + entry.age)),
      age: Math.max(18, Math.round(number(entry.age, profile.age))),
      annualIncome: Math.max(0, number(entry.annualIncome)),
      note: String(entry.note || "Salary override").slice(0, 80),
    })).sort((a, b) => a.age - b.age),
    events: events.map((event, index) => ({
      id: String(event.id || ("event-" + index + "-" + event.age)),
      age: Math.max(profile.age, Math.round(number(event.age, profile.age))),
      type: LIFE_EVENT_TYPES[event.type] ? event.type : "major_purchase",
      label: String(event.label || LIFE_EVENT_TYPES[event.type]?.name || "Life event").slice(0, 80),
      amount: Math.max(0, number(event.amount)),
      certainty: ["confirmed", "likely", "possible"].includes(event.certainty) ? event.certainty : "possible",
    })).sort((a, b) => a.age - b.age),
  };
}

function number(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function normalizeProfile(input = {}) {
  const merged = { ...DEFAULT_PROFILE, ...input };
  const targetAge = Math.max(number(merged.age, 31) + 1, number(merged.targetAge, 50));
  return {
    currency: ["USD", "EUR", "GBP", "CHF"].includes(merged.currency) ? merged.currency : "USD",
    age: Math.max(18, number(merged.age, 31)),
    targetAge,
    monthlyIncome: Math.max(0, number(merged.monthlyIncome)),
    essentialExpenses: Math.max(0, number(merged.essentialExpenses)),
    flexibleExpenses: Math.max(0, number(merged.flexibleExpenses)),
    cash: Math.max(0, number(merged.cash)),
    debt: Math.max(0, number(merged.debt)),
    debtApr: Math.max(0, number(merged.debtApr)),
    investments: Math.max(0, number(merged.investments)),
    propertyEquity: Math.max(0, number(merged.propertyEquity)),
    rentalTarget: Math.max(0, number(merged.rentalTarget)),
    risk: ["conservative", "balanced", "growth"].includes(merged.risk) ? merged.risk : "balanced",
  };
}

export function profileSummary(input) {
  const profile = normalizeProfile(input);
  const monthlySpending = profile.essentialExpenses + profile.flexibleExpenses;
  const monthlySurplus = profile.monthlyIncome - monthlySpending;
  const netWorth = profile.cash + profile.investments + profile.propertyEquity - profile.debt;
  const emergencyMonths = profile.essentialExpenses > 0 ? profile.cash / profile.essentialExpenses : 0;
  return { ...profile, monthlySpending, monthlySurplus, netWorth, emergencyMonths };
}

function monthlyRate(annualRate) {
  return Math.pow(1 + annualRate, 1 / MONTHS_PER_YEAR) - 1;
}

function allocateSurplus({ available, balances, definition, targets }) {
  const allocation = { debt: 0, reserve: 0, invest: 0, rental: 0 };
  if (available <= 0) return allocation;

  const open = {
    debt: balances.debt > 0.01,
    reserve: balances.cash + 0.01 < targets.reserve,
    invest: true,
    rental: definition.id === "rental" && balances.rentalFund + 0.01 < targets.rental,
  };

  const shares = { ...definition.allocation };
  let redirected = 0;
  for (const key of ["debt", "reserve", "rental"]) {
    if (!open[key]) {
      redirected += shares[key];
      shares[key] = 0;
    }
  }
  shares.invest += redirected;

  const shareTotal = Object.values(shares).reduce((sum, value) => sum + value, 0) || 1;
  for (const key of Object.keys(shares)) allocation[key] = available * (shares[key] / shareTotal);

  allocation.debt = Math.min(allocation.debt, balances.debt);
  allocation.reserve = Math.min(allocation.reserve, Math.max(0, targets.reserve - balances.cash));
  allocation.rental = Math.min(allocation.rental, Math.max(0, targets.rental - balances.rentalFund));

  const used = allocation.debt + allocation.reserve + allocation.invest + allocation.rental;
  allocation.invest += Math.max(0, available - used);
  return allocation;
}

export function simulatePlan(input, planId, horizonYears = 10) {
  const profile = normalizeProfile(input);
  const definition = PLAN_DEFINITIONS[planId] || PLAN_DEFINITIONS.balanced;
  const months = Math.max(12, Math.round(number(horizonYears, 10) * MONTHS_PER_YEAR));
  const surplus = Math.max(0, profile.monthlyIncome - profile.essentialExpenses - profile.flexibleExpenses);
  const targets = {
    reserve: profile.essentialExpenses * definition.emergencyMonths,
    rental: definition.id === "rental" ? profile.rentalTarget : 0,
  };
  const balances = {
    cash: profile.cash,
    debt: profile.debt,
    investments: profile.investments,
    propertyEquity: profile.propertyEquity,
    rentalFund: 0,
  };
  const rates = {
    cash: monthlyRate(0.025),
    debt: profile.debtApr / 100 / MONTHS_PER_YEAR,
    investments: monthlyRate(definition.annualReturn),
    property: monthlyRate(0.025),
    rentalFund: monthlyRate(0.03),
  };
  const milestones = { debtFree: null, reserveReady: null, rentalReady: null, first100k: null };
  const timeline = [];
  let firstMonthAllocation = null;

  for (let month = 0; month <= months; month += 1) {
    const netWorth = balances.cash + balances.investments + balances.propertyEquity + balances.rentalFund - balances.debt;
    if (month % 12 === 0 || month === months) {
      timeline.push({
        month,
        netWorth,
        cash: balances.cash,
        investments: balances.investments,
        propertyEquity: balances.propertyEquity,
        rentalFund: balances.rentalFund,
        debt: balances.debt,
      });
    }
    if (milestones.debtFree === null && balances.debt <= 0.01) milestones.debtFree = month;
    if (milestones.reserveReady === null && balances.cash + 0.01 >= targets.reserve) milestones.reserveReady = month;
    if (definition.id === "rental" && milestones.rentalReady === null && balances.rentalFund + 0.01 >= targets.rental) milestones.rentalReady = month;
    if (milestones.first100k === null && netWorth >= 100000) milestones.first100k = month;
    if (month === months) break;

    balances.cash *= 1 + rates.cash;
    balances.debt *= 1 + rates.debt;
    balances.investments *= 1 + rates.investments;
    balances.propertyEquity *= 1 + rates.property;
    balances.rentalFund *= 1 + rates.rentalFund;

    const allocation = allocateSurplus({ available: surplus, balances, definition, targets });
    if (!firstMonthAllocation) firstMonthAllocation = { ...allocation };
    balances.debt = Math.max(0, balances.debt - allocation.debt);
    balances.cash += allocation.reserve;
    balances.investments += allocation.invest;
    balances.rentalFund += allocation.rental;
  }

  const ending = timeline[timeline.length - 1];
  return {
    id: definition.id,
    name: definition.name,
    shortName: definition.shortName,
    description: definition.description,
    annualReturn: definition.annualReturn,
    emergencyMonths: definition.emergencyMonths,
    horizonYears: months / MONTHS_PER_YEAR,
    monthlySurplus: surplus,
    targetReserve: targets.reserve,
    rentalTarget: targets.rental,
    endingNetWorth: ending.netWorth,
    growth: ending.netWorth - profileSummary(profile).netWorth,
    firstMonthAllocation: firstMonthAllocation || { debt: 0, reserve: 0, invest: 0, rental: 0 },
    milestones,
    timeline,
    ending,
  };
}

export function comparePlans(input, horizonYears = 10) {
  return Object.keys(PLAN_DEFINITIONS).map((id) => simulatePlan(input, id, horizonYears));
}

export function salaryAtAge(profileInput, lifeMapInput, age) {
  const profile = normalizeProfile(profileInput);
  const lifeMap = normalizeLifeMap(lifeMapInput, profile);
  const retirementAge = lifeMap.events
    .filter((event) => event.type === "retirement")
    .reduce((earliest, event) => Math.min(earliest, event.age), Infinity);
  if (age >= retirementAge) return 0;

  const applicable = lifeMap.salaryEntries.filter((entry) => entry.age <= age);
  const anchor = applicable[applicable.length - 1] || {
    age: profile.age,
    annualIncome: profile.monthlyIncome * MONTHS_PER_YEAR,
  };
  const yearsSinceAnchor = Math.max(0, age - anchor.age);
  return anchor.annualIncome * Math.pow(1 + lifeMap.salaryGrowthPct / 100, yearsSinceAnchor);
}

function drawFromLiquidAssets(balances, amount) {
  let remaining = Math.max(0, amount);
  const fromCash = Math.min(balances.cash, remaining);
  balances.cash -= fromCash;
  remaining -= fromCash;
  const fromInvestments = Math.min(balances.investments, remaining);
  balances.investments -= fromInvestments;
  remaining -= fromInvestments;
  return { fromCash, fromInvestments, shortfall: remaining };
}

export function projectLifeMap(profileInput, lifeMapInput, endAgeInput) {
  const profile = normalizeProfile(profileInput);
  const lifeMap = normalizeLifeMap(lifeMapInput, profile);
  const endAge = Math.max(profile.age + 1, Math.round(number(endAgeInput, profile.targetAge)));
  const investmentReturn = profile.risk === "conservative" ? 0.045 : profile.risk === "growth" ? 0.075 : 0.06;
  const expenseInflation = 0.025;
  const reserveMonths = 4;
  const balances = {
    cash: profile.cash,
    debt: profile.debt,
    investments: profile.investments,
    propertyEquity: profile.propertyEquity,
  };
  const rows = [];
  const eventAssessments = [];
  const startingNetWorth = balances.cash + balances.investments + balances.propertyEquity - balances.debt;

  for (let age = profile.age; age <= endAge; age += 1) {
    const yearsFromNow = age - profile.age;
    const annualSalary = salaryAtAge(profile, lifeMap, age);
    const annualExpenses = (profile.essentialExpenses + profile.flexibleExpenses)
      * MONTHS_PER_YEAR
      * Math.pow(1 + expenseInflation, yearsFromNow);
    const reserveTarget = profile.essentialExpenses
      * reserveMonths
      * Math.pow(1 + expenseInflation, yearsFromNow);
    const events = lifeMap.events.filter((event) => event.age === age);

    if (age > profile.age) {
      balances.cash *= 1.02;
      balances.investments *= 1 + investmentReturn;
      balances.propertyEquity *= 1.025;
      balances.debt *= 1 + profile.debtApr / 100;
    }

    const liquidBeforeEvents = balances.cash + balances.investments;
    for (const event of events) {
      const definition = LIFE_EVENT_TYPES[event.type];
      if (definition.direction === "inflow") {
        balances.cash += event.amount;
        eventAssessments.push({ ...event, status: "received", gap: 0, reserveTarget });
      } else if (definition.direction === "outflow" || definition.direction === "transfer") {
        const liquidBefore = balances.cash + balances.investments;
        const requiredWithReserve = event.amount + reserveTarget;
        const status = liquidBefore >= requiredWithReserve
          ? "comfortable"
          : liquidBefore >= event.amount
            ? "tight"
            : "unfunded";
        const draw = drawFromLiquidAssets(balances, event.amount);
        if (draw.shortfall > 0) balances.debt += draw.shortfall;
        if (definition.direction === "transfer") balances.propertyEquity += event.amount;
        eventAssessments.push({
          ...event,
          status,
          gap: Math.max(0, requiredWithReserve - liquidBefore),
          reserveTarget,
          liquidBefore,
        });
      } else {
        eventAssessments.push({ ...event, status: "scheduled", gap: 0, reserveTarget });
      }
    }

    let annualSurplus = age === profile.age ? 0 : annualSalary - annualExpenses;
    if (annualSurplus >= 0) {
      const debtShare = profile.debtApr >= 7 ? 0.45 : 0.2;
      const debtPayment = Math.min(balances.debt, annualSurplus * debtShare);
      balances.debt -= debtPayment;
      let available = annualSurplus - debtPayment;
      const reserveGap = Math.max(0, reserveTarget - balances.cash);
      const reserveContribution = Math.min(reserveGap, available * 0.35);
      balances.cash += reserveContribution;
      available -= reserveContribution;
      balances.investments += available;
    } else {
      const draw = drawFromLiquidAssets(balances, Math.abs(annualSurplus));
      if (draw.shortfall > 0) balances.debt += draw.shortfall;
    }

    const netWorth = balances.cash + balances.investments + balances.propertyEquity - balances.debt;
    rows.push({
      age,
      yearOffset: yearsFromNow,
      phase: age === profile.age ? "current" : "projected",
      annualSalary,
      annualExpenses,
      annualSurplus,
      reserveTarget,
      liquidBeforeEvents,
      events,
      cash: balances.cash,
      debt: balances.debt,
      investments: balances.investments,
      propertyEquity: balances.propertyEquity,
      liquidAssets: balances.cash + balances.investments,
      netWorth,
    });
  }

  return {
    currentAge: profile.age,
    endAge,
    startingNetWorth,
    endingNetWorth: rows[rows.length - 1].netWorth,
    investmentReturn,
    expenseInflation,
    reserveMonths,
    rows,
    eventAssessments,
    salaryHistory: lifeMap.salaryEntries.filter((entry) => entry.age < profile.age),
  };
}

export function recommendPlan(input) {
  const summary = profileSummary(input);
  if (summary.monthlySurplus <= 0) return "safety";
  if (summary.debt > 0 && summary.debtApr >= 7) return "safety";
  if (summary.emergencyMonths < 2) return "safety";
  return "balanced";
}

export function monthLabel(month) {
  if (month === null || month === undefined) return "Beyond projection";
  if (month === 0) return "Ready now";
  if (month < 12) return `${month} month${month === 1 ? "" : "s"}`;
  const years = Math.floor(month / 12);
  const remainder = month % 12;
  return remainder ? `${years}y ${remainder}m` : `${years} year${years === 1 ? "" : "s"}`;
}
