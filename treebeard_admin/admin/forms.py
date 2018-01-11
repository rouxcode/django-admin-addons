from __future__ import unicode_literals

from django import forms
from django.db.models.query import QuerySet
from django.forms.models import modelform_factory
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from treebeard.forms import _get_exclude_for_model


class TreeAdminForm(forms.ModelForm):

    max_depth = None

    _position_choices = (
        ('last-child', _('At the bottom')),
        ('first-child', _('At the top')),
    )

    _parent_id = forms.TypedChoiceField(
        coerce=int,
        label=_('Parent node'),
    )
    _position = forms.ChoiceField(
        choices=_position_choices,
        initial=_position_choices[0][0],
        label=_('Position'),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        self.declared_fields['_parent_id'].choices = self.mk_dropdown_tree(
            self._meta.model,
            for_node=kwargs.get('instance', None)
        )
        if instance:
            parent = instance.get_parent()
            if parent:
                self.declared_fields['_parent_id'].initial = parent.pk
        super(TreeAdminForm, self).__init__(*args, **kwargs)

    def _clean_cleaned_data(self):
        """
        delete auxilary fields not belonging to node model
        """
        parent_id = self.cleaned_data.get('_parent_id', None)
        try:
            del self.cleaned_data['_parent_id']
        except KeyError:
            pass
        default = self._position_choices[0][0]
        position = self.cleaned_data.get('_position', default)
        try:
            del self.cleaned_data['_position']
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
        if self.instance.pk is None:
            data = self._get_creation_data()
            parent = self._get_parent(pk=parent_id)
            if parent:
                self.instance = parent.add_child(**data)
                self.instance.move(parent, pos=position)
            else:
                self.instance = self._meta.model.add_root(**data)
                if position == 'first-child':
                    self.instance.move(parent, pos=position)
        else:
            parent = self.instance.get_parent()
            self.instance.save()
            # If the parent_id changed move the node to the new parent
            if not parent_id == getattr(parent, 'pk', None):
                new_parent = self._meta.model.objects.get(pk=parent_id)
                self.instance.move(new_parent, position)
        # Reload the instance
        self.instance = self._meta.model.objects.get(pk=self.instance.pk)
        super(TreeAdminForm, self).save(commit=commit)
        return self.instance

    @staticmethod
    def is_loop_safe(for_node, possible_parent):
        if for_node is not None:
            return not (
                possible_parent == for_node
            ) or (
                possible_parent.is_descendant_of(for_node)
            )
        return True

    @staticmethod
    def mk_indent(level):
        return '&nbsp;&nbsp;&nbsp;&nbsp;' * (level - 1)

    @classmethod
    def add_subtree(cls, for_node, node, options):
        """
        Recursively build options tree.
        """
        # If max_depth is set limit the subtree rendering
        if not cls.max_depth or node.depth <= cls.max_depth:
            if cls.is_loop_safe(for_node, node):
                options.append(
                    (
                        node.pk,
                        mark_safe(
                            cls.mk_indent(node.get_depth()) + escape(node)
                        )
                    )
                )
                for subnode in node.get_children():
                    cls.add_subtree(for_node, subnode, options)

    @classmethod
    def mk_dropdown_tree(cls, model, for_node=None):
        """
        Creates a tree-like list of choices
        """
        options = [(0, _('-- root --'))]
        for node in model.get_root_nodes():
            cls.add_subtree(for_node, node, options)
        return options


def movenodeform_factory(model, form=TreeAdminForm, exclude=None, **kwargs):
    tree_exclude = _get_exclude_for_model(model, exclude)
    return modelform_factory(model, form=form, exclude=tree_exclude, **kwargs)
