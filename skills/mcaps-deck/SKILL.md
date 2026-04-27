---
name: MCAPS-Deck
description: Generate Microsoft MCAPS-styled .pptx presentations for Azure announcements, customer briefings, and Ignite-style decks.
version: 1.0.0
author: MCAPS Israel
category: Sales & Demos
tags: [MCAPS, Azure, PowerPoint, Ignite, Presentation]
compatible: [ClawPilot, Claude Code, Cursor, GitHub Copilot]
---

# MCAPS-Deck

Generate Microsoft MCAPS-styled `.pptx` presentations for Azure announcements, customer briefings, and Ignite-style decks.

## Triggers

Use this skill when the user asks for:

- "MCAPS deck"
- "Azure announcement deck"
- "Microsoft template style"
- "Ignite-style slides"
- any Microsoft/Azure-branded PowerPoint

## What it builds

The builder creates Microsoft-style 16:9 decks with:

- dark navy + ribbon hero title slides
- gradient pill badges for real GA / Public Preview features
- 3-card layouts with light-blue header strips
- light pipeline diagrams
- KPI stat blocks
- thank-you closer

## Workflow

1. Confirm scope: title, audience, and approximate slide count.
2. Build an outline JSON using the schema below.
3. Run:

```bash
python3 ~/.copilot/m-skills/mcaps-deck/scripts/build_mcaps_deck.py outline.json output.pptx
```

4. QA visually:

```bash
export PATH=/Applications/LibreOffice.app/Contents/MacOS:/opt/homebrew/bin:$PATH
soffice --headless --convert-to pdf output.pptx
pdftoppm -jpeg -r 80 output.pdf slide
```

5. Iterate until clean, then open the `.pptx` for the user.

```bash
open output.pptx
```

## Outline JSON schema

```json
{
  "title": "Deck title",
  "slides": [
    { "layout": "...", "...props": "..." }
  ]
}
```

## Layouts

### `title`
Opening slide, dark navy + blue/purple ribbon hero.

Props: `title`, `subtitle`, `presenters`, `hero_style` (`"blue"` or `"purple"`)

### `section_divider`
Dark slide, big centered title.

Props: `title`, `subtitle`, `badge`

### `section_word`
Light cream slide, single huge magenta word + gradient orb.

Props: `title`, `subtitle`

### `agenda`
Dark slide, "Agenda" lockup + numbered card list.

Props: `subtitle`, `items[]`

### `feature_pill`
Dark slide, gradient pill badge + headline + three bullet cards.

Props: `badge`, `title`, `subtitle`, `bullets[]`

### `three_cards`
Dark slide, three cards with light-blue header strip + dark body.

Props: `title`, `subtitle`, `cards[{title, body}]`

### `pipeline`
Light background, horizontal step pipeline with arrows + icon circles.

Props: `title`, `subtitle`, `steps[{icon, title, body}]`

### `kpi`
Dark slide, large stat cards with pink accent bar. Auto-shrinks long values.

Props: `title`, `stats[{value, label, note}]`

### `quote`
Dark slide, big magenta quote mark + pull quote + attribution.

Props: `text`, `attribution`

### `two_col`
Dark slide, two cards with bullets.

Props: `title`, `subtitle`, `columns[{title, bullets[]}]`

### `bullets`
Dark slide, single-column bullet list.

Props: `title`, `subtitle`, `bullets[]`

### `thanks`
Dark + ribbon hero, thank-you closer.

Props: `title`, `subtitle`, `contact`, `hero_style`

## Design tokens

- `bg_dark`: `#0A1A2F`
- `bg_light`: `#F5F2EF`
- `bg_card_dark`: `#142842`
- `header_strip`: `#8DC8E8`
- `pink`: `#E94B89`
- `magenta`: `#A02B93`
- `teal`: `#49C5B1`
- `azure_blue`: `#0078D4`
- Pill badge gradient: teal → purple → pink. Use only for real GA / Preview features.
- Fonts: Segoe UI Black for titles, Segoe UI for body.
- Size: 16:9 widescreen, 13.333 × 7.5 inches.

## Tips

- Mix dark and light slides for rhythm.
- Use `section_word` between major sections.
- Prefer `pipeline` over `bullets` for any multi-step process.
- Sample outline: run the builder with no args:

```bash
python3 ~/.copilot/m-skills/mcaps-deck/scripts/build_mcaps_deck.py
```
