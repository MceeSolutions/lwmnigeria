# -*- coding: utf-8 -*-
{
    'name': "LWM",
    'summary': """
        LWM Modules""",
    'description': """
        Long description of module's purpose
    """,
    'author': "MCEE Solutions",
    'website': "http://www.mceesolutions.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'LWM',
    'version': '0.10',
    'license': 'AGPL-3',
    # any module necessary for this one to work correctly
    'depends': ['base','account','stock','stock_account','purchase','sale_management'],
    # always loaded
    'data': [
        # 'views/stock_views.xml',
        'views/account_views.xml',
        'views/res_config_views.xml',
        'views/sale_views.xml',
    ],
}