# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HydroponicTalang(models.Model):
    _name = 'hydroponic.talang'
    _description = 'Master Data Talang'
    _order = 'name asc'

    name = fields.Char(string='Nama Talang', required=True)
    capacity = fields.Integer(string='Kapasitas Maksimal', default=100)
    
    # Relasi balik agar Odoo otomatis menghitung saat ada perubahan di menu Pendewasaan
    maturation_line_ids = fields.One2many('hydroponic.maturation.line', 'talang_id', string='Riwayat Tanam')

    # Tambahkan store=True agar bisa difilter di dropdown
    current_load = fields.Integer(string='Terisi', compute='_compute_capacity', store=True)
    remaining_capacity = fields.Integer(string='Sisa Kuota', compute='_compute_capacity', store=True)

    @api.depends('capacity', 'maturation_line_ids.qty_transfer', 'maturation_line_ids.is_harvested')
    def _compute_capacity(self):
        for record in self:
            # Hanya hitung tanaman yang is_harvested (Ceklist Selesai) masih False
            active_lines = record.maturation_line_ids.filtered(lambda l: not l.is_harvested)
            record.current_load = sum(active_lines.mapped('qty_transfer'))
            record.remaining_capacity = record.capacity - record.current_load