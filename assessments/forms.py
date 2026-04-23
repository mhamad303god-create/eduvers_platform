from django import forms
from .models import Assessment, AssessmentQuestion, QuestionChoice

class AssessmentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css_class = 'form-control'
            if isinstance(field.widget, forms.CheckboxInput):
                css_class = ''
            if css_class:
                current = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f"{current} {css_class}".strip()
        self.fields['title'].widget.attrs.setdefault('placeholder', 'مثال: اختبار الفصل الأول')
        self.fields['description'].widget.attrs.setdefault('placeholder', 'وصف مختصر للتقييم...')

    class Meta:
        model = Assessment
        fields = [
            'title', 'description', 'type', 'subject', 'course',
            'duration_minutes', 'total_points', 'passing_score',
            'max_attempts', 'is_randomized', 'show_results_immediately'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'duration_minutes': forms.NumberInput(attrs={'min': 1}),
            'total_points': forms.NumberInput(attrs={'min': 1}),
            'passing_score': forms.NumberInput(attrs={'min': 0, 'max': 100}),
            'max_attempts': forms.NumberInput(attrs={'min': 1}),
        }

    def clean(self):
        cleaned = super().clean()
        total_points = cleaned.get('total_points')
        passing_score = cleaned.get('passing_score')
        max_attempts = cleaned.get('max_attempts')
        duration = cleaned.get('duration_minutes')

        if total_points is not None and total_points <= 0:
            self.add_error('total_points', 'إجمالي النقاط يجب أن يكون أكبر من صفر.')
        if passing_score is not None and (passing_score < 0 or passing_score > 100):
            self.add_error('passing_score', 'درجة النجاح يجب أن تكون بين 0 و100.')
        if max_attempts is not None and max_attempts < 1:
            self.add_error('max_attempts', 'الحد الأدنى للمحاولات هو 1.')
        if duration is not None and duration < 1:
            self.add_error('duration_minutes', 'المدة يجب أن تكون دقيقة واحدة على الأقل.')
        return cleaned

class AssessmentQuestionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            current = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{current} form-control".strip()
        self.fields['question_text'].widget.attrs.setdefault('placeholder', 'اكتب نص السؤال بوضوح...')

    class Meta:
        model = AssessmentQuestion
        fields = ['question_text', 'question_type', 'points', 'difficulty', 'explanation']
        widgets = {
            'question_text': forms.Textarea(attrs={'rows': 3}),
            'explanation': forms.Textarea(attrs={'rows': 2}),
            'points': forms.NumberInput(attrs={'min': 1}),
        }

    def clean_points(self):
        points = self.cleaned_data.get('points')
        if points is not None and points < 1:
            raise forms.ValidationError('النقاط يجب أن تكون 1 أو أكثر.')
        return points

class QuestionChoiceForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        text_widget = self.fields['choice_text'].widget
        text_widget.attrs['class'] = f"{text_widget.attrs.get('class', '')} form-control".strip()
        self.fields['is_correct'].widget.attrs['class'] = 'form-check-input'

    class Meta:
        model = QuestionChoice
        fields = ['choice_text', 'is_correct']
        widgets = {
            'choice_text': forms.Textarea(attrs={'rows': 2}),
        }

QuestionChoiceFormSet = forms.inlineformset_factory(
    AssessmentQuestion,
    QuestionChoice,
    form=QuestionChoiceForm,
    extra=4,
    max_num=10,
    can_delete=True
)

class AssessmentAnswerForm(forms.Form):
    def __init__(self, question, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.question = question
        if question.question_type in ['multiple_choice', 'true_false']:
            choices = [(choice.choice_id, choice.choice_text) for choice in question.questionchoice_set.all()]
            self.fields[f'question_{question.question_id}'] = forms.ChoiceField(
                choices=choices,
                widget=forms.RadioSelect,
                required=False
            )
        elif question.question_type == 'short_answer':
            self.fields[f'question_{question.question_id}'] = forms.CharField(
                max_length=500,
                required=False,
                widget=forms.TextInput(attrs={'placeholder': 'أدخل إجابتك'})
            )
        elif question.question_type == 'essay':
            self.fields[f'question_{question.question_id}'] = forms.CharField(
                required=False,
                widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'اكتب إجابتك هنا'})
            )
        elif question.question_type == 'fill_blank':
            self.fields[f'question_{question.question_id}'] = forms.CharField(
                max_length=200,
                required=False,
                widget=forms.TextInput(attrs={'placeholder': 'أكمل الفراغ'})
            )
