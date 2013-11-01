#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    d$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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

import pooler
from openerp.addons.account_report_lib.account_report_base import accountReportbase
from report import report_sxw

class GeneralLedgerReportWebkit(accountReportbase):

    def __init__(self, cr, uid, name, context):
        super(GeneralLedgerReportWebkit, self).__init__(cr, uid, name, context=context)
        self.pool = pooler.get_pool(self.cr.dbname)
        self.cursor = self.cr

        self.localcontext.update({
            'cr': cr,
            'uid': uid,
            'get_chart_account_id': self.get_chart_account_id,
            'get_fiscalyear': self.get_fiscalyear,
            'get_filter': self.get_filter,
            'get_accounts_ids': self.get_accounts_ids,
            'get_data':self.get_data,           
        })

    def get_data(self, cr, uid, data):
        filter_data = []
        account_list = []        
        account_selected = []
        
        account_lines = {}
        account_balance = {}
        account_conciliation = {}
                
        library_obj = self.pool.get('account.webkit.report.library')
        
        filter_type = self.get_filter(data)
        chart_account = self.get_chart_account_id(data)
        
        if filter_type == 'filter_date':
            start_date = self.get_date_from(data)
            stop_date = self.get_date_to(data)
            
            filter_data.append(start_date)
            filter_data.append(stop_date)
            
        elif filter_type == 'filter_period':
            
            start_period = self.get_start_period(data) #return the period object
            stop_period = self.get_end_period(data)
            
            filter_data.append(start_period)
            filter_data.append(stop_period)
            
        else:
            filter_type = ''
        
        fiscalyear = self.get_fiscalyear(data)
        target_move = self.get_target_move(data)
        
        #From the wizard can select specific account, extract this accounts
        account_selected = self.get_accounts_ids(cr, uid, data)
        
        if not account_selected:
            account_selected = [chart_account.id]
            account_list_ids = library_obj.get_account_child_ids(cr, uid, account_selected) #get all the accounts in the chart_account_id
        
        #Extract the id for the browse record
        else:
            account_ids = []
            for account in account_selected:
                account_ids.append(account.id)
                account_list_ids = library_obj.get_account_child_ids(cr, uid, account_ids) #get all the accounts in the chart_account_id
        
        account_list_obj = self.pool.get('account.account').browse(cr, uid, account_list_ids)
          
        #Get the move_lines for each account.
        move_lines = library_obj.get_move_lines(cr, 1,
                                                account_list_ids, 
                                                filter_type=filter_type, 
                                                filter_data=filter_data, 
                                                fiscalyear=fiscalyear, 
                                                target_move=target_move,
                                                order_by='account_id asc, date asc, ref asc')
        
       
        #Reconcile -> show reconcile in the mako.
        '''
        First, if the account permit reconcile (reconcile == True), add to the dictionary.
        If the account don't allow the reconcile, search if the lines have reconcile_id or partial_reconcile_id
        If the account allow the reconcile or the lines have reconcile_id or partial_reconcile_id, add in the dictionary
        and show in the mako the column "Reconcile"
        
        the final result is:
           {account_id: {line.id: [conciliation_name]}}
        '''        
        #Search if the move_lines have partial or reconcile id
        for line in move_lines:           
            #If the account have reconcile, add to the dictionary              
            if line.account_id.id not in account_conciliation:
                account_conciliation[line.account_id.id] = {}
            
            if line.reconcile_id and line.reconcile_id.name != '':
                 account_conciliation[line.account_id.id][line.id] = line.reconcile_id.name
             
            elif line.reconcile_partial_id and line.reconcile_partial_id.name != '':
                str_name = 'P: ' + line.reconcile_partial_id.name
                #conciliation_lines.append(str_name)
                account_conciliation[line.account_id.id][line.id] = str_name             
            
            if line.account_id.id not in account_lines:
                account_lines[line.account_id.id] = []
            
            account_lines[line.account_id.id].append(line)
        
        fields = ['balance']            
        if self.get_amount_currency(data):
            fields.append('foreign_balance')
        
        if filter_type == 'filter_date':
            account_balance = library_obj.get_account_balance(cr, uid, 
                                                              account_list_ids,
                                                              fields,
                                                              initial_balance=True,
                                                              company_id=chart_account.company_id.id,
                                                              fiscal_year_id = fiscalyear.id,
                                                              state = target_move,
                                                              start_date = start_date,
                                                              end_date = stop_date,
                                                              chart_account_id = chart_account.id,
                                                              filter_type=filter_type)
        elif filter_type == 'filter_period':
            account_balance = library_obj.get_account_balance(cr, uid, 
                                                              account_list_ids,
                                                              fields,
                                                              initial_balance=True,
                                                              company_id=chart_account.company_id.id,
                                                              fiscal_year_id = fiscalyear.id,
                                                              state = target_move,
                                                              start_period_id = start_period.id,
                                                              end_period_id = stop_period.id,
                                                              chart_account_id = chart_account.id,
                                                              filter_type=filter_type)
        else:
            account_balance = library_obj.get_account_balance(cr, uid, 
                                                              account_list_ids,
                                                              fields,
                                                              initial_balance=True,
                                                              company_id=chart_account.company_id.id,
                                                              fiscal_year_id = fiscalyear.id,
                                                              state = target_move,
                                                              chart_account_id = chart_account.id,
                                                              filter_type=filter_type)
        
        
        return account_list_obj, account_lines, account_conciliation, account_balance
    
report_sxw.report_sxw('report.account_general_ledger_webkit',
                             'account.account',
                             'addons/account_general_ledger_report/report/account_general_ledger_report.mako',
                             parser=GeneralLedgerReportWebkit)