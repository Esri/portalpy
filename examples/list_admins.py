#!/usr/bin/python 

import portalpy

"""
    This example script lists the names and roles of all users who are publishers or administrators.  
    
    To invoke this script simply type python list_admins.py.  This will run the script against
    the portalpy.esri.com portal.  To run it against your Portal, change the values in 
    portalUrl, portalAdminUser, and portalAdminPassword.

"""


portalUrl           = "https://portalpy.esri.com/arcgis"
portalAdminUser     = "portaladmin"
portalAdminPassword = "portaladmin"

    
portal = portalpy.Portal(portalUrl, portalAdminUser, portalAdminPassword)
users = portal.search_users('(role:account_admin OR role:account_publisher)')

for user in users :
    userResp = portal.get_user(user['username'])
    print user['username'] + ":  " + userResp['role']
