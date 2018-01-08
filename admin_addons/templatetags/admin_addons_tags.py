from __future__ import unicode_literals

from django import template
from django.contrib.admin.templatetags.admin_modify import submit_row

register = template.Library()


@register.inclusion_tag(
    'admin/admin_addons/tree_submit.html',
    takes_context=True
)
def admin_addons_submit_row(context):
    return submit_row(context)
