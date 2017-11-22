# -*- coding: utf-8 -*-
import werkzeug
import json
import base64
from random import randint
import os

import logging
_logger = logging.getLogger(__name__)

import openerp.http as http
from openerp.http import request

from openerp.addons.website.models.website import slug

class SupportTicketController(http.Controller):

    @http.route('/support/subcategories/fetch', type='http', auth="public", website=True)
    def support_subcategories_fetch(self, **kwargs):

        values = {}
	for field_name, field_value in kwargs.items():
	    values[field_name] = field_value
	            
	sub_categories = request.env['website.support.ticket.subcategory'].sudo().search([('parent_category_id','=', int(values['category']) )])
	
	#Only return a dropdown if this category has subcategories
	return_string = ""
	
	if sub_categories:
            return_string = ""

	    return_string += "<div class=\"form-group\">\n"
	    return_string += "    <label class=\"col-md-3 col-sm-4 control-label\" for=\"subcategory\">Subcategoría</label>\n"
	    return_string += "    <div class=\"col-md-7 col-sm-8\">\n"

            return_string += "        <select class=\"form-control\" name=\"subcategory\">\n"
            for sub_category in request.env['website.support.ticket.subcategory'].sudo().search([('parent_category_id','=', int(values['category']) )]):
                return_string += "            <option value=\"" + str(sub_category.id) + "\">" + sub_category.name.encode("utf-8") + "</option>\n"

            return_string += "        </select>\n"
	    return_string += "    </div>\n"
            return_string += "</div>\n"
            
        return return_string

    @http.route('/support/survey/<portal_key>', type="http", auth="public", website=True)
    def support_ticket_survey(self, portal_key):
        """Display the survey"""

        support_ticket = request.env['website.support.ticket'].search([('portal_access_key','=', portal_key)])

        if support_ticket.support_rating:
            #TODO some security incase they guess the portal key of an incomplete survey
            return "Survey Already Complete"
        else:
            return http.request.render('website_support.support_ticket_survey_page', {'support_ticket': support_ticket})


    @http.route('/support/survey/process/<portal_key>', type="http", auth="public", website=True)
    def support_ticket_survey_process(self, portal_key, **kw):
        """Insert Survey Response"""

        values = {}
 	for field_name, field_value in kw.items():
            values[field_name] = field_value

        support_ticket = request.env['website.support.ticket'].search([('portal_access_key','=', portal_key)])

        if support_ticket.support_rating:
            #TODO some security incase they guess the portal key of an incomplete survey
            return "Survey Already Complete"
        else:
            support_ticket.support_rating = values['rating']
            support_ticket.support_comment = values['comment']
            return http.request.render('website_support.support_survey_thank_you', {})

    @http.route('/support/help', type="http", auth="public", website=True)
    def support_help(self, **kw):
        """Displays all help groups and thier child help pages"""
        return http.request.render('website_support.support_help_pages', {'help_groups': http.request.env['website.support.help.groups'].sudo().search([])})
        
    @http.route('/support/ticket/submit', type="http", auth="public", website=True)
    def support_submit_ticket(self, **kw):
        """Let's public and registered user submit a support ticket"""
        person_name = ""
        if http.request.env.user.name != "Public user":
            person_name = http.request.env.user.name

        setting_max_ticket_attachments = request.env['ir.values'].get_default('website.support.settings', 'max_ticket_attachments')
        
        if setting_max_ticket_attachments == 0:
            #Back compatablity
            setting_max_ticket_attachments = 2
 
        setting_max_ticket_attachment_filesize = request.env['ir.values'].get_default('website.support.settings', 'max_ticket_attachment_filesize')

        if setting_max_ticket_attachment_filesize == 0:
            #Back compatablity
            setting_max_ticket_attachment_filesize = 500
            
        return http.request.render('website_support.support_submit_ticket', {'categories': http.request.env['website.support.ticket.categories'].sudo().search([]), 'person_name': person_name, 'email': http.request.env.user.email, 'setting_max_ticket_attachments': setting_max_ticket_attachments, 'setting_max_ticket_attachment_filesize': setting_max_ticket_attachment_filesize})

    @http.route('/support/feedback/process/<help_page>', type="http", auth="public", website=True)
    def support_feedback(self, help_page, **kw):
        """Process user feedback"""
 
        values = {}
 	for field_name, field_value in kw.items():
            values[field_name] = field_value
            
        #Don't want them distorting the rating by submitting -50000 ratings
        if int(values['rating']) < 1 or int(values['rating']) > 5:
            return "Invalid rating"
           
        #Feeback is required
        if values['feedback'] == "":
            return "Feedback required"
        
        request.env['website.support.help.page.feedback'].sudo().create({'hp_id': int(help_page), 'feedback_rating': values['rating'], 'feedback_text': values['feedback'] })

        return werkzeug.utils.redirect("/support/help")

    @http.route('/helpgroup/new/<group>', type='http', auth="public", website=True)
    def help_group_create(self, group, **post):
        """Add new help group via content menu"""
        help_group = request.env['website.support.help.groups'].create({'name': group})
        return werkzeug.utils.redirect("/support/help")

    @http.route('/helppage/new', type='http', auth="public", website=True)
    def help_page_create(self, group_id, **post):
        """Add new help page via content menu"""
        help_page = request.env['website.support.help.page'].create({'group_id': group_id,'name': "New Help Page"})
        return werkzeug.utils.redirect("/support/help/%s/%s?enable_editor=1" % (slug(help_page.group_id), slug(help_page)))

    @http.route(['''/support/help/<model("website.support.help.groups"):help_group>/<model("website.support.help.page", "[('group_id','=',help_group[0])]"):help_page>'''], type='http', auth="public", website=True)
    def help_page(self, help_group, help_page, enable_editor=None, **post):
        """Displays help page template"""
        return http.request.render("website_support.help_page", {'help_page':help_page})


    @http.route('/support/ticket/process', type="http", auth="public", website=True, csrf=True)
    def support_process_ticket(self, **kwargs):
        """Adds the support ticket to the database and sends out emails to everyone following the support ticket category"""
        values = {}
	for field_name, field_value in kwargs.items():
            values[field_name] = field_value

        if values['my_gold'] != "256":
            return "Bot Detected"
        
        my_attachment = ""
        file_name = ""
        if 'file' in values:
            #Back compatablity for single attachment
            my_attachment = base64.encodestring(values['file'].read() )
            file_name = values['file'].filename
            file_extension = os.path.splitext(file_name)[1]
            if file_extension == ".exe":
                return "exe files are not allowed"
        
        if "subcategory" in values:
            sub_category = values['subcategory']
        else:
            sub_category = ""
            
        
        if http.request.env.user.name != "Public user":
            portal_access_key = randint(1000000000,2000000000)
            new_ticket_id = request.env['website.support.ticket'].sudo().create({'person_name':values['person_name'],'last_name':values['last_name'],'num_id':values['num_id'],'country':values['country'],'departamento':values['departamento'],'city_origin':values['city_origin'],'school':values['school'], 'address':values['address'],'phone_number':values['phone_number'],'category':values['category'], 'sub_category_id': sub_category, 'email':values['email'], 'description':values['description'], 'subject':values['subject'],'partner_id':http.request.env.user.partner_id.id, 'attachment': my_attachment, 'attachment_filename': file_name})
            partner = http.request.env.user.partner_id
            
            #Add to the communication history
            partner.message_post(body="Customer " + partner.name + " has sent in a new support ticket", subject="New Support Ticket")
            
        else:
            search_partner = request.env['res.partner'].sudo().search([('email','=', values['email'] )])


            if len(search_partner) > 0:
                portal_access_key = randint(1000000000,2000000000)
                new_ticket_id = request.env['website.support.ticket'].sudo().create({'person_name':values['person_name'],'last_name':values['last_name'],'num_id':values['num_id'],'country':values['country'],'departamento':values['departamento'],'city_origin':values['city_origin'],'school':values['school'], 'address':values['address'],'phone_number':values['phone_number'], 'category':values['category'], 'sub_category_id': sub_category, 'email':values['email'],'description':values['description'], 'subject':values['subject'], 'attachment': my_attachment, 'attachment_filename': file_name, 'partner_id':search_partner[0].id, 'portal_access_key': portal_access_key})
            else:
                portal_access_key = randint(1000000000,2000000000)
                new_ticket_id = request.env['website.support.ticket'].sudo().create({'person_name':values['person_name'], 'last_name':values['last_name'],'num_id':values['num_id'],'country':values['country'],'departamento':values['departamento'],'city_origin':values['city_origin'],'school':values['school'], 'address':values['address'],'phone_number':values['phone_number'],'category':values['category'], 'sub_category_id': sub_category, 'email':values['email'], 'description':values['description'], 'subject':values['subject'],'attachment': my_attachment, 'attachment_filename': file_name, 'portal_access_key': portal_access_key})

        if 'file' in values:
            try:
                for c_file in request.httprequest.files.getlist('file'):
                    data = c_file.read()

                    request.env['ir.attachment'].create({
                        'name': c_file.filename,
                        'datas': data.encode('base64'),
                        'datas_fname': c_file.filename,
                        'res_model': 'website.support.ticket',
                        'res_id': new_ticket_id.id
                    })
            except Exception, e:
                logger.exception("Failed to upload image to attachment")

        return werkzeug.utils.redirect("/support/ticket/thanks")
        
        
    @http.route('/support/ticket/thanks', type="http", auth="public", website=True)
    def support_ticket_thanks(self, **kw):
        """Displays a thank you page after the user submits a ticket"""
        return http.request.render('website_support.support_thank_you', {})

    @http.route('/support/ticket/view', type="http", auth="user", website=True)
    def support_ticket_view_list(self, **kw):
        """Displays a list of Tiquetes de Solicitudes owned by the logged in user"""
        
        extra_access = []
        for extra_permission in http.request.env.user.partner_id.stp_ids:
            extra_access.append(extra_permission.id)
        
        support_tickets = http.request.env['website.support.ticket'].sudo().search(['|', ('partner_id','=',http.request.env.user.partner_id.id), ('partner_id', 'in', extra_access), ('partner_id','!=',False) ])
        
        return http.request.render('website_support.support_ticket_view_list', {'support_tickets':support_tickets,'ticket_count':len(support_tickets)})

    @http.route('/support/ticket/view/<ticket>', type="http", auth="user", website=True)
    def support_ticket_view(self, ticket):
        """View an individual support ticket"""
        
        extra_access = []
        for extra_permission in http.request.env.user.partner_id.stp_ids:
            extra_access.append(extra_permission.id)
        
        #only let the user this ticket is assigned to view this ticket
        support_ticket = http.request.env['website.support.ticket'].sudo().search(['|', ('partner_id','=',http.request.env.user.partner_id.id), ('partner_id', 'in', extra_access), ('id','=',ticket) ])[0]
        return http.request.render('website_support.support_ticket_view', {'support_ticket':support_ticket})

    @http.route('/support/portal/ticket/view/<portal_access_key>', type="http", auth="public", website=True)
    def support_portal_ticket_view(self, portal_access_key):
        """View an individual support ticket (portal access)"""
        
        support_ticket = http.request.env['website.support.ticket'].sudo().search([('portal_access_key','=',portal_access_key) ])[0]
        return http.request.render('website_support.support_ticket_view', {'support_ticket':support_ticket, 'portal_access_key': portal_access_key})

    @http.route('/support/portal/ticket/comment', type="http", auth="public", website=True)
    def support_portal_ticket_comment(self, **kw):
        """Adds a comment to the support ticket"""

        values = {}
        for field_name, field_value in kw.items():
            values[field_name] = field_value
        
        support_ticket = http.request.env['website.support.ticket'].sudo().search([('portal_access_key','=', values['portal_access_key'] ) ])[0]

        http.request.env['website.support.ticket.message'].create({'ticket_id':support_ticket.id, 'by': 'customer','content':values['comment']})
        
        support_ticket.state = request.env['ir.model.data'].sudo().get_object('website_support', 'website_ticket_state_customer_replied')
            
        request.env['website.support.ticket'].sudo().browse(support_ticket.id).message_post(body=values['comment'], subject="Support Ticket Reply", message_type="comment")
        
        return werkzeug.utils.redirect("/support/portal/ticket/view/" + str(support_ticket.portal_access_key) )
        
    @http.route('/support/ticket/comment',type="http", auth="user")
    def support_ticket_comment(self, **kw):
        """Adds a comment to the support ticket"""

        values = {}
        for field_name, field_value in kw.items():
            values[field_name] = field_value
        
        ticket = http.request.env['website.support.ticket'].search([('id','=',values['ticket_id'])])
        
        #check if this user owns this ticket
        if ticket.partner_id.id == http.request.env.user.partner_id.id or ticket.partner_id in http.request.env.user.partner_id.stp_ids:

            http.request.env['website.support.ticket.message'].create({'ticket_id':ticket.id, 'by': 'customer','content':values['comment']})
            
            ticket.state = request.env['ir.model.data'].sudo().get_object('website_support', 'website_ticket_state_customer_replied')
            
            request.env['website.support.ticket'].sudo().browse(ticket.id).message_post(body=values['comment'], subject="Support Ticket Reply", message_type="comment")

        else:
            return "You do not have permission to submit this commment"
            
        return werkzeug.utils.redirect("/support/ticket/view/" + str(ticket.id))
        

    @http.route('/support/help/auto-complete',auth="public", website=True, type='http')
    def support_help_autocomplete(self, **kw):
        """Provides an autocomplete list of help pages"""
        values = {}
        for field_name, field_value in kw.items():
            values[field_name] = field_value
        
        return_string = ""
        
        my_return = []
        
        help_pages = request.env['website.support.help.page'].sudo().search([('name','=ilike',"%" + values['term'] + "%")],limit=5)
        
        for help_page in help_pages:
            #return_item = {"label": help_page.name + "<br/><sub>" + help_page.group_id.name + "</sub>","value": help_page.url_generated}
            return_item = {"label": help_page.name,"value": help_page.url_generated}
            my_return.append(return_item) 
        
        return json.JSONEncoder().encode(my_return)
