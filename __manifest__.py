# -*- coding: utf-8 -*-

{
    'name': 'Mining Fuel Report',
    'version': '1.0',
    'author': 'Technoindo.com',
    'category': 'Mining Management',
    'depends': [
        'mining_production',
        'stock',
        'vehicle_monitoring'
    ],
    'data': [
        "wizard/fuel_diesel_report.xml",
        "wizard/fuel_petrol_report.xml",
        "wizard/oil_report.xml",

        "report/fuel_diesel_report.xml",
        "report/fuel_diesel_temp.xml",
        "report/fuel_petrol_report.xml",
        "report/fuel_petrol_temp.xml",
        "report/oil_report.xml",
        "report/oil_temp.xml",

    ],
    'qweb': [
        # 'static/src/xml/cashback_templates.xml',
    ],
    'demo': [
        # 'demo/sale_agent_demo.xml',
    ],
    "installable": True,
	"auto_instal": False,
	"application": False,
}