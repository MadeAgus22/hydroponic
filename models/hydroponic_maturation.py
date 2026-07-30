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
        ('draft', 'Perencanaan'),
        ('in_progress', 'Pendewasaan'),
        ('harvest', 'Masa Panen'),
        ('done', 'Selesai')
    ], string='Status', default='draft', required=True)

    # 2 Tabel Berbeda untuk Tab 1 dan Tab 2
    line_ids = fields.One2many('hydroponic.maturation.line', 'maturation_id', string='Alokasi Talang')
    harvest_line_ids = fields.One2many('hydroponic.harvest.line', 'maturation_id', string='Riwayat Panen')

    @api.depends('qty_entered', 'line_ids.qty_transfer')
    def _compute_unallocated(self):
        for record in self:
            allocated = sum(record.line_ids.mapped('qty_transfer'))
            record.qty_unallocated = record.qty_entered - allocated

    def write(self, vals):
        res = super(HydroponicMaturation, self).write(vals)
        
        # 1. SAAT DIKLIK "PENDEWASAAN"
        if vals.get('state') == 'in_progress':
            for record in self:
                if not record.line_ids:
                    raise ValidationError("Gagal! Anda harus mengalokasikan minimal 1 Talang sebelum masuk ke fase Pendewasaan!")

                # Jika sisa > 0, DAN tidak berasal dari tombol paksa, DAN bukan otomatisasi
                if record.qty_unallocated > 0 and not self.env.context.get('force_progress') and not self.env.context.get('auto_progress'):
                    raise ValidationError("Peringatan! Masih ada sisa tanaman yang belum dialokasikan.\nJika Anda ingin mengabaikan sisa tersebut, silakan gunakan tombol 'Paksa Masuk Pendewasaan' di pojok kiri atas.")

                # Sinkronisasi mundur ke Peremajaan
                if record.juvenile_id.state != 'transferred':
                    record.juvenile_id.state = 'transferred'
                
                # Logika Inventory: Masuk Talang (Dari fungsi action_start_process lama)
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

                

        # 2. SAAT DIKLIK "MASA PANEN"
        if vals.get('state') == 'harvest':
            for record in self:
                if record.qty_unallocated > 0:
                    raise ValidationError(f"Belum bisa masuk Masa Panen! Masih ada {record.qty_unallocated} tanaman yang belum dialokasikan ke Talang.")
        
        # 3. SAAT DIKLIK "SELESAI"
        if vals.get('state') == 'done':
            for record in self:
                if any(not line.is_done for line in record.line_ids):
                    raise ValidationError("Masih ada Talang yang sisa panennya belum 0. Selesaikan semua terlebih dahulu!")
                record.juvenile_id.with_context(allow_revert=True).state = 'done'
                record.juvenile_id.seeding_id.with_context(allow_revert=True).state = 'done'

        # 4. JIKA DIBATALKAN MANUAL DARI "SELESAI" KEMBALI KE "MASA PANEN"
        if vals.get('state') == 'harvest':
            for record in self:
                if record.qty_unallocated > 0:
                    raise ValidationError(f"Belum bisa masuk Masa Panen! Masih ada {record.qty_unallocated} tanaman yang belum dialokasikan ke Talang.")
                
                # BUKA KUNCI MUNDUR: Jika status sebelumnya adalah Selesai, kembalikan menu sblmnya ke posisi "Pindah"
                if record.state == 'done':
                    record.juvenile_id.with_context(allow_revert=True).state = 'transferred'
                    record.juvenile_id.seeding_id.with_context(allow_revert=True).state = 'transferred'

        return res

    def action_force_in_progress(self):
        """ Tombol untuk memaksa masuk pendewasaan dengan konfirmasi Ya/Tidak """
        for record in self:
            # Mengirimkan konteks 'force_progress' agar lolos dari blokiran
            record.with_context(force_progress=True).state = 'in_progress'


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

    @api.constrains('qty_transfer')
    def _check_batch_quota(self):
        """ Mencegah pemindahan tanaman melebihi sisa dari Peremajaan """
        for record in self:
            # Hitung total yang dialokasikan di seluruh baris pada batch ini
            allocated = sum(record.maturation_id.line_ids.mapped('qty_transfer'))
            
            # Jika total alokasi lebih besar dari total masuk, munculkan error!
            if allocated > record.maturation_id.qty_entered:
                raise ValidationError(f"Alokasi Gagal! Anda mencoba memasukkan total {allocated} tanaman, padahal Total Tanaman Masuk hanya {record.maturation_id.qty_entered}. Sisa kuota tidak cukup!")

    @api.constrains('qty_remaining')
    def _check_qty_remaining(self):
        for record in self:
            if record.qty_remaining < 0:
                raise ValidationError(f"Error: Total Input Panen & Gagal di {record.talang_id.name} melebihi jumlah yang ditanam!")

    @api.model_create_multi
    def create(self, vals_list):
        records = super(HydroponicMaturationLine, self).create(vals_list)
        # Cek otomatis setelah baris ditambahkan
        for record in records:
            if record.maturation_id.state == 'draft' and record.maturation_id.qty_unallocated <= 0:
                # Otomatis maju dengan konteks 'auto_progress' agar lolos validasi
                record.maturation_id.with_context(auto_progress=True).state = 'in_progress'
        return records

    def write(self, vals):
        res = super(HydroponicMaturationLine, self).write(vals)
        # Cek otomatis jika ada perubahan jumlah
        if 'qty_transfer' in vals:
            for record in self:
                if record.maturation_id.state == 'draft' and record.maturation_id.qty_unallocated <= 0:
                    record.maturation_id.with_context(auto_progress=True).state = 'in_progress'
        return res

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

            maturation = record.maturation_id
            
            # Cek apakah setelah diinput, SEMUA talang sisa panennya sudah 0 (Habis)
            if all(line.is_done for line in maturation.line_ids):
                maturation.state = 'done'
            elif maturation.state == 'in_progress':
                maturation.state = 'harvest'

        return records