# -*- coding: utf-8 -*-
import datetime

from datetime import date, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError
from odoo.tools import float_is_zero

from functools import partial
from odoo.tools.misc import formatLang

from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    @api.model
    def _anglo_saxon_sale_move_lines(self, name, product, uom, qty, price_unit, currency=False, amount_currency=False, fiscal_position=False, account_analytic=False, analytic_tags=False):
        """Prepare dicts describing new journal COGS journal items for a product sale.

        Returns a dict that should be passed to `_convert_prepared_anglosaxon_line()` to
        obtain the creation value for the new journal items.

        :param Model product: a product.product record of the product being sold
        :param Model uom: a product.uom record of the UoM of the sale line
        :param Integer qty: quantity of the product being sold
        :param Integer price_unit: unit price of the product being sold
        :param Model currency: a res.currency record from the order of the product being sold
        :param Interger amount_currency: unit price in the currency from the order of the product being sold
        :param Model fiscal_position: a account.fiscal.position record from the order of the product being sold
        :param Model account_analytic: a account.account.analytic record from the line of the product being sold
        """

        if product.type == 'product' and product.valuation == 'real_time':
            accounts = product.product_tmpl_id.get_product_accounts(fiscal_pos=fiscal_position)
            # debit account dacc will be the output account
            dacc = accounts['stock_output'].id
            # credit account cacc will be the expense account
            cacc = accounts['expense'].id
            if dacc and cacc:
                return [
#                     {
#                         'type': 'src',
#                         'name': name[:64],
#                         'price_unit': price_unit,
#                         'quantity': qty,
#                         'price': price_unit * qty,
#                         'currency_id': currency and currency.id,
#                         'amount_currency': amount_currency,
#                         'account_id': dacc,
#                         'product_id': product.id,
#                         'uom_id': uom.id,
#                         'account_analytic_id': account_analytic and account_analytic.id,
#                         'analytic_tag_ids': analytic_tags and analytic_tags.ids and [(6, 0, analytic_tags.ids)] or False,
#                     },
# 
#                     {
#                         'type': 'src',
#                         'name': name[:64],
#                         'price_unit': price_unit,
#                         'quantity': qty,
#                         'price': -1 * price_unit * qty,
#                         'currency_id': currency and currency.id,
#                         'amount_currency': -1 * amount_currency,
#                         'account_id': cacc,
#                         'product_id': product.id,
#                         'uom_id': uom.id,
#                         'account_analytic_id': account_analytic and account_analytic.id,
#                         'analytic_tag_ids': analytic_tags and analytic_tags.ids and [(6, 0, analytic_tags.ids)] or False,
#                     },
                ]
        return []

    
class StockMove(models.Model):
    _inherit = "stock.move"
    
    @api.multi
    @api.onchange('product_id')
    def product_change(self):
        accounts_data = self.product_id.product_tmpl_id.get_product_accounts()
        if self.location_dest_id.valuation_in_account_id:
            acc_dest = self.location_dest_id.valuation_in_account_id.id
        else:
            acc_dest = accounts_data['stock_output'].id
        self.account_id = acc_dest
        
    @api.multi
    def _get_accounting_data_for_valuation(self):
        """ Return the accounts and journal to use to post Journal Entries for
        the real-time valuation of the quant. """
        self.ensure_one()
        accounts_data = self.product_id.product_tmpl_id.get_product_accounts()

        if self.location_id.valuation_out_account_id:
            acc_src = self.location_id.valuation_out_account_id.id
        else:
            acc_src = accounts_data['stock_input'].id

        if self.account_id:
            acc_dest = self.account_id.id
        elif self.location_dest_id.valuation_in_account_id:
            acc_dest = self.location_dest_id.valuation_in_account_id.id
        else:
            acc_dest = accounts_data['stock_output'].id

        acc_valuation = accounts_data.get('stock_valuation', False)
        if acc_valuation:
            acc_valuation = acc_valuation.id
        if not accounts_data.get('stock_journal', False):
            raise UserError(_('You don\'t have any stock journal defined on your product category, check if you have installed a chart of accounts'))
        if not acc_src:
            raise UserError(_('Cannot find a stock input account for the product %s. You must define one on the product category, or on the location, before processing this operation.') % (self.product_id.name))
        if not acc_dest:
            raise UserError(_('Cannot find a stock output account for the product %s. You must define one on the product category, or on the location, before processing this operation.') % (self.product_id.name))
        if not acc_valuation:
            raise UserError(_('You don\'t have any stock valuation account defined on your product category. You must define one before processing this operation.'))
        journal_id = accounts_data['stock_journal'].id
        return journal_id, acc_src, acc_dest, acc_valuation
    
#     @api.model
#     def _get_account_id(self):
#         accounts_data = self.product_id.product_tmpl_id.get_product_accounts()
#         print(accounts_data) 
#         if self.location_dest_id.valuation_in_account_id:
#             acc_dest = self.location_dest_id.valuation_in_account_id.id
#         else:
#             acc_dest = accounts_data['stock_output'].id
#         return acc_dest
        
    
    account_id = fields.Many2one('account.account', string='Account', index=True, ondelete='cascade')


