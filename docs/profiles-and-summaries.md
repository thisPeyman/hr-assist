# پروفایل، ادغام و خلاصهٔ نسخه‌ای

بانک افراد در `/candidates` و پروندهٔ کامل در `/candidates/:id` قرار دارد. فرم کامل تماس، معرفی، مهارت‌ها، صنایع، سوابق، تحصیلات، زبان‌ها، گواهی‌ها و پیوندها را ویرایش می‌کند. رویدادهای انسانی و مقادیر قبلی/جدید در تاریخچه ثبت می‌شوند.

## هویت و نسخهٔ جدید

- ایمیل با حذف فاصله و یکسان‌سازی بزرگی حروف مقایسه می‌شود. تلفن با حذف نشانه‌ها، تبدیل ارقام فارسی/عربی، و یکسان‌سازی `09…`، `0098…` و `+98…` مقایسه می‌شود. ایمیل خالی یا تلفن خالی تطابق محسوب نمی‌شود.
- تطابق دقیق ایمیل یا تلفن، رزومه را به فرد موجود وصل می‌کند؛ اگر دو هویت موجود را به هم متصل کند، پرونده‌ها در قدیمی‌ترین فرد جمع می‌شوند.
- شباهت نام فقط پیشنهاد می‌دهد. ادغام دستی با تأیید نام فرد مقصد انجام می‌شود.
- فیلدهای خالیِ بدون اصلاح انسانی پر می‌شوند. سایر اختلاف‌ها پیشنهادند. برای جلوگیری از آمیختن ردیف‌های بازچینش‌شده، مجموعه‌هایی مثل سوابق کاری و تحصیلات به‌عنوان یک فیلد پیشنهاد می‌شوند.
- پذیرش پیشنهاد فقط وقتی مجاز است که مقدار فعلی هنوز با مقدار مبنای پیشنهاد یکسان باشد؛ در غیر این صورت پاسخ `409` از بازنویسی اصلاح بعدی جلوگیری می‌کند. رد پیشنهاد مقدار فعلی را حفظ می‌کند.
- فقط فایل دارای جدیدترین زمان دریافت باقی می‌ماند. فایل قدیمی و خروجی استخراج مربوط به آن با حذف آبشاری کنار گذاشته می‌شوند؛ تاریخچه، پیشنهادها و خلاصه‌های نسخه‌ای مستقل از فایل نگهداری می‌شوند. پردازش دیرهنگام یک ورودی قدیمی، نسخهٔ جدیدتر را جایگزین نمی‌کند.
- ادغام، یادداشت‌ها، ارتباط درخواست‌های شغلی، تاریخچه و کش خلاصه‌ها را منتقل می‌کند. مدل ارتباط درخواست‌ها برای این انتقال وجود دارد؛ مدیریت کامل موقعیت‌ها و گردش‌کار درخواست‌ها همچنان مربوط به تسک ۱۲ است.

## خلاصهٔ هوشمند

`resume_summaries` برای هر `(candidate_id, resume_version)` یک رکورد دارد؛ نسخه همان SHA-256 فایل است. دریافت نسخهٔ جدید خلاصه را پیش‌محاسبه می‌کند. `GET` فقط رکورد ذخیره‌شده را می‌خواند. شکست تولید هم ذخیره می‌شود و با بازکردن صفحه تکرار نمی‌شود. بازتولید دستی رویداد `ai_summary_regenerated` دارد؛ در شکست بازتولید، متن قبلی از کش حذف نمی‌شود.

خروجی شامل متن فارسی ۱۲۰ تا ۱۸۰ کلمه، موارد نامشخص و نام فیلدهای مبناست. قرارداد v2 دسته‌های حرفه‌ای را جدا از متن تولیدشده، مستقیماً از داده‌های مبنا نمایش می‌دهد. بازهٔ کلمات، وجود حروف فارسی، نام و وجود مقدار فیلدهای استناد و عبارت‌های ممنوع صریح کنترل می‌شوند؛ این کنترل‌ها اثبات زبان یا درستی معنایی همهٔ جمله‌ها نیستند. محاسبهٔ سابقه فقط برای بازه‌های دقیق و قابل اعتماد انجام می‌شود و هم‌پوشانی را یک‌بار می‌شمارد؛ تاریخ ناقص یا تقویم مبهم به‌عنوان نامشخص اعلام می‌شود.

چارچوب مشترک در `backend/app/ai/prompts/shared_v1.md` و قرارداد فعال خلاصه در `resume_summary_v2.md` است؛ v1 برای سابقه حفظ شده است. ورودی مدل فقط فیلدهای حرفه‌ای مجاز را دارد؛ نام، ایمیل، تلفن، تصویر و متن کامل رزومه به مرحلهٔ خلاصه‌سازی فرستاده نمی‌شوند. `HR_RESUME_SUMMARY_MODEL` اختیاری است و در نبود آن مدل استخراج انتخاب می‌شود.

۲۰ ورودی مرجع در `backend/tests/golden/resume_summary_v1.json` وجود دارد. پس از تغییر پرامپت، از پوشهٔ بک‌اند اجرا کنید:

```powershell
uv run python -m scripts.eval_resume_summary
uv run python -m scripts.eval_resume_summary --live
```

فرمان اول فقط کنترل آفلاین دادهٔ مبنا، دسته‌ها و انتظارهای قطعی است. فرمان دوم تولید زنده و اعتبارسنجی خودکار محدود را انجام می‌دهد و سهمیهٔ API مصرف می‌کند؛ تأیید معنایی محسوب نمی‌شود. تست‌های خودکار قرارداد با مدل ساختگی اجرا می‌شوند.

در اجرای اولیهٔ ۲۸ اکتبر ۲۰۲۶، Groq پاسخ `403 Forbidden` داد. در آزمایش مجدد همان روز، دسترسی مدل و تولید متن موفق شد؛ رزومهٔ موجود بازپردازش شد و خلاصهٔ فارسی ۱۷۳ کلمه‌ای در کش ذخیره شد. کنترل‌های آفلاین و تست‌های یکپارچه موفق‌اند؛ ارزیابی معنایی زندهٔ کل مجموعهٔ ۲۰ ورودی هنوز اجرا نشده است. مدل محلی برای این کار اجرا نشده است.

## API و مهاجرت

مهاجرت `0006` نرمال‌سازی هویت، علامت فیلدهای انسانی و جدول‌های اختلاف، خلاصه، یادداشت و ارتباط درخواست را اضافه می‌کند. همهٔ جدول‌ها RLS اجباری دارند. تغییرات هر سازمان هنگام تطبیق/ویرایش/ادغام با قفل تراکنشی همان سازمان سریالی می‌شوند.

- `GET /api/candidates/{id}/workspace`
- `PUT /api/candidates/{id}/profile`
- `POST /api/candidates/{id}/changes/{change_id}` با `accept` یا `reject`
- `POST /api/candidates/{id}/merge` با `target_id`
- `POST /api/candidates/{id}/summary/regenerate`
- `POST /api/candidates/{id}/notes`
- `POST /api/candidates/{id}/acknowledge-resume`

## Repair 29 — human ingestion paths (2026-10-31)

Review acceptance and manual resume PATCH creation now reuse `attach_profile`,
identity normalization, empty-field reconciliation, latest-file retention and
per-version summary initialization. Only intentionally edited fields are human
overrides. Review requests may send `edited_fields` plus `expected_values` keyed
by profile field path; the UI derives these from the original form and current
linked Profile. A conflicting baseline returns `409 PROFILE_CHANGED_REFRESH`
atomically. Legacy review clients without explicit edits infer changes from raw
extraction but never overwrite a conflicting existing correction. Unchanged
extraction values remain proposals, not silent overrides.

PATCH ignores omitted fields (explicit null/empty clears them) and accepts
`expected_values` for optimistic protection. Human edits supersede pending
proposals for those paths; proposal acceptance also verifies the current resume
version. An older unassigned review returns `409 RESUME_SUPERSEDED` rather than
replacing a newer attached file. Raw extraction remains immutable while retained
under the latest-resume-only policy.

Deleting a resume deletes the file/parse provenance only. The Candidate, Notes,
Applications, prior Activity and versioned summary remain; `resume_deleted` is
appended. Admin erasure/anonymization remains ticket 26.

Regression verification: public HTTP APIs against isolated Postgres `hr_test`.
UI is statically typechecked/built/linted; no new UI/browser tests were added,
per the user's API/database-only test boundary. Browser and live semantic/model
acceptance remain pending for this repair.

## Ticket 14 contract v2 — API/database boundary (2026-10-31)

No SQL migration or paid cache backfill is needed: stored JSONB is additive.
Workspace exposes `coverage_status=structured_v2`, `legacy_unverified` (retained
pre-v2 content), or `unavailable` (no content). GET never generates, upgrades,
revalidates or relabels old prose as verified category coverage. A prompt change
does not invalidate per-SHA success/failure caches. Manual regeneration is the
explicit opt-in; it returns HTTP200 with `status`/`error`, **not** an unconditional
success assertion. Failed regeneration retains successful content, model, prompt
version and timestamp together. Its Activity records the attempted model/prompt
and outcome; raw provider exception details are never returned. For no successful
content, `model`/`generated_at` may be null; the initial prompt version is retained.

New content includes `contract_version=2`, application-owned `facts`, and a minimal
`evidence` map of cited snapshot paths to supplied values. These are **not model
output fields**. Each category has `state=supplied|partial|unknown` and `items`
containing `value` plus `evidence` paths. The map preserves the cited values after
Profile edits, including date inputs behind computed years, without retaining
contact identifiers or whole work bullets just to resolve a pointer. Categories:
`headline`, `current_titles`, `current_employers`, `experience_years`, `skills`,
`employers`, `industries`, `education`, `languages`, `residence`, `locations`.
Employer names are neutral, not an inferred "notable"/prestige ranking. Headline
is never substituted for current title. Only `current=true` marks a current job;
all explicit current jobs remain, and an incomplete current job makes otherwise
supplied current titles/employers partial. Historical-only jobs yield unknown
current titles/employers. Nested-empty education/languages are unknown; a
proficiency without a language does not identify a language. No proficiency,
industry or nationality is inferred. Residence remains unknown even when work
locations exist; `locations` preserves both with distinct evidence. Full exact
date intervals are unioned; year/month-only, Jalali, invalid, future or incomplete
dates yield unknown years, never zero guessed from absence.

### Snapshot/cache semantics

- Automated ingestion snapshots the **incoming extracted Profile** for the new
  SHA, even if human-protected fields remain different in the accepted Profile.
- Human review/PATCH initialization uses the accepted Profile (repair29 paths).
- Manual regeneration snapshots the currently accepted/edited Candidate Profile
  for the same SHA. Ordinary Profile edits and diff decisions do not regenerate.
- Prose, facts, evidence and successful provenance share a single stored snapshot;
  facts are not recomputed from the current Profile during GET. Prior SHA rows
  remain retained. New SHA generation, duplicate cache and tenant404 behavior are
  preserved. In particular a cross-tenant regeneration never calls the provider.

### Validation bounds and pending acceptance

The provider schema is strict; extra fields (including model-authored employer,
years or facts) are rejected. Grounded field names must be allowed and nonempty
in the supplied snapshot; empty evidence is allowed for an empty professional
profile. Invalid output gets one validation repair, then a cached `invalid_summary`
without blocking ingestion/review. Responses and chat transports use the configured
summary model and action-aware repair guidance. Explicit Persian/English forbidden
phrases are checked in prose and model gaps. These checks and deterministic facts
**do not prove that arbitrary prose is factual, comprehensive Persian, free of
implicit protected-attribute claims, or non-evaluative in all formulations**.
Generic but syntactically valid prose can pass; category coverage is reliable only
in the application-owned facts panel, not certified in the prose.

Offline golden evaluation prints per-case `offline_deterministic_only` results,
category states and literal expected category values. All 20 fixtures now include
expectations; overlap uses full dates and expects4.0, year-only expects unknown.
`--live` prints `live_automatic_contract`, not semantic PASS. `--output <path>` can
save model/provider/prompt/date, prose, gaps and evidence for later human review.
No new live calls were authorized or made for v2. The historical single v1
173-word result does not validate v2 or all 20 cases.

Release/pilot gate remains unchecked: obtain authorization/API credit, run all20
cases with the deployed provider/model and v2 prompt, save the output, and have a
Persian reviewer check every statement against input (including English-grounded
input), required factual prose coverage, no invented employer/title/years,
current-vs-past accuracy, unknown-vs-negative wording, protected attributes and
non-evaluation. Record per-case failures/revisions and date/model/prompt. Separately
perform responsive/RTL/keyboard UI acceptance for category, legacy and retained
failure states. Static build/lint and mocked API tests are not substitutes.
