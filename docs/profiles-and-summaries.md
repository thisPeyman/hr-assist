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

خروجی شامل متن فارسی ۱۲۰ تا ۱۸۰ کلمه، موارد نامشخص و نام فیلدهای مبناست. بازهٔ کلمات و زبان، نام فیلدهای استناد، عبارت‌های ارزیابانه و اشاره‌های صریح به ویژگی‌های محافظت‌شده اعتبارسنجی می‌شوند. این کنترل‌ها جای بازبینی معنایی HR را نمی‌گیرند. محاسبهٔ سابقه فقط برای بازه‌های دقیق و قابل اعتماد انجام می‌شود و هم‌پوشانی را یک‌بار می‌شمارد؛ تاریخ ناقص یا تقویم مبهم به‌عنوان نامشخص اعلام می‌شود.

چارچوب مشترک در `backend/app/ai/prompts/shared_v1.md` و قرارداد خلاصه در `resume_summary_v1.md` است. ورودی مدل فقط فیلدهای حرفه‌ای مجاز را دارد؛ نام، ایمیل، تلفن، تصویر و متن کامل رزومه به مرحلهٔ خلاصه‌سازی فرستاده نمی‌شوند. `HR_RESUME_SUMMARY_MODEL` اختیاری است و در نبود آن مدل استخراج انتخاب می‌شود.

۲۰ ورودی مرجع در `backend/tests/golden/resume_summary_v1.json` وجود دارد. پس از تغییر پرامپت، از پوشهٔ بک‌اند اجرا کنید:

```powershell
uv run python -m scripts.eval_resume_summary
uv run python -m scripts.eval_resume_summary --live
```

فرمان اول فقط کنترل آفلاین دادهٔ مبناست. فرمان دوم تولید زنده، زبان، طول، موارد نامشخص و عبارت‌های ارزیابانه را می‌سنجد و سهمیهٔ API مصرف می‌کند. تست‌های خودکار قرارداد با مدل ساختگی اجرا می‌شوند.

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
