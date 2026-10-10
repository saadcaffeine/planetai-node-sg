# The heat margin stays at one degree

2026-10-10 · Tomas

## The question

Node #1 ran a sustained heat event from 21:00 through the next morning: the room's apparent
temperature sat at 35.1–35.5 all night, and the clear rule (SPEC_alerts §4: no candidate for 30
minutes, with the candidate window starting 1 °C under the line) therefore never fired. The Decide
card showed the same open event for twelve hours and looked, to Tomas, "fixed and locked".

Two readings were possible: the margin is wrong for a hot climate (tighten it, or add a daily
auto-clear), or the margin is right and the card's stillness is the problem.

## The decision

**The margin stays as written.** Kuta Selatan is a hot place; a house whose nights sit at 34–35 °C
apparent is not malfunctioning, and an event that stays open through such a night is describing the
weather, not failing. A tighter margin would flap; a daily auto-clear would say the heat ended when
it did not.

The card's stillness is addressed separately: it renders nothing that moves between polls, though
the wire carries `last_seen_at`. That is a presentation gap, not a reason to change the clear
semantics.
