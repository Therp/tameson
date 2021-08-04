
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests, codecs


import logging
_logger = logging.getLogger(__name__)



def add_translation(env, product, lang_code, src, value):
    nl_name = env['ir.translation'].search(
        [('res_id', '=', product.id), ('name', '=', 'product.template,name'), ('lang', '=', lang_code)])
    if not nl_name:
        nl_name = env['ir.translation'].create({'type': 'model',
                                                'name': 'product.template,name',
                                                'lang': lang_code,
                                                'res_id': product.id,
                                                'src': src,
                                                'value': value,
                                                'state': 'translated',
                                                })
    else:
        nl_name.write({'value': value})


def add_pricelist_item(pricelist, product, price):
    pricelist.write({'item_ids': [(0, 0, {
        'applied_on': '1_product',
        'product_tmpl_id': product.id,
        'compute_price': 'fixed',
        'fixed_price': price
        })]
    })

class PimcoreProductResponseLine(models.Model):
    _name = 'pimcore.product.response'
    _inherit = ['mail.thread', 'mail.activity.mixin']    
    _description = 'PimcoreProductResponse'

    
    line_ids = fields.One2many(comodel_name='pimcore.product.response.line', inverse_name='response_id',)
    config_id = fields.Many2one(comodel_name='pimcore.config', ondelete='cascade',)
    
    def create_products(self):
        Category = self.env['product.category']
        Products = self.env['product.template'].search([])
        Skus = Products.mapped('default_code')
        new_lines = self.env['pimcore.product.response.line'].search([('response_id','=',self.id),('sku','not in',Skus),('state','=','draft')])[:100]
        Eur = self.env['product.pricelist'].search([('currency_id','=','EUR')], limit=1)
        Gbp = self.env['product.pricelist'].search([('currency_id','=','GBP')], limit=1)
        Usd = self.env['product.pricelist'].search([('currency_id','=','USD')], limit=1)
        _logger.warning('start')
        for line in new_lines:
            image_response = requests.get('%s/%s' % (self.config_id.api_host, line.image))
            if image_response.status_code == 200:
                image_data = codecs.encode(image_response.content, 'base64')
            else:
                image_data = False
            categ_path = line.full_path.split('/')[3:]

            child_categ = self.env['product.category']
            final_categ = self.env['product.category']
            for categ in categ_path[::-1]:
                break_loop = False
                this_categ = Category.search([('name','=',categ)], limit=1)
                if not this_categ:
                    this_categ = Category.create({'name': categ})
                else:
                    break_loop = True
                child_categ.parent_id = this_categ
                child_categ = this_categ
                if not final_categ:
                    final_categ = this_categ
                if break_loop:
                    break

            product = self.env['product.template'].create({
                'name': line.name,
                'default_code': line.sku,
                'weight': line.weight,
                't_height': line.height,
                't_length': line.depth,
                't_width': line.width,
                'type': 'product',
                'list_price': line.wholesaleprice,
                'image_1920': image_data,
                'categ_id': final_categ.id
            })
            add_translation(self.env, product, 'nl_NL', line.name, line.name_nl)
            add_pricelist_item(Eur, product, line.eur)
            add_pricelist_item(Gbp, product, line.gbp)
            add_pricelist_item(Usd, product, line.usd)
        new_lines.write({'state': 'created'})
        self.message_post(body = 'Products created %d' % len(new_lines))
        _logger.warning('end')


class PimcoreProductResponseLine(models.Model):
    _name = 'pimcore.product.response.line'
    _description = 'PimcoreProductResponseLine'

    
    state = fields.Selection(string='Status', default='draft',
        selection=[('draft', 'Draft'), ('created', 'Created'), ('updated', 'Updated'), ('skipped', 'Skipped'), ('error', 'Error')])
    response_id = fields.Many2one(comodel_name='pimcore.product.response', ondelete='restrict',)
    name = fields.Char()
    name_nl = fields.Char()
    pimcore_id = fields.Char()
    full_path = fields.Char()
    sku = fields.Char()
    ean = fields.Char()
    image = fields.Char()
    width = fields.Float()
    height = fields.Float()
    depth = fields.Float()
    weight = fields.Float()
    volume = fields.Float()
    modification_date = fields.Float()
    wholesaleprice = fields.Float()
    eur = fields.Float()
    gbp = fields.Float()
    usd = fields.Float()
    published = fields.Boolean()
    

