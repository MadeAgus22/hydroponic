# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HydroponicTalang(models.Model):
    _name = 'hydroponic.talang'
    _description = 'Master Data Talang'
    _order = 'name asc'

    name = fields.Char(string='Nama Talang', required=True)
    capacity = fields.Integer(string='Kapasitas Maksimal', default=100)
    
    # Menarik riwayat alokasi dari menu pendewasaan
    maturation_line_ids = fields.One2many('hydroponic.maturation.line', 'talang_id', string='Riwayat Tanam')

    current_load = fields.Integer(string='Terisi', compute='_compute_capacity', store=True)
    remaining_capacity = fields.Integer(string='Sisa Kuota', compute='_compute_capacity', store=True)

    @api.depends('capacity', 'maturation_line_ids.qty_remaining', 'maturation_line_ids.is_done')
    def _compute_capacity(self):
        for record in self:
            # Hitung HANYA tanaman yang belum selesai dipanen (Sisa)
            active_lines = record.maturation_line_ids.filtered(lambda l: not l.is_done)
            load = sum(active_lines.mapped('qty_remaining'))
            record.current_load = load
            record.remaining_capacity = record.capacity - load