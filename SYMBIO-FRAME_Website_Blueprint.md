# SYMBIO-FRAME — Website Redesign Blueprint (Scientific View)
### Complete architecture + design spec for full reconstruction
*Hand this to Claude Code as the build blueprint. Scientific view only — resident view to be planned after this framework is built.*

---

## DESIGN PRINCIPLE

The whole site is organised **sample-first, not function-first.** Each mycelium sample (cube) is a persistent object that accumulates records over time. Users either do a quick one-off check, or enter a specific sample's space to monitor it over time.

Information density deepens layer by layer — each layer answers exactly one question, so users are never overwhelmed.

---

## TOP-LEVEL NAVIGATION

```
┌──────────────────────────────────────────────────────┐
│  Logo  Mycelium Health Monitor      [Live] [Sign in]   │
│        Quick Check │ My Samples │ Contribute            │
└──────────────────────────────────────────────────────┘
```

The homepage is a single scrolling page with three screens. Nav links jump to each screen.

---

## HOMEPAGE — SCREEN 1: QUICK CHECK (轻量路径)

One-shot detection, no login, look-and-leave. Layout reference: **Image 2 hero area.**

```
┌─────────────────────────────────────────────┐
│  ┌───────────────┐   ┌─────────────────────┐ │
│  │ UPLOAD         │   │ RESULT              │ │
│  │ big heading    │   │ detection result    │ │
│  │ + upload box   │   │ state + score        │ │
│  └───────────────┘   └─────────────────────┘ │
│  [ stat: samples · contributions · accuracy ] │
└─────────────────────────────────────────────┘
```

- Left: upload heading + drop/click box
- Right: YOLO result (annotated image, state badge, score)
- Below: a row of statistics (total samples, total contributions, model accuracy, etc.)
- This is the existing Overview upload-detect feature, streamlined. No save to any sample.

---

## HOMEPAGE — SCREEN 2: MY SAMPLES (深度路径) — THREE LAYERS

### Layer 1 — Sample overview list (this is screen 2 itself). Layout ref: **Image 1.**

Simplest layer. Title + entry + each sample's "ID-photo" with minimal info.

```
┌─────────────────────────────────────────────┐
│  Samples                          [+ New]     │
│                                               │
│  [ID photo]  Name                             │
│              Overall status                   │
│              Last upload time                 │
│  ─────────────────────────────────────       │
│  [ID photo]  Name / status / time             │
│  [ID photo]  ...                              │
└─────────────────────────────────────────────┘
```

- Each row/card = one sample: ID photo + name + overall-status judgement + last-upload time
- **"+ New" create-sample entry present on THIS layer** (and also on layer 2)
- Click a sample → Layer 2

### Layer 2 — Per-sample recent summary (one model per row). Layout ref: **Image 3 (Airbnb row).**

Each sample expands to one horizontal row, four zones:

```
┌────────────────────────────────────────────────────────────┐
│ [ID photo]  │ Latest image    │ Latest humidity │ Latest      │
│             │ upload +        │ Mapping model   │ CloudCompare│
│  press↓     │ detection +     │                 │ result      │
│             │ score           │                 │             │
└────────────────────────────────────────────────────────────┘
  (scroll vertically for more samples)        [+ Create new sample]
```

- Zone 1: ID photo, with **press** → Layer 3
- Zone 2: **latest image upload's** detection result + score
  - **"Latest" = the single most recent upload, regardless of which face (Option A)**
- Zone 3: latest humidity Mapping model (thumbnail/render)
- Zone 4: latest CloudCompare result
- This layer can also **create a new sample identity**
- These four zones = the "latest snapshot" summary of the full archive in Layer 3

### Layer 3 — Single sample's complete archive

Click press → everything for this sample, time-organised, plus upload entries.

```
┌─────────────────────────────────────────────┐
│  ← Back        [Sample name] · ID photo       │
│                                               │
│  All detection results (same face,           │
│    different times) ............ [+ upload]   │
│  All humidity Mappings (over time)[+ upload]  │
│  All CloudCompare results ........[+ upload]  │
│  Sensing data (multiple faces) ...[+ upload]  │
│  Prediction scores                            │
└─────────────────────────────────────────────┘
```

- Organised by **time axis**, not flat panels — same sample's detections / sensing / mapping / CloudCompare / predictions all accumulate here chronologically
- Each section has an **upload-new-data entry**
- 3D interactive elements (clickable Houdini mapping model) live here — but for interim, static renders/thumbnails are acceptable; interactive is "try-to-do"

---

## HOMEPAGE — SCREEN 3: CONTRIBUTE — TWO LAYERS

### Layer 1 — Map + intro + invitation. Layout ref: **Image 2 "how we work" area.**
```
┌─────────────────────────────────────────────┐
│  Contribute                                   │
│  ┌──────────────┐  ┌──────────────────────┐ │
│  │ contribution  │  │ intro / how it works │ │
│  │ map (geo)     │  │ step explanations     │ │
│  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────┘
```
- Left: geographic contribution map (data collection display)
- Right: basic intro + invitation + step-by-step explanation
- Click → Layer 2

### Layer 2 — Existing annotation + upload interface
- Reuse the current Contribute upload/annotation UI unchanged

---

## FULL NAVIGATION TREE

```
Homepage (scroll)
├ Screen 1  Quick Check (upload + result + stats)
├ Screen 2  My Samples
│   └ Layer 1: sample overview list (Image 1 style; ID photo + name + status + time; +New)
│       └ click → Layer 2: per-sample recent row (Image 3 style; 4 zones; +New)
│           └ press → Layer 3: single-sample full archive (time-organised + upload entries)
└ Screen 3  Contribute
    └ Layer 1: map + intro + invitation
        └ click → Layer 2: existing annotation/upload UI
```

---

## DESIGN SPEC

### Layout / typography reference
- **Image 2 (real-estate homepage):** overall skeleton — generous whitespace, clear block separation, left-title/right-content structure, bottom step-list with small icon-notes
- **Image 3 (Airbnb row):** Screen-2 Layer-2 "one model per row" styling — horizontal columns, each with small-caps label + main info, rounded dark button
- Match the **font sizing, label styling, border styling, small captions** of these two references — precise, refined, lots of breathing room

### Colour palette (Image 4 — replaces the reference blue)
```
#8A6946  dark brown   — headings / key text / primary buttons
#AF9273  mid brown    — secondary / borders / icons
#CFBBA2  light taupe  — dividers / supporting surfaces
#EFE2CA  cream        — page background / card base
#F6D387  warm yellow  — emphasis / highlight / "attention" health state
```

### Colour as health-state language (bonus — palette doubles as semantic system)
- cream / light taupe = healthy
- warm yellow = attention / needs care
- dark brown = decay / contamination
This earth-tone + warm-yellow scheme suits the mycelium / bio-material theme far better than tech-blue, and maps naturally onto health semantics. Keep this colour logic consistent across all 3D maps and badges — it will carry the visual continuity into the resident view later.

---

## BUILD NOTES FOR CLAUDE CODE

- Full reconstruction (Option A) — author chose clean structure over saving time.
- Backend already has a `sample` concept; extend it to support the ID-card / archive model.
- Quick Check = existing detect feature, streamlined.
- Contribute Layer 2 = reuse existing annotation UI unchanged.
- 3D interactive (clickable Houdini model) is "try-to-do"; static renders acceptable for interim. Reserve interactive-3D effort for the spatial health map, not for per-face detection.
- Persistence: DB + uploads already on Railway volume at `/app/data` — do not regress this.
- Verify all JS with `node --check` and Python with `py_compile` before presenting changes.

---

## NEXT (after this framework is built)
- Resident view (future narrative) — mirror this exact structure, "future-tense skin": cube → designed building, same four-zone logic, same colour language.
- The structural correspondence (scientific ↔ resident) is the core argument; build scientific first, then re-skin.
