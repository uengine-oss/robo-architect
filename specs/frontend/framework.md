# Frontend Framework

Framework: vue

> Declared framework for this project's frontend, with conventions a coding
> agent should default to when generating components from the wireframes
> linked in `menu-structure.md` and `ui-flow.md`.
>
> Generated: 2026-05-12T11:55:59Z

## Conventions


- **Component file shape**: single-file `.vue` component (template / script setup / style scoped)
- **State management default**: Pinia store under `src/stores/`
- **Routing default**: Vue Router 4 with `<router-view>`
- **Styling default**: scoped CSS in the SFC


## Project Structure

- Components live next to the route they back (per the framework's routing default above).
- **Wireframe assets are not duplicated under `specs/frontend/`.** Each `ui-flow.md` entry links back to the canonical SVG and element-tree blocks at
  `../bounded-contexts/<bc>/requirements.assets/<userStoryId>-<ui-slug>.svg`
  and the matching `Wireframe:` block in `../bounded-contexts/<bc>/requirements.md`.
- Read `menu-structure.md` for the navigation table of contents and `ui-flow.md` for the user-journey order.
