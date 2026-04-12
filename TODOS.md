# TODOS

## Docker/deployment packaging

**What:** Create a Dockerfile that bundles the MELTS binary, shared libs, Python dependencies, and the web app so the research group can `docker run` it.

**Why:** Distribution is deferred for the UI polish iteration, but once the advisor sees the app, the next question will be "how do I run this on my machine?" The current setup requires symlinked binaries from external directories, which only works on the developer's machine.

**Pros:** Solves the distribution problem completely. Anyone with Docker can run the app.

**Cons:** Requires understanding MELTS binary licensing for redistribution. The MELTS C library may have restrictions on bundling.

**Context:** The app depends on `alphamelts-app` (binary), `alphamelts-py` (Python bindings), and `lib/` (shared libraries), all symlinked from `/home/laz/proj/melts/`. A Dockerfile would need to COPY these into the image, or the user would need to mount them as volumes.

**Depends on:** Nothing. Can be done independently of any feature work.
