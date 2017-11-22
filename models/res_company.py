# -*- coding: utf-8 -*-
from openerp import api, fields, models

class ResCompanyTicket(models.Model):

    _inherit = "res.company"
    
    next_support_ticket_number = fields.Integer(string="Next Support Num. de Tiquete", default="51976386")