I want to rebuild the current `landing.html` because the previous implementation used the wrong layout architecture.

Please do **not** continue patching the current visual result.

Instead, inspect the current `landing.html`, then replace its landing-page layout with a clean implementation based on the requirements below.

## 1. Visual source of truth

I have attached a screenshot of my finished Figma landing page design.

**The attached Figma screenshot is the visual source of truth.**

This is NOT a redesign task.

Do not reinterpret the page, change its visual language, or redesign the composition.

Please preserve as closely as possible:

- overall composition
- typography hierarchy
- colours
- spacing relationships
- text placement
- image placement
- button style
- feature navigation section
- overall visual balance

The original Figma frame was designed at **1440px width**.

However:

**1440px is only the reference design width. It must NOT become a fixed-width webpage container.**

---

## 2. Main problem with the previous implementation

The previous implementation behaves like a fixed or centred 1440px canvas inside a wider browser.

For example, on a 1920px-wide browser, the content remains around 1440px wide and large empty white margins appear on the left and right.

This is incorrect.

The landing page should instead expand horizontally with the browser.

At:

- 1440px browser width → closely match the Figma design
- 1600px browser width → expand naturally
- 1920px browser width → use the full browser width

There should NOT be a fixed 1440px page sitting in the centre of a larger viewport.

---

# 3. Full-width page behaviour

The entire landing page must span the full available browser width.

Use a fluid page architecture.

Prefer:

```css
width: 100%;
```

Avoid using `100vw` unnecessarily if it causes horizontal scrollbar issues.

Do NOT use any main-page wrapper such as:

```css
width: 1440px;
min-width: 1440px;
max-width: 1440px;

width: 1280px;
max-width: 1280px;

margin: 0 auto;
```

Do NOT put the whole landing page inside a fixed-width or max-width centred container.

The page should visually reach both sides of the browser.

---

# 4. Vertical behaviour

The design is intentionally taller than one browser screen.

It is completely acceptable — and expected — that the user scrolls vertically.

Do NOT attempt to fit the entire landing page into one viewport.

Do NOT use:

```css
height: 100vh;
overflow-y: hidden;
```

for the full page.

The page height should be determined naturally by its content.

Use normal vertical scrolling.

The goal is:

**full-width horizontally + natural scrolling vertically**

NOT:

**everything forced into one screen**

---

# 5. Do not use the Anima DOM structure

The original Anima export should only be treated as a reference for:

- original Figma measurements
- approximate positions
- colours
- font sizes
- spacing
- proportions

Do NOT reuse Anima's generated DOM architecture.

Do NOT preserve classes such as:

```text
.frame
.rectangle
.text-wrapper
.text-wrapper-2
.text-wrapper-3
.group
.element
.element-2
.vector-2
.vector-3
```

etc.

Do not reproduce the page using dozens of absolutely positioned Figma layers.

Instead, build clean semantic HTML.

A structure approximately like this is preferred:

```html
<div class="landing-page">

    <header class="landing-header">
        ...
    </header>

    <main>

        <section class="hero">

            <div class="hero-copy">
                ...
            </div>

            <div class="hero-visual">
                ...
            </div>

        </section>

        <section class="feature-nav">

            <div class="feature-item">
                ...
            </div>

            <div class="feature-item">
                ...
            </div>

            <div class="feature-item">
                ...
            </div>

        </section>

    </main>

</div>
```

You may adapt the exact semantic structure if needed, but keep it clean and maintainable.

---

# 6. Desktop hero architecture

For desktop screens, preserve the Figma composition.

The page should behave approximately like a two-part composition:

```text
LEFT:
text / title / button / credits

RIGHT:
mycelium visual collage
```

The visual balance is approximately:

```text
left content: 40–45%
right visual: 55–60%
```

Do not treat these percentages as rigid columns if a more accurate implementation requires overlapping or art-directed positioning.

The important thing is to reproduce the visual composition of the attached Figma screenshot while remaining fluid.

You may use:

- CSS Grid
- Flexbox
- percentages
- `clamp()`
- `calc()`
- relative positioning
- absolute positioning inside the hero visual

Do NOT use absolute positioning to construct the entire webpage.

---

# 7. Figma coordinates are reference proportions

The 1440px Figma coordinates should be interpreted proportionally rather than as a fixed canvas.

For example:

The right-side visual begins at approximately:

```text
x = 659px
```

in the 1440px Figma design.

That corresponds to approximately:

```text
659 / 1440 ≈ 45.8%
```

Therefore, the hero visual begins around 45.8% of the page width at the reference composition.

Similarly, do not blindly preserve positions like:

```css
left: 659px;
```

on every screen.

Translate important design relationships into fluid percentages or responsive CSS.

---

# 8. Hero right image

Do NOT use the individual Anima-exported mycelium images.

The complete right-side composition has already been combined into one image.

Use ONLY:

```text
/static/images/hero_right.png
```

for the hero collage.

Do not use:

```text
1.png
2.png
3.png
4.png
1-1.png
2-1.png
3-1.png
4-1.png
```

or any other individual mycelium component images.

At the 1440px Figma reference width:

- the image begins at approximately `left: 45.8%`
- the image intentionally extends above the top of the hero
- its approximate vertical reference is `top: -70px`

The visual should preserve this intentional top bleed.

The hero should crop the overflowing part appropriately.

Using something conceptually similar to:

```css
.hero {
    position: relative;
    overflow: hidden;
}

.hero-visual {
    position: absolute;
    left: 45.8%;
    top: -70px;
}
```

is acceptable if it reproduces the Figma composition.

However, do NOT blindly copy those exact values if they make the fluid layout incorrect.

The right image must:

- preserve its aspect ratio
- grow responsively on wider desktop screens
- remain visually anchored to the right side
- continue filling the right side of the composition
- not sit inside a centred 1440px wrapper

Do NOT use:

```css
transform: scale(...)
```

on the entire webpage.

---

# 9. Header

Preserve the Figma header:

```text
[logo] Mycelium Research
```

Use:

```text
/static/images/logo.png
```

for the logo.

Keep the header visually positioned like the Figma reference.

The header belongs to the overall full-width composition and should not introduce a centred max-width container.

---

# 10. Main title

Keep the main title exactly:

```text
Mycologic
```

Preserve the Figma:

- size hierarchy
- colour
- weight
- position
- visual relationship with the description below it

The Figma uses a large warm brown title.

Do not redesign it into a standard SaaS-style hero heading.

---

# 11. Description text

Use exactly the following content:

```text
Mycelium is a living material. It continues to interact with its environment long after fabrication —
responding to moisture, temperature, and seasonal change.

Mycologic is a monitoring platform for mycelium-based materials. Through environmental sensing,
3D scanning, and machine learning, it helps researchers read and record how the material behaves
over time — tracking humidity, surface condition, and geometric change.
```

Preserve the paragraph separation.

Do not add the older paragraphs about:

- researchers uploading specimen photos
- the goal being pre-tending

Those paragraphs should NOT appear in the new version.

Keep the text column width visually similar to the Figma screenshot.

---

# 12. Enter platform button

Keep:

```text
Enter platform →
```

The button must link to:

```text
/app
```

Preserve the Figma button styling:

- brown background
- white text
- rounded corners
- similar proportions
- similar placement

Do not redesign it.

---

# 13. Credits

Keep:

```text
Built by Kecen Yi . Beckett Lab
BARTLETT SCHOOL OF ARCHITECTURE, UCL . RC7 BIO-INTEGRATED DESIGN
```

Preserve the subtle visual hierarchy shown in the Figma reference.

The credit block should appear near the bottom-left of the white hero area as in the design.

---

# 14. Bottom feature navigation section

The bottom cream-coloured section contains three features:

```text
QUICK CHECK
SAMPLE ARCHIVE
CONTRIBUTE
```

It must span the FULL browser width.

Do NOT constrain the cream background to a 1440px or other centred container.

Its background colour should extend from the absolute left edge to the absolute right edge of the browser.

Within the section, arrange the three feature items evenly across the available width.

Preserve the Figma composition with subtle vertical separators between them.

---

## QUICK CHECK

Use the corresponding existing icon asset.

Text:

```text
QUICK CHECK
```

Description:

```text
Instant health reading. Upload a photo, get a score. No sensors, no setup.
```

---

## SAMPLE ARCHIVE

Use:

```text
/static/images/cards_stack.png
```

Text:

```text
SAMPLE ARCHIVE
```

Description:

```text
Long-term specimen care. Track changes over time with photos, scans, and sensing data.
```

---

## CONTRIBUTE

Use the corresponding existing icon asset.

Text:

```text
CONTRIBUTE
```

Description:

```text
Help train the model. Annotate and submit — every image improves detection.
```

---

# 15. Image assets

Use these image paths:

```text
Logo:
/static/images/logo.png

Archive:
/static/images/archive.png

Cards stack:
/static/images/cards_stack.png

Sync saved locally:
/static/images/sync_saved_locally.png

Hero collage:
/static/images/hero_right.png
```

Do not reference the old Anima `img/...` paths.

Do not reference individual mycelium images.

---

# 16. CSS implementation

IMPORTANT:

Only modify:

```text
landing.html
```

Do NOT modify:

- Flask backend
- Python files
- routes
- database
- other templates
- existing application pages
- global CSS files
- JavaScript belonging to other pages

All new landing-page-specific CSS should therefore be written inside:

```html
<style>
...
</style>
```

inside `landing.html`.

The new landing page should NOT rely on Anima's `style.css` for its layout.

If the current `landing.html` contains Flask/Jinja integration required by the application, preserve that integration.

Do not break existing Flask routing or template behaviour.

---

# 17. Remove incorrect legacy layout behaviour

Before implementing the new page, inspect the current `landing.html`.

Remove or neutralise any landing-page layout rules involving:

```css
width: 1440px;
min-width: 1440px;
max-width: 1440px;

width: 1200px;
width: 1280px;

max-width: 1200px;
max-width: 1280px;

margin: 0 auto;

height: 100vh;

overflow: hidden;
```

when they are being used on the overall page structure incorrectly.

Also remove any:

```css
transform: scale(...)
```

used to scale the entire Figma frame.

Do not leave the previous layout architecture underneath the new CSS.

I want a clean replacement, not another CSS patch layered over the old implementation.

---

# 18. Responsive behaviour

Desktop fidelity is the first priority.

### Desktop: >= 1024px

Preserve the Figma composition.

The layout must:

- use the full viewport width
- preserve the left/right visual relationship
- allow the hero collage to grow on wider screens
- maintain the title/text/button hierarchy
- keep the cream navigation section full width

At 1440px, closely match the attached Figma screenshot.

At 1920px, the composition should expand naturally rather than staying 1440px wide in the centre.

---

### Tablet / mobile: < 1024px

The layout may adapt.

For smaller screens, it is acceptable to:

- stack the copy and visual
- reduce typography with `clamp()`
- change the hero collage positioning
- stack or reorganise the three feature items
- reduce spacing appropriately

Do NOT preserve a 1440px minimum width on mobile.

There must be no horizontal scrolling caused by the desktop design.

---

# 19. Important implementation principle

Please understand this distinction:

The Figma file means:

```text
"At 1440px browser width, the website should look like this."
```

It does NOT mean:

```text
"The website itself should always be 1440px wide."
```

Translate the Figma design into a fluid webpage.

Do NOT simply reproduce the Figma frame as a fixed HTML canvas.

---

# 20. What NOT to do

Do NOT:

- redesign the page
- change the colour palette
- invent new sections
- change the copy
- add a navigation menu
- add animations
- add gradients
- add shadows that are not in the design
- centre the entire page inside a max-width container
- force the page into 100vh
- use `min-width: 1440px`
- scale the whole page using CSS transforms
- recreate the individual mycelium collage images
- continue patching the previous broken layout
- modify files other than `landing.html`

---

# 21. Final expected result

The final result should behave conceptually like:

```text
Browser width
←────────────────────────────────────────────────────────→

HEADER

Mycologic                     HERO COLLAGE
description                   HERO COLLAGE
description                   HERO COLLAGE

button                        HERO COLLAGE

credits


──────────────────────────────────────────────────────────
          cream feature navigation — full width
──────────────────────────────────────────────────────────

Quick Check       Sample Archive       Contribute
```

The composition should extend to the full width of the browser.

On wider screens, the design should gain horizontal space naturally.

The page may and should extend vertically beyond one viewport, with normal scrolling.

---

# 22. Execution

Please:

1. Inspect the current `landing.html`.
2. Identify the old fixed-canvas / centred-container layout.
3. Replace that architecture rather than patching it.
4. Build clean semantic HTML.
5. Put all landing-specific CSS inside `landing.html`.
6. Use the attached Figma screenshot as the visual source of truth.
7. Use the specified image assets.
8. Modify no other file.
9. After implementation, briefly summarise what layout architecture you changed.

Do not ask me to manually convert the Anima CSS.

Please implement the corrected version directly.