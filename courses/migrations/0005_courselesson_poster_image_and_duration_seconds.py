from django.db import migrations, models
import courses.models


def populate_duration_seconds(apps, schema_editor):
    CourseLesson = apps.get_model('courses', 'CourseLesson')
    for lesson in CourseLesson.objects.exclude(video_duration__isnull=True):
        if not lesson.video_duration_seconds:
            lesson.video_duration_seconds = lesson.video_duration * 60
            lesson.save(update_fields=['video_duration_seconds'])


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0004_alter_course_preview_video_alter_course_thumbnail'),
    ]

    operations = [
        migrations.AddField(
            model_name='courselesson',
            name='poster_image',
            field=models.ImageField(blank=True, max_length=255, null=True, upload_to=courses.models.lesson_poster_upload_path),
        ),
        migrations.AddField(
            model_name='courselesson',
            name='video_duration_seconds',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(populate_duration_seconds, migrations.RunPython.noop),
    ]
