# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import logging

from openerp.modules.module import get_module_resource
from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp import tools
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)


class hr_employee_category(osv.osv):

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        reads = self.read(cr, uid, ids, ['name','parent_id'], context=context)
        res = []
        for record in reads:
            name = record['name']
            if record['parent_id']:
                name = record['parent_id'][1]+' / '+name
            res.append((record['id'], name))
        return res

    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    _name = "hr.employee.category"
    _description = "Employee Category"
    _columns = {
        'name': fields.char("Category", size=64, required=True),
        'complete_name': fields.function(_name_get_fnc, type="char", string='Name'),
        'parent_id': fields.many2one('hr.employee.category', 'Parent Category', select=True),
        'child_ids': fields.one2many('hr.employee.category', 'parent_id', 'Child Categories'),
        'employee_ids': fields.many2many('hr.employee', 'employee_category_rel', 'category_id', 'emp_id', 'Employees'),
    }

    def _check_recursion(self, cr, uid, ids, context=None):
        level = 100
        while len(ids):
            cr.execute('select distinct parent_id from hr_employee_category where id IN %s', (tuple(ids), ))
            ids = filter(None, map(lambda x:x[0], cr.fetchall()))
            if not level:
                return False
            level -= 1
        return True

    _constraints = [
        (_check_recursion, 'Error! You cannot create recursive Categories.', ['parent_id'])
    ]


class hr_job(osv.osv):

    def _no_of_employee(self, cr, uid, ids, name, args, context=None):
        res = {}
        for job in self.browse(cr, uid, ids, context=context):
            nb_employees = len(job.employee_ids or [])
            res[job.id] = {
                'no_of_employee': nb_employees,
                'expected_employees': nb_employees + job.no_of_recruitment,
            }
        return res

    def _get_job_position(self, cr, uid, ids, context=None):
        res = []
        for employee in self.pool.get('hr.employee').browse(cr, uid, ids, context=context):
            if employee.job_id:
                res.append(employee.job_id.id)
        return res

    _name = "hr.job"
    _description = "Job Description"
    _inherit = ['mail.thread']
    _columns = {
        'name': fields.char('Job Name', size=128, required=True, select=True),
        # TO CLEAN: when doing a cleaning, we should change like this:
        #   no_of_recruitment: a function field
        #   expected_employees: float
        # This would allow a clean update when creating new employees.
        'expected_employees': fields.function(_no_of_employee, string='Total Forecasted Employees',
            help='Expected number of employees for this job position after new recruitment.',
            store = {
                'hr.job': (lambda self,cr,uid,ids,c=None: ids, ['no_of_recruitment'], 10),
                'hr.employee': (_get_job_position, ['job_id'], 10),
            },
            multi='no_of_employee'),
        'no_of_employee': fields.function(_no_of_employee, string="Current Number of Employees",
            help='Number of employees currently occupying this job position.',
            store = {
                'hr.employee': (_get_job_position, ['job_id'], 10),
            },
            multi='no_of_employee'),
        'no_of_recruitment': fields.float('Expected in Recruitment', help='Number of new employees you expect to recruit.'),
        'employee_ids': fields.one2many('hr.employee', 'job_id', 'Employees', groups='base.group_user'),
        'description': fields.text('Job Description'),
        'requirements': fields.text('Requirements'),
        'department_id': fields.many2one('hr.department', 'Department'),
        'company_id': fields.many2one('res.company', 'Company'),
        'state': fields.selection([('open', 'No Recruitment'), ('recruit', 'Recruitement in Progress')], 'Status', readonly=True, required=True,
            help="By default 'In position', set it to 'In Recruitment' if recruitment process is going on for this job position."),
    }
    _defaults = {
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'hr.job', context=c),
        'state': 'open',
    }

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)', 'The name of the job position must be unique per company!'),
    ]


    def on_change_expected_employee(self, cr, uid, ids, no_of_recruitment, no_of_employee, context=None):
        if context is None:
            context = {}
        return {'value': {'expected_employees': no_of_recruitment + no_of_employee}}

    def job_recruitement(self, cr, uid, ids, *args):
        for job in self.browse(cr, uid, ids):
            no_of_recruitment = job.no_of_recruitment == 0 and 1 or job.no_of_recruitment
            self.write(cr, uid, [job.id], {'state': 'recruit', 'no_of_recruitment': no_of_recruitment})
        return True

    def job_open(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state': 'open', 'no_of_recruitment': 0})
        return True


class hr_employee(osv.osv):
    _name = "hr.employee"
    _description = "Employee"
    _order = 'name_related'
    _inherits = {'resource.resource': "resource_id"}
    _inherit = ['mail.thread']

    def _get_image(self, cr, uid, ids, name, args, context=None):
        result = dict.fromkeys(ids, False)
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = tools.image_get_resized_images(obj.image)
        return result

    def _set_image(self, cr, uid, id, name, value, args, context=None):
        return self.write(cr, uid, [id], {'image': tools.image_resize_image_big(value)}, context=context)

    _columns = {
        #we need a related field in order to be able to sort the employee by name
        'name_related': fields.related('resource_id', 'name', type='char', string='Name', readonly=True, store=True),
        'country_id': fields.many2one('res.country', 'Nationality'),
        'birthday': fields.date("Date of Birth"),
        'ssnid': fields.char('SSN No', size=32, help='Social Security Number'),
        'sinid': fields.char('SIN No', size=32, help="Social Insurance Number"),
        'identification_id': fields.char('Identification No', size=32),
        'otherid': fields.char('Other Id', size=64),
        'gender': fields.selection([('male', 'Male'), ('female', 'Female')], 'Gender'),
        'marital': fields.selection([('single', 'Single'), ('married', 'Married'), ('widower', 'Widower'), ('divorced', 'Divorced')], 'Marital Status'),
        'department_id': fields.many2one('hr.department', 'Department'),
        'address_id': fields.many2one('res.partner', 'Working Address'),
        'address_home_id': fields.many2one('res.partner', 'Home Address'),
        'bank_account_id': fields.many2one('res.partner.bank', 'Bank Account Number', domain="[('partner_id','=',address_home_id)]", help="Employee bank salary account"),
        'work_phone': fields.char('Work Phone', size=32, readonly=False),
        'mobile_phone': fields.char('Work Mobile', size=32, readonly=False),
        'work_email': fields.char('Work Email', size=240),
        'work_location': fields.char('Office Location', size=32),
        'notes': fields.text('Notes'),
        'parent_id': fields.many2one('hr.employee', 'Manager'),
        'category_ids': fields.many2many('hr.employee.category', 'employee_category_rel', 'emp_id', 'category_id', 'Tags'),
        'child_ids': fields.one2many('hr.employee', 'parent_id', 'Subordinates'),
        'resource_id': fields.many2one('resource.resource', 'Resource', ondelete='cascade', required=True),
        'coach_id': fields.many2one('hr.employee', 'Coach'),
        'job_id': fields.many2one('hr.job', 'Job'),
        # image: all image fields are base64 encoded and PIL-supported
        'image': fields.binary("Photo",
            help="This field holds the image used as photo for the employee, limited to 1024x1024px."),
        'image_medium': fields.function(_get_image, fnct_inv=_set_image,
            string="Medium-sized photo", type="binary", multi="_get_image",
            store = {
                'hr.employee': (lambda self, cr, uid, ids, c={}: ids, ['image'], 10),
            },
            help="Medium-sized photo of the employee. It is automatically "\
                 "resized as a 128x128px image, with aspect ratio preserved. "\
                 "Use this field in form views or some kanban views."),
        'image_small': fields.function(_get_image, fnct_inv=_set_image,
            string="Smal-sized photo", type="binary", multi="_get_image",
            store = {
                'hr.employee': (lambda self, cr, uid, ids, c={}: ids, ['image'], 10),
            },
            help="Small-sized photo of the employee. It is automatically "\
                 "resized as a 64x64px image, with aspect ratio preserved. "\
                 "Use this field anywhere a small image is required."),
        'passport_id': fields.char('Passport No', size=64),
        'color': fields.integer('Color Index'),
        'city': fields.related('address_id', 'city', type='char', string='City'),
        'login': fields.related('user_id', 'login', type='char', string='Login', readonly=1),
        'last_login': fields.related('user_id', 'date', type='datetime', string='Latest Connection', readonly=1),
    }

    def _get_default_image(self, cr, uid, context=None):
        image_path = get_module_resource('hr', 'static/src/img', 'default_image.png')
        return tools.image_resize_image_big(open(image_path, 'rb').read().encode('base64'))

    defaults = {
        'active': 1,
        'image': _get_default_image,
        'color': 0,
    }

    def create(self, cr, uid, data, context=None):
        if context is None:
            context = {}
        create_ctx = dict(context, mail_create_nolog=True)
        employee_id = super(hr_employee, self).create(cr, uid, data, context=create_ctx)
        employee = self.browse(cr, uid, employee_id, context=context)
        if employee.user_id:
            # send a copy to every user of the company
            company_id = employee.user_id.partner_id.company_id.id
            partner_ids = self.pool.get('res.partner').search(cr, uid, [
                ('company_id', '=', company_id),
                ('user_ids', '!=', False)], context=context)
        else:
            partner_ids = []
        self.message_post(cr, uid, [employee_id],
            body=_('Welcome to %s! Please help him/her take the first steps with OpenERP!') % (employee.name),
            partner_ids=partner_ids,
            subtype='mail.mt_comment', context=context
        )
        return employee_id

    def unlink(self, cr, uid, ids, context=None):
        resource_ids = []
        for employee in self.browse(cr, uid, ids, context=context):
            resource_ids.append(employee.resource_id.id)
        return self.pool.get('resource.resource').unlink(cr, uid, resource_ids, context=context)

    def onchange_address_id(self, cr, uid, ids, address, context=None):
        if address:
            address = self.pool.get('res.partner').browse(cr, uid, address, context=context)
            return {'value': {'work_phone': address.phone, 'mobile_phone': address.mobile}}
        return {'value': {}}

    def onchange_company(self, cr, uid, ids, company, context=None):
        address_id = False
        if company:
            company_id = self.pool.get('res.company').browse(cr, uid, company, context=context)
            address = self.pool.get('res.partner').address_get(cr, uid, [company_id.partner_id.id], ['default'])
            address_id = address and address['default'] or False
        return {'value': {'address_id': address_id}}

    def onchange_department_id(self, cr, uid, ids, department_id, context=None):
        value = {'parent_id': False}
        if department_id:
            department = self.pool.get('hr.department').browse(cr, uid, department_id)
            value['parent_id'] = department.manager_id.id
        return {'value': value}

    def onchange_user(self, cr, uid, ids, user_id, context=None):
        work_email = False
        if user_id:
            work_email = self.pool.get('res.users').browse(cr, uid, user_id, context=context).email
        return {'value': {'work_email': work_email}}

    def action_follow(self, cr, uid, ids, context=None):
        """ Wrapper because message_subscribe_users take a user_ids=None
            that receive the context without the wrapper. """
        return self.message_subscribe_users(cr, uid, ids, context=context)

    def action_unfollow(self, cr, uid, ids, context=None):
        """ Wrapper because message_unsubscribe_users take a user_ids=None
            that receive the context without the wrapper. """
        return self.message_unsubscribe_users(cr, uid, ids, context=context)

    def get_suggested_thread(self, cr, uid, removed_suggested_threads=None, context=None):
        """Show the suggestion of employees if display_employees_suggestions if the
        user perference allows it. """
        user = self.pool.get('res.users').browse(cr, uid, uid, context)
        if not user.display_employees_suggestions:
            return []
        else:
            return super(hr_employee, self).get_suggested_thread(cr, uid, removed_suggested_threads, context)

    def _message_get_auto_subscribe_fields(self, cr, uid, updated_fields, auto_follow_fields=['user_id'], context=None):
        """ Overwrite of the original method to always follow user_id field,
        even when not track_visibility so that a user will follow it's employee
        """
        user_field_lst = []
        for name, column_info in self._all_columns.items():
            if name in auto_follow_fields and name in updated_fields and column_info.column._obj == 'res.users':
                user_field_lst.append(name)
        return user_field_lst

    def _check_recursion(self, cr, uid, ids, context=None):
        level = 100
        while len(ids):
            cr.execute('SELECT DISTINCT parent_id FROM hr_employee WHERE id IN %s AND parent_id!=id',(tuple(ids),))
            ids = filter(None, map(lambda x:x[0], cr.fetchall()))
            if not level:
                return False
            level -= 1
        return True

    _constraints = [
        (_check_recursion, 'Error! You cannot create recursive hierarchy of Employee(s).', ['parent_id']),
    ]

    # ---------------------------------------------------
    # Mail gateway
    # ---------------------------------------------------

    def check_mail_message_access(self, cr, uid, mids, operation, model_obj=None, context=None):
        """ mail.message document permission rule: can post a new message if can read
            because of portal document. """
        if not model_obj:
            model_obj = self
        employee_ids = model_obj.search(cr, uid, [('user_id', '=', uid)], context=context)
        if employee_ids and operation == 'create':
            model_obj.check_access_rights(cr, uid, 'read')
            model_obj.check_access_rule(cr, uid, mids, 'read', context=context)
        else:
            return super(hr_employee, self).check_mail_message_access(cr, uid, mids, operation, model_obj=model_obj, context=context)


class hr_department(osv.osv):
    _description = "Department"
    _inherit = 'hr.department'
    _columns = {
        'manager_id': fields.many2one('hr.employee', 'Manager'),
        'member_ids': fields.one2many('hr.employee', 'department_id', 'Members', readonly=True),
    }

    def copy(self, cr, uid, ids, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['member_ids'] = []
        return super(hr_department, self).copy(cr, uid, ids, default, context=context)

class res_users(osv.osv):
    _name = 'res.users'
    _inherit = 'res.users'

    def create(self, cr, uid, data, context=None):
        user_id = super(res_users, self).create(cr, uid, data, context=context)

        # add shortcut unless 'noshortcut' is True in context
        if not(context and context.get('noshortcut', False)):
            data_obj = self.pool.get('ir.model.data')
            try:
                data_id = data_obj._get_id(cr, uid, 'hr', 'ir_ui_view_sc_employee')
                view_id  = data_obj.browse(cr, uid, data_id, context=context).res_id
                self.pool.get('ir.ui.view_sc').copy(cr, uid, view_id, default = {
                                            'user_id': user_id}, context=context)
            except:
                # Tolerate a missing shortcut. See product/product.py for similar code.
                _logger.debug('Skipped meetings shortcut for user "%s".', data.get('name','<new'))

        return user_id

    _columns = {
        'employee_ids': fields.one2many('hr.employee', 'user_id', 'Related employees'),
        }



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: