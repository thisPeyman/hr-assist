# 13: Editable Profile — diff-accept and Merge

**What to build:** Corrections are never silently overwritten. HR edits a Candidate's Profile and the edits stick. Uploading a newer resume for an existing Candidate keeps only the latest file (older discarded), re-extracts into empty fields only, and surfaces changed fields as a diff the HR person accepts or dismisses field by field. Identity matching on ingest: email/phone match auto-Merges — the resume attaches to the existing Candidate with a "new resume added" flag; fuzzy name-only match creates the new Candidate but prompts HR "possible duplicate — merge?"; a confirmed Merge unions the two Candidates' Applications and Notes. Merges, diffs, and accepts are logged as Activity. (Spec §5 Merge & duplicates, Resume & Profile.)

**Blocked by:** 11 (Upload → parse → Candidate in the Talent Pool).

**Status:** ready-for-agent

- [ ] Manual Profile edits persist and are never overwritten by re-extraction
- [ ] New resume on an existing Candidate → per-field diff the HR person accepts or dismisses; re-extraction fills empty fields only
- [ ] Latest-resume-only: the newest file is kept, older ones discarded
- [ ] Email/phone match auto-Merges with a "new resume added" flag; fuzzy name-only match prompts before merging
- [ ] Merge unions Applications and Notes onto the surviving Candidate
- [ ] Diff accepts/dismissals and Merges appear in Activity
