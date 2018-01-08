from __future__ import unicode_literals

from django import forms
from django.db.models.query import QuerySet
from django.forms.models import modelform_factory
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from treebeard.forms import _get_exclude_for_model


class TreeAdminForm(forms.ModelForm):

    _position_choices = (
        ('last-child', _('At the top')),
        ('first-child', _('At the Bottom')),
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
        instance = kwargs.get('instance')
        choices = self.mk_dropdown_tree(
            self._meta.model,
            for_node=kwargs.get('instance', None)
        )
        self.declared_fields['tree_parent_id'].choices = choices
        if instance:
            self.declared_fields['tree_position'].widget = forms.HiddenInput()
            parent = instance.get_parent()
            if parent:
                label = '{}{}'.format(self.mk_indent(parent.depth), parent)
                initial = (parent.pk, label)
                self.declared_fields['tree_parent_id'].initial = initial
        else:
            self.declared_fields['tree_parent_id'].widget = forms.HiddenInput()
        super(TreeAdminForm, self).__init__(*args, **kwargs)

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
            print parent_id, self.instance.get_parent()
            self.instance.save()
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
        if cls.is_loop_safe(for_node, node):
            options.append(
                (node.pk,
                 mark_safe(cls.mk_indent(node.get_depth()) + escape(node))))
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
