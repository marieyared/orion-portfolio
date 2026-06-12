# Orion — The One Test (capture validation)

> Goal: in ~3 weeks and with ~6 people, find out whether the bet under Orion is alive or
> dead — *before* writing another feature. Pre-register the bars below and hold yourself to
> them like a sell rule: decide while calm, not after you see results you like.

## The bet being tested (just one)

Everything Orion is worth rests on a single behavior:

> **A real DIY investor will record their honest reasoning — the why and the fear — repeatedly
> and unprompted, and the record will produce a moment worth coming back for.**

If that happens, the moat compounds and the rest is execution. If it doesn't, no amount of
better code, data, or coverage saves it. So we test *that*, nothing else. We are **not**
testing whether people like the dossiers, the UI, or the idea in the abstract. Only the
behavior counts.

Break it into three sub-questions, each with a hard bar set *before* we run:

| # | Question | Pass bar |
|---|----------|----------|
| **H1 — Does capture happen?** | After a 5-min intro, will they log theses on their real holdings without being walked through each one? | ≥4 of 6 users capture **≥3 theses** (each with a sell rule + the psychology fields) in week 1, unprompted after the first one. |
| **H2 — Is the capture honest?** | Is the "why / fear" real reasoning, or filler typed to clear the form? | For ≥4 of 6, the captured fear/why is something they **recognize and stand by** in the exit interview — not "what was easy to type." |
| **H3 — Does the mirror land?** | When an alert quotes their own past words back, does it create an "oh" — recognition, a decision, or a wish to keep it? | ≥half of users have a **genuine reaction** to a fired alert: they re-examine the name, amend the thesis, or say unprompted they'd want this running. |

## Who (and who NOT)

**6 people**, recruited to the actual tribe:
- They pick their **own** individual US stocks (not just index funds, not advisor-managed).
- They lean quality/long-term — they'd recognize "compounder" as a word they'd use.
- They have **≥5 real holdings** they can talk about from memory.

**Hard rule: no friends, no family, no one who wants you to succeed.** They flatter, and
flattery is the one thing that makes this test worthless. Find them in DIY-investing
subreddits, a Bogleheads/quality-investing Discord, an investing club, or 2nd-degree intros
where the person has no stake in your feelings.

## The setup (what to build first — keep it tiny)

Do **not** rebuild the product before testing. Two small prep tasks only:

1. **Knock the worst friction off capture** (≤1 day). Pre-fill suggested pillars from the
   scorecard so the user *confirms* rather than authors; keep conviction one-tap; keep the
   fear field but make text optional *on top of* a required chip-select. Goal: capturing one
   thesis takes <60s. Anything bigger is a different project — resist it.
2. **Seed one guaranteed alert per user** (≤1 day). The watch runs on *annual* filings, which
   won't move during a 3-week test — so a real alert may never fire on its own. For each
   user, make sure **at least one of their holdings** already breaches or drifts a plausible
   sell rule against the latest committed dossier (pick names, or pre-load a demo holding,
   where the most recent FY number is genuinely below a sensible line). Without this, H3 is
   untestable in the window.

You also need to **see their data**, which localStorage hides. Cheapest path: moderated
screen-share sessions + a one-click "copy my thesis JSON" button you read after. Don't build
accounts/telemetry for this — observe directly.

## The method

**Week 0 — prep & recruit.** Build the two prep tasks. Recruit 6. Write down your *predicted*
result for each bar **now**, before any session (pre-registration — same discipline Orion
preaches: commit the line while calm).

**Week 1 — kickoff session (30 min each, moderated, screen-share).**
- 5-min intro: what Orion is, one sentence. Then hand them the keyboard.
- Ask them to add 3–5 of their real holdings and write the thesis for each.
- **Do not coach. Do not explain the fields. Stay silent and watch.** Where they hesitate,
  what they skip, what they type in the fear box, how long it takes — that's the whole point.
  Note every abandon and every "do I have to fill this in?"
- End: let them hit the seeded alert if it surfaces; watch their face, don't narrate it.

**Week 1→2 — leave them alone.** Tell them to use it (or not) as they like. The test of a
return visit is whether one happens without you prompting it. A nudge here invalidates H1.

**Week 2/3 — exit interview (30 min each).** The make-or-break conversation:
- "Show me a thesis you wrote." Then the killer question: **"Is this fear what you actually
  felt, or what was easy to type?"** Their answer is the H2 verdict in one sentence.
- Show them their seeded alert (or re-show it): "What did you think when you saw this?"
  Listen for recognition vs. shrug. Did it change anything? Would they want it on all names?
- "Did you open it again on your own this week? Why / why not?"
- Last: "Would you pay for this, and what would it have to do first?" (signal, not gospel.)

## The decision rule (pre-committed — pick the branch the data points to)

- **GREEN — keep going, this is a company.** H1 and H3 both clear, and H2 is mostly real.
  People capture honestly, unprompted, and the mirror moment matters to them. → Now you're
  allowed to invest in reducing capture friction further and moving the store off localStorage.
- **YELLOW — the bet's alive, the form is in the way.** H3 clears (they *love* the alert when
  it fires) but H1 fails (capture friction or skipped psychology blocks them). The problem is
  the *form*, not the *idea*. → Rebuild capture to near-zero friction and **rerun this exact
  test once.** One retry, not three.
- **RED — switch.** Either they won't write honest psychology even when it's effortless (H2
  fails), **or** they capture fine but shrug at the alert (H3 fails). The core behavior isn't
  there. → The moat can't form. Kill or pivot — and you'll do it knowing exactly why, which is
  worth far more than killing it on theory today.

## What would make this test lie to you (guard against it)

- **Friendly recruits** → false GREEN. Strangers only.
- **Coaching during capture** → false H1. Sit on your hands.
- **Leading the interview** ("Pretty useful, right?") → false H2/H3. Ask open, then shut up.
- **Counting enthusiasm as a pass.** "This is cool" is not capture and not a return visit.
  Only logged theses and unprompted re-opens count.
- **Skipping the seed** → H3 never gets tested, and you'll wrongly read "no reaction" as a fail
  when really no alert ever fired.

## Cost & timeline

~3 weeks wall-clock, ~2 days of build, ~6 hours of sessions. Cheaper than one more feature —
and it answers the only question that decides whether to keep building or switch.
