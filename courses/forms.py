from django import forms
import os
from .models import Course, CourseLesson, Subject


class CourseForm(forms.ModelForm):
    preview_video = forms.FileField(
        required=False,
        label="فيديو تعريفي (Preview)",
        max_length=255
    )
    thumbnail = forms.ImageField(
        required=False,
        label="صورة الغلاف (Thumbnail)"
    )


    
    # Override JSON fields with CharField for better UX
    requirements = forms.CharField(
        required=False,
        label="المتطلبات",
        widget=forms.Textarea(attrs={
            'rows': 3, 
            'placeholder': 'المتطلب الأول\nالمتطلب الثاني'
        })
    )
    
    objectives = forms.CharField(
        required=False,
        label="الأهداف",
        widget=forms.Textarea(attrs={
            'rows': 3, 
            'placeholder': 'الهدف الأول\nالهدف الثاني'
        })
    )

    class Meta:
        model = Course
        fields = [
            'title', 'description', 'course_type', 'level',
            'max_students', 'price', 'currency', 'duration_minutes',
            'thumbnail', 'preview_video', 'status'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance or not self.instance.pk:
            self.fields['status'].initial = 'published'
            self.fields['status'].widget = forms.HiddenInput()

    def clean_requirements(self):
        data = self.cleaned_data.get('requirements', '')
        if not data or not data.strip():
            return []
        return [line.strip() for line in data.split('\n') if line.strip()]

    def clean_objectives(self):
        data = self.cleaned_data.get('objectives', '')
        if not data or not data.strip():
            return []
        return [line.strip() for line in data.split('\n') if line.strip()]

    def clean_preview_video(self):
        file_obj = self.cleaned_data.get('preview_video')
        if not file_obj:
            return file_obj
        base, ext = os.path.splitext(file_obj.name)
        max_name_len = 255
        if len(file_obj.name) > max_name_len:
            keep = max(1, max_name_len - len(ext))
            file_obj.name = f"{base[:keep]}{ext}"
        return file_obj


class CourseLessonForm(forms.ModelForm):
    class Meta:
        model = CourseLesson
        fields = [
            'title', 'description', 'content', 'video', 'video_duration',
            'order_index', 'is_free', 'status'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'content': forms.Textarea(attrs={'rows': 5}),
            'video_duration': forms.NumberInput(attrs={'min': 0, 'step': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance or not self.instance.pk:
            self.fields['status'].initial = 'published'
            self.fields['status'].widget = forms.HiddenInput()
        self.fields['video'].widget.attrs.update({'accept': 'video/mp4,video/webm,video/ogg,video/quicktime,.mp4,.webm,.ogg,.mov,.m4v'})
        self.fields['video_duration'].required = False
        self.fields['video_duration'].widget = forms.HiddenInput()


class CourseFilterForm(forms.Form):
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.filter(is_active=True),
        required=False,
        empty_label="جميع المواد"
    )
    level = forms.ChoiceField(
        choices=[('', 'جميع المستويات')] + list(Course._meta.get_field('level').choices),
        required=False
    )
    teacher = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'البحث بالمعلم'})
    )
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'البحث في العنوان أو الوصف'})
    )
