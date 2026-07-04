# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_hydroponic = fields.Boolean(
        string='Hydroponic Route',
        help='Centang jika stok produk ini diatur melalui proses modul Hydroponic.'
    )