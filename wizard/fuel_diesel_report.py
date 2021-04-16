# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import datetime
import calendar 
import logging
_logger = logging.getLogger(__name__)

class FuelDieselReport(models.TransientModel):
    _name = 'fuel.diesel.report'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date(string="End Date", required=True)
    product_id = fields.Many2one('product.product', 'Fuel', default=4698, readonly=True )
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

        stype_vehicle_cost_dict = {}
        vehicle_cost_domain = [ ( "date", ">=", self.start_date ), ( "date", "<=", self.end_date ), ( "product_id", "=", self.product_id.id ) ]
        if self.type == "posted":
            vehicle_cost_domain += [ ( "state", "=", "posted" ) ]
        vehicle_costs = self.env['fleet.vehicle.cost'].search( vehicle_cost_domain , order="name asc" )
        for vehicle_cost in vehicle_costs:
            stype = vehicle_cost.cost_subtype_id.name
            vehicle_name = vehicle_cost.vehicle_id.name
            if stype_vehicle_cost_dict.get( stype, False ):
                if stype_vehicle_cost_dict[ stype ]["vehicles"].get( vehicle_name, False ):
                    stype_vehicle_cost_dict[ stype ]["vehicles"][ vehicle_name ]["product_uom_qty"] += vehicle_cost.product_uom_qty
                    stype_vehicle_cost_dict[ stype ]["vehicles"][ vehicle_name ]["amount"] += vehicle_cost.amount
                else :
                    stype_vehicle_cost_dict[ stype ]["vehicles"][ vehicle_name ] = {
                        "name" : vehicle_name,
                        "product_uom_qty" : vehicle_cost.product_uom_qty,
                        "amount" : vehicle_cost.amount,
                    }

                stype_vehicle_cost_dict[ stype ]['product_uom_qty'] += vehicle_cost.product_uom_qty
                stype_vehicle_cost_dict[ stype ]['total_amount'] += vehicle_cost.amount

            else :
                stype_vehicle_cost_dict[ stype ] = {
                    "vehicles" : {},
                    "product_uom_qty" : vehicle_cost.product_uom_qty,
                    "total_amount" : vehicle_cost.amount
                }
                stype_vehicle_cost_dict[ stype ]["vehicles"][ vehicle_name ] = {
                    "name" : vehicle_name,
                    "product_uom_qty" : vehicle_cost.product_uom_qty,
                    "amount" : vehicle_cost.amount,
                }

        tag_log_domain = [ ( "date", ">=", self.start_date ), ( "date", "<=", self.end_date ), ( "tag_id", "in", tag_ids ), ( "product_id", "=", self.product_id.id ) ]
        if self.type == "posted":
            tag_log_domain += [ ( "state", "=", "posted" ) ]
        tag_logs = self.env['production.cop.tag.log'].search( tag_log_domain , order="date asc" )
        tag_log_dict = {}
        for tag_log in tag_logs:
            tag_name = tag_log.tag_id.name
            if tag_log_dict.get( tag_name, False ):
                tag_log_dict[ tag_name ]['items'] += [
                    {
                        "date" : tag_log.date,
                        "product" : tag_log.product_id.name if tag_log.product_id else "" ,
                        "product_uom_qty" : tag_log.product_uom_qty,
                        "amount" : tag_log.amount,
                        "remarks" : tag_log.remarks,
                    }
                ]
                tag_log_dict[ tag_name ]["total_amount"] += tag_log.amount
                tag_log_dict[ tag_name ]["product_uom_qty"] += tag_log.product_uom_qty
            else :
                tag_log_dict[ tag_name ] = {
                    "items" : [
                        {
                            "date" : tag_log.date,
                            "product" : tag_log.product_id.name if tag_log.product_id else "" ,
                            "product_uom_qty" : tag_log.product_uom_qty,
                            "amount" : tag_log.amount,
                            "remarks" : tag_log.remarks,
                        }
                    ],
                    "total_amount" : tag_log.amount,
                    "product_uom_qty" : tag_log.product_uom_qty,
                }


        final_dict = {}
        final_dict["vehicle_cost"] = stype_vehicle_cost_dict
        final_dict["tag_log"] = tag_log_dict
        final_dict["stock_on_start_date"] = self.product_id.with_context({'to_date': self.start_date }).qty_available
        final_dict["stock_on_end_date"] = self.product_id.with_context({'to_date': self.end_date }).qty_available
        final_dict["consumtion"] = sum( [ y["product_uom_qty"] for x, y in stype_vehicle_cost_dict.items() ] + [ y["product_uom_qty"] for x, y in tag_log_dict.items() ] )
        final_dict["total_amount"] = sum( [ y["total_amount"] for x, y in stype_vehicle_cost_dict.items() ] + [ y["total_amount"] for x, y in tag_log_dict.items() ] )

        datas = {
            'ids': self.ids,
            'model': 'fuel.diesel.report',
            'form': final_dict,
            'type': self.type,
            'start_date': self.start_date,
            'end_date': self.end_date,
        }
        return self.env['report'].get_action(self,'mining_fuel_report.fuel_diesel_temp', data=datas)