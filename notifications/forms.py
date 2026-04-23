import json
import os

from django import forms
from django.core.exceptions import ValidationError
from .models import ContactRequest, Message, NewsletterSubscription
from accounts.models import User


MESSAGE_ALLOWED_ATTACHMENT_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.svg',
    '.pdf', '.txt', '.csv', '.json', '.zip', '.rar', '.7z',
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.mp3', '.wav', '.m4a', '.ogg',
    '.mp4', '.mov', '.avi', '.mkv', '.webm',
}
MESSAGE_MAX_ATTACHMENT_SIZE = 100 * 1024 * 1024


def validate_message_attachment(file):
    if not file:
        return file

    extension = os.path.splitext(file.name.lower())[1]
    if extension not in MESSAGE_ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValidationError('نوع الملف غير مدعوم. يمكنك رفع صور أو PDF أو مستندات أو ملفات مضغوطة أو ملفات صوت/فيديو شائعة.')
    if file.size > MESSAGE_MAX_ATTACHMENT_SIZE:
        raise ValidationError('حجم الملف يجب ألا يتجاوز 100 ميجابايت.')
    return file


class ContactRequestForm(forms.ModelForm):
    class Meta:
        model = ContactRequest
        fields = ["full_name", "email", "subject", "message"]
        widgets = {
            "full_name": forms.TextInput(),
            "email": forms.EmailInput(),
            "subject": forms.TextInput(),
            "message": forms.Textarea(),
        }


class ReceiverChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name() or obj.email


class MessageForm(forms.ModelForm):
    receiver = ReceiverChoiceField(
        queryset=User.objects.none(),
        label='المستلم',
        widget=forms.Select(attrs={'class': 'form-control form-select-premium'}),
        empty_label='اختر المستلم...',
        help_text='اختر اسم المستلم من القائمة بدلاً من كتابة البريد الإلكتروني.',
    )

    attachment_urls = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'اختياري: ضع كل رابط في سطر مستقل أو أدخل قائمة JSON مثل ["https://..."]',
            }
        ),
        help_text='اختياري. استخدمه فقط إذا أردت إرسال روابط ملفات أو مراجع أو تسجيلات مرتبطة بالرسالة.',
    )

    class Meta:
        model = Message
        fields = ['receiver', 'subject', 'content', 'attachment_file', 'attachment_urls']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'اكتب موضوع الرسالة'}),
            'content': forms.Textarea(attrs={'class': 'form-control textarea-lg', 'rows': 6, 'placeholder': 'اكتب محتوى الرسالة هنا'}),
            'attachment_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.sender = kwargs.pop('sender', None)
        super().__init__(*args, **kwargs)
        receivers = User.objects.filter(is_active=True)
        if self.sender:
            receivers = receivers.exclude(id=self.sender.id)
        self.fields['receiver'].queryset = receivers.order_by('first_name', 'last_name', 'email')
        attachment_value = self.initial.get('attachment_urls')
        if isinstance(attachment_value, list):
            self.initial['attachment_urls'] = "\n".join(str(url) for url in attachment_value if url)

    def clean_attachment_urls(self):
        raw_value = (self.cleaned_data.get('attachment_urls') or '').strip()
        if not raw_value:
            return []

        if raw_value.startswith('['):
            try:
                parsed = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                raise forms.ValidationError('صيغة JSON غير صالحة في روابط المرفقات.') from exc
            if not isinstance(parsed, list):
                raise forms.ValidationError('يجب أن تكون المرفقات على شكل قائمة روابط.')
            return [str(item).strip() for item in parsed if str(item).strip()]

        lines = [line.strip().strip(',') for line in raw_value.replace('\r', '\n').split('\n')]
        compact = []
        for line in lines:
            if not line:
                continue
            compact.extend(part.strip() for part in line.split(',') if part.strip())
        return compact

    def clean_attachment_file(self):
        return validate_message_attachment(self.cleaned_data.get('attachment_file'))

class ReplyMessageForm(forms.ModelForm):
    attachment_urls = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'اختياري: روابط مراجع أو ملفات داعمة للرد، كل رابط في سطر مستقل',
            }
        ),
        help_text='اختياري. مفيد إذا كان الرد يحتاج ملفاً أو رابط شرح أو تسجيلاً خارجياً.',
    )

    class Meta:
        model = Message
        fields = ['content', 'attachment_file', 'attachment_urls']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control textarea-lg', 'rows': 6, 'placeholder': 'اكتب الرد هنا'}),
            'attachment_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.sender = kwargs.pop('sender', None)
        self.parent = kwargs.pop('parent', None)
        super().__init__(*args, **kwargs)
        attachment_value = self.initial.get('attachment_urls')
        if isinstance(attachment_value, list):
            self.initial['attachment_urls'] = "\n".join(str(url) for url in attachment_value if url)

    def clean_attachment_urls(self):
        raw_value = (self.cleaned_data.get('attachment_urls') or '').strip()
        if not raw_value:
            return []

        if raw_value.startswith('['):
            try:
                parsed = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                raise forms.ValidationError('صيغة JSON غير صالحة في روابط المرفقات.') from exc
            if not isinstance(parsed, list):
                raise forms.ValidationError('يجب أن تكون المرفقات على شكل قائمة روابط.')
            return [str(item).strip() for item in parsed if str(item).strip()]

        lines = [line.strip().strip(',') for line in raw_value.replace('\r', '\n').split('\n')]
        compact = []
        for line in lines:
            if not line:
                continue
            compact.extend(part.strip() for part in line.split(',') if part.strip())
        return compact

    def clean_attachment_file(self):
        return validate_message_attachment(self.cleaned_data.get('attachment_file'))


class NewsletterSubscriptionForm(forms.ModelForm):
    class Meta:
        model = NewsletterSubscription
        fields = ["email"]
        widgets = {
            "email": forms.EmailInput(attrs={
                "class": "newsletter-input",
                "placeholder": "بريدك الإلكتروني...",
            }),
        }
