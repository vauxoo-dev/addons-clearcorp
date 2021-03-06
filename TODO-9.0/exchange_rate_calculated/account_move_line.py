# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Addons modules by CLEARCORP S.A.
#    Copyright (C) 2009-TODAY CLEARCORP S.A. (<http://clearcorp.co.cr>).
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

from openerp import models, fields, api
import time
import copy


class accountMoveline(models.Model):

    _inherit = 'account.move.line'

    @api.onchange('amount_currency')
    def onchange_amount_currency(self):
        """This method provides convert the amount_currency to debit or credit
        depends of currency selected. It only works in amount_currency to debit/credit.
        In debit/credit to amount_currency it isn't implemented."""

        if(self.amount_currency):
            # 1. Get currency for current company. 
            # (The exchange rate for this case is from currency_company to currency_id)
            company_currency = self.move_id.company_id.currency_id
            # 2. Get date as string
            if self.move_id and not self.move_id.date:
                date = time.strftime('%Y-%m-%d')
            else:
                date = self.move_id.date

            if self.amount_currency != 0 and self.currency_id:
                # 3. Get amount_currency for today
                currency_selected = self.currency_id.with_context(date=date)
                exchange_amount = currency_selected.compute(self.amount_currency, company_currency)
                # 4. Asign values to debit or credit
                if exchange_amount >= 0:
                    self.debit = exchange_amount
                    self.credit = 0.0
                else:
                    self.credit = -1 * exchange_amount
                    self.debit = 0.0
