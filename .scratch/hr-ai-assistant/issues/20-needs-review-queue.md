# 20: `needs_review` queue

**What to build:** Nothing dropped silently, made visible. A first-class screen listing every flagged parse — low confidence, missing name/contact, failed formats — showing the original document and whatever partial data was extracted, so HR works the queue in the UI rather than reading a log. Resolving a row means editing and accepting the partial data into a Profile (human corrections win), or dismissing it to an explicit terminal status (`not_a_resume`, `failed`). Queue presence and counts are visible from the home surface; every submitted document is either worked here or landed cleanly — nothing sits invisible. (Spec §4 principle 2, §11 screen 4.)

**Blocked by:** 11 (Upload → parse → Candidate in the Talent Pool).

**Status:** ready-for-agent

- [ ] Every `needs_review` row surfaces in the queue with the original doc + partial extracted data
- [ ] HR can resolve a row by editing and accepting the partial Profile, or dismissing to an explicit terminal status
- [ ] Accepted corrections win — later re-extraction never overflows them (respects ticket 13's rules)
- [ ] Queue is discoverable with visible counts; no document can end in an invisible state
