# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HydroponicJuvenile(models.Model):
    _name = 'hydroponic.juvenile'
    _description = 'Data Peremajaan Hidroponik'
    _order = 'id desc'
    _rec_name = 'seeding_id'

    # Relasi ke data Pembibitan
    seeding_id = fields.Many2one('hydroponic.seeding', string='Kode Batch', required=True, ondelete='cascade', readonly=True)
    
    # Menarik data otomatis (Read-only) dari Pembibitan
    product_id = fields.Many2one(related='seeding_id.product_id', string='Nama Sayuran', readonly=True)
    estimated_start_date = fields.Date(related='seeding_id.estimated_transfer_date', string='Estimasi Masuk Peremajaan', readonly=True)
    qty_seeding = fields.Integer(related='seeding_id.qty_seeding', string='Jumlah Awal Semai', readonly=True)
    
    # Kolom khusus fase Peremajaan
    qty_dead = fields.Integer(string='Jumlah Mati/Sortir', default=0)
    qty_alive = fields.Integer(string='Jumlah Hidup', required=True, default=0)
    duration = fields.Integer(string='Durasi Peremajaan (Hari)', required=True, default=14)
    
    # Status Ceklist (Menggunakan Boolean)
    is_done = fields.Boolean(string='Ceklist Pindah Tanam (Selesai)', default=False)

    # Otomatisasi pengurangan jumlah hidup jika ada yang mati
    @api.onchange('qty_dead')
    def _onchange_qty_dead(self):
        if self.qty_seeding:
            self.qty_alive = self.qty_seeding - self.qty_dead