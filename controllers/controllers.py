# -*- coding: utf-8 -*-
# from odoo import http


# class Hydroponic(http.Controller):
#     @http.route('/hydroponic/hydroponic', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/hydroponic/hydroponic/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('hydroponic.listing', {
#             'root': '/hydroponic/hydroponic',
#             'objects': http.request.env['hydroponic.hydroponic'].search([]),
#         })

#     @http.route('/hydroponic/hydroponic/objects/<model("hydroponic.hydroponic"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('hydroponic.object', {
#             'object': obj
#         })

