from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.db import transaction
import logging
from .models import Role, UserRole, StudentProfile, TeacherProfile

logger = logging.getLogger(__name__)

User = get_user_model()


class CustomUserCreationForm(forms.ModelForm):
    role = forms.ChoiceField(
        choices=[
            ('student', 'Student'),
            ('teacher', 'Teacher'),
        ],
        widget=forms.HiddenInput(),
        initial='student'
    )
    
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': '••••••••'}),
    )
    password2 = forms.CharField(
        label="Confirm Password",
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': '••••••••'}),
    )

    # Minimalist Fields
    grade_level = forms.ChoiceField(
        choices=[
            ('elementary', 'Elementary'),
            ('middle', 'Middle'),
            ('high', 'High'),
            ('university', 'University'),
            ('other', 'Other'),
        ],
        required=False,
        label='Grade Level'
    )
    school_name = forms.CharField(max_length=255, required=False, label='School Name')
    parent_name = forms.CharField(max_length=255, required=False, label='Parent Name')
    parent_email = forms.EmailField(required=False, label='Parent Email')
    
    bio = forms.CharField(required=False, widget=forms.Textarea, label='Bio')
    subjects = forms.CharField(required=False, label='Subjects')
    hourly_rate = forms.DecimalField(max_digits=10, decimal_places=2, required=False, label='Hourly Rate')

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
             # Add classes to all fields
            if 'class' not in field.widget.attrs:
                field.widget.attrs.update({'class': 'form-input', 'placeholder': ' '})
        self.fields['role'].required = True

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password2")
        email = cleaned_data.get("email")

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("كلمة المرور غير متطابقة.")
            
        if email and User.objects.filter(email=email).exists():
             raise forms.ValidationError("البريد الإلكتروني مسجل بالفعل.")

        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.username = user.email  # Force username to be email
        
        role_name = self.cleaned_data.get('role', 'student')

        if commit:
            user.save()
            logger.info(f"User {user.email} created (Robust Mode).")

            try:
                # 1. Get/Create Role
                role, _ = Role.objects.get_or_create(
                    role_name=role_name,
                    defaults={'description': f'{role_name.title()} Role'}
                )
                
                # 2. Assign Role
                UserRole.objects.create(user=user, role=role)
                
                # 3. Create Profile
                if role_name == 'student':
                    StudentProfile.objects.create(
                        user=user,
                        grade_level=self.cleaned_data.get('grade_level', 'other'),
                        school_name=self.cleaned_data.get('school_name', ''),
                        parent_name=self.cleaned_data.get('parent_name', ''),
                        parent_email=self.cleaned_data.get('parent_email', '')
                    )
                elif role_name == 'teacher':
                    subjects_str = self.cleaned_data.get('subjects', '')
                    subjects_list = [s.strip() for s in subjects_str.split(',') if s.strip()]
                    TeacherProfile.objects.create(
                        user=user,
                        bio=self.cleaned_data.get('bio', ''),
                        subjects=subjects_list,
                        hourly_rate=self.cleaned_data.get('hourly_rate') or 0.0
                    )
            except Exception as e:
                logger.error(f"Profile creation failed: {e}")
                # Don't delete user, just log error and maybe self-heal later
                # user.delete() 
                # Better to let user exist and fix profile on dashboard redirect
        
        return user


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': ' '}),
        label='Email'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].widget.attrs.update({'class': 'form-input', 'placeholder': ' '})


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'avatar']

class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ['grade_level', 'school_name', 'parent_name', 'parent_phone']

class TeacherProfileForm(forms.ModelForm):
    class Meta:
        model = TeacherProfile
        fields = ['bio', 'subjects', 'hourly_rate']