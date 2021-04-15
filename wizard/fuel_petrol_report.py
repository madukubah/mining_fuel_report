# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import datetime
import calendar 
import logging
_logger = logging.getLogger(__name__)

class FuelPetrolReport(models.TransientModel):
    _name = 'fuel.petrol.report'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date(string="End Date", required=True)
    product_id = fields.Many2one('product.product', 'Fuel', default=4699, readonly=True )
    type = fields.Selection([
        ( "all" , 'All Entries'),
        ( "posted" , 'Posted Entries'),
        ], default="posted", string='Type', index=True, required=True )

    @api.multi
    def action_print(self):
        final_dict = {
            "rows" : [],
            "product_uom_qty" : 0,
            "total_amount" : 0,
        }
        tag_ids = self.env['production.cop.tag'].search( [] )
        tag_ids = tag_ids.ids
        service_types = self.env['fleet.service.type'].search([ ( 'tag_id', 'in', tag_ids ) ])
        stag_ids = [ service_type.tag_id.id for service_type in service_types ]

        tag_ids = [ x for x in tag_ids if x not in stag_ids ]

        stype_vehicle_cost_dict = {}
        vehicle_cost_domain = [ ( "date", ">=", self.start_date ), ( "date", "<=", self.end_date ), ( "product_id", "=", self.product_id.id ) ]
        if self.type == "posted":
            vehicle_cost_domain += [ ( "state", "=", "posted" ) ]
        vehicle_costs = self.env['fleet.vehicle.log.services'].search( vehicle_cost_domain , order="name asc" )
        for vehicle_cost in vehicle_costs:
            temp = {}
            temp["date"] = vehicle_cost.date
            temp["product"] = ""
            temp["product_uom_qty"] = vehicle_cost.product_uom_qty
            temp["amount"] = vehicle_cost.amount
            temp["remarks"] = vehicle_cost.vehicle_id.name

            final_dict["rows"] += [ temp ]
            final_dict["product_uom_qty"] += vehicle_cost.product_uom_qty
            final_dict["total_amount"] += vehicle_cost.amount
        
        tag_log_domain = [ ( "date", ">=", self.start_date ), ( "date", "<=", self.end_date ), ( "tag_id", "in", tag_ids ), ( "product_id", "=", self.product_id.id ) ]
        if self.type == "posted":
            tag_log_domain += [ ( "state", "=", "posted" ) ]
        tag_logs = self.env['production.cop.tag.log'].search( tag_log_domain , order="date asc" )
        for tag_log in tag_logs:
            temp = {}
            temp["date"] = tag_log.date
            temp["product"] = tag_log.product_id.name if tag_log.product_id else ""
            temp["product_uom_qty"] = tag_log.product_uom_qty
            temp["amount"] = tag_log.amount
            temp["remarks"] = tag_log.remarks

            final_dict["rows"] += [ temp ]
            final_dict["product_uom_qty"] += tag_log.product_uom_qty
            final_dict["total_amount"] += tag_log.amount

        final_dict["rows"].sort(key=lambda x: x['date'], reverse=False)
        final_dict["stock_on_start_date"] = self.product_id.with_context({'to_date': self.start_date }).qty_available
        final_dict["stock_on_end_date"] = self.product_id.with_context({'to_date': self.end_date }).qty_available
        final_dict["consumtion"] = final_dict["product_uom_qty"]
        final_dict["total_amount"] = final_dict["total_amount"]

        datas = {
            'ids': self.ids,
            'model': 'fuel.petrol.report',
            'form': final_dict,
            'type': self.type,
            'start_date': self.start_date,
            'end_date': self.end_date,
        }
        return self.env['report'].get_action(self,'mining_fuel_report.fuel_petrol_temp', data=datas)