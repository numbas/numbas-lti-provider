from datetime import timedelta
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.shortcuts import redirect
from django_auth_lti.patch_reverse import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now
from django.views import generic
from numbas_lti.models import LTIConsumer, Resource
from numbas_lti.forms import CreateSuperuserForm
from .mixins import ManagementViewMixin, HelpLinkMixin

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

class DashboardView(HelpLinkMixin, ManagementViewMixin, generic.TemplateView):
    template_name = 'numbas_lti/management/admin/dashboard.html'
    management_tab = 'dashboard'
    helplink = 'admin/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        start_time = now() - timedelta(days=1)

        not_deleted = Q(attempts__deleted=False)

        recent_launch = Q(launches__time__gt=start_time)

        active_resources = Resource.objects.filter(recent_launch).annotate(
            recent_launches=Count('launches',filter=recent_launch,distinct=True),
            recent_completions=Count('attempts',filter=not_deleted & Q(attempts__end_time__gt=start_time),distinct=True)
        ).filter(recent_launches__gt=0).order_by('-recent_launches')

        context['active_resources'] = active_resources

        return context

class GlobalUserInfoView(HelpLinkMixin, ManagementViewMixin, generic.DetailView):
    model = User
    management_tab = ''
    template_name = 'numbas_lti/management/admin/user_info.html'
    helplink = 'admin/search.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.get_object()

        consumers = LTIConsumer.objects.filter(contexts__resources__launches__user=user).distinct()
        context['consumers'] = consumers
        
        return context
