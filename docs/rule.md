# Development rules

## Keep the existing code as the core

The user's existing code is the foundation of Open-PiRobot. Every request must
be implemented by understanding, reusing, and extending that code wherever
possible. A feature request or bug report is not permission to rewrite the
project, replace its architecture, or recreate working modules from scratch.

## Make focused changes

- Find the existing implementation and modify the smallest coherent set of
  code needed to satisfy the request correctly.
- Preserve working behavior, module boundaries, public interfaces, naming,
  configuration, and coding style unless the requested change requires otherwise.
- Reuse existing helpers and dependencies. Add abstractions, frameworks, or
  parallel implementations only when there is a concrete need in the task.
- Avoid unrelated refactors, formatting sweeps, file moves, dependency upgrades,
  and cleanup. Do not replace custom logic merely because a different design
  would be easier to write.
- Preserve existing local changes, including work inside submodules. Never
  discard or overwrite them to simplify the task.
- If a broad rewrite or architectural replacement is genuinely necessary,
  explain the concrete limitation and proposed scope before doing it, and obtain
  explicit agreement unless the user has already authorized that scope.
  Routine focused fixes do not need repeated confirmation.

## Build and validate only what is needed

- A small request does not require rebuilding every image or package. Build
  and test the changed components and any dependents affected by their contracts.
- Use static checks for documentation or other changes that do not need a build.
- Expand validation to the whole stack when integration changes justify it;
  explain why. Do not perform blanket clean builds or disable caches by default.
- Preserve generated artifacts, persistent data, and the running environment
  unless changing them is necessary and within the requested scope.
- Report what changed, why it was needed, and what was actually verified.

## Apply the same principle during migration

A Humble-to-Jazzy migration adapts the existing project. Preserve its algorithms,
robot behavior, calibration, protocols, and module structure unless a verified
compatibility issue requires a focused change. Keep optional redesigns and
unrelated improvements separate from the migration.

These rules apply to future project work alongside [AGENTS.md](../AGENTS.md).
Explicit user instructions may authorize a different scope.
