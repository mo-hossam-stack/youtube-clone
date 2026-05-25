from django.shortcuts import redirect
from django.contrib.auth import login
from django.views.generic import CreateView
from django.urls import reverse_lazy
from .forms import CustomUserCreationForm


# Create your views here.
class RegisterView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('accounts:login')
    template_name = "accounts/register.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("/")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return redirect("/")