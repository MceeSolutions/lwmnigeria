# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from collections import defaultdict

class AccountMove(models.Model):
    _name = "account.move"
    _inherit = "account.move"

    # @api.depends(
    #     'line_ids.matched_debit_ids.debit_move_id.move_id.payment_id.is_matched',
    #     'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
    #     'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
    #     'line_ids.matched_credit_ids.credit_move_id.move_id.payment_id.is_matched',
    #     'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
    #     'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
    #     'line_ids.balance',
    #     'line_ids.currency_id',
    #     'line_ids.amount_currency',
    #     'line_ids.amount_residual',
    #     'line_ids.amount_residual_currency',
    #     'line_ids.payment_id.state',
    #     'line_ids.full_reconcile_id')
    # def _compute_amount(self):
    #     for move in self:
    #         total_untaxed, total_untaxed_currency = 0.0, 0.0
    #         total_tax, total_tax_currency = 0.0, 0.0
    #         total_residual, total_residual_currency = 0.0, 0.0
    #         total, total_currency = 0.0, 0.0

    #         for line in move.line_ids:
    #             if move.is_invoice(True):
    #                 # === Invoices ===
    #                 if line.display_type == 'tax' or (line.display_type == 'rounding' and line.tax_repartition_line_id):
    #                     # Tax amount.
    #                     total_tax += line.balance
    #                     total_tax_currency += line.amount_currency
    #                     total += line.balance
    #                     total_currency += line.amount_currency
    #                 elif line.display_type in ('product', 'rounding'):
    #                     # Untaxed amount.
    #                     total_untaxed += line.balance
    #                     total_untaxed_currency += line.amount_currency
    #                     total += line.balance
    #                     total_currency += line.amount_currency
    #                 elif line.display_type == 'payment_term':
    #                     # Residual amount.
    #                     total_residual += line.amount_residual
    #                     total_residual_currency += line.amount_residual_currency
    #             else:
    #                 # === Miscellaneous journal entry ===
    #                 if line.debit:
    #                     total += line.balance
    #                     total_currency += line.amount_currency

    #         sign = move.direction_sign
    #         move.amount_untaxed = sign * total_untaxed_currency
    #         move.amount_tax = sign * total_tax_currency
    #         move.amount_total = sign * total_currency - move.discounted_amount
    #         move.amount_residual = -sign * total_residual_currency
    #         move.amount_untaxed_signed = -total_untaxed
    #         move.amount_tax_signed = -total_tax
    #         move.amount_total_signed = abs(total) if move.move_type == 'entry' else -total
    #         move.amount_residual_signed = total_residual
    #         move.amount_total_in_currency_signed = abs(move.amount_total) if move.move_type == 'entry' else -(sign * move.amount_total)
    
    @api.depends(
    'line_ids.matched_debit_ids.debit_move_id.move_id.payment_id.is_matched',
    'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
    'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
    'line_ids.matched_credit_ids.credit_move_id.move_id.payment_id.is_matched',
    'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
    'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
    'line_ids.debit',
    'line_ids.credit',
    'line_ids.currency_id',
    'line_ids.amount_currency',
    'line_ids.amount_residual',
    'line_ids.amount_residual_currency',
    'line_ids.payment_id.state',
    'line_ids.full_reconcile_id')
    def _compute_amount(self):
        in_invoices = self.filtered(lambda m: m.move_type == 'in_invoice')
        out_invoices = self.filtered(lambda m: m.move_type == 'out_invoice')
        entries = self.filtered(lambda m: m.move_type == 'entry')
        reversed_mapping = defaultdict(lambda: self.env['account.move'])
        if in_invoices or out_invoices or entries:
            for reverse_move in self.env['account.move'].search([
                ('state', '=', 'posted'),
                '|', '|',
                '&', ('reversed_entry_id', 'in', in_invoices.ids), ('move_type', '=', 'in_refund'),
                '&', ('reversed_entry_id', 'in', out_invoices.ids), ('move_type', '=', 'out_refund'),
                '&', ('reversed_entry_id', 'in', entries.ids), ('move_type', '=', 'entry'),
            ]):
                reversed_mapping[reverse_move.reversed_entry_id] += reverse_move

        caba_mapping = defaultdict(lambda: self.env['account.move'])
        caba_company_ids = self.company_id.filtered(lambda c: c.tax_exigibility)
        if caba_company_ids:
            reverse_moves_ids = [move.id for moves in reversed_mapping.values() for move in moves]
            for caba_move in self.env['account.move'].search([
                ('tax_cash_basis_origin_move_id', 'in', self.ids + reverse_moves_ids),
                ('state', '=', 'posted'),
                ('move_type', '=', 'entry'),
                ('company_id', 'in', caba_company_ids.ids)
            ]):
                caba_mapping[caba_move.tax_cash_basis_origin_move_id] += caba_move

        for move in self:

            if move.payment_state == 'invoicing_legacy':
                # invoicing_legacy state is set via SQL when setting setting field
                # invoicing_switch_threshold (defined in account_accountant).
                # The only way of going out of this state is through this setting,
                # so we don't recompute it here.
                move.payment_state = move.payment_state
                continue

            total_untaxed = 0.0
            total_untaxed_currency = 0.0
            total_tax = 0.0
            total_tax_currency = 0.0
            total_to_pay = 0.0
            total_residual = 0.0
            total_residual_currency = 0.0
            total = 0.0
            total_currency = 0.0
            currencies = move._get_lines_onchange_currency().currency_id

            for line in move.line_ids:
                if move._payment_state_matters():
                    # === Invoices ===

                    if not line.exclude_from_invoice_tab:
                        # Untaxed amount.
                        total_untaxed += line.balance
                        total_untaxed_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.tax_line_id:
                        # Tax amount.
                        total_tax += line.balance
                        total_tax_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.account_id.user_type_id.type in ('receivable', 'payable'):
                        # Residual amount.
                        total_to_pay += line.balance
                        total_residual += line.amount_residual
                        total_residual_currency += line.amount_residual_currency
                else:
                    # === Miscellaneous journal entry ===
                    if line.debit:
                        total += line.balance
                        total_currency += line.amount_currency

            if move.move_type == 'entry' or move.is_outbound():
                sign = 1
            else:
                sign = -1
            move.amount_untaxed = sign * (total_untaxed_currency if len(currencies) == 1 else total_untaxed)
            move.amount_tax = sign * (total_tax_currency if len(currencies) == 1 else total_tax)
            move.amount_total = sign * (total_currency if len(currencies) == 1 else total) - move.discounted_amount
            move.amount_residual = -sign * (total_residual_currency if len(currencies) == 1 else total_residual)
            move.amount_untaxed_signed = -total_untaxed
            move.amount_tax_signed = -total_tax
            move.amount_total_signed = abs(total) if move.move_type == 'entry' else -total
            move.amount_residual_signed = total_residual
            move.amount_total_in_currency_signed = abs(move.amount_total) if move.move_type == 'entry' else -(sign * move.amount_total)

            currency = currencies if len(currencies) == 1 else move.company_id.currency_id

            # Compute 'payment_state'.
            new_pmt_state = 'not_paid' if move.move_type != 'entry' else False

            if move._payment_state_matters() and move.state == 'posted':
                if currency.is_zero(move.amount_residual):
                    reconciled_payments = move._get_reconciled_payments()
                    if not reconciled_payments or all(payment.is_matched for payment in reconciled_payments):
                        new_pmt_state = 'paid'
                    else:
                        new_pmt_state = move._get_invoice_in_payment_state()
                elif currency.compare_amounts(total_to_pay, total_residual) != 0:
                    new_pmt_state = 'partial'

            if new_pmt_state == 'paid' and move.move_type in ('in_invoice', 'out_invoice', 'entry'):
                reverse_moves = reversed_mapping[move]
                caba_moves = caba_mapping[move]
                for reverse_move in reverse_moves:
                    caba_moves |= caba_mapping[reverse_move]

                # We only set 'reversed' state in cas of 1 to 1 full reconciliation with a reverse entry; otherwise, we use the regular 'paid' state
                # We ignore potentials cash basis moves reconciled because the transition account of the tax is reconcilable
                reverse_moves_full_recs = reverse_moves.mapped('line_ids.full_reconcile_id')
                if reverse_moves_full_recs.mapped('reconciled_line_ids.move_id').filtered(lambda x: x not in (caba_moves + reverse_moves + reverse_moves_full_recs.mapped('exchange_move_id'))) == move:
                    new_pmt_state = 'reversed'

            move.payment_state = new_pmt_state
    
    discounted_amount = fields.Float(string='Discount', compute='_compute_discounted_amount', store=True, default=0.0)
    
    sub_total = fields.Float(string='Sub Total', compute='_compute_sub_amount', store=True, default=0.0)
    
    total_ordered_quantity = fields.Float(string='Total Quantity', compute='_compute_total_ordered_quantity', store=False, default=0.0)
    
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

    _sql_constraints = [
        (
            'check_credit_debit',
            'CHECK(credit + debit>=0 AND credit * debit=0)',
            'Wrong credit or debit value in accounting entry !'
        ),
        (
            'check_accountable_required_fields',
             "CHECK(COALESCE(display_type IN ('line_section', 'line_note'), 'f') OR account_id IS NOT NULL)",
             "Missing required account on accountable invoice line."
        ),
        (
            'check_non_accountable_fields_null',
             "CHECK(display_type NOT IN ('line_section', 'line_note') OR (amount_currency = 0 AND debit = 0 AND credit = 0 AND account_id IS NULL))",
             "Forbidden unit price, account and quantity on non-accountable invoice line"
        ),
        (
            "check_amount_currency_balance_sign",
            """CHECK(
                display_type IN ('line_section', 'line_note')
                OR (
                    (balance <= 0 AND amount_currency <= 0)
                    OR
                    (balance >= 0 AND amount_currency >= 0)
                )
            )""",
            "The amount expressed in the secondary currency must be positive when account is debited and negative when "
            "account is credited. If the currency is the same as the one from the company, this amount must strictly "
            "be equal to the balance."
        ),
        # (
        #     'check_amount_currency_balance_sign',
        #     '''CHECK(
        #         (
        #             (currency_id != company_currency_id)
        #             AND
        #             (
        #                 (debit - credit <= 0 AND amount_currency <= 0)
        #                 OR
        #                 (debit - credit >= 0 AND amount_currency >= 0)
        #             )
        #         )
        #         OR
        #         (
        #             currency_id = company_currency_id
        #             AND
        #             ROUND(debit - credit - amount_currency, 2) = 0
        #         )
        #     )''',
        #     "The amount expressed in the secondary currency must be positive when account is debited and negative when "
        #     "account is credited. If the currency is the same as the one from the company, this amount must strictly "
        #     "be equal to the balance."
        # ),
    ]

    