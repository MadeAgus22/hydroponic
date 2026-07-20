# -*- coding: utf-8 -*-
from odoo import models, fields

class HydroponicTalang(models.Model):
    _name = 'hydroponic.talang'
    _description = 'Master Data Talang'
    _order = 'name asc'

    name = fields.Char(string='Nama Talang', required=True)
    capacity = fields.Integer(string='Kapasitas (Lubang Tanam)', default=100)
    status = fields.Selection([
        ('available', 'Tersedia'),
        ('in_use', 'Sedang Dipakai')
    ], string='Status', default='available', readonly=True)