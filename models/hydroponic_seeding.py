# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import timedelta

class HydroponicSeeding(models.Model):
    _name = 'hydroponic.seeding'
    _description = 'Data Pembibitan Hidroponik'
    _order = 'id desc'

    name = fields.Char(
        string='Kode Batch', 
        required=True, 
        copy=False, 
        readonly=True, 
        default='New'
    )
    
    product_id = fields.Many2one(
        'product.product', 
        string='Nama Sayuran', 
        required=True,
        domain=[('type', '=', 'consu')] 
    )
    
    start_date = fields.Date(
        string='Tanggal Pembibitan', 
        required=True, 
        default=fields.Date.context_today
    )
    
    duration = fields.Integer(
        string='Durasi (Hari)', 
        required=True, 
        default=7
    )
    
    qty_seeding = fields.Integer(
        string='Jumlah Pembibitan', 
        required=True, 
        default=1
    )
    
    estimated_transfer_date = fields.Date(
        string='Estimasi Pindah Tanam', 
        compute='_compute_estimated_transfer_date', 
        store=True
    )
    
    state = fields.Selection([
        ('draft', 'Perencanaan'),
        ('transferred', 'Pindah Tanam'),
        ('cancel', 'Gagal/Cancel')
    ], string='Status', default='draft', required=True, copy=False)

    # Perhitungan otomatis: Tanggal Pembibitan + Durasi Hari
    @api.depends('start_date', 'duration')
    def _compute_estimated_transfer_date(self):
        for record in self:
            if record.start_date and record.duration:
                record.estimated_transfer_date = record.start_date + timedelta(days=record.duration)
            else:
                record.estimated_transfer_date = False

    # Logika Generate Otomatis Kode Batch (Contoh: JUN/0001)
    @api.model_create_multi
    def create(self, vals_list):
        # Mapping nama bulan singkat dalam bahasa Inggris/Standar internasional
        months_map = {
            1: 'JAN', 2: 'FEB', 3: 'MAR', 4: 'APR', 5: 'MEI', 6: 'JUN',
            7: 'JUL', 8: 'AGU', 9: 'SEP', 10: 'OKT', 11: 'NOV', 12: 'DES'
        }
        
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                # Mengambil tanggal pembibitan yang diinput pengguna
                start_date_val = vals.get('start_date') or fields.Date.context_today(self)
                if isinstance(start_date_val, str):
                    start_date = fields.Date.from_string(start_date_val)
                else:
                    start_date = start_date_val
                
                # Menentukan prefix bulan (Contoh: JUN)
                month_string = months_map.get(start_date.month, 'TXT')
                
                # Mengambil nomor urut dari ir.sequence Odoo
                seq_number = self.env['ir.sequence'].next_by_code('hydroponic.seeding.number') or '0001'
                
                # Menggabungkan menjadi format BLN/Nomer (Contoh: JUN/0001)
                vals['name'] = f"{month_string}/{seq_number}"
                
        return super(HydroponicSeeding, self).create(vals_list)