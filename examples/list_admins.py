#!/usr/bin/python 

import sys
import ssl
sys.path.append('..')

import portalpy

"""
    This example script lists the names and roles of all users who are publishers or administrators.  
    
    To invoke this script simply type python list_admins.py.  This will run the script against
    the portalpy.esri.com portal.  To run it against your Portal, change the values in 
    portalUrl, portalAdminUser, and portalAdminPassword.

"""
# disable ssl certificate validation
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't verify HTTPS certificates by default
    pass
else:
    # Handle target environment that doesn't support HTTPS verification
    ssl._create_default_https_context = _create_unverified_https_context

portalUrl           = "https://portalpy.esri.com/arcgis"
portalAdminUser     = "portaladmin"
portalAdminPassword = "portaladmin"

    
portal = portalpy.Portal(portalUrl, portalAdminUser, portalAdminPassword)
users = portal.search_users('(role:account_admin OR role:account_publisher)')

for user in users :
    userResp = portal.get_user(user['username'])
    print user['username'] + ":  " + userResp['role']
