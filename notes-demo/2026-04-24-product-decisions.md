---
title: Product Decisions — Q2 Roadmap Review
date: 2026-04-24
type: note
tags: [product, roadmap, q2, strategy]
author: Elena Rodriguez
source: notion-export
---

## Goals for Q2

We agreed on three primary objectives for the quarter:

1. **Launch the self-serve onboarding flow** — reduce time-to-first-value from 45 minutes to under 10 minutes
2. **Ship the real-time collaboration beta** — multiplayer cursors, live comments, conflict resolution
3. **Improve mobile performance** — target 60fps on mid-range Android devices

## Decisions Made

### Self-Serve Onboarding

- Drop the mandatory credit card step. Data shows a 34% drop-off at that stage.
- Replace the 7-step wizard with a 3-step progressive disclosure pattern.
- Add an interactive demo video on the landing page (max 90 seconds).

### Real-Time Collaboration

- Use Operational Transform instead of CRDT. Our use case is simpler and OT is well-understood by the team.
- Scope for beta: max 10 concurrent editors per document.
- Defer presence indicators (who's online) to Q3 — not critical for beta success.

### Mobile Performance

- Adopt a virtualized list for the document explorer. Current flat list chokes at 500+ items.
- Implement image lazy loading with blurhash placeholders.
- Drop support for iOS 15. Only 2% of users are on it and it blocks several WebRTC features.

## Open Questions

- Should we offer a free tier with collaboration limits, or keep collaboration as a paid feature only?
- What's the migration path for customers on the old pricing model?

## Next Review

May 8th. Please come prepared with updated metrics for onboarding conversion and mobile crash rates.
