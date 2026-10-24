# Diagrams

Rendered images for diagrams embedded in `README.md`.

GitHub's mobile apps do not render ` ```mermaid ` blocks; they show the raw source. So the README's diagram is committed here as Mermaid source and rendered ahead of time to an SVG that the README embeds as a normal image. The policy is in the constitution's `ARCHITECTURE.md`, "Visual Architecture".

## Files

- `how-it-fits-together.mmd`: source for the README's "How It Fits Together" diagram. The README also shows it in a collapsed block; keep the two identical.
- `how-it-fits-together.svg`: the rendered image the README embeds.
- `mermaid-config.json`: native SVG text (`htmlLabels: false`), straight edges (`curve: linear`), and the light palette from `docs/BRAND.md` (Surface fills, Line borders, Ink text, Muted lines). The `ours` class marks what this repository builds in Beam soft with a Beam border.

The diagram is top-down (`flowchart TD`) on purpose: GitHub scales an image to the column width, so a tall diagram stays readable on a phone where a wide one shrinks.

## Regenerating

After editing the `.mmd` file, re-render the `.svg` and update the collapsed copy in `README.md`:

```bash
npm install --no-save @mermaid-js/mermaid-cli
npx mmdc -i assets/diagrams/how-it-fits-together.mmd -o assets/diagrams/how-it-fits-together.svg -b white -c assets/diagrams/mermaid-config.json
```

Commit the source and the image together so they never drift.
