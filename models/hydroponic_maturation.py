# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class HydroponicMaturation(models.Model):
    _name = 'hydroponic.maturation'
    _description = 'Data Pendewasaan Hidroponik'
    _order = 'id desc'
    _rec_name = 'batch_name'

    juvenile_id = fields.Many2one('hydroponic.juvenile', string='Ref Peremajaan', required=True, ondelete='cascade', readonly=True)
    batch_name = fields.Char(related='juvenile_id.seeding_id.name', string='Kode Batch', readonly=True)
    
    juvenile_product_id = fields.Many2one(related='juvenile_id.juvenile_product_id', string='Sayur Masuk', readonly=True)
    qty_entered = fields.Integer(string='Total Tanaman Masuk', related='juvenile_id.qty_alive', readonly=True)
    qty_unallocated = fields.Integer(string='Sisa Belum Dialokasi', compute='_compute_unallocated')
    
    harvest_product_id = fields.Many2one('product.product', string='Produk Hasil Panen (Inventory)', domain=[('product_tmpl_id.is_hydroponic', '=', True)])

    state = fields.Selection([
        ('draft', 'Belum Masuk Talang'),
        ('process', 'Proses Pendewasaan'),
        ('done', 'Selesai Semua')
    ], string='Status', default='draft')

    # 2 Tabel Berbeda untuk Tab 1 dan Tab 2
    line_ids = fields.One2many('hydroponic.maturation.line', 'maturation_id', string='Alokasi Talang')
    harvest_line_ids = fields.One2many('hydroponic.harvest.line', 'maturation_id', string='Riwayat Panen')

    @api.depends('qty_entered', 'line_ids.qty_transfer')
    def _compute_unallocated(self):
        for record in self:
            allocated = sum(record.line_ids.mapped('qty_transfer'))
            record.qty_unallocated = record.qty_entered - allocated

    def action_start_process(self):
        for record in self:
            if not record.line_ids:
                raise ValidationError("Anda harus mengalokasikan minimal 1 Talang sebelum memulai proses!")
            
            total_transfer = sum(record.line_ids.mapped('qty_transfer'))
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
            if any(not line.is_done for line in record.line_ids):
                raise ValidationError("Masih ada Talang yang belum dipanen habis. Selesaikan semua terlebih dahulu!")
            record.state = 'done'


# ==========================================
# TAB 1: ALOKASI TALANG
# ==========================================
class HydroponicMaturationLine(models.Model):
    _name = 'hydroponic.maturation.line'
    _description = 'Rincian Alokasi Per Talang'
    _rec_name = 'talang_id' # Agar namanya muncul sebagai nama Talang di dropdown

    maturation_id = fields.Many2one('hydroponic.maturation', ondelete='cascade')
    talang_id = fields.Many2one('hydroponic.talang', string='Talang', required=True)
    
    transfer_date = fields.Date(string='Tgl Pindah Tanam', default=fields.Date.context_today, required=True)
    qty_transfer = fields.Integer(string='Jml Pindah Tanam', required=True, default=1)

    harvest_line_ids = fields.One2many('hydroponic.harvest.line', 'allocation_id', string='Riwayat Panen')
    
    qty_harvested = fields.Integer(string='Total Panen', compute='_compute_harvest_totals', store=True)
    qty_failed = fields.Integer(string='Total Gagal', compute='_compute_harvest_totals', store=True)
    qty_remaining = fields.Integer(string='Sisa Belum Panen', compute='_compute_harvest_totals', store=True)
    is_done = fields.Boolean(string='Selesai', compute='_compute_harvest_totals', store=True)

    @api.depends('qty_transfer', 'harvest_line_ids.qty_harvested', 'harvest_line_ids.qty_failed')
    def _compute_harvest_totals(self):
        for record in self:
            h = sum(record.harvest_line_ids.mapped('qty_harvested'))
            f = sum(record.harvest_line_ids.mapped('qty_failed'))
            record.qty_harvested = h
            record.qty_failed = f
            record.qty_remaining = record.qty_transfer - (h + f)
            record.is_done = record.qty_remaining <= 0

    @api.constrains('talang_id', 'qty_transfer')
    def _check_talang_capacity(self):
        for record in self:
            if record.talang_id.remaining_capacity < 0:
                raise ValidationError(f"Talang {record.talang_id.name} Penuh! Kuota tidak cukup.")

    @api.constrains('qty_remaining')
    def _check_qty_remaining(self):
        for record in self:
            if record.qty_remaining < 0:
                raise ValidationError(f"Error: Total Input Panen & Gagal di {record.talang_id.name} melebihi jumlah yang ditanam!")


# ==========================================
# TAB 2: BUKU LOG PANEN (BARU)
# ==========================================
class HydroponicHarvestLine(models.Model):
    _name = 'hydroponic.harvest.line'
    _description = 'Riwayat Input Panen'

    maturation_id = fields.Many2one('hydroponic.maturation', ondelete='cascade', required=True)
    allocation_id = fields.Many2one('hydroponic.maturation.line', string='Pilih Talang', required=True, ondelete='cascade')
    
    qty_remaining_info = fields.Integer(related='allocation_id.qty_remaining', string='Sisa Sblm Input')
    
    harvest_date = fields.Date(string='Tgl Panen', default=fields.Date.context_today, required=True)
    qty_harvested = fields.Integer(string='Jml Panen (Qty)', required=True, default=0)
    qty_failed = fields.Integer(string='Jml Gagal/Mati', required=True, default=0)

    @api.model_create_multi
    def create(self, vals_list):
        records = super(HydroponicHarvestLine, self).create(vals_list)
        for record in records:
            if record.qty_harvested <= 0 and record.qty_failed <= 0:
                raise ValidationError("Jumlah Panen atau Gagal harus diisi minimal 1!")
            
            if not record.maturation_id.harvest_product_id:
                raise ValidationError("Pilih 'Produk Hasil Panen' di formulir utama terlebih dahulu!")

            # Menambah Stok ke Inventory (Hanya untuk tanaman yang berhasil dipanen)
            if record.qty_harvested > 0:
                company_id = self.env.company.id
                stock_loc = self.env['stock.location'].search([('usage', '=', 'internal'), ('company_id', 'in', [company_id, False])], limit=1)
                prod_loc = self.env['stock.location'].search([('usage', '=', 'production'), ('company_id', 'in', [company_id, False])], limit=1)
                
                if stock_loc and prod_loc:
                    move_in = self.env['stock.move'].sudo().create({
                        'name': f'Panen {record.allocation_id.talang_id.name} - {record.maturation_id.batch_name}',
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

        return records