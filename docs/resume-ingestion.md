# دریافت و پردازش رزومه

تسک‌های مرتبط: [۱۱](../.scratch/hr-ai-assistant/issues/11-upload-parse-candidate-talent-pool.md)، [۱۶](../.scratch/hr-ai-assistant/issues/16-email-in-ingestion.md)، [۲۰](../.scratch/hr-ai-assistant/issues/20-needs-review-queue.md) و [۲۱](../.scratch/hr-ai-assistant/issues/21-parse-hardening-ocr-vision.md).

## قابلیت‌ها

- آپلود PDF، DOCX، TXT، تصویر PNG/JPEG/WebP/TIFF و تبدیل مشروط DOC/RTF.
- استخراج ساختاریافته با حفظ زبان فارسی، انگلیسی یا ترکیبی؛ ذخیرهٔ متن کامل حتی وقتی ورودی مدل کوتاه می‌شود.
- تشخیص فایل یکسان در هر سازمان با SHA-256.
- PDF فاقد متن کافی ← OCR فارسی و انگلیسی ← پردازش تصویری در صورت شکست OCR.
- دریافت ایمیل با webhook احرازشده، ذخیرهٔ پایدار پیام خام پیش از پاسخ HTTP و پردازش بعدی با worker.
- جلوگیری از تحویل تکراری با Message-ID و گیرنده؛ در نبود Message-ID، هش پیام خام جایگزین می‌شود.
- پردازش پیوست‌ها پیش از بدنه؛ پشتیبانی از UTF-8، عنوان و نام فایل فارسی و بدنهٔ HTML به‌صورت متن.
- بررسی نوع، اندازه و تعداد پیوست، بررسی ClamAV و مسدود ماندن سند هنگام خطای اسکنر.
- صف بررسی `/review`، تاریخچهٔ همهٔ اسناد، پیش‌نمایش امن PDF/تصویر و فرم اصلاح اطلاعات.
- پذیرش انسانی، ثبت Activity، حفظ خروجی خام مدل و جلوگیری از بازنویسی پروفایل موجود در بازپردازش.
- اسکن مجدد پیوست قرنطینه‌شده بعد از رفع اشکال اسکنر؛ استخراج تا موفقیت اسکن شروع نمی‌شود.

## تنظیمات محلی

نمونهٔ تنظیمات در [backend/.env.example](../backend/.env.example) است. فقط مقادیر مورد نیاز را به `.env` موجود اضافه کنید؛ اعتبارنامه‌های فعلی دیتابیس را جایگزین نکنید.

### مدل رایگان محلی

اگر OpenAI API اعتبار ندارد، می‌توان پردازش رزومه را با Ollama روی همان رایانه انجام داد. این مسیر به حساب یا کلید ابری نیاز ندارد و برای رزومه‌های تصویری از مدل دارای بینایی ماشین استفاده می‌کند. روی Windows، [Ollama](https://docs.ollama.com/windows) را نصب و مدل را دریافت کنید:

```powershell
ollama pull qwen3-vl:4b
```

در `backend/.env` این مقدارها را تنظیم و بک‌اند را دوباره اجرا کنید:

```env
HR_RESUME_AI_PROVIDER=ollama
HR_OLLAMA_BASE_URL=http://127.0.0.1:11434/v1/
HR_RESUME_EXTRACT_MODEL=qwen3-vl:4b
HR_RESUME_EXTRACT_MODEL_ESCALATION=qwen3-vl:4b
```

برای بازگشت به OpenAI، مقدار `HR_RESUME_AI_PROVIDER=openai` و نام مدل‌های OpenAI را تنظیم کنید. پردازش محلی روی CPU ممکن است کند باشد؛ خروجی را در صف بررسی بازبینی کنید.

### پردازش ابری با Groq

Groq از کلید و آدرس API جداگانه استفاده می‌کند. برای مدل تصویری دارای خروجی ساختاریافته، تنظیمات زیر را در `backend/.env` قرار دهید و بک‌اند را دوباره اجرا کنید:

```env
HR_RESUME_AI_PROVIDER=groq
HR_GROQ_API_KEY=کلید-شخصی-Groq
HR_GROQ_BASE_URL=https://api.groq.com/openai/v1
HR_RESUME_EXTRACT_MODEL=qwen/qwen3.8-27b
HR_RESUME_EXTRACT_MODEL_ESCALATION=qwen/qwen3.8-27b
```

کلید Groq را در `HR_OPENAI_API_KEY` قرار ندهید. مدل انتخاب‌شده طبق [مستندات Groq](https://console.groq.com/docs/vision) ورودی تصویری را می‌پذیرد و حداکثر سه تصویر را در هر درخواست پردازش می‌کند؛ برای PDFهای تصویری طولانی‌تر ممکن است بازبینی انسانی لازم شود. محدودیت تعداد درخواست و توکن به حساب و طرح Groq بستگی دارد.

برای تست ایمیل، دامنهٔ فرضی `jobs.yourdomain.com` کافی است. نیازی به خرید دامنه، تغییر DNS، ارسال SMTP یا اتصال Cloudflare نیست. آدرس هر سازمان بعد از تنظیم متغیرهای محیطی در `/settings/ingestion` دیده می‌شود.

نمونه در PowerShell، از پوشهٔ `backend`:

```powershell
$env:HR_INBOUND_DOMAIN = "jobs.yourdomain.com"
$env:HR_INBOUND_WEBHOOK_SECRET = "local-only-change-me"
$env:HR_COOKIE_SECURE = "false"
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

همین دو متغیر مربوط به ایمیل باید در محیط ترمینال اجرای ابزار تست هم تنظیم باشند. سپس با آدرس نمایش‌داده‌شده در تنظیمات سازمان:

```powershell
uv run python -m scripts.mock_inbound --recipient "resumes+ORG-SLUG@jobs.yourdomain.com" --save local-test.eml
uv run python -m scripts.mock_inbound --recipient "resumes+ORG-SLUG@jobs.yourdomain.com" --file local-test.eml
```

بار اول `accepted: true, duplicate: false` و بار دوم `duplicate: true` برمی‌گردد. Worker برنامه پیام را از صف Postgres پردازش می‌کند. فایل `local-test.eml` شامل پیام ساختگی با عنوان و ضمیمهٔ فارسی است. ابزار هیچ ایمیلی به شخص واقعی ارسال نمی‌کند.

این ابزار دریافت ایمیل را شبیه‌سازی می‌کند؛ روی سرور عادی، استخراج بعدی از تنظیمات واقعی مدل و اسکنر استفاده می‌کند. تست‌های خودکار زیر، مدل و ابزارهای خارجی را با نمونهٔ ساختگی جایگزین می‌کنند و هزینهٔ API ندارند.

## ابزارهای پردازش سند

مسیر فایل اجرایی را می‌توان در تنظیمات تعیین کرد؛ در Windows مسیر کامل فایل اجرایی هم پذیرفته می‌شود.

| ابزار | تنظیمات | رفتار در نبود ابزار |
|---|---|---|
| ClamAV با پایگاه امضای به‌روز | `HR_CLAMAV_COMMAND` | پیوست ایمیلی قرنطینه و در صف بررسی نمایش داده می‌شود. پذیرش و دریافت فایل مسدود می‌ماند؛ بعد از رفع مشکل، «بررسی دوبارهٔ ایمنی» را اجرا کنید. |
| OCRmyPDF و Tesseract با بسته‌های `fas` و `eng` | `HR_OCR_ENABLED`، `HR_OCR_COMMAND` | در صورت فعال بودن، مسیر تصویری امتحان می‌شود؛ شکست آن به بررسی انسانی می‌رود. |
| LibreOffice | `HR_LEGACY_CONVERSION_ENABLED`، `HR_LIBREOFFICE_COMMAND` | فایل DOC/RTF با راهنمای بارگذاری PDF/DOCX به صف بررسی می‌رود. |
| مدل دارای قابلیت تصویری | `HR_VISION_ENABLED` و مدل‌های استخراج | در صورت نبود اعتبارنامه یا شکست پردازش تصویر، سند در صف بررسی می‌ماند. |

تبدیل DOC/RTF به‌صورت پیش‌فرض خاموش است. فرمان OCR از `--skip-text --language fas+eng` استفاده می‌کند. این گزینه‌ها با [مستندات OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF/blob/main/docs/advanced.md) سازگار هستند.

## ذخیرهٔ پیام خام

در محیط محلی، فایل `.eml` با نام مبتنی بر هش، ابتدا در فایل موقت نوشته و `fsync` می‌شود، سپس جایگزینی اتمیک انجام می‌شود. بعد از آن رکورد دریافت در دیتابیس commit و پاسخ ۲۰۰ ارسال می‌شود. محل پیش‌فرض `backend/.data/inbound` است و وارد Git نمی‌شود.

برای استقرار چندنمونه‌ای یا ذخیرهٔ ابری، `HR_INBOUND_S3_BUCKET` را تنظیم کنید. endpoint اختیاری `HR_INBOUND_S3_ENDPOINT_URL` امکان استفاده از R2، MinIO یا سایر ذخیره‌سازهای سازگار با S3 را می‌دهد. اعتبارنامه‌ها از محیط یا پروفایل استاندارد AWS خوانده می‌شوند. خطای نوشتن در ذخیره‌ساز نباید پاسخ موفق دریافت ایجاد کند.

در استفاده از دیسک محلی، مسیر ذخیره باید پایدار و برای همهٔ workerهای مربوط قابل دسترسی باشد. دیتابیس و پیام‌های خام باید با هم پشتیبان‌گیری شوند.

## Cloudflare برای مرحلهٔ بعد

[Worker](../infra/email-worker/worker.mjs) و [نمونهٔ تنظیمات](../infra/email-worker/wrangler.jsonc) آماده‌اند، اما هیچ دامنه، DNS یا Worker واقعی در این کار تنظیم یا منتشر نشده است.

Worker پیام خام را همراه `X-Webhook-Secret` و گیرندهٔ واقعی SMTP در `X-Envelope-To` ارسال می‌کند و هم‌زمان به صندوق پشتیبان می‌فرستد. گیرندهٔ نامعتبر با `setReject` رد می‌شود. برای اتصال واقعی بعداً باید دامنه و مسیر webhook جایگزین، مقصد پشتیبان در Cloudflare تأیید و secret مشترک به‌عنوان secret محیط Worker تنظیم شود. طراحی بر اساس [رابط رسمی Email Worker](https://developers.cloudflare.com/email-service/api/route-emails/email-handler/) است.

فایل پشتیبان را می‌توان با همان ابزار `scripts.mock_inbound --file` بازپخش کرد. شناسهٔ پیام و گیرنده از پردازش دوباره جلوگیری می‌کنند.

## تست و محدودیت اعتبارسنجی

- `backend/tests/test_resume_ingestion.py`: دریافت پایدار، تحویل تکراری، MIME فارسی، قرنطینه، اسکن مجدد، صف، اصلاح پروفایل، دسترسی سازمانی، پیش‌نمایش، S3 و مسیرهای OCR/تصویر/تبدیل.
- `frontend/src/lib/review.test.ts`: آماده‌سازی امن اطلاعات ناقص برای فرم، با حفظ زبان و تاریخ رزومه.
- `node --test infra/email-worker/worker.test.mjs`: مسیریابی، webhook، پشتیبان و رد گیرندهٔ نامعتبر بدون تماس خارجی.
- بررسی مرورگری با Edge و Playwright روی دیتابیس مجزای `hr_test`: بارگذاری PDF اسکن‌شده، تصویر و RTF، پیش‌نمایش، اصلاح و پذیرش، ایمیل فارسی، تحویل تکراری، رد سند، تاریخچه و عرض موبایل.

در تست‌های خودکار و مرورگری، خروجی مدل، OCR، تبدیل LibreOffice و اسکن آنتی‌ویروس ساختگی بوده‌اند؛ پردازش PDF/تصویر، دیتابیس، HTTP و رابط مرورگر واقعی بوده‌اند. اجرای واقعی OCR فارسی/انگلیسی، LibreOffice، پایگاه کامل ClamAV، مدل پولی و سرویس ابری هنوز در این محیط تأیید نشده است. این ابزارهای سیستمی در زمان اجرای کار روی ماشین حاضر نبودند؛ برنامه در نبود آن‌ها مسیر جایگزین یا وضعیت صریح بررسی را نشان می‌دهد.

تنظیمات دسترسی ادمین تست باید به دیتابیس قابل‌آزمایش اشاره کند. مجموعهٔ تست فقط دیتابیس ثابت `hr_test` را حذف و دوباره ایجاد می‌کند؛ برای اجرای محلی `HR_TEST_ADMIN_URL` را طبق راهنمای اصلی پروژه تنظیم کنید.

## Repair 29 — current UI and verification boundary (2026-10-31)

The Material UI continuation now actually registers `/review` and
`/settings/ingestion`, with links and the unresolved count in the desktop/mobile
shell and header. Review includes queue/history, full partial-profile editing,
original download and safe preview, accept/dismiss, quarantine rescan and mail
receipt failures. Settings show the org forwarding address and disabled-service
guidance. Review decisions refresh counts; upload and window focus refresh the
shell count. Failed receipt recovery remains manual upload or operator replay
of the durable message; there is no invented retry API or live mail setup.

Prior browser-verification statements above describe historical work, not
acceptance of this continuation. This repair follows the confirmed API/Postgres
test boundary only; frontend validation is static lint/typecheck/build. Desktop,
mobile, clipboard, safe-preview and screen-reader browser acceptance of the new
screens is deferred. No DNS, real mail, paid inference or remote storage calls
were used. Diff date values and certificate dates now use the existing Jalali
presentation helper without changing API/storage values.
