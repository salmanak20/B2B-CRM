---
name: Premium Enterprise CRM
colors:
  surface: '#f9f9ff'
  surface-dim: '#cfdaf2'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f0f3ff'
  surface-container: '#e7eeff'
  surface-container-high: '#dee8ff'
  surface-container-highest: '#d8e3fb'
  on-surface: '#111c2d'
  on-surface-variant: '#464555'
  inverse-surface: '#263143'
  inverse-on-surface: '#ecf1ff'
  outline: '#777587'
  outline-variant: '#c7c4d8'
  surface-tint: '#4d44e3'
  primary: '#3525cd'
  on-primary: '#ffffff'
  primary-container: '#4f46e5'
  on-primary-container: '#dad7ff'
  inverse-primary: '#c3c0ff'
  secondary: '#0058be'
  on-secondary: '#ffffff'
  secondary-container: '#2170e4'
  on-secondary-container: '#fefcff'
  tertiary: '#571ac0'
  on-tertiary: '#ffffff'
  tertiary-container: '#6f3dd9'
  on-tertiary-container: '#e3d5ff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e2dfff'
  primary-fixed-dim: '#c3c0ff'
  on-primary-fixed: '#0f0069'
  on-primary-fixed-variant: '#3323cc'
  secondary-fixed: '#d8e2ff'
  secondary-fixed-dim: '#adc6ff'
  on-secondary-fixed: '#001a42'
  on-secondary-fixed-variant: '#004395'
  tertiary-fixed: '#e9ddff'
  tertiary-fixed-dim: '#d0bcff'
  on-tertiary-fixed: '#23005c'
  on-tertiary-fixed-variant: '#5516be'
  background: '#f9f9ff'
  on-background: '#111c2d'
  surface-variant: '#d8e3fb'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  container-padding: 24px
  gutter: 20px
---

## Brand & Style

This design system is built for high-stakes B2B relationship management. It prioritizes clarity, efficiency, and a premium "pro-tool" aesthetic inspired by modern desktop operating systems. The visual narrative combines the strict functionalism of enterprise software with the refined elegance of consumer hardware interfaces.

The style is **Apple-inspired Minimalism with Subtle Glassmorphism**. It balances high information density with visual breathing room, ensuring that users can manage complex sales pipelines without cognitive overload. The interface feels light, responsive, and tactile.

## Colors

The palette is anchored by a crisp white foundation to ensure maximum readability and a "fresh" feel. 

- **Primary & Secondary:** Deep Indigo and Blue are used for high-intent actions and active states. Indigo represents authority, while Blue is used for navigation and link-level interactions.
- **Accents:** Subtle Purple is reserved for specialized insights, AI-driven features, or secondary analytical highlights.
- **Surface Strategy:** Use `#FFFFFF` for primary content cards and `#F8FAFC` for the global application background to create a subtle layered effect.
- **Typography:** The Dark Navy/Charcoal (`#1E293B`) provides high contrast against white backgrounds without the harshness of pure black.

## Typography

Inter is the sole typeface, utilized for its exceptional legibility in data-heavy environments. 

- **Hierarchy:** Use tight letter-spacing on larger headlines to achieve a premium, editorial look.
- **Data Tables:** Use `body-sm` for table cells and `label-md` for column headers to maximize horizontal space.
- **Numbers:** Tabular lining should be enabled for all financial and numerical data to ensure columns align perfectly in reports and lists.

## Layout & Spacing

This design system employs a **12-column fluid grid** for main dashboards, with fixed-width sidebars (typically 260px or 80px collapsed). 

- **Rhythm:** An 8px base grid governs all spatial relationships. 
- **Density:** To achieve "high information density with generous whitespace," use internal component padding of 12px-16px, but maintain external margins of 24px between major layout blocks. 
- **Adaptive Rules:** On tablet (under 1024px), margins reduce to 16px and sidebars transition to an overlay drawer. On mobile, all cards stack vertically with 100% width.

## Elevation & Depth

Depth is used sparingly and purposefully to communicate hierarchy.

- **Standard Cards:** Use a thin 1px border (`#E2E8F0`) with no shadow for a flat, organized look.
- **Active/Hover Cards:** When a user interacts with a card (like a Kanban lead), apply a soft, diffused shadow: `0px 10px 15px -3px rgba(0, 0, 0, 0.05)`.
- **Glassmorphism Overlays:** Modals, dropdown menus, and sticky navigation headers use a background blur (12px to 20px) with a semi-transparent white fill (`rgba(255, 255, 255, 0.8)`). This allows the content beneath to provide a sense of context without distracting the user.

## Shapes

The shape language is modern and approachable. 

- **Standard Elements:** Buttons, inputs, and small cards use a **12px** (0.75rem) corner radius.
- **Large Containers:** Dashboard widgets and main content areas use a **16px** (1rem) corner radius.
- **Status Badges:** Use a fully rounded "pill" shape (999px) to clearly differentiate them from interactive buttons or input fields.

## Components

### Buttons
- **Primary:** Solid Deep Indigo with white text. Subtle gradient from top to bottom (Indigo-500 to Indigo-600) for a tactile feel.
- **Secondary:** White background with a 1px border (`#E2E8F0`) and Dark Navy text.
- **Ghost:** No background or border. Text is Blue (`#3B82F6`). Used for low-emphasis actions like "Cancel" or "Learn More."

### Input Fields
- Heights should be standardized at 40px for desktop. 
- Background: `#FFFFFF`. 
- Border: `#E2E8F0`. 
- Focus State: 2px border of `#3B82F6` with a soft blue outer glow.

### Data Tables
- Header row background: `#F8FAFC`. 
- Row hover state: Subtle shift to `#F1F5F9`.
- Vertical borders should be avoided; use horizontal dividers only to keep the view clean.

### Kanban & KPI Cards
- **KPI Cards:** Feature large `headline-lg` numbers. Use secondary/accent colors for progress sparklines.
- **Kanban Cards:** Use the `rounded-lg` token (12px). Include a small colored "source" indicator strip on the left edge.

### Status Badges
- Use a "Soft Color" treatment: a low-opacity version of the semantic color for the background (e.g., 10% opacity Red) with high-contrast text in the same hue.

### Progress Indicators
- Linear bars should be 6px tall with a light gray track and a primary indigo fill. For circular indicators, use a medium stroke weight (4px) to ensure visibility without feeling heavy.