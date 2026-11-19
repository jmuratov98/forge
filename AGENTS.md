# Forge

## Agent skills

### Issue tracker

GitHub Issues on jmuratov98/forge, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Build and test

CMake + Ninja. `docs/building.md` has the commands, the presets, and how to add a library or an end-to-end case. Run `cmake --build --preset debug --target check` before pushing. Work test-first (`docs/testing.md`) and follow `docs/style.md`.
