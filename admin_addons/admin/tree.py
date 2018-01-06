from __future__ import unicode_literals

from django import forms
from django.conf import settings
from django.conf.urls import url
from django.contrib import admin
from django.contrib.admin.utils import quote
from django.contrib.admin.views.main import ChangeList
from django.db.models.query import QuerySet
from django.forms.models import modelform_factory
from django.http import (
    Http404,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    HttpResponseRedirect,
    JsonResponse
)
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import mark_safe
from django.utils.translation import ugettext_lazy as _

from treebeard.forms import _get_exclude_for_model


class TreeAdminForm(forms.ModelForm):

    _position_choices = (
        ('last-child', _('At the end')),
        ('first-child', _('At the top')),
    )
    tree_position = forms.ChoiceField(
        choices=_position_choices,
        initial=_position_choices[0][0],
        label=_('Position'),
    )
    tree_parent_id = forms.TypedChoiceField(
        required=False,
        coerce=int,
        label=_('Parent node'),
    )

    def __init__(self, *args, **kwargs):
        choices = self.get_parent_choices()
        self.declared_fields['tree_parent_id'].choices = choices
        self.declared_fields['tree_parent_id'].widget = forms.HiddenInput()
        super(TreeAdminForm, self).__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['tree_position'].widget = forms.HiddenInput()

    def get_parent_choices(self):
        objects = self._meta.model._default_manager
        return [
            [p['pk'], p['pk']]
            for p in objects.get_queryset().values('pk')
        ]

    def _clean_cleaned_data(self):
        """ delete auxilary fields not belonging to node model """
        parent_id = self.cleaned_data.get('tree_parent_id', None)
        try:
            del self.cleaned_data['tree_parent_id']
        except KeyError:
            pass
        default = self._position_choices[0][0]
        position = self.cleaned_data.get('tree_position', default)
        try:
            del self.cleaned_data['tree_position']
        except KeyError:
            pass

        return parent_id, position

    def _get_parent(self, pk=None):
        if not pk:
            return None
        model = self._meta.model
        try:
            parent = self._meta.model.objects.get(pk=pk)
        except model.DoesNotExist:
            return None
        return parent

    def _get_creation_data(self):
        data = {}
        for field in self.cleaned_data:
            if not isinstance(self.cleaned_data[field], (list, QuerySet)):
                data[field] = self.cleaned_data[field]
        return data

    def save(self, commit=True):
        parent_id, position = self._clean_cleaned_data()
        parent = self._get_parent(pk=parent_id)
        if self.instance.pk is None:
            data = self._get_creation_data()
            if parent:
                self.instance = parent.add_child(**data)
                self.instance.move(parent, pos=position)
            else:
                self.instance = self._meta.model.add_root(**data)
                if position == 'first-child':
                    self.instance.move(parent, pos=position)
        else:
            self.instance.save()
        # Reload the instance
        self.instance = self._meta.model.objects.get(pk=self.instance.pk)
        super(TreeAdminForm, self).save(commit=commit)
        return self.instance


def movenodeform_factory(model, form=TreeAdminForm, exclude=None, **kwargs):
    tree_exclude = _get_exclude_for_model(model, exclude)
    return modelform_factory(model, form=form, exclude=tree_exclude, **kwargs)


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
            'all': ['admin/admin_addons/css/tree.css']
        }
        if 'djangocms_admin_style' in settings.INSTALLED_APPS:
            css['all'].append('admin/admin_addons/css/tree.cms.css')
        js = [
            'admin/admin_addons/js/changelist.tree.js',
            'admin/admin_addons/js/sortable.js',
            'admin/admin_addons/js/sortable.tree.js',
        ]

    def get_urls(self):
        urls = [

            # Ajax Views
            url(
                r'^update/$',
                self.admin_site.admin_view(self.update_view),
                name='{}_{}_update'.format(
                    self.model._meta.app_label,
                    self.model._meta.model_name
                )
            ),

            # Template Views
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

    def get_list_display(self, request):
        list_display = ['col_position_node'] + [
            d for d in super(TreeAdmin, self).get_list_display(request)
        ]
        list_display.append('col_node_children_count')
        # TODO implement move ajax
        # list_display.append('col_move_node')
        list_display.append('col_edit_node')
        return list_display

    def get_list_display_links(self, request, list_display):
        return ['col_edit_node']

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

    def get_changeform_initial_data(self, request):
        data = super(TreeAdmin, self).get_changeform_initial_data(request)
        if self._node:
            data['tree_parent_id'] = self._node.id
        return data

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
            'add_url': self.get_add_url(),
            'update_url': self.get_update_url(),
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

    def get_update_url(self):
        url_name = 'admin:{}_{}_update'.format(
            self.model._meta.app_label,
            self.model._meta.model_name
        )
        return reverse(url_name)

    def update_view(self, request):
        if not request.is_ajax() or request.method != 'POST':
            return HttpResponseBadRequest('Not an XMLHttpRequest')
        if request.method != 'POST':
            return HttpResponseNotAllowed('Must be a POST request')
        if not self.has_change_permission(request):
            return HttpResponseForbidden(
                'Missing permissions to perform this request'
            )
        Form = self.get_update_form_class()
        form = Form(request.POST)
        if form.is_valid():
            data = {'message': 'ok'}
            pos = form.cleaned_data.get('pos')
            parent = form.cleaned_data.get('parent')
            node = form.cleaned_data.get('node')
            target = form.cleaned_data.get('target')
            if pos == 'first':
                if parent:
                    node.move(parent, pos='first-child')
                else:
                    target = node.get_first_root_node()
                    node.move(target, pos='left')
            elif pos == 'last':
                if parent:
                    node.move(parent, pos='last-child')
                else:
                    target = node.get_last_root_node()
                    node.move(target, pos='right')
            else:
                node.move(target, pos=pos)
            node = self.model.objects.get(pk=node.pk)
            node.save()
        else:
            data = {
                'message': 'error',
                'error': _('There seams to be a problem with your list')
            }
        return JsonResponse(data)

    def get_update_form_class(self):
        class UpdateForm(forms.Form):
            depth = forms.IntegerField()
            pos = forms.ChoiceField(
                choices=[
                    ('left', 'left'),
                    ('right', 'right'),
                    ('last', 'last'),
                    ('first', 'first'),
                ]
            )
            node = forms.ModelChoiceField(
                queryset=self.model._default_manager.get_queryset()
            )
            target = forms.ModelChoiceField(
                queryset=self.model._default_manager.get_queryset()
            )
            parent = forms.ModelChoiceField(
                required=False,
                queryset=self.model._default_manager.get_queryset()
            )
        return UpdateForm

    def col_position_node(self, obj):
        data_attrs = [
            'data-pk="{}"'.format(obj.pk),
            'data-depth="{}"'.format(obj.depth),
            'data-name="{}"'.format(obj.__str__()),
        ]
        if self._node:
            data_attrs.append('data-parent="{}"'.format(self._node.pk))
        html = '<span class="admin-addons-drag" {}></span>'.format(
            ' '.join(data_attrs)
        )
        return mark_safe(html)
    col_position_node.short_description = ''

    def col_move_node(self, obj):
        css_classes = 'icon-button admin-addons-icon-button place'
        data_attrs = [
            'data-pk="{}"'.format(obj.pk),
            'data-depth="{}"'.format(obj.depth),
            'data-name="{}"'.format(obj.__str__()),
        ]
        html = '<span class="{}" {}>{}</span>'.format(
            css_classes,
            ' '.join(data_attrs),
            render_to_string('admin/svg/icon-move.svg')
        )
        return mark_safe(html)
    col_move_node.short_description = _('Move')

    def col_edit_node(self, obj):
        css_classes = 'icon-button admin-addons-icon-button edit'
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
    col_edit_node.short_description = _('Edit')

    def col_node_children_count(self, obj):
        html = '{}'.format(obj.get_children_count())
        return mark_safe(html)
    col_node_children_count.short_description = _('Children')


class TreeAdminWithSideTree(TreeAdmin):
    pass
