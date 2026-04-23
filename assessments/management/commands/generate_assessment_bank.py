from django.core.management.base import BaseCommand

from accounts.models import TeacherProfile
from assessments.bank_generator import generate_assessment_bank_for_all_subjects


class Command(BaseCommand):
    help = "Generate published assessments for all subjects and levels (beginner/intermediate/advanced)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--teacher-id",
            type=int,
            default=None,
            help="Optional teacher_id to assign generated assessments to a specific teacher.",
        )

    def handle(self, *args, **options):
        teacher = None
        teacher_id = options.get("teacher_id")
        if teacher_id:
            teacher = TeacherProfile.objects.filter(teacher_id=teacher_id).first()
            if not teacher:
                self.stdout.write(self.style.WARNING(f"TeacherProfile {teacher_id} not found. Using global assessments."))

        result = generate_assessment_bank_for_all_subjects(teacher=teacher)
        self.stdout.write(self.style.SUCCESS("Assessment bank generation completed."))
        self.stdout.write(f"Subjects: {result['subjects_count']}")
        self.stdout.write(f"Created assessments: {result['created_assessments']}")
        self.stdout.write(f"Created questions: {result['created_questions']}")
        self.stdout.write(f"Total published assessments: {result['total_published_assessments']}")
