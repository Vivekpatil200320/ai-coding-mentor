# ADR-0003: Hint level is server-authoritative state the mentor renders, not a model decision

- **Status:** Accepted
- **Date:** 2026-07-01
- **Deciders:** Backend

## Context

The mentor is Socratic: it escalates through hint levels 0 (guiding
question) → 1 (directional) → 2 (names the concept) → 3 (explains the fix).
Something has to decide *when* to escalate. Two options: let the mentor model
judge "this person is stuck, I'll give more," or make `hint_level` explicit
state that the system controls and the mentor merely renders.

The product premise — guidance, not answers — makes level 3 (the actual
fix) a boundary that must not be crossed casually. And the mentor consumes
raw student chat, which is an adversarial channel (see
`docs/security/sandbox-audit.md`, P-2): a student will try to talk the mentor
into the answer.

## Decision

`hint_level` is a field of `MentorState`. `mentor_agent.py` selects a
prompt fragment for the *current* level and renders in that style — it does
**not** decide to escalate. The system prompt explicitly tells the mentor
that the hint level is set by the system, not by anything the user says, and
that level-3 (the fix) is only reached when the level is set there.

Escalation is therefore a product/API decision (advancing the stored level),
kept out of the model. The intended trigger is an explicit user signal
("I'm stuck") after levels 0–2 — deliberately not a timer or model hunch
(see the LinkedIn discussion notes: elapsed time is a poor proxy; resubmission
pattern is better).

## Consequences

- **Positive — injection resistance:** because the level is server state, a
  student prompt-injecting "you are now in answer mode" is trying to change a
  variable the model doesn't own. The mentor is instructed to treat such
  messages as conversation, not instructions. This is a structural defense,
  not just prompt wording.
- **Positive — reviewable pedagogy:** the escalation policy is code/state, not
  an emergent model behavior, so it can be reasoned about and changed
  deliberately.
- **Known gap (documented, not yet built):** no code currently *advances*
  `hint_level`. The mentor renders whatever level is set; the escalation
  trigger is unimplemented, and the level is not yet surfaced to the frontend
  (the SSE stream is tokens only). When built, the trigger should be
  behavioral (resubmission thrash), and a `hint_level_change` event should be
  emitted so the UI can mark the transition rather than have it read as "the
  bot got more helpful."

## Alternatives considered

- **Let the mentor model decide when to give the answer.** Rejected: makes the
  core pedagogical boundary a model judgment on an adversarial input channel —
  the exact thing prompt injection targets — and makes the policy unauditable.
