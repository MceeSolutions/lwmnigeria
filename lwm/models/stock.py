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

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    date_order = fields.Datetime('Order Date', required=True, states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, index=True, copy=False, default=fields.Datetime.now,\
        help="Depicts the date where the Quotation should be validated and converted into a purchase order.")

class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = "sale.order"
    
    @api.depends('order_line.price_total')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': order.pricelist_id.currency_id.round(amount_untaxed),
                'amount_tax': order.pricelist_id.currency_id.round(amount_tax),
                'amount_total': amount_untaxed + amount_tax - order.discounted_amount,
            })
    
    sub_total = fields.Float(string='Sub Total', compute='_compute_sub_amount', store=True, default=0.0)
    
    discounted_amount = fields.Float(string='Discount', compute='_compute_discounted_amount', store=True, default=0.0)
    total_ordered_quantity = fields.Float(string='Total Quantity', compute='_compute_total_ordered_quantity', store=True, default=0.0)
    confirmation_date = fields.Datetime(string='Confirmation Date', readonly=False, index=True, help="Date on which the sales order is confirmed.", oldname="date_confirm", copy=False, track_visibility='onchange')
        
    @api.one
    @api.depends('amount_untaxed', 'amount_tax')
    def _compute_sub_amount(self):
        for order in self:
            sub_total = order.amount_untaxed + order.amount_tax
            self.sub_total = sub_total
    
    @api.one
    @api.depends('order_line.discount')
    def _compute_discounted_amount(self):
        for line in self.order_line:
            discount_price = line.price_unit * ((line.discount or 0.0) / 100.0)
            self.discounted_amount += discount_price
    @api.one        
    @api.depends('order_line.product_uom_qty')
    def _compute_total_ordered_quantity(self):
        for line in self.order_line:
            self.total_ordered_quantity += line.product_uom_qty

class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = 'sale.order.line'
    
    @api.one
    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            price = line.price_unit
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })
    
    
class AccountInvoice(models.Model):
    _name = "account.invoice"
    _inherit = "account.invoice"
    
    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'tax_line_ids.amount_rounding',
                 'currency_id', 'company_id', 'date_invoice', 'type')
    def _compute_amount(self):
        round_curr = self.currency_id.round
        self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
        self.amount_tax = sum(round_curr(line.amount_total) for line in self.tax_line_ids)
        self.amount_total = self.amount_untaxed + self.amount_tax - self.discounted_amount
        amount_total_company_signed = self.amount_total
        amount_untaxed_signed = self.amount_untaxed
        if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
            currency_id = self.currency_id.with_context(date=self.date_invoice)
            amount_total_company_signed = currency_id.compute(self.amount_total, self.company_id.currency_id)
            amount_untaxed_signed = currency_id.compute(self.amount_untaxed, self.company_id.currency_id)
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        self.amount_total_company_signed = amount_total_company_signed * sign
        self.amount_total_signed = self.amount_total * sign
        self.amount_untaxed_signed = amount_untaxed_signed * sign
    
    discounted_amount = fields.Float(string='Discount', compute='_compute_discounted_amount', store=True, default=0.0)
    
    sub_total = fields.Float(string='Sub Total', compute='_compute_sub_amount', store=True, default=0.0)
    
    total_ordered_quantity = fields.Float(string='Total Quantity', compute='_compute_total_ordered_quantity', store=True, default=0.0)
    
    @api.one
    @api.depends('amount_untaxed', 'amount_tax')
    def _compute_sub_amount(self):
        for order in self:
            sub_total = order.amount_untaxed + order.amount_tax
            self.sub_total = sub_total
    
    @api.one
    @api.depends('invoice_line_ids.discount')
    def _compute_discounted_amount(self):
        for line in self.invoice_line_ids:
            discount_price = line.price_unit * ((line.discount or 0.0) / 100.0)
            self.discounted_amount += discount_price
    
    @api.one        
    @api.depends('invoice_line_ids.quantity')
    def _compute_total_ordered_quantity(self):
        for line in self.invoice_line_ids:
            self.total_ordered_quantity += line.quantity
    
class AccountInvoiceLine(models.Model):
    _name = "account.invoice.line"
    _inherit = "account.invoice.line"
    
    
    @api.one
    @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
        'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
        'invoice_id.date_invoice', 'invoice_id.date')
    def _compute_price(self):
        currency = self.invoice_id and self.invoice_id.currency_id or None
        price = self.price_unit
        taxes = False
        if self.invoice_line_tax_ids:
            taxes = self.invoice_line_tax_ids.compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
        self.price_subtotal = price_subtotal_signed = taxes['total_excluded'] if taxes else self.quantity * price
        self.price_total = taxes['total_included'] if taxes else self.price_subtotal
        if self.invoice_id.currency_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
            price_subtotal_signed = self.invoice_id.currency_id.with_context(date=self.invoice_id._get_currency_rate_date()).compute(price_subtotal_signed, self.invoice_id.company_id.currency_id)
        sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
        self.price_subtotal_signed = price_subtotal_signed * sign  

class Picking(models.Model):
    _inherit = "stock.picking"
    
    @api.multi
    def button_reset(self):
        for move in self.move_lines:
            move.state = 'draft'
        self.write({'state': 'draft'})
        return {}
    
    location_id = fields.Many2one(
        'stock.location', "Source Location",
        default=lambda self: self.env['stock.picking.type'].browse(self._context.get('default_picking_type_id')).default_location_src_id,
        readonly=True, required=True,
        states={'draft': [('readonly', False)]})
    
class ResCompany(models.Model):
    _inherit = "res.company"
    
    company_discount_account_id = fields.Many2one(comodel_name='account.account', string='Discount Account', company_dependent=True)
    
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    discount_account_id = fields.Many2one(comodel_name='account.account', string='Discount Account', company_dependent=True, related='company_id.company_discount_account_id')
    

