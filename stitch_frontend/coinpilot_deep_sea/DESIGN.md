# Design System Strategy: High-Performance Precision

## 1. Overview & Creative North Star: "The Digital Cockpit"
This design system moves beyond the standard "fintech template" to create a high-performance environment for CoinPilot. Our Creative North Star is **"The Digital Cockpit"**—a space where information density meets surgical clarity. We avoid the "boxy" look of traditional dashboards by prioritizing tonal depth, atmospheric layering, and intentional asymmetry.

The system is designed to feel like an advanced navigational instrument. We break the grid by allowing key data points (like real-time price action) to breathe with expansive white space, while secondary technical metadata is nested within sophisticated, layered surfaces. This creates a rhythmic hierarchy that guides the eye toward critical market movements without overstimulating the user.

---

## 2. Colors & Surface Architecture
The color palette is rooted in a deep, midnight foundation that minimizes eye strain during long trading sessions.

### Surface Hierarchy & Nesting
We do not use flat backgrounds. Depth is achieved through the **"Tonal Stacking"** of surface containers:
- **Base Layer:** `surface` (#071325) is the infinite void of the application background.
- **Sectioning:** Use `surface-container-low` (#101c2e) for broad layout areas like the sidebar or secondary navigation panels.
- **Actionable Cards:** Use `surface-container` (#142032) or `surface-container-high` (#1f2a3d) for the primary trading widgets.

### The "No-Line" Rule
**Explicit Instruction:** Prohibit the use of 1px solid borders for sectioning or separating content. Boundaries must be defined solely through background color shifts. If two areas need to be distinct, place a `surface-container-lowest` card against a `surface-container-low` background. This creates a "soft edge" that feels integrated and high-end.

### The Glass & Gradient Rule
For floating elements (modals, dropdowns, or hovering price alerts), utilize **Glassmorphism**. Apply `surface-variant` (#2a3548) at 60% opacity with a `backdrop-blur` of 12px. 
- **Signature Polish:** Primary CTAs should not be flat. Use a subtle linear gradient from `primary` (#adc6ff) to `primary-container` (#4d8eff) at a 135-degree angle to provide a "lit from within" metallic sheen.

---

## 3. Typography
We use **Inter** as our sole typeface, relying on its variable weight axis and our custom scale to create an editorial feel.

- **Display (display-md/lg):** Used for large-scale price data and portfolio totals. These should feel authoritative and monumental.
- **Headline (headline-sm/md):** Used for section headers (e.g., "Market Overview"). 
- **Body & Labels:** Use `body-md` for technical English terms (e.g., "Order Book," "Liquidity") and `label-md` for Korean labels (e.g., "주문 내역"). 
- **The Hierarchy Strategy:** Use `on-surface-variant` (#c2c6d6) for labels to create a sophisticated "receded" effect, ensuring the primary data in `on-surface` (#d7e3fc) remains the focal point.

---

## 4. Elevation & Depth
In this design system, shadows are not structural; they are atmospheric.

- **The Layering Principle:** Stack `surface-container` tiers to create natural lift. For example, a "Buy/Sell" panel should be `surface-container-highest` sitting on a `surface-container` dashboard area.
- **Ambient Shadows:** For floating elements, use a shadow color tinted with the `primary` token at 4% opacity with a 32px blur. This mimics the glow of a high-end monitor rather than a physical shadow.
- **The "Ghost Border" Fallback:** If a border is required for high-contrast accessibility in the trading view, use `outline-variant` (#424754) at **15% opacity**. Never use a 100% opaque border.

---

## 5. Components

### Buttons
- **Primary:** Gradient-fill (`primary` to `primary-container`), 12px (`md`) rounded corners. Text is `on-primary` (#002e6a) in semi-bold.
- **Secondary:** Transparent background with a "Ghost Border" and `primary` text.
- **Tertiary (Ghost):** No background or border. Use for low-emphasis actions like "View More."

### Input Fields
- **Styling:** Use `surface-container-lowest` for the field background. 
- **States:** On focus, do not use a heavy border; instead, shift the background to `surface-container-high` and apply a subtle `primary` outer glow.

### Cards & Data Lists
- **The "No-Divider" Rule:** Forbid 1px dividers between list items (e.g., in the Order Book). Instead, use `0.5rem` (Spacing 2.5) of vertical white space or alternating subtle background shifts using `surface-container-low` and `surface-container-lowest`.
- **Price Chips:** Use `tertiary` (#4ae176) for "Long/Success" and `error` (#ffb4ab) for "Short/Danger." These should have a low-opacity background (10%) of the same color to avoid "neon-shouting."

### Professional Components
- **The Ticker Tape:** A seamless, edge-to-edge `surface-container-low` bar at the top of the viewport for scrolling global market stats.
- **Depth Charts:** Use `tertiary-container` and `error_container` with a 20% opacity fill and a 2px stroke for the area graphs.

---

## 6. Do's and Don'ts

### Do:
- **Do** use Korean labels (`label-sm`) as secondary metadata under larger English technical terms to cater to a global-pro user base.
- **Do** use the Spacing Scale religiously. Use `1.75rem` (Spacing 8) for major section padding to ensure the dashboard doesn't feel cluttered.
- **Do** lean into asymmetry. A wider "Main Chart" column (8 cols) paired with a narrower "Order Book" column (4 cols) creates a dynamic, custom feel.

### Don't:
- **Don't** use pure black (#000000) or pure white (#FFFFFF). All colors must be tinted with the navy/blue core tokens to maintain the "Digital Cockpit" atmosphere.
- **Don't** use 1px dividers to separate data rows; use vertical space and typography weight instead.
- **Don't** use standard 4px "web" rounding. Stick to the `md` (12px) and `lg` (16px) tokens to maintain the sophisticated, modern silhouette.