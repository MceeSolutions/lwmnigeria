# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class AccountMove(models.Model):
    _name = "account.move"
    _inherit = "account.move"

    @api.depends(
        'line_ids.matched_debit_ids.debit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_credit_ids.credit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.balance',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.payment_id.state',
        'line_ids.full_reconcile_id')
    def _compute_amount(self):
        for move in self:
            total_untaxed, total_untaxed_currency = 0.0, 0.0
            total_tax, total_tax_currency = 0.0, 0.0
            total_residual, total_residual_currency = 0.0, 0.0
            total, total_currency = 0.0, 0.0

            for line in move.line_ids:
                if move.is_invoice(True):
                    # === Invoices ===
                    if line.display_type == 'tax' or (line.display_type == 'rounding' and line.tax_repartition_line_id):
                        # Tax amount.
                        total_tax += line.balance
                        total_tax_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.display_type in ('product', 'rounding'):
                        # Untaxed amount.
                        total_untaxed += line.balance
                        total_untaxed_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.display_type == 'payment_term':
                        # Residual amount.
                        total_residual += line.amount_residual
                        total_residual_currency += line.amount_residual_currency
                else:
                    # === Miscellaneous journal entry ===
                    if line.debit:
                        total += line.balance
                        total_currency += line.amount_currency

            sign = move.direction_sign
            move.amount_untaxed = sign * total_untaxed_currency
            move.amount_tax = sign * total_tax_currency
            move.amount_total = sign * total_currency - move.discounted_amount
            move.amount_residual = -sign * total_residual_currency
            move.amount_untaxed_signed = -total_untaxed
            move.amount_tax_signed = -total_tax
            move.amount_total_signed = abs(total) if move.move_type == 'entry' else -total
            move.amount_residual_signed = total_residual
            move.amount_total_in_currency_signed = abs(move.amount_total) if move.move_type == 'entry' else -(sign * move.amount_total)
    
    # @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'tax_line_ids.amount_rounding',
    #              'currency_id', 'company_id', 'date_invoice', 'type')
    # def _compute_amount(self):
    #     for rec in self:
    #         round_curr = rec.currency_id.round
    #         rec.amount_untaxed = sum(line.price_subtotal for line in rec.invoice_line_ids)
    #         rec.amount_tax = sum(round_curr(line.amount_total) for line in rec.tax_line_ids)
    #         rec.amount_total = rec.amount_untaxed + rec.amount_tax - rec.discounted_amount
    #         amount_total_company_signed = rec.amount_total
    #         amount_untaxed_signed = rec.amount_untaxed
    #         if rec.currency_id and rec.company_id and rec.currency_id != rec.company_id.currency_id:
    #             currency_id = self.currency_id.with_context(date=self.date_invoice)
    #             amount_total_company_signed = currency_id.compute(rec.amount_total, rec.company_id.currency_id)
    #             amount_untaxed_signed = currency_id.compute(rec.amount_untaxed, rec.company_id.currency_id)
    #         sign = rec.type in ['in_refund', 'out_refund'] and -1 or 1
    #         rec.amount_total_company_signed = amount_total_company_signed * sign
    #         rec.amount_total_signed = rec.amount_total * sign
    #         rec.amount_untaxed_signed = amount_untaxed_signed * sign
    
    discounted_amount = fields.Float(string='Discount', compute='_compute_discounted_amount', store=True, default=0.0)
    
    sub_total = fields.Float(string='Sub Total', compute='_compute_sub_amount', store=True, default=0.0)
    
    total_ordered_quantity = fields.Float(string='Total Quantity', compute='_compute_total_ordered_quantity', store=True, default=0.0)
    
    @api.depends('amount_untaxed', 'amount_tax')
    def _compute_sub_amount(self):
        for order in self:
            sub_total = order.amount_untaxed + order.amount_tax
            self.sub_total = sub_total
    
    @api.depends('invoice_line_ids.discount')
    def _compute_discounted_amount(self):
        for rec in self:
            for line in rec.invoice_line_ids:
                discount_price = line.price_unit * ((line.discount or 0.0) / 100.0)
                rec.discounted_amount += discount_price
         
    @api.depends('invoice_line_ids.quantity')
    def _compute_total_ordered_quantity(self):
        for rec in self:
            for line in rec.invoice_line_ids:
                rec.total_ordered_quantity += line.quantity
    
class AccountInvoiceLine(models.Model):
    _name = "account.move.line"
    _inherit = "account.move.line"
    
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