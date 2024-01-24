from .mixins import ManagementViewMixin, HelpLinkMixin
from django import http
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.forms.models import inlineformset_factory, BaseInlineFormSet
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django_auth_lti.patch_reverse import reverse
from django.utils.translation import gettext_lazy as _
from django.views import generic
from numbas_lti import forms, requests_session
from numbas_lti.models import EditorLink, EditorLinkProject
import json
import requests

class EditorLinkManagementMixin(PermissionRequiredMixin,LoginRequiredMixin,ManagementViewMixin):
    permission_required = ('numbas_lti.add_editorlink',)
    management_tab = 'editor-links'
    login_url = reverse_lazy('login')

class ListEditorLinksView(HelpLinkMixin, EditorLinkManagementMixin,generic.list.ListView):
    model = EditorLink
    template_name = 'numbas_lti/management/admin/editorlink/list.html'
    helplink = 'admin/editorlink.html'

class GettingProjectDataException(Exception):
    pass

class UpdateEditorLinkView(EditorLinkManagementMixin,generic.edit.UpdateView):
    template_name = 'numbas_lti/management/admin/editorlink/edit.html'
    model = EditorLink
    fields = ['name']
    success_url = reverse_lazy('list_editorlinks')

    def projectformset(self,*args,**kwargs):
        if 'initial' in kwargs:
            extra = len(kwargs['initial'])
        else:
            extra = 0
        factory = inlineformset_factory(
            EditorLink,
            EditorLinkProject,
            form=forms.EditorLinkProjectForm,
            can_delete=False,
            extra=extra
        )
        return factory(*args,**kwargs)

    def get_projects_data(self):
        try:
            link = self.get_object()
            projects_data = requests_session.get_session().get('{}/api/projects'.format(link.url), timeout=getattr(settings,'REQUEST_TIMEOUT',60)).json()
            return projects_data
        except (json.JSONDecodeError, requests.exceptions.RequestException) as e:
            raise GettingProjectDataException(str(e))

    def get(self, request, *args, **kwargs):
        try:
            self.projects_data = self.get_projects_data()
        except GettingProjectDataException as e:
            return http.HttpResponseServerError(_('Error obtaining the list of projects to edit: {}'.format(e)),{})

        return super(UpdateEditorLinkView,self).get(request, *args, **kwargs)

    def get_context_data(self,*args,**kwargs):
        context = super(UpdateEditorLinkView,self).get_context_data(*args,**kwargs)

        if 'project_form' not in kwargs:
            selected_projects = [p.remote_id for p in self.object.projects.all()]

            projects_data = self.projects_data
            projects = sorted(projects_data,key=lambda p:p['name'].lower())
            project_forms = []
            for p in projects:
                project_forms.append({
                    'name': p['name'],
                    'description': p['description'],
                    'remote_id': p['pk'],
                    'homepage': p['homepage'],
                    'rest_url': p['url'],
                    'use': p['pk'] in selected_projects,
                })

            project_formset = self.projectformset(initial=project_forms)
            context['project_formset'] = project_formset
            context['projects'] = zip(project_formset, projects)

        return context

    def post(self,request,*args,**kwargs):
        self.object = self.get_object()
        project_form = self.projectformset(self.request.POST)
        form = self.get_form()
        if project_form.is_valid():
            return self.form_valid(form,project_form)
        else:
            return self.form_invalid(form,project_form)

    def form_valid(self,form,project_form):
        form.save()
        self.object.projects.all().delete()
        for pform in project_form:
            if pform.cleaned_data['use']:
                pform.instance.editor = self.object
                link = pform.save()
        exams = self.object.available_exams

        return http.HttpResponseRedirect(self.get_success_url())

    def form_invalid(self,form,project_form):
        return self.render_to_response(self.get_context_data(form=form,project_form=project_form))

class CreateEditorLinkView(HelpLinkMixin, EditorLinkManagementMixin,generic.edit.CreateView):
    model = EditorLink
    form_class = forms.CreateEditorLinkForm
    template_name = 'numbas_lti/management/admin/editorlink/create.html'
    helplink = 'admin/editorlink.html#creating-an-editor-link'

    def form_valid(self,form):
        editorlink = self.object = form.save()
        messages.add_message(self.request,messages.SUCCESS,_('Connected to {} at {}.'.format(editorlink.name,editorlink.url)))
        return http.HttpResponseRedirect(self.get_success_url())

    def form_invalid(self,form):
        url = form.data['url']
        try:
            link = EditorLink.objects.get(url=url)
            return redirect(reverse('edit_editorlink',args=(link.pk,)))
        except EditorLink.DoesNotExist:
            return super(CreateEditorLinkView,self).form_invalid(form)

    def get_success_url(self):
        return reverse('edit_editorlink',args=(self.object.pk,))

class DeleteEditorLinkView(EditorLinkManagementMixin,generic.edit.DeleteView):
    model = EditorLink
    template_name = 'numbas_lti/management/admin/editorlink/confirm_delete.html'
    success_url = reverse_lazy('list_editorlinks')
    context_object_name = 'editorlink'

    def delete(self,request,*args,**kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.delete()
        messages.add_message(self.request,messages.SUCCESS,_('The connection to {} has been deleted.'.format(self.object.name)))
        return http.HttpResponseRedirect(success_url)

