# -*- coding: utf-8 -*-

from odoo import models, fields, _

class ResCompany(models.Model):
    _inherit = "res.company"
    
    company_discount_account_id = fields.Many2one(comodel_name='account.account', string='Discount Account', company_dependent=True)