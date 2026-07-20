# -*- coding: utf-8 -*-
{
    'name': 'Hydroponic Management System',
    'version': '18.0.1.0.0',
    'summary': 'Manajemen Produksi Penanaman Hidroponik',
    'description': """
        Modul kustom untuk mengelola siklus produksi hidroponik:
        - Dashboard Produksi
        - Manajemen Pembibitan (Seeding)
        - Manajemen Peremajaan (Juvenile)
        - Manajemen Pendewasaan & Panen (Harvest)
    """,
    'author': 'Artgroo',
    'category': 'Manufacturing',
    'depends': ['base', 'product', 'stock'],
    'data': [
        # 'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/hydroponic_seeding_views.xml',
        'views/hydroponic_juvenile_views.xml',
        'views/hydroponic_maturation_views.xml',
        'views/product_template_views.xml',
        'views/hydroponic_menus.xml',
        
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}