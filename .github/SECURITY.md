# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Use GitHub's private vulnerability reporting instead:
**[Report a vulnerability](https://github.com/luckiday/vibe-hardware/security/advisories/new)**
(the "Security" tab → "Report a vulnerability"). If that is unavailable, open a regular
issue asking the maintainer (**@luckiday**) to enable private reporting — without including
any details of the vulnerability.

We aim to acknowledge a report within a few days and will coordinate a fix and disclosure
timeline with you.

## Scope

This repository is a collection of **agent skills, scripts, and example hardware designs**.
The most relevant concerns are:

- Scripts under `skills/*/scripts/` and `examples/*/bridge/` that run on a contributor's
  machine (shell/Python) — command injection, unsafe path handling, etc.
- The example **Mac bridge** for pager-buddy, which registers Claude Code hooks and opens
  a local network endpoint.

Generated hardware artifacts (gerbers, STEP/STL) are not a security boundary. Never commit
secrets — see the `.example` convention in the repo and `.gitignore`.
