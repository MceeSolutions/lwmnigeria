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
    'category': 'Netcom',
    'version': '0.10',


    # any module necessary for this one to work correctly
    'depends': ['stock','stock_account','purchase'],

    # always loaded
    'data': [
        'views/stock_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}