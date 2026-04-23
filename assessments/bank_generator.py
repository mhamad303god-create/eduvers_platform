from django.db import transaction

from courses.models import Course, Subject
from .models import Assessment, AssessmentQuestion, QuestionChoice


LEVELS = [
    ("beginner", "مبتدئ"),
    ("intermediate", "متوسط"),
    ("advanced", "متقدم"),
]


DEFAULT_SUBJECTS = [
    ("رياضيات", "MATH"),
    ("علوم", "SCI"),
    ("لغة إنجليزية", "ENG"),
    ("لغة عربية", "ARB"),
    ("برمجة", "PRG"),
]


def _ensure_subjects_exist():
    if Subject.objects.filter(is_active=True).exists():
        return list(Subject.objects.filter(is_active=True))

    subjects = []
    for name, code in DEFAULT_SUBJECTS:
        subject, _ = Subject.objects.get_or_create(
            subject_name=name,
            defaults={
                "subject_code": code,
                "description": f"مادة {name}",
                "is_active": True,
            },
        )
        subjects.append(subject)
    return subjects


def _build_question_specs(subject_name, level_label):
    # 10 questions x 10 points = 100
    return [
        {
            "text": f"[{subject_name} - {level_label}] اختيار استراتيجية التعلم المناسبة يساعد على فهم أسرع.",
            "type": "true_false",
            "choices": [("صح", True), ("خطأ", False)],
        },
        {
            "text": f"ما أفضل طريقة لاكتساب أساس قوي في {subject_name} بمستوى {level_label}؟",
            "type": "multiple_choice",
            "choices": [
                ("الممارسة المنتظمة مع مراجعة الأخطاء", True),
                ("الحفظ فقط بدون تدريب", False),
                ("تجاهل الأساسيات", False),
                ("الاكتفاء بالمشاهدة دون تطبيق", False),
            ],
        },
        {
            "text": f"حل الأسئلة المتدرجة في الصعوبة يحسن الأداء في {subject_name}.",
            "type": "true_false",
            "choices": [("صح", True), ("خطأ", False)],
        },
        {
            "text": f"عند دراسة {subject_name}، ما السلوك الأكثر فاعلية؟",
            "type": "multiple_choice",
            "choices": [
                ("تلخيص المفاهيم ثم اختبار نفسك", True),
                ("تأجيل المراجعة حتى آخر يوم", False),
                ("تجاهل التغذية الراجعة", False),
                ("حل نفس النوع فقط من الأسئلة", False),
            ],
        },
        {
            "text": "إدارة الوقت داخل الاختبار تؤثر مباشرة على النتيجة.",
            "type": "true_false",
            "choices": [("صح", True), ("خطأ", False)],
        },
        {
            "text": "أي خيار يعكس تعلمًا عميقًا؟",
            "type": "multiple_choice",
            "choices": [
                ("فهم السبب وراء الإجابة الصحيحة", True),
                ("تكرار الإجابة دون فهم", False),
                ("نسخ الحل دون تحليل", False),
                ("ترك الأسئلة الصعبة دائمًا", False),
            ],
        },
        {
            "text": "المراجعة الدورية القصيرة أفضل من جلسة واحدة طويلة جدًا.",
            "type": "true_false",
            "choices": [("صح", True), ("خطأ", False)],
        },
        {
            "text": f"لاختيار خطة مناسبة لمستوى {level_label}، ماذا تفعل أولًا؟",
            "type": "multiple_choice",
            "choices": [
                ("تحديد نقاط القوة والضعف", True),
                ("البدء في أصعب محتوى فورًا بدون تقييم", False),
                ("تجاهل الأهداف التعليمية", False),
                ("الدراسة العشوائية بدون خطة", False),
            ],
        },
        {
            "text": "حل الاختبارات التجريبية قبل الاختبار الحقيقي مفيد.",
            "type": "true_false",
            "choices": [("صح", True), ("خطأ", False)],
        },
        {
            "text": "ما أفضل مؤشر لتحسن مستواك؟",
            "type": "multiple_choice",
            "choices": [
                ("تحسن الدرجات مع انخفاض عدد الأخطاء المتكررة", True),
                ("زيادة الوقت المستغرق دون تحسن النتائج", False),
                ("الاعتماد على التخمين دائمًا", False),
                ("تجنب الأسئلة الجديدة", False),
            ],
        },
    ]


@transaction.atomic
def generate_assessment_bank_for_all_subjects(teacher=None):
    subjects = _ensure_subjects_exist()

    created_assessments = 0
    created_questions = 0

    for subject in subjects:
        for level_code, level_label in LEVELS:
            related_course = Course.objects.filter(
                status="published",
                subject=subject,
                level=level_code,
            ).order_by("-created_at").first()
            if not related_course:
                # Fallback: keep assessment linked to a published course in the same subject
                # even if that exact level is not available yet.
                related_course = Course.objects.filter(
                    status="published",
                    subject=subject,
                ).order_by("-created_at").first()

            title = f"اختبار {subject.subject_name} - {level_label}"
            assessment, created = Assessment.objects.get_or_create(
                title=title,
                subject=subject,
                type="exam",
                defaults={
                    "description": f"اختبار شامل لمادة {subject.subject_name} - مستوى {level_label}.",
                    "teacher": teacher,
                    "course": related_course,
                    "duration_minutes": 30,
                    "total_points": 100,
                    "passing_score": 60,
                    "max_attempts": 3,
                    "is_randomized": True,
                    "show_results_immediately": True,
                    "status": "published",
                },
            )

            # keep assessment up-to-date even when it already exists
            updated = False
            if assessment.status != "published":
                assessment.status = "published"
                updated = True
            if related_course and assessment.course_id != related_course.course_id:
                assessment.course = related_course
                updated = True
            if teacher and assessment.teacher_id is None:
                assessment.teacher = teacher
                updated = True
            if updated:
                assessment.save()

            if created:
                created_assessments += 1

            if assessment.assessmentquestion_set.exists():
                continue

            specs = _build_question_specs(subject.subject_name, level_label)
            for idx, spec in enumerate(specs, start=1):
                question = AssessmentQuestion.objects.create(
                    assessment=assessment,
                    question_text=spec["text"],
                    question_type=spec["type"],
                    points=10,
                    difficulty="easy" if idx <= 3 else ("medium" if idx <= 7 else "hard"),
                    explanation="راجع أساسيات السؤال وحاول تحليل الخيارات قبل الاختيار.",
                    order_index=idx,
                )
                for choice_idx, (choice_text, is_correct) in enumerate(spec["choices"], start=1):
                    QuestionChoice.objects.create(
                        question=question,
                        choice_text=choice_text,
                        is_correct=is_correct,
                        order_index=choice_idx,
                    )
                created_questions += 1

    return {
        "subjects_count": len(subjects),
        "created_assessments": created_assessments,
        "created_questions": created_questions,
        "total_published_assessments": Assessment.objects.filter(status="published").count(),
    }
