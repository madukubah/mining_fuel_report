# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import datetime
import calendar 
import logging
_logger = logging.getLogger(__name__)

class OilReport(models.TransientModel):
    _name = 'oil.report'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date(string="End Date", required=True)
    category_id = fields.Many2one('product.category', 'Category', default=13, readonly=True )
    type = fields.Selection([
        ( "all" , 'All Entries'),
        ( "posted" , 'Posted Entries'),
        ], default="posted", string='Type', index=True, required=True )

    @api.multi
    def action_print(self):
        tag_ids = self.env['production.cop.tag'].search( [] )
        tag_ids = tag_ids.ids
        service_types = self.env['fleet.service.type'].search([ ( 'tag_id', 'in', tag_ids ) ])
        stag_ids = [ service_type.tag_id.id for service_type in service_types ]

        tag_ids = [ x for x in tag_ids if x not in stag_ids ]

        product_ids = self.env['product.product'].search( [ ("categ_id", "=", self.category_id.id ) ] )
        product_dict = {}
        for product_id in product_ids:
            product_dict[ product_id.name ] = {
                "product_uom_qty" : 0,
                "total_amount" : 0,
                "stock_on_end_date" : product_id.with_context({'to_date': self.end_date }).qty_available,
            }
        rows = []
        vehicle_cost_domain = [ ( "date", ">=", self.start_date ), ( "date", "<=", self.end_date ), ( "product_id", "in", product_ids.ids ) ]
        if self.type == "posted":
            vehicle_cost_domain += [ ( "state", "=", "posted" ) ]
        vehicle_costs = self.env['fleet.vehicle.cost'].search( vehicle_cost_domain , order="date asc" )
        for vehicle_cost in vehicle_costs:
            temp = {}
            temp["date"] = vehicle_cost.date
            temp["remarks"] = vehicle_cost.vehicle_id.name
            driver_name = ""
            services = self.env['fleet.vehicle.log.services'].search([ ( "cost_id", "=", vehicle_cost.id ) ], limit = 1)
            if services :
                driver_name = services[0].purchaser_id.name if services[0].purchaser_id else ""
                if driver_name.find("[") != -1:
                    driver_name = driver_name[0: int( driver_name.find("[") ) ]
            temp["receiver"] = driver_name
            for product_id in product_ids:
                temp[ product_id.name ] =  0
            if vehicle_cost.product_id :
                temp[ vehicle_cost.product_id.name ] = vehicle_cost.product_uom_qty
                temp[ "amount" ] = vehicle_cost.amount
                product_dict[ vehicle_cost.product_id.name ]["product_uom_qty"] += vehicle_cost.product_uom_qty
                product_dict[ vehicle_cost.product_id.name ]["total_amount"] += vehicle_cost.amount

            rows += [ temp ]
        
        tag_log_domain = [ ( "date", ">=", self.start_date ), ( "date", "<=", self.end_date ), ( "tag_id", "in", tag_ids ), ( "product_id", "in", product_ids.ids ) ]
        if self.type == "posted":
            tag_log_domain += [ ( "state", "=", "posted" ) ]
        tag_logs = self.env['production.cop.tag.log'].search( tag_log_domain , order="date asc" )
        for tag_log in tag_logs:
            temp = {}
            temp["date"] = tag_log.date
            temp["remarks"] = tag_log.remarks
            temp["receiver"] = ""
            for product_id in product_ids:
                temp[ product_id.name ] =  0
            if tag_log.product_id :
                temp[ tag_log.product_id.name ] = tag_log.product_uom_qty
                temp[ "amount" ] = tag_log.amount
                product_dict[ tag_log.product_id.name ]["product_uom_qty"] += tag_log.product_uom_qty
                product_dict[ tag_log.product_id.name ]["total_amount"] += tag_log.amount
            rows += [ temp ]

        rows.sort(key=lambda x: x['date'], reverse=False)

        final_dict = {
            "rows":rows,
            "product_uom_qty": 0,
            "total_amount": 0,
            "consumtion":0,
            "stock_on_end_date":0,
        }
        datas = {
            'ids': self.ids,
            'model': 'fuel.diesel.report',
            'form': final_dict,
            'type': self.type,
            'product_dict': product_dict,
            'start_date': self.start_date,
            'end_date': self.end_date,
        }
        return self.env['report'].with_context( landscape=True ).get_action(self,'mining_fuel_report.oil_temp', data=datas)

    