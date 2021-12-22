# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import datetime
from dateutil.relativedelta import relativedelta
import dateutil
import calendar 
import logging
_logger = logging.getLogger(__name__)

class FuelDieselReport(models.TransientModel):
    _name = 'fuel.diesel.report'

    def _default_vehicle_type(self):
        VehicleType = self.env['fleet.vehicle.type'].sudo()
        vehicle_types = VehicleType.search([]) 
        return vehicle_types.ids

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date(string="End Date", required=True)
    product_id = fields.Many2one('product.product', 'Fuel', default=4698, readonly=True )
    vehicle_type_ids = fields.Many2many('fleet.vehicle.type', 'diesel_report_vehicle_type_rel', 'diesel_report_id', 'vehicle_type_id', string='Vehicle Type', default=_default_vehicle_type )
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

        tag_log_domain = [ ( "date", "=", self.end_date ), ( "tag_id", "in", tag_ids ), ( "product_id", "=", self.product_id.id ) ]
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
        final_dict["fuel_consume_by_date"] = self.get_fuel_consume_by_date()
        final_dict["fuel_consume_by_vehicles"] = self.get_fuel_consume_by_vehicles()
        vehicle_type_names = []
        for vehicle_type in self.vehicle_type_ids:
            vehicle_type_names += [vehicle_type.name]
        final_dict["vehicle_types"] = vehicle_type_names
        datas = {
            'ids': self.ids,
            'model': 'fuel.diesel.report',
            'form': final_dict,
            'type': self.type,
            'start_date': self.start_date,
            'end_date': self.end_date,
        }
        return self.env['report'].get_action(self,'mining_fuel_report.fuel_diesel_temp', data=datas)

    def get_fuel_consume_by_vehicles(self):
        Vehicle = self.env['fleet.vehicle'].sudo()
        vehicles = Vehicle.search( [ ( "type_id", "in", self.vehicle_type_ids.ids ) ], order="type_id asc" )
        
        tag_ids = self.env['production.cop.tag'].search( [] )
        tag_ids = tag_ids.ids
        service_types = self.env['fleet.service.type'].search([ ( 'tag_id', 'in', tag_ids ) ])
        stag_ids = [ service_type.tag_id.id for service_type in service_types ]

        tag_ids = [ x for x in tag_ids if x not in stag_ids ]

        stype_vehicle_cost_dict = {}
        vehicle_cost_domain = [ ( "date", "=", self.end_date ), ( "product_id", "=", self.product_id.id ) ]
        if self.type == "posted":
            vehicle_cost_domain += [ ( "state", "=", "posted" ) ]
        vehicle_costs = self.env['fleet.vehicle.cost'].search( vehicle_cost_domain , order="name asc" )
        for vehicle in vehicles:
            stype_vehicle_cost_dict[vehicle.name] = {
                "name": vehicle.name,
                "type": vehicle.type_id.name,
                "consume": 0
            }
            for vehicle_cost in vehicle_costs:
                if vehicle_cost.vehicle_id.name == vehicle.name:
                    stype_vehicle_cost_dict[vehicle.name]["consume"] += vehicle_cost.product_uom_qty
                
            if stype_vehicle_cost_dict[vehicle.name]["consume"] == 0 :
                del stype_vehicle_cost_dict[vehicle.name]

        vehicle_types = []
        type_vehicle_cost_dict = {}
        for key, value in stype_vehicle_cost_dict.items():
            if type_vehicle_cost_dict.get( value["type"], False ):
                type_vehicle_cost_dict[value["type"]]["items"] +=[value]
            else:
                vehicle_types += [ value["type"] ]
                type_vehicle_cost_dict[value["type"]] = {
                    "items": [
                        value
                    ]
                }

        return {
            "types": vehicle_types,
            "vehicles": type_vehicle_cost_dict
        }
        # return stype_vehicle_cost_dict

    def get_fuel_consume_by_date(self):
        start = datetime.datetime.strptime( self.start_date, '%Y-%m-%d')
        end = datetime.datetime.strptime( self.end_date, '%Y-%m-%d')
        days = abs( relativedelta(end, start).days )

        tag_ids = self.env['production.cop.tag'].search( [] )
        tag_ids = tag_ids.ids
        service_types = self.env['fleet.service.type'].search([ ( 'tag_id', 'in', tag_ids ) ])
        stag_ids = [ service_type.tag_id.id for service_type in service_types ]

        tag_ids = [ x for x in tag_ids if x not in stag_ids ]

        fuel_date_dict={}
        start = datetime.datetime.strptime( self.start_date, '%Y-%m-%d')
        date = self.start_date
        dates = []
        for i in range( days+1 ) :
            dates += [ date ]
            fuel_date_dict[ date ] = {
                "date" : date,
                "begining_balance" : 0,
                "in" : 0,
                "out" : 0,
                "balance" : 0
            }
            start += datetime.timedelta(days=1)
            date = start.strftime( '%Y-%m-%d')
        
        fuel_date_dict["dates"] = dates


        vehicle_cost_domain = [ ( "date", ">=", self.start_date ), ( "date", "<=", self.end_date ), ( "product_id", "=", self.product_id.id ) ]
        if self.type == "posted":
            vehicle_cost_domain += [ ( "state", "=", "posted" ) ]
        vehicle_costs = self.env['fleet.vehicle.cost'].search( vehicle_cost_domain , order="name asc" )

        for vehicle_cost in vehicle_costs:
            if fuel_date_dict.get( vehicle_cost.date, False ):
                fuel_date_dict[ vehicle_cost.date ]["out"] += vehicle_cost.product_uom_qty

        tag_log_domain = [ ( "date", ">=", self.start_date ), ( "date", "<=", self.end_date ), ( "tag_id", "in", tag_ids ), ( "product_id", "=", self.product_id.id ) ]
        if self.type == "posted":
            tag_log_domain += [ ( "state", "=", "posted" ) ]
        tag_logs = self.env['production.cop.tag.log'].search( tag_log_domain , order="date asc" )
        for tag_log in tag_logs:
            if fuel_date_dict.get( tag_log.date, False ):
                fuel_date_dict[ tag_log.date ]["out"] += tag_log.product_uom_qty

        stock_move_domain = [ ( "date", ">=", self.start_date ), ( "date", "<=", self.end_date ), ( "product_id", "=", self.product_id.id ), ( "location_dest_id", "=", 22 ), ( "state", "=", "done" ) ]
        stock_moves = self.env['stock.move'].search( stock_move_domain )

        for stock_move in stock_moves:

            date = dateutil.parser.parse(stock_move.date).date()
            date = date.strftime( '%Y-%m-%d')
            # _logger.warning(date)

            if fuel_date_dict.get( date, False ):
                fuel_date_dict[ date ]["in"] += stock_move.product_uom_qty

        stock_on_start_date = self.product_id.with_context({'to_date': self.start_date }).qty_available
        stock_on_end_date = self.product_id.with_context({'to_date': self.end_date }).qty_available
        
        for date in fuel_date_dict["dates"]:
            fuel_date_dict[date]["begining_balance"] = stock_on_start_date
            fuel_date_dict[date]["balance"] = fuel_date_dict[date]["begining_balance"] + fuel_date_dict[date]["in"] - fuel_date_dict[date]["out"]
            stock_on_start_date = fuel_date_dict[date]["balance"]

        return fuel_date_dict
