# 🎓 منصة EduVerse التعليمية - دليل شامل

<div dir="rtl">

## 📖 نظرة عامة

منصة EduVerse هي منصة تعليمية متكاملة مبنية بـ Django، توفر تجربة تعليمية شاملة للطلاب والمعلمين.

---

## ✨ المميزات الرئيسية

### 🎯 للطلاب
- ✅ التسجيل في الكورسات والدروس
- 📊 تتبع التقدم الدراسي
- 📝 حل الاختبارات والواجبات
- 📅 حجز جلسات خاصة مع المعلمين
- 💬 التواصل المباشر مع المعلمين
- 🎓 الحصول على شهادات معتمدة
- 📈 لوحة تحليلات شخصية

### 👨‍🏫 للمعلمين
- 📚 إنشاء وإدارة الكورسات
- 🎬 رفع محتوى الفيديو والملفات
- ✍️ إنشاء اختبارات وتقييمات
- 📊 متابعة أداء الطلاب
- 💰 إدارة المدفوعات والأرباح
- 🗓️ إدارة جدول الحجوزات
- 📹 جلسات Zoom مباشرة

### 🔧 للإداريين
- 👥 إدارة المستخدمين والصلاحيات
- 📊 إحصائيات شاملة للمنصة
- 💳 إدارة المدفوعات والمعاملات
- 🎓 إدارة المواد الدراسية
- 📧 إرسال الإشعارات الجماعية

---

## 🚀 التقنيات المستخدمة

### Backend
- **Django 5.1.5** - إطار العمل الرئيسي
- **Django REST Framework** - واجهات برمجية RESTful
- **PostgreSQL** - قاعدة البيانات
- **Redis** - التخزين المؤقت والطوابير
- **Celery** - المهام الخلفية والمجدولة
- **Django Channels** - WebSocket للإشعارات الفورية

### الدفع والتكامل
- **Stripe** - بوابة دفع عالمية
- **Moyasar** - بوابة دفع سعودية
- **Zoom API** - جلسات فيديو مباشرة
- **AWS S3** - تخزين الملفات السحابي
- **CloudFront** - توزيع المحتوى (CDN)

### المستندات والشهادات
- **ReportLab** - توليد ملفات PDF
- **QRCode** - رموز QR للتحقق
- **Pillow** - معالجة الصور

### الأمان والمصادقة
- **Django Allauth** - المصادقة عبر OAuth
- **JWT** - رموز الوصول الآمنة
- **Cryptography** - التشفير

---

## 📁 هيكل المشروع

```
eduverseplatform/
├── accounts/               # إدارة المستخدمين والحسابات
│   ├── models.py          # User, StudentProfile, TeacherProfile
│   ├── views.py           # تسجيل الدخول، لوحات التحكم
│   └── forms.py           # نماذج التسجيل
│
├── courses/               # إدارة الكورسات
│   ├── models.py          # Course, Lesson, Enrollment
│   ├── views.py           # عرض الكورسات وإدارتها
│   ├── search.py          # محرك البحث المتقدم
│   ├── analytics.py       # تحليلات وإحصائيات
│   ├── certificate_generator.py  # توليد الشهادات
│   ├── storage_backends.py       # تكامل AWS S3
│   └── tasks.py           # مهام Celery الخلفية
│
├── assessments/           # الاختبارات والتقييمات
│   ├── models.py          # Assessment, Question, Attempt
│   └── views.py           # إدارة وحل الاختبارات
│
├── bookings/              # نظام الحجوزات
│   ├── models.py          # Booking, TeacherAvailability
│   ├── zoom_integration.py   # تكامل Zoom
│   ├── booking_manager.py    # منع التعارضات
│   └── tasks.py           # تذكيرات الحجز
│
├── payments/              # المدفوعات
│   ├── models.py          # Payment, Wallet
│   ├── payment_gateways.py   # Stripe & Moyasar
│   └── views.py           # معالجة الدفع
│
├── notifications/         # الإشعارات
│   ├── models.py          # Notification, Message
│   ├── consumers.py       # WebSocket consumers
│   └── routing.py         # WebSocket routing
│
├── static/                # ملفات الواجهة
│   ├── css/              # ملفات التنسيق
│   └── js/               # ملفات JavaScript
│
├── templates/             # قوالب HTML
│   ├── accounts/
│   ├── courses/
│   ├── assessments/
│   └── bookings/
│
├── eduverse/              # إعدادات المشروع
│   ├── settings.py       # الإعدادات الرئيسية
│   ├── urls.py           # الروابط الرئيسية
│   ├── celery.py         # إعدادات Celery
│   └── asgi_channels.py  # إعدادات ASGI/WebSocket
│
├── requirements.txt       # المكتبات المطلوبة
├── .env.example          # مثال لملف البيئة
└── manage.py             # أداة إدارة Django
```

---

## 🔧 التثبيت والإعداد

### 1️⃣ المتطلبات الأساسية
```bash
# تثبيت Python 3.10+
python --version

# تثبيت PostgreSQL
# تثبيت Redis
```

### 2️⃣ نسخ المشروع
```bash
git clone <repository-url>
cd eduverseplatform
```

### 3️⃣ إنشاء بيئة افتراضية
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 4️⃣ تثبيت المكتبات
```bash
pip install -r requirements.txt
```

### 5️⃣ إعداد ملف البيئة
```bash
copy .env.example .env
# قم بتعديل الملف وإضافة بياناتك
```

### 6️⃣ إعداد قاعدة البيانات
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py populate_data  # بيانات تجريبية اختيارية
```

### 7️⃣ تشغيل الخادم
```bash
# الخادم الرئيسي
python manage.py runserver

# Celery Worker (نافذة منفصلة)
celery -A eduverse worker --loglevel=info

# Celery Beat (نافذة منفصلة)
celery -A eduverse beat --loglevel=info

# WebSocket Server (نافذة منفصلة)
daphne -b 0.0.0.0 -p 8001 eduverse.asgi_channels:application
```

---

## 🎯 الميزات المتقدمة

### 🔍 نظام البحث الذكي
```python
# مثال على استخدام محرك البحث
from courses.search import CourseSearchEngine

engine = CourseSearchEngine()
results = engine.search('برمجة', level='beginner', price_max=500)
```

### 📊 التحليلات والإحصائيات
```python
# تحليلات الطالب
from courses.analytics import StudentAnalytics

analytics = StudentAnalytics(student_profile)
overview = analytics.get_overview()
progress = analytics.get_progress_by_course()
```

### 💳 معالجة الدفع
```python
# إنشاء عملية دفع
from payments.payment_gateways import PaymentProcessor

processor = PaymentProcessor(gateway_name='stripe')
result = processor.process_payment(
    user=user,
    amount=299.99,
    currency='SAR',
    payment_method='credit_card'
)
```

### 🎓 توليد الشهادات
```python
# إصدار شهادة
from courses.certificate_generator import CertificateGenerator

generator = CertificateGenerator()
certificate = generator.generate_certificate(enrollment)
```

### 📹 تكامل Zoom
```python
# إنشاء اجتماع Zoom
from bookings.zoom_integration import ZoomIntegration

zoom = ZoomIntegration()
meeting = zoom.create_meeting(
    topic='درس خاص - رياضيات',
    start_time=start_datetime,
    duration=60
)
```

---

## 🔒 الأمان والحماية

### التدابير الأمنية المطبقة
- ✅ حماية CSRF
- ✅ تشفير كلمات المرور
- ✅ حماية XSS
- ✅ SQL Injection Prevention
- ✅ Rate Limiting
- ✅ HTTPS Enforcement (للإنتاج)
- ✅ JWT للمصادقة
- ✅ Webhook Signature Verification

### أفضل الممارسات
```python
# استخدام متغيرات البيئة
from decouple import config

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)

# تشفير البيانات الحساسة
from cryptography.fernet import Fernet

cipher_suite = Fernet(key)
encrypted_data = cipher_suite.encrypt(data)
```

---

## 📧 المهام الخلفية

### مهام Celery المجدولة

#### يومياً
- ✉️ إرسال ملخصات يومية
- 🧹 تنظيف الملفات المؤقتة
- 💳 معالجة المدفوعات المعلقة

#### أسبوعياً
- 📊 تقارير تقدم الطلاب
- 📈 تحديث إحصائيات المنصة

#### كل ساعة
- 🔔 إشعارات الحجوزات
- 📅 تحديث حالات الحجوزات

---

## 🧪 الاختبارات

### تشغيل الاختبارات
```bash
# جميع الاختبارات
python manage.py test

# اختبارات محددة
python manage.py test accounts.tests_comprehensive

# مع تقرير التغطية
coverage run --source='.' manage.py test
coverage report
coverage html
```

### أنواع الاختبارات المتوفرة
- ✅ اختبارات المصادقة
- ✅ اختبارات الكورسات
- ✅ اختبارات البحث
- ✅ اختبارات المدفوعات
- ✅ اختبارات الحجوزات
- ✅ اختبارات التكامل الشاملة

---

## 📱 واجهة برمجة التطبيقات (API)

### نقاط النهاية الرئيسية

#### الكورسات
```
GET    /api/courses/          # قائمة الكورسات
GET    /api/courses/{id}/     # تفاصيل الكورس
POST   /api/courses/          # إنشاء كورس جديد
PUT    /api/courses/{id}/     # تحديث الكورس
DELETE /api/courses/{id}/     # حذف الكورس
```

#### البحث
```
GET    /api/search/courses/   # بحث متقدم
GET    /api/recommendations/  # توصيات شخصية
GET    /api/trending/         # الكورسات الرائجة
```

#### المدفوعات
```
POST   /payments/create-intent/      # إنشاء نية دفع
POST   /payments/{id}/confirm/       # تأكيد الدفع
POST   /payments/webhook/stripe/     # Webhook من Stripe
```

---

## 🌐 النشر (Deployment)

### الإنتاج مع Gunicorn + Nginx
راجع ملف `README_DEPLOYMENT.md` للتفاصيل الكاملة.

### النشر باستخدام Docker
```bash
docker-compose up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

---

## 📞 الدعم الفني

### لطلب المساعدة
- 📧 البريد: support@eduverse.com
- 📚 التوثيق: docs.eduverse.com
- 🐛 الأخطاء: GitHub Issues

---

## 👨‍💻 المساهمة

نرحب بمساهماتكم! يرجى:
1. Fork المشروع
2. إنشاء فرع جديد (`git checkout -b feature/amazing-feature`)
3. Commit التغييرات (`git commit -m 'إضافة ميزة رائعة'`)
4. Push إلى الفرع (`git push origin feature/amazing-feature`)
5. فتح Pull Request

---

## 📄 الترخيص

جميع الحقوق محفوظة © 2026 EduVerse Platform

---

## 🎉 شكر خاص

تم بناء هذه المنصة بالحب ❤️ والقهوة ☕ لخدمة التعليم في العالم العربي! 🌍

</div>
