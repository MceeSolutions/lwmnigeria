# -*- coding: utf-8 -*-

from odoo import models, fields, _

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    date_order = fields.Datetime('Order Date', required=True, states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, index=True, copy=False, default=fields.Datetime.now,\
        help="Depicts the date where the Quotation should be validated and converted into a purchase order.")