# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class HydroponicMaturation(models.Model):
    _name = 'hydroponic.maturation'
    _description = 'Data Pendewasaan Hidroponik'
    _order = 'id desc'
    _rec_name = 'batch_name'

    juvenile_id = fields.Many2one('hydroponic.juvenile', string='Referensi Peremajaan', required=True, ondelete='cascade', readonly=True)
    batch_name = fields.Char(related='juvenile_id.seeding_id.name', string='Kode Batch', readonly=True)
    
    # Produk asal (mengurangi stok)
    juvenile_product_id = fields.Many2one(related='juvenile_id.juvenile_product_id', string='Sayur Masuk', readonly=True)
    qty_entered = fields.Integer(string='Total Tanaman Masuk', related='juvenile_id.qty_alive', readonly=True)
    
    # Produk tujuan (menambah stok panen)
    harvest_product_id = fields.Many2one(
        'product.product', 
        string='Produk Hasil Panen (Inventory)', 
        domain=[('product_tmpl_id.is_hydroponic', '=', True)]
    )

    state = fields.Selection([
        ('draft', 'Belum Masuk Talang'),
        ('process', 'Proses Pendewasaan'),
        ('done', 'Selesai Semua')
    ], string='Status', default='draft')

    # Relasi ke sub-tabel Talang
    line_ids = fields.One2many('hydroponic.maturation.line', 'maturation_id', string='Alokasi & Panen Talang')

    def action_start_process(self):
        """ Tombol untuk memulai proses dan memotong stok peremajaan """
        for record in self:
            if not record.line_ids:
                raise ValidationError("Anda harus menambahkan minimal 1 Talang sebelum memulai proses!")
            
            total_transfer = sum(record.line_ids.mapped('qty_transfer'))
            
            # Pengurangan Stok Remaja
            company_id = self.env.company.id
            stock_loc = self.env['stock.location'].search([('usage', '=', 'internal'), ('company_id', 'in', [company_id, False])], limit=1)
            prod_loc = self.env['stock.location'].search([('usage', '=', 'production'), ('company_id', 'in', [company_id, False])], limit=1)
            
            if stock_loc and prod_loc and record.juvenile_product_id:
                move_out = self.env['stock.move'].sudo().create({
                    'name': f'Masuk Talang - {record.batch_name}',
                    'product_id': record.juvenile_product_id.id,
                    'product_uom_qty': total_transfer,
                    'product_uom': record.juvenile_product_id.uom_id.id,
                    'location_id': stock_loc.id,
                    'location_dest_id': prod_loc.id,
                    'company_id': company_id,
                    'state': 'draft',
                })
                move_out._action_confirm()
                move_out._action_assign()
                if hasattr(move_out, 'picked'): move_out.picked = True
                move_out.quantity = total_transfer
                move_out._action_done()

            record.state = 'process'

    def action_mark_done(self):
        for record in self:
            if any(not line.is_harvested for line in record.line_ids):
                raise ValidationError("Masih ada Talang yang belum dipanen. Selesaikan semua terlebih dahulu!")
            record.state = 'done'


class HydroponicMaturationLine(models.Model):
    _name = 'hydroponic.maturation.line'
    _description = 'Rincian Panen Per Talang'

    maturation_id = fields.Many2one('hydroponic.maturation', string='Maturation Ref', ondelete='cascade')
    
    # Domain: Hanya munculkan talang yang statusnya 'Tersedia' atau yang sudah terlanjur dipilih di baris ini
    talang_id = fields.Many2one('hydroponic.talang', string='Pilih Talang', required=True, 
                                domain="['|', ('status', '=', 'available'), ('id', '=', talang_id)]")
    
    qty_transfer = fields.Integer(string='Jml Pindah Tanam', required=True, default=1)
    
    # Kolom Input Panen
    harvest_date = fields.Date(string='Tgl Panen')
    qty_harvested = fields.Integer(string='Hasil Panen (Qty/Kg)', default=0)
    qty_failed = fields.Integer(string='Jml Gagal/Mati', default=0)
    
    is_harvested = fields.Boolean(string='Selesai (Ceklist Panen)', default=False)

    @api.model_create_multi
    def create(self, vals_list):
        """ Otomatis mengunci talang saat dipilih agar tidak dibooking batch lain """
        lines = super(HydroponicMaturationLine, self).create(vals_list)
        for line in lines:
            if line.talang_id:
                line.talang_id.status = 'in_use'
        return lines

    def write(self, vals):
        """ Memicu penambahan stok jika dichecklist panen per talang """
        res = super(HydroponicMaturationLine, self).write(vals)
        if vals.get('is_harvested'):
            for record in self:
                if record.qty_harvested <= 0:
                    raise ValidationError(f"Jumlah panen untuk {record.talang_id.name} harus lebih dari 0!")
                if not record.maturation_id.harvest_product_id:
                    raise ValidationError("Pilih 'Produk Hasil Panen' di formulir atas terlebih dahulu!")
                
                # Penambahan Stok Panen
                company_id = self.env.company.id
                stock_loc = self.env['stock.location'].search([('usage', '=', 'internal'), ('company_id', 'in', [company_id, False])], limit=1)
                prod_loc = self.env['stock.location'].search([('usage', '=', 'production'), ('company_id', 'in', [company_id, False])], limit=1)
                
                if stock_loc and prod_loc:
                    move_in = self.env['stock.move'].sudo().create({
                        'name': f'Panen {record.talang_id.name} - {record.maturation_id.batch_name}',
                        'product_id': record.maturation_id.harvest_product_id.id,
                        'product_uom_qty': record.qty_harvested,
                        'product_uom': record.maturation_id.harvest_product_id.uom_id.id,
                        'location_id': prod_loc.id,
                        'location_dest_id': stock_loc.id,
                        'company_id': company_id,
                        'state': 'draft',
                    })
                    move_in._action_confirm()
                    move_in._action_assign()
                    if hasattr(move_in, 'picked'): move_in.picked = True
                    move_in.quantity = record.qty_harvested
                    move_in._action_done()
                
                # Otomatis melepaskan talang agar bisa dipakai oleh Batch berikutnya
                record.talang_id.status = 'available'
                if not record.harvest_date:
                    record.harvest_date = fields.Date.context_today(self)
        
        # Jika ceklis dihilangkan (batal panen), kunci talang kembali
        if 'is_harvested' in vals and not vals.get('is_harvested'):
            for record in self:
                record.talang_id.status = 'in_use'

        return res