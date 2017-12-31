from __future__ import unicode_literals


class SortAdminMediaMixin(object):

    class Media:
        js = [
            'admin/admin_addons/sortable.js',
        ]
