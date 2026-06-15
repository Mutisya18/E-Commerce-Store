from django import forms
from allauth.account.forms import SignupForm
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomSignupForm(SignupForm):
    first_name = forms.CharField(max_length=50, required=True)
    last_name = forms.CharField(max_length=50, required=True)
    phone_number = forms.CharField(max_length=20, required=True)
    username = forms.CharField(
        max_length=150, min_length=3, required=True,
        error_messages={
            'required': 'Please choose a username.',
            'min_length': 'Username must be at least 3 characters.',
        }
    )

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('That username is already taken.')
        if not username.replace('_', '').replace('.', '').isalnum():
            raise forms.ValidationError('Username may only contain letters, numbers, underscores and dots.')
        return username

    def save(self, request):
        user = super().save(request)
        user.username = self.cleaned_data['username']
        user.first_name = self.cleaned_data['first_name'].strip()
        user.last_name = self.cleaned_data['last_name'].strip()
        user.phone_number = self.cleaned_data['phone_number'].strip()
        user.save(update_fields=['username', 'first_name', 'last_name', 'phone_number'])
        return user
