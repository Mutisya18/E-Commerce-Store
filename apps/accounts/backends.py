from django.contrib.auth.backends import ModelBackend


class BanAwareBackend(ModelBackend):
    def authenticate(self, request, **kwargs):
        user = super().authenticate(request, **kwargs)
        if user is not None and user.is_banned:
            return None
        return user
