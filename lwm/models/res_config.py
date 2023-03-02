# -*- coding: utf-8 -*-

from odoo import models, fields, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    discount_account_id = fields.Many2one(comodel_name='account.account', string='Discount Account', company_dependent=True, related='company_id.company_discount_account_id', readonly=False)