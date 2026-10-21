# 26: Admin pipeline editor + hard delete

**What to build:** Org-level shaping, Admin-gated. The org-wide Stage list is editable in settings — add, rename, reorder — and the board immediately reflects it while existing Applications stay valid. Admin-only hard delete of a Candidate removes the person, resume, and Notes but anonymizes Activity entries rather than deleting them, preserving audit continuity (GDPR erasure); a soft remove-from-pool also exists. Admin actions append to the org-level Activity stream; Members can do none of this. (Spec §5 Deletion, §10, §11 screen 9.)

**Blocked by:** 12 (board — the Stage list the editor shapes).

**Status:** ready-for-agent

- [ ] Stage editor: add / rename / reorder the org-wide pipeline; board reflects changes immediately; existing Applications remain attached and valid
- [ ] Hard delete (Admin-only) removes person, resume, and Notes; Activity entries are anonymized, not deleted
- [ ] Soft remove-from-pool works and is distinct from hard delete
- [ ] Members are refused both powers (tested); admin actions append to org-level Activity
