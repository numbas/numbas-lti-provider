from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django_auth_lti.patch_reverse import reverse
from django.utils.translation import ugettext_lazy as _
from django.views import generic
from numbas_lti.models import LTIConsumer
from numbas_lti.forms import CreateSuperuserForm

class CreateSuperuserView(generic.edit.CreateView):
    model = User
    form_class = CreateSuperuserForm
    template_name = 'numbas_lti/management/create_superuser.html'

    def form_valid(self,form):
        self.object = form.save()
        user = authenticate(username=self.object.username,password=form.cleaned_data['password1'])
        login(self.request,user)
        return redirect(self.get_success_url())

    def dispatch(self,request,*args,**kwargs):
        if User.objects.filter(is_superuser=True).exists():
            return redirect(reverse('index'))
        else:
            return super(CreateSuperuserView,self).dispatch(request,*args,**kwargs)

    def get_success_url(self):
        if LTIConsumer.objects.exists():
            return reverse('list_consumers')
        else:
            return reverse('create_consumer')
