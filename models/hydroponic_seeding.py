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
        domain=[('product_tmpl_id.is_hydroponic', '=', True)]
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
        ('in_progress', 'Pembibitan'),
        ('transferred', 'Pindah Tanam'),
        ('cancel', 'Gagal/Cancel')
    ], string='Status', default='draft', required=True, copy=False)

    def action_cancel(self):
        for record in self:
            record.state = 'cancel'

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
        months_map = {
            1: 'JAN', 2: 'FEB', 3: 'MAR', 4: 'APR', 5: 'MEI', 6: 'JUN',
            7: 'JUL', 8: 'AGU', 9: 'SEP', 10: 'OKT', 11: 'NOV', 12: 'DES'
        }
        
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                start_date_val = vals.get('start_date') or fields.Date.context_today(self)
                if isinstance(start_date_val, str):
                    start_date = fields.Date.from_string(start_date_val)
                else:
                    start_date = start_date_val
                
                month_string = months_map.get(start_date.month, 'TXT')
                
                # --- JURUS PAMUNGKAS: Cek Database Langsung ---
                Sequence = self.env['ir.sequence'].sudo()
                # 1. Cari apakah sequence sudah ada di database
                seq = Sequence.search([('code', '=', 'hydroponic.seeding.batch')], limit=1)
                
                # 2. Jika ternyata XML gagal membuatnya, Python yang akan membuatnya sekarang juga!
                if not seq:
                    seq = Sequence.create({
                        'name': 'Nomor Urut Batch Pembibitan (Auto)',
                        'code': 'hydroponic.seeding.batch',
                        'padding': 4,
                        'number_next': 1,
                        'number_increment': 1,
                        'implementation': 'no_gap'
                    })
                
                # 3. Ambil nomor antrian secara paksa menggunakan ID sequence
                seq_number = seq.next_by_id()
                
                # 4. Gabungkan menjadi format JUL/0001, JUL/0002, dst.
                vals['name'] = f"{month_string}/{seq_number}"
                
        return super(HydroponicSeeding, self).create(vals_list)
    
    def write(self, vals):
        res = super(HydroponicSeeding, self).write(vals)
        
        # Trigger jika status diklik menjadi 'in_progress' (Pembibitan)
        if vals.get('state') == 'in_progress':
            for record in self:
                # 1. LOGIKA PEREMAJAAN
                existing = self.env['hydroponic.juvenile'].search([('seeding_id', '=', record.id)])
                if not existing:
                    self.env['hydroponic.juvenile'].create({
                        'seeding_id': record.id,
                        'qty_alive': record.qty_seeding, 
                    })
                
                # 2. LOGIKA INVENTORY SESUAI STANDAR ODOO (MULTI-COMPANY SAFE)
                if record.product_id and record.product_id.product_tmpl_id.is_hydroponic:
                    
                    # Dapatkan identitas perusahaan yang sedang aktif (PT Semesta Jaya)
                    current_company = self.env.company
                    
                    # Cari Gudang Tujuan yang khusus milik perusahaan ini (atau bersifat global/False)
                    dest_location = self.env['stock.location'].search([
                        ('usage', '=', 'internal'),
                        ('company_id', 'in', [current_company.id, False])
                    ], limit=1)
                    
                    # Cari Gudang Asal (Produksi) yang khusus milik perusahaan ini
                    src_location = self.env['stock.location'].search([
                        ('usage', '=', 'production'),
                        ('company_id', 'in', [current_company.id, False])
                    ], limit=1)
                    
                    # Fallback jika gudang produksi belum ada
                    if not src_location:
                        src_location = self.env['stock.location'].search([
                            ('usage', '=', 'inventory'),
                            ('company_id', 'in', [current_company.id, False])
                        ], limit=1)
                    
                    # Eksekusi Surat Jalan (Stock Move)
                    if dest_location and src_location:
                        move = self.env['stock.move'].sudo().create({
                            'name': f'Pembibitan Hidroponik - {record.name}',
                            'product_id': record.product_id.id,
                            'product_uom_qty': record.qty_seeding,
                            'product_uom': record.product_id.uom_id.id,
                            'location_id': src_location.id,
                            'location_dest_id': dest_location.id,
                            'company_id': current_company.id, # KUNCI PENYELESAIAN ERROR
                            'state': 'draft',
                        })
                        
                        # Proses otomatisasi pemindahan barang ala Odoo 18
                        move._action_confirm()
                        move._action_assign()
                        
                        if hasattr(move, 'picked'):
                            move.picked = True
                        move.quantity = record.qty_seeding 
                        
                        move._action_done()
                        
        return res