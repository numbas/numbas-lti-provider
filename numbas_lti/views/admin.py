from datetime import timedelta
from django.core import exceptions
from django.conf import settings
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django import http
from django.shortcuts import redirect
from django_auth_lti.patch_reverse import reverse
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import now
from django.views import generic
from numbas_lti.models import LTIConsumer, Resource
from numbas_lti.forms import CreateSuperuserForm
from .mixins import ManagementViewMixin

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

class DashboardView(ManagementViewMixin, generic.TemplateView):
    template_name = 'numbas_lti/management/admin/dashboard.html'
    management_tab = 'dashboard'

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

class GlobalUserInfoView(ManagementViewMixin, generic.DetailView):
    model = User
    management_tab = ''
    template_name = 'numbas_lti/management/admin/user_info.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.get_object()

        consumers = LTIConsumer.objects.filter(contexts__resources__launches__user=user).distinct()
        context['consumers'] = consumers
        
        return context

def calendar(request):
    token = request.GET.get('token')
    if token != settings.CALENDAR_TOKEN:
        raise exceptions.PermissionDenied()

    from icalendar import Calendar, Event
    from icalendar.prop import vDatetime
    c = Calendar()
    c.add('prodid','-//Numbas LTI//{host}//'.format(host=request.get_host()))
    c.add('version','2.0')
    for r in Resource.objects.exclude(available_from=None).exclude(available_until=None):
        if r.available_until < r.available_from:
            continue
        e = Event()
        e['summary'] = '{context} - {resource}'.format(context=r.context.name if r.context else '', resource=r.title)
        e['dtstart'] = vDatetime(r.available_from)
        e['dtend'] = vDatetime(r.available_until)
        e['uid'] = r.pk
        e['dtstamp'] = vDatetime(r.creation_time)
        c.add_component(e)

    content = c.to_ical().decode('utf-8')
    response = http.HttpResponse(content, content_type="text/calendar")
    response['Content-Disposition'] = 'attachment; filename="numbas-lti-calendar.ics"'
    return response
