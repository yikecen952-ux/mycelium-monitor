# SYMBIO-FRAME — Project Structure & Deliverables
### Mycelium Material Research Project · RC7 · Bartlett / UCL
*Working document — synthesised from planning discussion. Last updated for near-final interim (target 28 June).*

---

## PART 1 — CORE ARGUMENT (核心论点)

### The one-sentence thesis
> Through experiment I show that mycelium material can be **actively maintained (tended)** — its health can be sensed, read, and predicted — and on that evidence I project a future in which people inhabit living mycelium architecture that is kept healthy through ongoing **tending**.

### The two halves and how they connect
- **A — Evidence / Method (现在时, proven):** the experiments, sensing data, scanning models, and the detection system. *This is the foundation.*
- **B — Argument / Vision (未来时, projected):** a future of inhabited, tended, living mycelium architecture. *This is the building on the foundation.*
- **tending = the connecting verb.** It is simultaneously a concrete lab operation (regeneration, co-cultivation, humidity control, monitoring) **and** a way of relating to a living building. tending is what makes A and B one continuous idea rather than two parallel claims.

**Key principle:** A is the ground, B is the building, tending is the hinge. B is not fantasy — it is a *grounded projection* built on A's evidence.

---

## PART 2 — THE FIVE-STEP LOGIC CHAIN (汇报主线)

A single, non-skippable causal chain. Each step depends on the previous one. **This is the spine of the oral presentation.**

```
1. SENSE   感知   I can collect mycelium state data
                  (multi-point sensing + photos + scanning)
                       ↓ because I can sense, therefore…
2. READ    读懂   I can turn data into legible health states
                  (detection website + health score)
                       ↓ because I can read, therefore…
3. PREDICT 预测   I can predict how mycelium will trend under
                  environmental change (weather-linked forecast + alerts)
                       ↓ only because I can predict, can I…
4. TEND    照料   Based on prediction, decide WHEN, WHERE and HOW
                  to intervene
                  ├─ Strategy (projected): when/where/how to act
                  └─ Validation (proven): regeneration experiment =
                     one real tending intervention
                       ↓ if this runs continuously, it points to…
5. INHABIT 共居   People live in a continuously-tended living
                  mycelium building (future vision)
```

**Mapping to A/B:**
- Steps 1–3 = **A** (really achieved, has data + system)
- Step 4 = **the hinge** (regeneration experiment is proven; full tending strategy is projected)
- Step 5 = **B** (future vision)

**Why this prevents confusion:** it is one causal chain, not two parallel things. By the time the audience reaches the Step 5 narrative, they have already walked through the Steps 1–4 evidence, so they accept the vision as grounded projection, not invention.

---

## PART 3 — THE TWO EXPERIMENTS AS AN EVOLUTION (两批实验 = 方法进化)

The two data sets are **not parallel** — they are **two stages of one evolving research method.**

```
BATCH 1 (Exploratory / Establishing)
  Method: coarse — ~2 faces per cube, whole-surface sensing, long time-series
  Purpose: establish how mycelium changes over time; rough environment↔health relationship
  Output: WHEN — a rough temporal rule → supports PREDICT (Step 3)
          │
          │ Realised limitation: "whole-surface health" is too coarse;
          │ real mycelium surfaces are non-uniform
          ↓ evolved into…
BATCH 2 (Refining / Deepening)
  Method: fine — 5 faces × 9 points grid, spatial sensing, 2-day window
  Purpose: not "how the whole changes" but "how different locations differ"
  Output: WHERE — spatial health distribution map → supports TEND (Step 4)
          + map-over-time demo (2 days) → makes resident view feel "alive"
```

**This evolution maps directly onto tending:**
- Batch 1 → proves tending is **necessary** (mycelium does decay)
- Batch 2 → proves tending is **executable** (because health can be located precisely, care becomes a concrete action: "water the 3rd zone of the west wall today" instead of vague "check on it")

**Honesty note for presentation:** Batch 1 and Batch 2 are **different cubes**. Frame Batch 2 as *"a newly designed, more refined experiment built on Batch 1's insight"* — an evolution of experimental design — NOT as "finer measurement of the same samples."

---

## PART 4 — DATA INVENTORY & ROLES (数据分工)

| Data | Batch | Answers | Primary role | On website? |
|------|-------|---------|-------------|-------------|
| Time-series photos (~2 faces/cube) | 1 | WHEN | Find prediction rule (dependent variable, scored by detection net) | **Partially** — as timeline of decay |
| Surface sensing (matching those faces) | 1 | WHEN | Find prediction rule (independent variable) | Mostly backstage; can annotate timeline |
| Time-series scanning (every 5 days) | 1 | WHEN | Physical-change evidence (shrinkage/deformation) | **Yes** — CloudCompare volume/deformation-over-time |
| 45-point sensing (5 faces × 9 pts) | 2 | WHERE | Drive spatial colour-mapping | Backstage data (raw numbers not shown) |
| 45-point × 2 days | 2 | WHERE + a little change | Animate the health map over time | **Yes** — dynamic "map evolving" demo |
| Scanning + Houdini mapping result | 2 | WHERE | **The spatial health map** | **CORE display** — resident view "house health map" |

**Summary:**
- **Batch 1** works mostly *backstage* to build the prediction rule, but its **photo timeline** and **scanning changes** are shown as visual proof that "mycelium really decays."
- **Batch 2** is mostly *front-stage*: its mapping result is the core visual of the resident view — the spatial health map.

**Caveat already known:** the first two old cubes were scanned **without a wood base plate**, so their 3D models can't be precisely aligned. Impact is **local** — it only affects Batch-1 scanning *deformation-over-time* comparison in CloudCompare. It does **not** affect photo timelines, surface sensing, or Batch-2 spatial mapping. The third cube (with base plate) can still carry the deformation comparison. Main logic chain is unaffected.

---

## PART 5 — WEBSITE: ONE SYSTEM, TWO VIEWS (网站双视图规划)

**Decision made:** NOT two separate websites. **One system, two ways of telling**, sharing the same real data. (Option B.)

### Why one system, not two
- Two separate sites = double the work, audience confusion ("why two?"), and it contradicts the core argument that monitoring and tending are *continuous*.

### The relationship: same function core, two layers of language
The functional core stays identical:
`upload image → detect state → score → predict trend → recommend action`
Only the outer language/framing changes.

| Same function | Scientific language (now) | Resident language (future narrative) |
|---|---|---|
| Health score 82 | "Health 82/100, state: dry_aging" | "Your west wall is a bit dry — time to add water" |
| Weather forecast | "3-day forecast: score → 68" | "Cold this weekend, mycelium may be unhappy — keep an eye on it" |
| Maintenance advice | "Recommend humidity intervention" | "Today's care task: mist the living-room wall" |

Same number, same prediction, different skin.

### The Scientific View ↔ Resident View correspondence (the strongest single idea)
```
Scientific View (now / real)         Resident View (future / designed)
──────────────────────────          ──────────────────────────
real cube                            designed mycelium building
  ↓ same method                        ↓ same method
real scanning                        simulated scanning
real multi-point sensing             projected sensor network
real humidity mapping                building-surface health map
  ↓                                    ↓
"which part of this cube             "which wall of this house
 needs care"                          needs care"
```
The cube is the **scaled experiment** for the building. Real cube gives the simulated building its **methodological credibility**. When asked "is the building map real or invented?" → *"Building-scale is simulated because the building doesn't exist yet, but the method behind it is validated on a real cube."*

### Resident View — three layers (build as time allows)
1. **Language-translation layer (must-do, lowest cost):** same data, resident's voice. Backend fully reused.
2. **Spatialisation layer (the killer feature):** connect scanning + humidity mapping → a 3D health map of "the house." Click a wall → see its state + care advice. *This is where all your material converges.*
3. **Time/narrative layer (nice-to-have):** care log — past tending (regeneration experiment), health curve over time, upcoming care tasks. Turns tending from one action into an ongoing relationship → echoes INHABIT.

**Visual-consistency requirement:** both views must share the same colour logic (healthy=green/white, dry=yellow, contamination/decay=brown-red), same interaction (click region → state + advice), same map style. Visual continuity does most of the "they are continuous" argument for you.

---

## PART 6 — CONFIRMED TECHNICAL DIRECTIONS (已定技术路线)

### Houdini mapping → website
- **Route B (recommended):** export model as **GLB/glTF with vertex colours**, display in-browser with **Three.js** → interactive, clickable 3D health map.
- **Route A (fallback):** rendered images / turntable video. Zero-tech safety net for interim.
- **Route C (not now):** live sensor → backend → real-time recolour. Write as *future work*, do not build.
- **Open checkpoint:** confirm Houdini can export vertex colour to GLB. If not, fallback = bake to texture.

### Prediction — current honest status
- Current forecast = **rule-based weighted extrapolation** (recent score trend + weather temp/humidity/rain). Direction is sound (mycelium is humidity-sensitive) but the **weights are reasoned guesses, not learned from your data.**
- **To make it evidence-based:** use Batch-1 time-series to find real "environment → health-change" patterns, then recalibrate the weights with observed rules (e.g. "humidity below 60% for 3 days → dry_aging appears").
- **Interim framing (a strength, not a weakness):** state clearly that prediction is rule-based, validate/correct the rules with real cube data, and list "train a real predictive model on more data" as future work.
- **Batch-2 (2 days) does NOT carry prediction** — too short. It serves the spatial map + "map evolving" demo only.

### UI design workflow
- **Do NOT learn Figma now.** You already have a running site; Figma adds a translate-to-code step.
- **Use:** screenshot + plain-language description (+ optional iPad hand-drawn annotation) → Claude Code edits HTML/CSS directly → refresh → iterate.
- Hand-drawn annotation works: arrows, circles, boxes, handwritten notes (clear colours, legible text, 3–5 edits per image). **Visual changes = draw; logic changes = write.**

---

## PART 7 — DELIVERABLES CHECKLIST (产出清单, by priority)

### MUST-DO (minimum complete form for interim)
- [ ] **Five-step logic chain diagram** — one clean graphic; the backbone of the oral presentation
- [ ] **Scientific view (existing website)** — Steps 2–3 working, demoable with real cube data
- [ ] **Resident view, layer 1** — language-translation interface (science data → resident language)
- [ ] **Resident view, layer 2 (static)** — at least one cube's humidity mapping as 3D visual (rendered image / embedded model) proving "house health map" works
- [ ] **CloudCompare cube visualisation** — Batch-1 change over time (use the base-plate cube), as Step 1–3 empirical proof

### TRY-TO-DO (if time allows)
- [ ] Resident view layer 2 **interactive** — clickable 3D model (Three.js / GLB)
- [ ] Resident view layer 3 — care log + regeneration-experiment record
- [ ] Batch-2 **dynamic map** — day1 → day2 humidity evolution animation
- [ ] Prediction recalibration — derive 1–2 real rules from Batch-1 data

### PRESENTATION MATERIALS (needed regardless)
- [ ] Oral presentation built on the five-step chain
- [ ] The Scientific↔Resident correspondence diagram (cube → building)
- [ ] Clear "done / in-progress / planned" boundary slide (interim maturity signal)
- [ ] User guide for the website (DONE — one-page docx with contact email)

### EXPLICIT FUTURE WORK (state, don't build)
- Live sensor → website real-time interface (Route C)
- Trained predictive model on larger dataset
- Full resident-view spatialisation at building scale with environmental simulation
- Crowd-sourced dataset growth via Contribute feature

---

## PART 8 — OPEN THREADS FOR NEXT SESSIONS (明天起逐块深入)

Topics raised but parked, to deepen one at a time:
1. **Prediction rules** — pull Batch-1 time-series, find real environment→health patterns *(recommended first — core of scientific credibility)*
2. **Houdini → web technical path** — confirm GLB vertex-colour export, set up Three.js viewer
3. **Resident-view spatialisation** — full spec, method, and assets for the building-scale health map *(depends on: does the environment-simulation output building-surface temp/humidity? what state is the building 3D model in?)*
4. **Website continued optimisation** — for real public use
5. **Building-scale simulation** — how to generate a credible simulated health map (3 approaches: hand-paint → migrate cube patterns → environment-simulation-driven)

---

*This document is the master outline. Each open thread above will be deepened in its own session.*
