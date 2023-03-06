# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = "sale.order"
    
    # @api.depends('order_line.price_total')
    # def _amount_all(self):
    #     """
    #     Compute the total amounts of the SO.
    #     """
    #     for order in self:
    #         amount_untaxed = amount_tax = 0.0
    #         for line in order.order_line:
    #             amount_untaxed += line.price_subtotal
    #             amount_tax += line.price_tax
    #         order.update({
    #             'amount_untaxed': order.pricelist_id.currency_id.round(amount_untaxed),
    #             'amount_tax': order.pricelist_id.currency_id.round(amount_tax),
    #             'amount_total': amount_untaxed + amount_tax - order.discounted_amount,
    #         })

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
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax - order.discounted_amount,
            })
    
    sub_total = fields.Float(string='Sub Total', compute='_compute_sub_amount', store=True, default=0.0)
    
    discounted_amount = fields.Float(string='Discount', compute='_compute_discounted_amount', store=True, default=0.0)
    total_ordered_quantity = fields.Float(string='Total Quantity', compute='_compute_total_ordered_quantity', store=True, default=0.0)
    confirmation_date = fields.Datetime(string='Confirmation Date', readonly=False, index=True, help="Date on which the sales order is confirmed.", copy=False, tracking=True)

    @api.depends('amount_untaxed', 'amount_tax')
    def _compute_sub_amount(self):
        for order in self:
            sub_total = order.amount_untaxed + order.amount_tax
            order.sub_total = sub_total
    
    @api.depends('order_line.discount')
    def _compute_discounted_amount(self):
        for rec in self:
            for line in rec.order_line:
                discount_price = line.price_unit * ((line.discount or 0.0) / 100.0)
                rec.discounted_amount += discount_price
  
    @api.depends('order_line.product_uom_qty')
    def _compute_total_ordered_quantity(self):
        for rec in self:
            for line in rec.order_line:
                rec.total_ordered_quantity += line.product_uom_qty

class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = 'sale.order.line'
    

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