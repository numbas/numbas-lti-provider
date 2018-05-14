from .mixins import ManagementViewMixin
from channels import Channel
from django import http
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.forms.models import inlineformset_factory, BaseInlineFormSet
from django.shortcuts import render
from django.urls import reverse_lazy
from django_auth_lti.patch_reverse import reverse
from django.utils.translation import ugettext_lazy as _
from django.views import generic
from numbas_lti import forms
from numbas_lti.models import EditorLink, EditorLinkProject
import json
import requests

class EditorLinkManagementMixin(PermissionRequiredMixin,LoginRequiredMixin,ManagementViewMixin):
    permission_required = ('numbas_lti.add_editorlink',)
    management_tab = 'editor-links'
    login_url = reverse_lazy('login')

class ListEditorLinksView(EditorLinkManagementMixin,generic.list.ListView):
    model = EditorLink
    template_name = 'numbas_lti/management/admin/list_editorlinks.html'

class UpdateEditorLinkView(EditorLinkManagementMixin,generic.edit.UpdateView):
    template_name = 'numbas_lti/management/admin/edit_editorlink.html'
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

    def get_context_data(self,*args,**kwargs):
        context = super(UpdateEditorLinkView,self).get_context_data(*args,**kwargs)

        if 'project_form' not in kwargs:
            selected_projects = [p.remote_id for p in self.object.projects.all()]

            projects_data = requests.get('{}/api/projects'.format(self.object.url)).json()
            projects = []
            for p in sorted(projects_data,key=lambda p:p['name'].lower()):
                projects.append({
                    'name': p['name'],
                    'description': p['description'],
                    'remote_id': p['pk'],
                    'homepage': p['homepage'],
                    'rest_url': p['url'],
                    'use': p['pk'] in selected_projects,
                })

            context['project_form'] = self.projectformset(initial=projects)

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
        Channel("editorlink.update_cache").send({'pk':self.object.pk,'bounce':False})

        return http.HttpResponseRedirect(self.get_success_url())

    def form_invalid(self,form,project_form):
        return self.render_to_response(self.get_context_data(form=form,project_form=project_form))

class CreateEditorLinkView(EditorLinkManagementMixin,generic.edit.CreateView):
    model = EditorLink
    form_class = forms.CreateEditorLinkForm
    template_name = 'numbas_lti/management/admin/create_editorlink.html'

    def form_valid(self,form):
        editorlink = self.object = form.save()
        messages.add_message(self.request,messages.SUCCESS,_('Connected to {} at {}.'.format(editorlink.name,editorlink.url)))
        return http.HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('edit_editorlink',args=(self.object.pk,))

class DeleteEditorLinkView(EditorLinkManagementMixin,generic.edit.DeleteView):
    model = EditorLink
    template_name = 'numbas_lti/management/admin/confirm_delete_editorlink.html'
    success_url = reverse_lazy('list_editorlinks')
    context_object_name = 'editorlink'

    def delete(self,request,*args,**kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.delete()
        messages.add_message(self.request,messages.SUCCESS,_('The connection to {} has been deleted.'.format(self.object.name)))
        return http.HttpResponseRedirect(success_url)

