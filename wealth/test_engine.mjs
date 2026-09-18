import assert from "node:assert/strict";
import {
  DEFAULT_PROFILE,
  comparePlans,
  defaultLifeMap,
  normalizeProfile,
  profileSummary,
  projectLifeMap,
  recommendPlan,
  salaryAtAge,
  simulatePlan,
} from "./engine.mjs";

const normalized = normalizeProfile({ monthlyIncome: "5000", debt: "-10", age: 40, targetAge: 30 });
assert.equal(normalized.monthlyIncome, 5000);
assert.equal(normalized.debt, 0);
assert.equal(normalized.targetAge, 41);

const summary = profileSummary(DEFAULT_PROFILE);
assert.equal(summary.monthlySurplus, 2300);
assert.equal(summary.netWorth, 44000);

const plans = comparePlans(DEFAULT_PROFILE, 10);
assert.equal(plans.length, 4);
assert.ok(plans.every((plan) => plan.timeline.length === 11));
assert.ok(plans.every((plan) => plan.endingNetWorth > summary.netWorth));

const safety = simulatePlan(DEFAULT_PROFILE, "safety", 10);
assert.ok(safety.firstMonthAllocation.debt >= safety.firstMonthAllocation.invest);
assert.ok(safety.milestones.debtFree !== null);

const rental = simulatePlan(DEFAULT_PROFILE, "rental", 10);
assert.ok(rental.firstMonthAllocation.rental > 0);
assert.ok(rental.milestones.rentalReady !== null);

assert.equal(recommendPlan(DEFAULT_PROFILE), "safety");
assert.equal(recommendPlan({ ...DEFAULT_PROFILE, debt: 0, cash: 20000 }), "balanced");

const deficit = simulatePlan({ ...DEFAULT_PROFILE, monthlyIncome: 2000 }, "balanced", 10);
assert.equal(deficit.monthlySurplus, 0);
assert.equal(deficit.firstMonthAllocation.invest, 0);

const lifeMap = defaultLifeMap(DEFAULT_PROFILE);
lifeMap.salaryGrowthPct = 0;
lifeMap.salaryEntries = lifeMap.salaryEntries.filter((entry) => entry.age === DEFAULT_PROFILE.age);
lifeMap.events = [];
lifeMap.salaryEntries.push({
  id: "promotion",
  age: DEFAULT_PROFILE.age + 2,
  annualIncome: 90000,
  note: "Promotion",
});
lifeMap.events.push(
  { id: "inheritance", age: DEFAULT_PROFILE.age + 1, type: "inheritance", label: "Inheritance", amount: 100000, certainty: "likely" },
  { id: "purchase", age: DEFAULT_PROFILE.age + 3, type: "major_purchase", label: "Major purchase", amount: 20000, certainty: "confirmed" },
  { id: "retirement", age: DEFAULT_PROFILE.age + 5, type: "retirement", label: "Retirement", amount: 0, certainty: "possible" },
);

assert.equal(salaryAtAge(DEFAULT_PROFILE, lifeMap, DEFAULT_PROFILE.age + 1), DEFAULT_PROFILE.monthlyIncome * 12);
assert.equal(salaryAtAge(DEFAULT_PROFILE, lifeMap, DEFAULT_PROFILE.age + 2), 90000);
assert.equal(salaryAtAge(DEFAULT_PROFILE, lifeMap, DEFAULT_PROFILE.age + 5), 0);

const lifeProjection = projectLifeMap(DEFAULT_PROFILE, lifeMap, DEFAULT_PROFILE.age + 10);
assert.equal(lifeProjection.rows.length, 11);
assert.equal(lifeProjection.eventAssessments.length, 3);
assert.ok(lifeProjection.endingNetWorth > lifeProjection.startingNetWorth);

console.log("Orion Wealth engine: 22 assertions passed");
