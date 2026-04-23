from django import forms
from .models import TeacherAvailability, Booking
from django.utils import timezone

class TeacherAvailabilityForm(forms.ModelForm):
    class Meta:
        model = TeacherAvailability
        fields = ['day_of_week', 'start_time', 'end_time', 'timezone', 'is_recurring', 'specific_date']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'specific_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError("End time must be after start time.")
        return cleaned_data

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['course', 'scheduled_start', 'scheduled_end', 'notes']
        widgets = {
            'scheduled_start': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'scheduled_end': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        self.teacher = kwargs.pop('teacher', None)
        self.student = kwargs.pop('student', None)
        super().__init__(*args, **kwargs)
        if self.teacher:
            self.fields['course'].queryset = self.teacher.course_set.all()

    def clean(self):
        cleaned_data = super().clean()
        scheduled_start = cleaned_data.get('scheduled_start')
        scheduled_end = cleaned_data.get('scheduled_end')
        if scheduled_start and scheduled_end:
            if scheduled_start >= scheduled_end:
                raise forms.ValidationError("End time must be after start time.")
            if scheduled_start <= timezone.now():
                raise forms.ValidationError("Booking start time must be in the future.")
        return cleaned_data