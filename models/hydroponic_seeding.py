# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta

class HydroponicSeeding(models.Model):
    _name = 'hydroponic.seeding'
    _description = 'Data Pembibitan Hidroponik'
    _order = 'id desc'

    name = fields.Char(string='Kode Batch', required=True, copy=False, readonly=True, default='New')
    product_id = fields.Many2one('product.product', string='Nama Sayuran', required=True, domain=[('product_tmpl_id.is_hydroponic', '=', True)])
    start_date = fields.Date(string='Tanggal Pembibitan', required=True, default=fields.Date.context_today)
    duration = fields.Integer(string='Durasi (Hari)', required=True, default=7)
    qty_seeding = fields.Integer(string='Jumlah Pembibitan', required=True, default=1)
    estimated_transfer_date = fields.Date(string='Estimasi Pindah Tanam', compute='_compute_estimated_transfer_date', store=True)
    
    actual_start_date = fields.Date(string='Aktual Pembibitan')
    actual_transfer_date = fields.Date(string='Aktual Pindah Tanam')
    start_color = fields.Char(compute='_compute_color_status')
    transfer_color = fields.Char(compute='_compute_color_status')

    # Label Pindah Tanam diubah menjadi Pindah Peremajaan
    state = fields.Selection([
        ('draft', 'Perencanaan'),
        ('in_progress', 'Pembibitan'),
        ('transferred', 'Pindah Peremajaan'),
        ('done', 'Selesai'),
        ('cancel', 'Gagal/Cancel')
    ], string='Status', default='draft', required=True, copy=False)

    def action_cancel(self):
        for record in self:
            record.state = 'cancel'

    @api.depends('start_date', 'duration')
    def _compute_estimated_transfer_date(self):
        for record in self:
            if record.start_date and record.duration:
                record.estimated_transfer_date = record.start_date + timedelta(days=record.duration)
            else:
                record.estimated_transfer_date = False

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
                year_str = start_date.strftime('%Y')
                month_str = start_date.strftime('%m')
                
                # 1. Buat kode antrian unik per bulan dan tahun (Contoh: hydroponic.batch.2026.09)
                seq_code = f'hydroponic.seeding.batch.{year_str}.{month_str}'
                
                Sequence = self.env['ir.sequence'].sudo()
                seq = Sequence.search([('code', '=', seq_code)], limit=1)
                
                # 2. Jika antrian untuk bulan tersebut belum ada, buat baru dari 0001
                if not seq:
                    seq = Sequence.create({
                        'name': f'Batch Pembibitan {month_string} {year_str}',
                        'code': seq_code,
                        'padding': 4,
                        'number_next': 1,
                        'number_increment': 1,
                        'implementation': 'standard'
                    })
                
                # 3. Tarik nomor murni (hanya angka, misal: '0001')
                seq_number = seq.next_by_id()
                
                # 4. Gabungkan teks bulan dan angka murni
                vals['name'] = f"{month_string}/{seq_number}"
                
        return super(HydroponicSeeding, self).create(vals_list)
        
    def write(self, vals):
        if 'state' in vals and not self.env.context.get('allow_revert'):
            # 1. Cegah klik manual menuju status Selesai
            if vals['state'] == 'done':
                raise ValidationError("Peringatan! Anda tidak boleh mengklik status 'Selesai' secara manual. Status ini akan terisi otomatis setelah semua tanaman habis dipanen di menu Pendewasaan & Panen.")
            
            # 2. Cegah klik status lain jika saat ini sudah Selesai (Kunci Mundur)
            for record in self:
                if record.state == 'done':
                    raise ValidationError("Batch ini sudah Selesai secara penuh! Pembatalan/Perubahan status hanya bisa dilakukan melalui menu Pendewasaan & Panen.")

        if vals.get('state') == 'in_progress':
            vals['actual_start_date'] = fields.Date.context_today(self)
        if vals.get('state') == 'transferred':
            vals['actual_transfer_date'] = fields.Date.context_today(self)
            
        res = super(HydroponicSeeding, self).write(vals)
        
        # Trigger jika status diklik menjadi 'in_progress' (Pembibitan)
        if vals.get('state') == 'in_progress':
            for record in self:
                existing = self.env['hydroponic.juvenile'].search([('seeding_id', '=', record.id)])
                if not existing:
                    # Dibuat dengan status default 'draft' (Perencanaan)
                    self.env['hydroponic.juvenile'].create({
                        'seeding_id': record.id,
                        'qty_alive': record.qty_seeding, 
                        'state': 'draft'
                    })
                
                # Logika Inventory Pengurangan/Penambahan Stok
                if record.product_id and record.product_id.product_tmpl_id.is_hydroponic:
                    current_company = self.env.company
                    dest_location = self.env['stock.location'].search([('usage', '=', 'internal'), ('company_id', 'in', [current_company.id, False])], limit=1)
                    src_location = self.env['stock.location'].search([('usage', '=', 'production'), ('company_id', 'in', [current_company.id, False])], limit=1)
                    
                    if not src_location:
                        src_location = self.env['stock.location'].search([('usage', '=', 'inventory'), ('company_id', 'in', [current_company.id, False])], limit=1)
                    
                    if dest_location and src_location:
                        move = self.env['stock.move'].sudo().create({
                            'name': f'Pembibitan Hidroponik - {record.name}',
                            'product_id': record.product_id.id,
                            'product_uom_qty': record.qty_seeding,
                            'product_uom': record.product_id.uom_id.id,
                            'location_id': src_location.id,
                            'location_dest_id': dest_location.id,
                            'company_id': current_company.id,
                            'state': 'draft',
                        })
                        move._action_confirm()
                        move._action_assign()
                        if hasattr(move, 'picked'): move.picked = True
                        move.quantity = record.qty_seeding 
                        move._action_done()

        # Jika Pembibitan diubah ke "Pindah Peremajaan", dorong form Peremajaan maju ke "Peremajaan"
        if vals.get('state') == 'transferred':
            for record in self:
                juveniles = self.env['hydroponic.juvenile'].search([('seeding_id', '=', record.id)])
                for juv in juveniles:
                    if juv.state != 'in_progress':
                        juv.state = 'in_progress'
                        
        return res

    @api.depends('start_date', 'estimated_transfer_date', 'actual_start_date', 'actual_transfer_date', 'state')
    def _compute_color_status(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.state == 'cancel':
                record.start_color = 'normal'
                record.transfer_color = 'normal'
                continue

            # 1. LOGIKA WARNA TANGGAL PEMBIBITAN
            if record.start_date:
                if record.state == 'draft': # Masih draf (warna dinamis)
                    delta = (record.start_date - today).days
                    if delta < 0: record.start_color = 'danger'     # Lewat hari (Merah)
                    elif delta == 0: record.start_color = 'success' # Hari H (Hijau)
                    elif delta == 1: record.start_color = 'warning' # H-1 (Kuning)
                    else: record.start_color = 'normal'             # Masih lama
                else: # Sudah dieksekusi (warna terkunci)
                    compare_date = record.actual_start_date or record.start_date
                    delta = (record.start_date - compare_date).days
                    if delta < 0: record.start_color = 'danger'     # Dieksekusi Terlambat
                    else: record.start_color = 'success'            # Dieksekusi Tepat/Lebih Awal
            else:
                record.start_color = 'normal'
                
            # 2. LOGIKA WARNA ESTIMASI PINDAH TANAM
            if record.estimated_transfer_date:
                if record.state in ['draft', 'in_progress']: # Belum pindah (warna dinamis)
                    delta = (record.estimated_transfer_date - today).days
                    if delta < 0: record.transfer_color = 'danger'
                    elif delta == 0: record.transfer_color = 'success'
                    elif delta == 1: record.transfer_color = 'warning'
                    else: record.transfer_color = 'normal'
                else: # Sudah pindah tanam (warna terkunci)
                    compare_date = record.actual_transfer_date or record.estimated_transfer_date
                    delta = (record.estimated_transfer_date - compare_date).days
                    if delta < 0: record.transfer_color = 'danger'
                    else: record.transfer_color = 'success'
            else:
                record.transfer_color = 'normal'