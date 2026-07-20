# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class HydroponicJuvenile(models.Model):
    _name = 'hydroponic.juvenile'
    _description = 'Data Peremajaan Hidroponik'
    _order = 'id desc'
    _rec_name = 'seeding_id'

    # Relasi ke data Pembibitan
    seeding_id = fields.Many2one('hydroponic.seeding', string='Kode Batch', required=True, ondelete='cascade', readonly=True)
    product_id = fields.Many2one(related='seeding_id.product_id', string='Sayuran Awal (Bibit)', readonly=True)
    
    # Field BARU: Memilih produk hasil peremajaan (harus diceklis Hydroponic Route)
    juvenile_product_id = fields.Many2one(
        'product.product', 
        string='Hasil Sayur Peremajaan', 
        required=True,
        domain=[('product_tmpl_id.is_hydroponic', '=', True)]
    )

    estimated_start_date = fields.Date(related='seeding_id.estimated_transfer_date', string='Estimasi Masuk Peremajaan', readonly=True)
    qty_seeding = fields.Integer(related='seeding_id.qty_seeding', string='Jumlah Awal Semai', readonly=True)
    
    # Kolom khusus fase Peremajaan
    qty_dead = fields.Integer(string='Jumlah Mati/Sortir', default=0)
    qty_alive = fields.Integer(string='Jumlah Hidup', required=True, default=0)
    duration = fields.Integer(string='Durasi Peremajaan (Hari)', required=True, default=14)
    
    is_done = fields.Boolean(string='Ceklist Pindah Tanam (Selesai)', default=False)

    @api.onchange('qty_dead')
    def _onchange_qty_dead(self):
        if self.qty_seeding:
            self.qty_alive = self.qty_seeding - self.qty_dead

    def write(self, vals):
        res = super(HydroponicJuvenile, self).write(vals)
        
        # Jika ceklist Pindah Tanam dicentang menjadi True
        if vals.get('is_done'):
            for record in self:
                
                # --- VALIDASI PENCEGAH ERROR ---
                if not record.juvenile_product_id:
                    raise ValidationError("Gagal menyimpan! Anda harus memilih 'Hasil Sayur Peremajaan' terlebih dahulu.")
                if not record.product_id:
                    raise ValidationError("Gagal menyimpan! Data Bibit (Sayuran Awal) kosong.")
                
                # --- PENCEGAH DUPLIKASI ---
                # Cek apakah batch ini sudah pernah dibuatkan data Pendewasaannya
                existing_maturation = self.env['hydroponic.maturation'].search([('juvenile_id', '=', record.id)])
                
                # Jika belum ada, baru kita jalankan otomatisasinya
                if not existing_maturation:
                    # 1. BUAT DATA PENDEWASAAN OTOMATIS
                    self.env['hydroponic.maturation'].create({
                        'juvenile_id': record.id,
                        # Catatan: qty_entered tidak perlu ditulis lagi karena sudah otomatis (related field)
                    })

                    # 2. LOGIKA INVENTORY (STOCK MOVE)
                    company_id = self.env.company.id
                    stock_loc = self.env['stock.location'].search([('usage', '=', 'internal'), ('company_id', 'in', [company_id, False])], limit=1)
                    prod_loc = self.env['stock.location'].search([('usage', '=', 'production'), ('company_id', 'in', [company_id, False])], limit=1)
                    
                    if stock_loc and prod_loc:
                        # A. Mengurangi (Konsumsi) stok Bibit
                        move_out = self.env['stock.move'].sudo().create({
                            'name': f'Konsumsi Bibit - {record.seeding_id.name}',
                            'product_id': record.product_id.id,
                            'product_uom_qty': record.qty_alive,
                            'product_uom': record.product_id.uom_id.id,
                            'location_id': stock_loc.id,
                            'location_dest_id': prod_loc.id,
                            'company_id': company_id,
                            'state': 'draft',
                        })
                        move_out._action_confirm()
                        move_out._action_assign()
                        if hasattr(move_out, 'picked'): move_out.picked = True
                        move_out.quantity = record.qty_alive
                        move_out._action_done()

                        # B. Menambah stok Hasil Peremajaan
                        move_in = self.env['stock.move'].sudo().create({
                            'name': f'Hasil Peremajaan - {record.seeding_id.name}',
                            'product_id': record.juvenile_product_id.id,
                            'product_uom_qty': record.qty_alive,
                            'product_uom': record.juvenile_product_id.uom_id.id,
                            'location_id': prod_loc.id,
                            'location_dest_id': stock_loc.id,
                            'company_id': company_id,
                            'state': 'draft',
                        })
                        move_in._action_confirm()
                        move_in._action_assign()
                        if hasattr(move_in, 'picked'): move_in.picked = True
                        move_in.quantity = record.qty_alive
                        move_in._action_done()

        return res