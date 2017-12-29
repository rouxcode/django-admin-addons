from __future__ import unicode_literals

from django import forms
from django.conf.urls import url
from django.contrib import admin
from django.contrib.admin.utils import quote
from django.contrib.admin.views.main import ChangeList
from django.http import Http404, HttpResponseRedirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import mark_safe
from django.utils.translation import ugettext_lazy as _


class TreeAdminForm(forms.ModelForm):
    pass


class TreeChangeList(ChangeList):

    def url_for_result(self, result):
        pk = getattr(result, self.pk_attname)
        parent = result.get_parent()
        if parent:
            url_name = 'admin:{}_{}_change'.format(
                self.opts.app_label,
                self.opts.model_name
            )
            try:
                return reverse(
                    url_name,
                    kwargs={
                        'node_id': quote(parent.id),
                        'object_id': quote(pk),
                    },
                    current_app=self.model_admin.admin_site.name
                )
            except Exception:
                pass
        return super(TreeChangeList, self).url_for_result(result)


class TreeAdmin(admin.ModelAdmin):

    _node = None

    # TODO implement max depth
    max_depth = None
    change_list_template = 'admin/admin_addons/tree_list.html'

    class Media:
        css = {
            'all': [
                'admin/admin_addons/css/tree.css',
            ]
        }
        js = [
            'admin/admin_addons/js/changelist.tree.js',
        ]

    def get_urls(self):
        urls = [
            url(
                r'^(?P<node_id>\d+)/list/$',
                self.admin_site.admin_view(self.changelist_view),
                name='{}_{}_changelist'.format(
                    self.model._meta.app_label,
                    self.model._meta.model_name
                )
            ),
            url(
                r'^(?P<node_id>\d+)/add/$',
                self.admin_site.admin_view(self.add_view),
                name='{}_{}_add'.format(
                    self.model._meta.app_label,
                    self.model._meta.model_name
                )
            ),
            url(
                r'^(?P<node_id>\d+)/(?P<object_id>\d+)/change/$',
                self.admin_site.admin_view(self.change_view),
                name='{}_{}_change'.format(
                    self.model._meta.app_label,
                    self.model._meta.model_name
                )
            ),
        ]
        urls += super(TreeAdmin, self).get_urls()
        return urls

    def get_changeform_initial_data(self, request):
        data = super(TreeAdmin, self).get_changeform_initial_data(request)
        if self._node:
            data['_ref_node_id'] = self._node.id
        return data

    def add_view(self, request, node_id=None, form_url='', extra_context=None):
        self._node = self.get_node(node_id)
        extra_context = extra_context or {}
        extra_context.update({'parent_node': self._node})
        return super(TreeAdmin, self).add_view(
            request,
            form_url,
            extra_context
        )

    def response_post_save_add(self, request, obj):
        if self._node:
            url_name = 'admin:{}_{}_changelist'.format(
                self.model._meta.app_label,
                self.model._meta.model_name
            )
            url = reverse(url_name, kwargs={'node_id': self._node.id})
            return HttpResponseRedirect(url)
        return super(TreeAdmin, self).response_post_save_add(request, obj)

    def change_view(self, request, object_id, node_id=None, form_url='',
                    extra_context=None):
        self._node = self.get_node(node_id)
        extra_context = extra_context or {}
        extra_context.update({'parent_node': self._node})
        return super(TreeAdmin, self).change_view(
            request,
            object_id,
            form_url,
            extra_context
        )

    def response_post_save_change(self, request, obj):
        if self._node:
            url_name = 'admin:{}_{}_changelist'.format(
                self.model._meta.app_label,
                self.model._meta.model_name
            )
            url = reverse(url_name, kwargs={'node_id': self._node.id})
            return HttpResponseRedirect(url)
        return super(TreeAdmin, self).response_post_save_change(request, obj)

    def changelist_view(self, request, node_id=None, extra_context=None):
        self._node = self.get_node(node_id)
        extra_context = extra_context or {}
        extra_context.update({
            'parent_node': self._node,
            'add_url': self.get_add_url()
        })
        return super(TreeAdmin, self).changelist_view(
            request,
            extra_context,
        )

    def get_changelist(self, request, **kwargs):
        return TreeChangeList

    def get_add_url(self):
        if self._node:
            url_name = 'admin:{}_{}_add'.format(
                self.model._meta.app_label,
                self.model._meta.model_name
            )
            return reverse(url_name, kwargs={'node_id': self._node.id})
        url_name = 'admin:{}_{}_add'.format(
            self.model._meta.app_label,
            self.model._meta.model_name
        )
        return reverse(url_name)

    def get_list_display(self, request):
        list_display = [
            d for d in super(TreeAdmin, self).get_list_display(request)
        ]
        list_display.append('edit_node')
        return list_display

    def get_list_display_links(self, request, list_display):
        return ['edit_node']

    def get_queryset(self, request):
        """
        Only display nodes for the current node or with depth = 1 (root)
        """
        if self._node:
            qs = self._node.get_children()
        else:
            depth = 1
            qs = super(TreeAdmin, self).get_queryset(request)
            qs = qs.filter(depth=depth)
        return qs

    def get_node(self, node_id):
        """
        Get the current root node
        """
        if node_id:
            qs = self.model._default_manager.get_queryset()
            try:
                id = int(node_id)
            except ValueError:
                return None
            try:
                return qs.get(pk=id)
            except self.model.DoesNotExist:
                raise Http404(
                    '{} with id "{}" does not exist'.format(
                        self.model._meta.model_name,
                        id
                    )
                )
        return None

    def edit_node(self, obj):
        css_classes = 'edit icon-button admin-addons-icon-button'
        url_name_edit = 'admin:{}_{}_change'.format(
            self.model._meta.app_label,
            self.model._meta.model_name
        )
        url_name_list = 'admin:{}_{}_changelist'.format(
            self.model._meta.app_label,
            self.model._meta.model_name
        )
        html_data_attrs = (
            'data-id="{}" data-edit-url="{}" data-list-url="{}"'
        ).format(
            obj.id,
            reverse(url_name_edit, args=[obj.id]),
            reverse(url_name_list, kwargs={'node_id': obj.id})
        )
        html = '<span class="{}" {}>{}</span>'.format(
            css_classes,
            html_data_attrs,
            render_to_string('admin/svg/icon-edit.svg')
        )
        return mark_safe(html)
    edit_node.short_description = _('Edit')
