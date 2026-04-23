# EduVerse Cloudflare Tunnel Setup

## الهدف
تشغيل المنصة محلياً ثم فتحها على جهاز آخر باستخدام Cloudflare Tunnel، مع دعم WebRTC للصوت والصورة.

## المتطلبات
- حساب Cloudflare
- تثبيت `cloudflared`
- المشروع يعمل محلياً على `http://127.0.0.1:8000`

## خطوات التثبيت

### 1. تثبيت cloudflared

macOS:
```bash
brew install cloudflare/cloudflare/cloudflared
```

Windows (PowerShell):
```powershell
choco install cloudflare-cli
```

Linux:
```bash
sudo apt install cloudflared
```

## 2. تشغيل المشروع محلياً

في مجلد المشروع:
```bash
python manage.py runserver 0.0.0.0:8000
```

يفضل تشغيل Daphne أيضًا للجلسات الحية:
```bash
daphne -b 0.0.0.0 -p 8001 eduverse.asgi_channels:application
```

## 3. تشغيل نفق Cloudflare

في نافذة طرفية جديدة:
```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

أو إذا كنت تريد توجيه WebSocket وHTTP:
```bash
cloudflared tunnel --url http://127.0.0.1:8000 --url http://127.0.0.1:8001
```

## 4. نسخ رابط النفق

بعد تشغيل `cloudflared`، سيظهر رابط من الشكل:
```text
https://abc123.trycloudflare.com
```

انسخ هذا الرابط وأدخلها في `.env`:
```text
CLOUDFLARE_TUNNEL_URL=https://abc123.trycloudflare.com
```

## 5. تحديث `.env`
تأكد من أن القيم التالية موجودة:
```text
ALLOWED_HOSTS=localhost,127.0.0.1,*.trycloudflare.com
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,https://localhost:8000,https://127.0.0.1:8000,https://*.trycloudflare.com
SITE_BASE_URL=https://abc123.trycloudflare.com
```

## 6. اختبر من جهاز آخر

افتح رابط `https://abc123.trycloudflare.com` من هاتف أو حاسوب آخر.

- يجب أن يعمل الصوت والمايك إذا منحت الأذونات.
- يجب أن يعمل WebSocket وWebRTC عبر `wss://` تلقائياً.

## ملاحظات مهمة
- إذا كان الصوت أو الفيديو لا يعمل، فعادةً السبب هو عدم وجود TURN صالح أو مشاكل NAT. استخدم خدمة TURN مدفوعة أو أضف TURN خاص في `.env`.
## ملاحظات مهمة لـ WebRTC عبر Cloudflare Tunnel

- Cloudflare Tunnel يدعم WebRTC، لكن قد يحتاج إلى تكوين خاص إذا كان هناك مشاكل في الاتصال.
- تأكد من أن الجهاز الآخر يفتح الرابط عبر HTTPS (يجب أن يكون `https://...trycloudflare.com`).
- إذا فشل الاتصال، جرب فتح المنصة محليًا على نفس الجهاز أولاً للتأكد من عمل WebRTC.
- TURN server مضبوط للمساعدة في الشبكات المختلفة، لكن قد يحتاج إلى TURN server مدفوع إذا استمر الفشل.
- في حالة فشل مستمر، استخدم نفس الشبكة للاختبار (مثل WiFi نفسه) بدلاً من شبكات مختلفة.
- لا تستخدم `http://192.168.x.x` إلا إذا عززت الاتصال بشهادة SSL محلية.
