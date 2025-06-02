from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import View
from django.shortcuts import render


class ManagerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.groups.filter(name="manager").exists()
