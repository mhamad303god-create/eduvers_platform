from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse

class MyAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        """
        Force redirect to dashboard-redirect view for ALL logins 
        (Social & Local), ignoring 'next' parameter if needed, 
        but usually better to respect it. here we force dashboard 
        to ensure self-healing runs.
        """
        return reverse('accounts:dashboard_redirect')
