""" The portalpy module for working with the ArcGIS Online and Portal APIs."""

__version__ = '1.0'

import collections
import copy
import gzip
import httplib
import imghdr
import json
import logging
import mimetools
import mimetypes
import os
import re
import tempfile
import unicodedata
import urllib
import urllib2
import urlparse
from cStringIO import StringIO


_log = logging.getLogger(__name__)

class Portal(object):
    """ An object representing a connection to a single portal (via URL).
    
        Notes:
        
            To instantiate a Portal object execute code like this: 
            
                PortalPy.Portal(portalUrl, user, password)
                
            There are a few things you should know as you use the methods below.
            
                Group IDs
                    Many of the group functions require a group id.  This id is
                    different than the group's name or title.  To determine
                    a group id, use the search_groups function using the title
                    to get the group id.
                    
                Time
                    Many of the methods return a time field.  All time is
                    returned as millseconds since 1 January 1970.  Python
                    expects time in seconds since 1 January 1970 so make sure
                    to divide times from PortalPy by 1000.  See the example
                    a few lines down to see how to convert from PortalPy time
                    to Python time.
                    
                    
        Example - converting time
                    import time
                    .
                    .
                    .
                    group = portalAdmin.get_group('67e1761068b7453693a0c68c92a62e2e')
                    pythontime = time.ctime(group['created']/1000)
        
    
        Example - list users in group 
            portal = PortalPy.Portal(portalUrl, user, password)
            resp = portal.get_group_members('67e1761068b7453693a0c68c92a62e2e')
            for user in resp['users']:
                print user
                
        Example - create a group
            portal= PortalPy.Portal(portalUrl, user, password)
            group_id = portalAdmin.create_group('my group', 'test tag', 'a group to share travel maps')

        Example - delete a user named amy and assign her content to bob
            portal= PortalPy.Portal(portalUrl, user, password)
            portal.delete_user('amy.user', True, 'bob.user')
    
    """


    def __init__(self, url, username=None, password=None, key_file=None,
                 cert_file=None, expiration=60, referer=None, proxy_host=None,
                 proxy_port=None, connection=None, workdir=tempfile.gettempdir()):
        """ The Portal constructor. Requires URL and optionally username/password."""
        self.url = url
        if url:
            normalized_url = _normalize_url(self.url)
            if not normalized_url[-1] == '/':
                normalized_url += '/'
            self.resturl = normalized_url + 'sharing/rest/'
            self.hostname = _parse_hostname(url)
        self.workdir = workdir

        # Setup the instance members
        self._basepostdata = { 'f': 'json' }
        self._version = None
        self._properties = None
        self._logged_in_user = None
        self._resources = None
        self._languages = None
        self._regions = None
        self._is_pre_162 = False
        self._is_pre_21 = False

        # If a connection was passed in, use it, otherwise setup the
        # connection (use all SSL until portal informs us otherwise)
        if connection:
            _log.debug('Using existing connection to: ' + \
                       _parse_hostname(connection.baseurl))
            self.con = connection
        if not connection:
            _log.debug('Connecting to portal: ' + self.hostname)
            self.con = _ArcGISConnection(self.resturl, username, password,
                                        key_file, cert_file, expiration, True,
                                        referer, proxy_host, proxy_port)

        # Store the logged in user information. It's useful.
        if self.is_logged_in():
            self._logged_in_user = self.get_user(username)

        self.get_version(True)
        self.get_properties(True)



    def add_group_users(self, user_names, group_id):
        """ Adds users to the group specified.    
        
            Note:
                This method will only work if the user for the
                Portal object is either an administrator for the entire
                Portal or the owner of the group.
        
            Arguments
                 user_names      required string, comma-separated users
                 group_id        required string, specifying group id
            
            Returns 
                 A dictionary with a key of "not_added" which contains the users that were not 
                 added to the group. 
        """

        if self._is_pre_21:
            _log.warning('The auto_accept option is not supported in ' \
                         + 'pre-2.0 portals')
            return

        user_names = _unpack(user_names, 'username')

        postdata = self._postdata()
        postdata['users'] = ','.join(user_names)
        resp = self.con.post('community/groups/' + group_id + '/addUsers',
                                 postdata)
        return resp
    
    
    
    def create_group_from_dict(self, group, thumbnail=None):
        
        """ Creates a group and returns a group id if successful.
        
        Note
           Use create_group in most cases.  This method is useful for taking a group
           dict returned from another PortalPy call and copying it.
        
        Arguments
            group        dict object
            thumbnail    url to image
        
        Example
             create_group({'title': 'Test', 'access':'public'})                
        """
        
        postdata = self._postdata()
        postdata.update(_unicode_to_ascii(group))

        # Build the files list (tuples)
        files = []
        if thumbnail:
            if _is_http_url(thumbnail):
                thumbnail = urllib.urlretrieve(thumbnail)[0]
                file_ext = os.path.splitext(thumbnail)[1]
                if not file_ext:
                    file_ext = imghdr.what(thumbnail)
                    if file_ext in ('gif', 'png', 'jpeg'):
                        new_thumbnail = thumbnail + '.' + file_ext
                        os.rename(thumbnail, new_thumbnail)
                        thumbnail = new_thumbnail
            files.append(('thumbnail', thumbnail, os.path.basename(thumbnail)))

        # Send the POST request, and return the id from the response
        resp = self.con.post('community/createGroup', postdata, files)
        if resp and resp.get('success'):
            return resp['group']['id']

    def create_group(self, title, tags, description=None,
                     snippet=None, access='public', thumbnail=None, 
                     is_invitation_only=False, sort_field='avgRating', 
                     sort_order='desc', is_view_only=False, ):
        """ Creates a group and returns a group id if successful.  
  
        Arguments
            title             required string, name of the group
            tags              required string, comma-delimited list of tags
            description       optional string, describes group in detail
            snippet           optional string, <250 characters summarizes group
            access            optional string, can be private, public, or org
            thumbnail         optional string, URL to group image
            isInvitationOnly  optional boolean, defines whether users can join by request.
            sort_field        optional string, specifies how shared items with the group are sorted.
            sort_order        optional string, asc or desc for ascending or descending.
            is_view_only      optional boolean, defines whether the group is searchable

        Returns
            a string that is a group id.
        """

        return self.create_group_from_dict({'title' : title, 'tags' : tags,
                    'snippet' : snippet, 'access' : access, 
                    'sortField' : sort_field, 'sortOrder' : sort_order,
                    'isViewOnly' : is_view_only, 
                    'isinvitationOnly' : is_invitation_only}, thumbnail)
              
        

    

    def delete_group(self, group_id):
        """ Deletes a group. 
        
        Arguments
            group_id is a string containing the id for the group to be deleted.
        
        Returns 
            a boolean indicating whether it was successful.
        
        """
        resp = self.con.post('community/groups/' + group_id + '/delete',
                             self._postdata())
        if resp:
            return resp.get('success')


    def _delete_items(self, owner, item_ids):
        """ Internal: Deletes items from the portal. """
        item_ids = _unpack(item_ids, 'id')
        postdata = self._postdata()
        postdata['items'] = ','.join(item_ids)
        return self.con.post('content/users/' + owner + '/deleteItems', postdata)



    def delete_user(self, username, cascade=False, reassign_to=None):
        """ Deletes a user from the portal, optionally deleting or reassigning groups and items.

            Notes
                You can not delete a user in Portal if that user owns groups or items.  If you
                choose to cascade then those items and groups will be reassigned to
                the user identified in the reassign_to option.  If you choose not to cascade
                the deletion will either succeed or fail depending on whether the user's items
                and groups have previously been transferred.
                
                When cascading, this method will delete up to 10,000 items.  If the user
                has more than 10,000 items the method will fail.  
            
            Arguments
                 username       required string, the name of the user
                 cascade:       optional boolean, true means reassign items and groups
                 reassign_to    optional string, new owner of items and groups
            
            Returns
                a boolean indicating whether the operation succeeded or failed.
        
        """

        # If we're cascading, handle items and groups
        if cascade:
            # Reassign or delete the user's items
            # This code works as long as the user has less than 10,000 items
            # At some point we should update the search functions to accept
            # None for the max results to solve this issue.
            items = self.search(['id'], 'owner:' + username, max_results=10000)
            if items:
                if reassign_to:
                    for item in items:
                        self._reassign_item(item['id'], reassign_to)
                else:
                    self._delete_items(username, items)
            # Reassign or delete the user's groups
            groups = self.search_groups(['id'], 'owner:' + username)
            if groups:
                for group in groups:
                    if reassign_to:
                        self.reassign_group(group['id'], reassign_to)
                    else:
                        self.delete_group(group['id'])

        # Delete the user
        resp = self.con.post('community/users/' + username + '/delete',
                             self._postdata())
        if resp:
            return resp.get('success')

    def generate_token(self, username, password, expiration=60):
        """ Generates and returns a new token, but doesn't re-login. 
        
            Notes
                This method is not needed when using the Portal class
                to make calls into Portal.  It's provided for the benefit
                of making calls into Portal outside of the Portal class.
        
                Portal uses a token-based authentication mechanism where
                a user provides their credentials and a short-term token
                is used for calls.  Most calls made to the Portal REST API
                require a token and this can be appended to those requests.
        
            Arguments
                username      required string, name of the user
                password      required password, name of the user
                expiration    optional integer, number of minutes until the token expires
            
            Returns
                a string with the token
        
        """
        return self.con.generate_token(username, password, expiration)


    def get_group(self, group_id):
        """ Returns group information for the specified group group_id. 
                   
            Arguments                 
                group_id : required string, indicating group.
            
            Returns 
                a dictionary object with the group's information.  The keys in
                the dictionary object will often include:
                   title:              the name of the group
                   isInvitationOnly:   if set to true, users can't apply to join the group.
                   owner:              the owner username of the group
                   description:        explains the group
                   snippet:            a short summary of the group
                   tags:               user-defined tags that describe the group
                   phone:              contact information for group.
                   thumbnail:          File name relative to http://<community-url>/groups/<groupId>/info 
                   created:            When group created, ms since 1 Jan 1970
                   modified:           When group last modified. ms since 1 Jan 1970
                   access:             Can be private, org, or public.
                   userMembership:     A dict with keys username and memberType.  
                   memberType:         provides the calling user's access (owner, admin, member, none).
            
        """
        return self.con.post('community/groups/' + group_id, self._postdata())



    def get_group_thumbnail(self, group_id):
        """ Returns the bytes that make up the thumbnail for the specified group group_id.
        
            Arguments
                 group_id:     required string, specifies the group's thumbnail
            
            Returns 
                 bytes that representt he image.
            
            Example 
                response = portal.get_group_thumbnail("67e1761068b7453693a0c68c92a62e2e")
                f = open(filename, 'wb')
                f.write(response)
        
        """
        thumbnail_file = self.get_group(group_id).get('thumbnail')
        if thumbnail_file:
            thumbnail_url_path = 'community/groups/' + group_id + '/info/' + thumbnail_file
            if thumbnail_url_path:
                return self.con.get(thumbnail_url_path, try_json=False)


    def get_group_members(self, group_id):
        """ Returns members of the specified group.
        
            Arguments
                group_id:    required string, specifies the group
            
            Returns 
                a dictionary with keys: owner, admins, and users.
                    owner      string value, the group's owner
                    admins     list of strings, typically this is the same as the owner.
                    users      list of strings, the members of the group
                
            Example (to print users in a group)
                response = portal.get_group_members("67e1761068b7453693a0c68c92a62e2e")
                for user in response['users'] :
                    print user
        
        """
        return self.con.post('community/groups/' + group_id + '/users',
                             self._postdata())


    def get_org_users(self, max_users=1000):
        """ Returns all users within the portal organization. 
             
            Arguments
                max_users : optional int, the maximum number of users to return.
            
           Returns 
               a list of dicts.  Each dict has the following keys:
                   username :      string
                   storageUsage:   int
                   storageQuota:   int
                   description:    string
                   tags:           list of strings
                   region:         string 
                   created:        int, when account created, ms since 1 Jan 1970
                   modified:       int, when account last modified, ms since 1 Jan 1970
                   email:          string
                   culture:        string
                   orgId:          string
                   preferredView:  string
                   groups:         list of strings
                   role:           string (org_user, org_publisher, org_admin) 
                   fullName:       string
                   thumbnail:      string
                   idpUsername:    string
       
           Example (print all usernames in portal):
           
               resp = portalAdmin.get_org_users()
                for user in resp:
                    print user['username']
       
        """

        # Execute the search and get back the results
        count = 0
        resp = self._org_users_page(1, min(max_users, 100))
        resp_users = resp.get('users')
        results = resp_users
        count += int(resp['num'])
        nextstart = int(resp['nextStart'])
        while count < max_users and nextstart > 0:
            resp = self._org_users_page(nextstart, min(max_users - count, 100))
            resp_users = resp.get('users')
            results.extend(resp_users)
            count += int(resp['num'])
            nextstart = int(resp['nextStart'])
 
        return results



    def get_properties(self, force=False):
        """ Returns the portal properties (using cache unless force=True). """

        # If we've never retrieved the properties before, or the caller is
        # forcing a check of the server, then check the server
        if not self._properties or force:
            path = 'accounts/self' if self._is_pre_162 else 'portals/self'
            resp = self.con.post(path, self._postdata(), ssl=True)
            if resp:
                self._properties = resp
                self.con.all_ssl = self.is_all_ssl()

        # Return a defensive copy
        return copy.deepcopy(self._properties)

    def get_user(self, username):
        """ Returns the user information for the specified username. 
        
            Arguments
                username        required string, the username whose information you want.
            
            Returns
                None if the user is not found and returns a dictionary object if the user is found
                the dictionary has the following keys: 
                    access            string
                    created           time (int) 
                    culture           string, two-letter language code ('en')
                    description       string
                    email             string
                    fullName          string  
                    idpUsername       string, name of the user in the enterprise system  
                    groups            list of dictionaries.  For dictionary keys, see get_group doc.
                    modified          time (int)
                    orgId             string, the organization id
                    preferredView     string, value is either Web, GIS, or null
                    region            string, None or two letter country code 
                    role              string, value is either org_user, org_publisher, org_admin
                    storageUsage      int
                    storageQuota      int
                    tags              list of strings  
                    thumbnail         string, name of file
                    username          string, name of user
        """
        return self.con.post('community/users/' + username, self._postdata())





    def invite_group_users(self, user_names, group_id,
                           role='group_member', expiration=10080):
        """ Invites users to a group.
        
            Notes:
                A user who is invited to a group will see a list of invitations
                in the "Groups" tab of portal listing invitations.  The user
                can either accept or reject the invitation.
        
            Requires
                The user executing the command must be group owner
        
            Arguments
                 user_names:   a required string list of users to invite
                 group_id :    required string, specifies the group you are inviting users to.
                 role:         an optional string, either group_member or group_admin
                 expiration:   an optional int, specifies how long the invitation is valid for in minutes.
            
            Returns
                a boolean that indicates whether the call succeeded.
        
        """

        user_names = _unpack(user_names, 'username')

        # Send out the invitations
        postdata = self._postdata()
        postdata['users'] = ','.join(user_names)
        postdata['role'] = role
        postdata['expiration'] = expiration
        resp = self.con.post('community/groups/' + group_id + '/invite',
                             postdata)

        if resp:
            return resp.get('success')
        

    def is_logged_in(self):
        """ Returns true if logged into the portal. """
        return self.con.is_logged_in()

    def is_all_ssl(self):
        """ Returns true if this portal requires SSL. """

        # If properties aren't set yet, return true (assume SSL until the
        # properties tell us otherwise)
        if not self._properties:
            return True

        # If access property doesnt exist, will correctly return false
        return self._properties.get('allSSL')

    def is_multitenant(self):
        """ Returns true if this portal is multitenant. """
        return self._properties['portalMode'] == 'multitenant'

    def is_arcgisonline(self):
        """ Returns true if this portal is ArcGIS Online. """
        return self._properties['portalName'] == 'ArcGIS Online' \
            and self.is_multitenant()

    def is_subscription(self):
        """ Returns true if this portal is an ArcGIS Online subscription. """
        return bool(self._properties.get('urlKey'))

    def is_org(self):
        """ Returns true if this portal is an organization. """
        return bool(self._properties.get('id'))


    def leave_group(self, group_id):
        """ Removes the logged in user from the specified group. 
            
            Requires: 
                User must be logged in.
            
            Arguments:
                 group_id:   required string, specifies the group id
            
            Returns:
                 a boolean indicating whether the operation was successful.
        """
        resp = self.con.post('community/groups/' + group_id + '/leave',
                             self._postdata())
        if resp:
            return resp.get('success')

    def login(self, username, password, expiration=60):
        """ Logs into the portal using username/password. 
        
            Notes:
                 You can log into a portal when you construct a portal
                 object or you can login later.  This function is 
                 for the situation when you need to log in later.
            
            Arguments
                 username:     required string
                 password:     required string
                 expiration:   optional int, how long the token generated should last.
                    
            Returns
                a string, the token
        
        """
        newtoken = self.con.login(username, password, expiration)
        if newtoken:
            self._logged_in_user = self.get_user(username)
        return newtoken

    def logout(self):
        """ Logs out of the portal. 
        
        Notes
             The portal will forget any existing tokens it was using, all 
             subsequent portal calls will be anonymous until another login
             call occurs.
        
        Returns
             No return value.
        
        """
        self.con.logout()


    def logged_in_user(self):
        """ Returns information about the logged in user.
        
            Returns 
                a dict with the following keys:
                    username       string
                    storageUsage   int
                    description    string
                    tags           comma-separated string
                    created        int, when group created (ms since 1 Jan 1970) 
                    modified       int, when group last modified (ms since 1 Jan 1970)
                    fullName       string
                    email          string
                    idpUsername    string, name of the user in their identity provider  
         
         """
        if self._logged_in_user:
            # Return a defensive copy
            return copy.deepcopy(self._logged_in_user)
        return None


    def _reassign_item(self, item_id, target_owner, target_folder_name=None):
        """ Reassigns a single item within the portal. """
        user_item_link = self._user_item_link(item_id, path_only=True)
        postdata = self._postdata()
        postdata['targetUsername'] = target_owner
        postdata['targetFoldername'] = target_folder_name if target_folder_name else '/'
        return self.con.post(user_item_link + '/reassign', postdata)


    def reassign_group(self, group_id, target_owner):
        """ Reassigns a group to another owner. 
        
            Arguments
                group_id :      required string, unique identifier for the group
                target_owner:   required string, username of new group owner
                
            Returns
                a boolean, indicating success
        
        """
        postdata = self._postdata()
        postdata['targetUsername'] = target_owner
        resp = self.con.post('community/groups/' + group_id + '/reassign', postdata)
        if resp:
            return resp.get('success')


    def reset_user(self, username, password, new_password=None,
                   new_security_question=None, new_security_answer=None):
        """ Resets a user's password, security question, and/or security answer.
        
            Notes
                This function does not apply to those using enterprise accounts
                that come from an enterprise such as ActiveDirectory, LDAP, or SAML.
                It only has an effect on built-in users.
                
                If a new security question is specified, a new security answer should
                be provided.
                
                
            Arguments
                username                    required string, account being reset
                password                    required string, current password
                new_password                optional string, new password if resetting password
                new_security_question       optional int, new security question if desired
                new_security_answer         optional string, new security question answer if desired
        
            Returns
                a boolean, indicating success
        
        """
        postdata = self._postdata()
        postdata['password'] = password
        if new_password:
            postdata['newPassword'] = new_password
        if new_security_question:
            postdata['newSecurityQuestionIdx'] = new_security_question
        if new_security_answer:
            postdata['newSecurityAnswer'] = new_security_answer
        resp = self.con.post('community/users/' + username + '/reset',
                             postdata, ssl=True)
        if resp:
            return resp.get('success')



    def remove_group_users(self, user_names, group_id):
        """ Remove users from a group.
        
            Arguments:
                user_names      required string, comma-separated list of users 
                group_id        required string, the id for a group.
       
            Returns:
                a dictionary with a key notRemoved that is a list of users not removed.

        """

        user_names = _unpack(user_names, 'username')
        
        # Remove the users from the group
        postdata = self._postdata()
        postdata['users'] = ','.join(user_names)
        resp = self.con.post('community/groups/' + group_id + '/removeUsers',
                                 postdata)
        return resp


    def search(self, q, bbox=None, sort_field='title', sort_order='asc', 
               max_results=1000, add_org=True):


        if add_org:
            accountid = self._properties.get('id')
            if accountid and q:
                q += ' accountid:' + accountid
            elif accountid:
                q = 'accountid:' + accountid
 
        count = 0
        resp = self._search_page(q, bbox, 1, min(max_results, 100), sort_field, sort_order)
        results = resp.get('results')
        count += int(resp['num'])
        nextstart = int(resp['nextStart'])
        while count < max_results and nextstart > 0:
            resp = self._search_page(q, bbox, nextstart, min(max_results - count, 100),
                               sort_field, sort_order)
            results.extend(resp)
            count += int(resp['num'])
            nextstart = int(resp['nextStart'])
   
        return results


    def search_groups(self, q, sort_field='title',sort_order='asc', 
                      max_groups=1000, add_org=True):
        """ Searches for portal groups.
        
            Notes
                A few things that will be helpful to know.
                
                1. The query syntax has quite a few features that can't 
                   be adequately described here.  The query syntax is 
                   available in ArcGIS help.  A short version of that URL
                   is http://bitly.com/1fJ8q31.
                   
                2. Most of the time when searching groups you want to 
                   search within your organization in ArcGIS Online
                   or within your Portal.  As a convenience, the method
                   automatically appends your organization id to the query by 
                   default.  If you don't want the API to append to your query
                   set add_org to false.  
                   
            Arguments
                q                required string, query string.  See notes.
                sort_field       optional string, valid values can be title, owner, created
                sort_order       optional string, valid values are asc or desc
                max_groups       optional int, maximum number of groups returned 
                add_org          optional boolean, controls whether to search within your org

            Returns
                A list of dictionaries.  Each dictionary has the following keys.
                    access              string, values=private, org, public
                    created             int, ms since 1 Jan 1970
                    description         string
                    id                  string, unique id for group
                    isInvitationOnly    boolean
                    isViewOnly          boolean
                    modified            int, ms since 1 Jan 1970
                    owner               string, user name of owner
                    phone               string
                    snippet             string, short summary of group
                    sortField           string, how shared items are sorted
                    sortOrder           string, asc or desc
                    tags                string list, user supplied tags for searching
                    thumbnail           string, name of file.  Append to http://<community url>/groups/<group id>/info/
                    title               string, name of group as shown to users
        """
        
        if add_org:
            accountid = self._properties.get('id')
            if accountid and q:
                q += ' accountid:' + accountid
            elif accountid:
                q = 'accountid:' + accountid
        
        # Execute the search and get back the results
        count = 0
        resp = self._groups_page(q, 1, min(max_groups,100), sort_field, sort_order) 
        results = resp.get('results')
        count += int(resp['num'])
        nextstart = int(resp['nextStart'])
        while count < max_groups and nextstart > 0:
            resp = self._groups_page(q, 1, min(max_groups - count,100), 
                                     sort_field, sort_order)
            resp_users = resp.get('results')
            results.extend(resp_users)
            count += int(resp['num'])
            nextstart = int(resp['nextStart'])

        return results
        
       
 
    def search_users(self, q, sort_field='username',
              sort_order='asc', max_users=1000, add_org=True):
        """ Searches portal users. 
        
            Notes
                A few things that will be helpful to know.
                
                1. The query syntax has quite a few features that can't 
                   be adequately described here.  The query syntax is 
                   available in ArcGIS help.  A short version of that URL
                   is http://bitly.com/1fJ8q31.
                   
                2. Most of the time when searching groups you want to 
                   search within your organization in ArcGIS Online
                   or within your Portal.  As a convenience, the method
                   automatically appends your organization id to the query by 
                   default.  If you don't want the API to append to your query
                   set add_org to false.  
                   
            Arguments
                q                required string, query string.  See notes.
                sort_field       optional string, valid values can be username or created
                sort_order       optional string, valid values are asc or desc
                max_users        optional int, maximum number of users returned 
                add_org          optional boolean, controls whether to search within your org

            Returns
                A dictionary object with the following keys:
                    created         time (int), when user created
                    culture         string, two-letter language code
                    description     string, user supplied description 
                    fullName        string, name of the user
                    modified        time (int), when user last modified
                    region          string, may be None
                    tags            string list, of user tags
                    thumbnail       string, name of file
                    username        string, name of the user        
        """

        if add_org:
            accountid = self._properties.get('id')
            if accountid and q:
                q += ' accountid:' + accountid
            elif accountid:
                q = 'accountid:' + accountid


        # Execute the search and get back the results
        count = 0
        resp = self._users_page(q, 1, min(max_users, 100), sort_field, sort_order)
        results = resp.get('results')
        count += int(resp['num'])
        nextstart = int(resp['nextStart'])
        while count < max_users and nextstart > 0:
            resp = self._users_page(q, nextstart, min(max_users - count, 100),
                                    sort_field, sort_order)
            resp_users = resp.get('results')
            results.extend(resp_users)
            count += int(resp['num'])
            nextstart = int(resp['nextStart'])

        return results



    # Used to signup a new user to an on-premises portal.
    def signup(self, username, password, fullname, email):
        """ Signs up users to an instance of Portal for ArcGIS. 
        
            Notes:
                This method only applies to Portal and not ArcGIS
                Online.  This method can be called anonymously, but
                keep in mind that self-signup can also be disabled 
                in a Portal.  It also only creates built-in
                accounts, it does not work with enterprise
                accounts coming from ActiveDirectory or your
                LDAP.  
                
                There is another method called createUser that 
                requires administrator access that can always
                be used against 10.2.1 portals or later that
                can create users whether they are builtin or
                enterprise accounts.
                
            Arguments
                username    required string, must be unique in the Portal, >4 characters
                password    required string, must be >= 8 characters.
                fullname    required string, name of the user
                email       required string, must be an email address
                
            Returns
                a boolean indicating success
        
        
        """
        if self.is_arcgisonline():
            raise ValueError('Signup is not supported on ArcGIS Online')

        postdata = self._postdata()
        postdata['username'] = username
        postdata['password'] = password
        postdata['fullname'] = fullname
        postdata['email'] = email
        resp = self.con.post('community/signUp', postdata, ssl=True)
        if resp:
            return resp.get('success')


    def update_user(self, username, access=None, preferred_view=None,
                    description=None, tags=None, thumbnail=None,
                    fullname=None, email=None, culture=None,
                    region=None):
        """ Updates a user's properties.
        
            Note:
                Only pass in arguments for properties you want to update.
                All other properties will be left as they are.  If you 
                want to update description, then only provide
                the description argument.
                
            Arguments:
                username            required string, name of the user to be updated.
                access              optional string, values: private, org, public
                preferred_view      optional string, values: Web, GIS, null
                description         optional string, a description of the user.
                tags                optional string, comma-separated tags for searching
                thumbnail           optional string, path or url to a file.  can be PNG, GIF, 
                                            JPEG, max size 1 MB
                fullname            optional string, name of the user, only for built-in users 
                email               optional string, email address, only for built-in users
                culture             optional string, two-letter language code, fr for example 
                region              optional string, two-letter country code, FR for example
        
            Returns
                a boolean indicating success
        
        """
        properties = dict()
        postdata = self._postdata()
        if access:
            properties['access'] = access
        if preferred_view:
            properties['preferredView'] = preferred_view
        if description:
            properties['description'] = description
        if tags:
            properties['tags'] = tags
        if fullname:
            properties['fullname'] = fullname
        if email:
            properties['email'] = email
        if culture:
            properties['culture'] = culture
        if region:
            properties['region'] = region

        files = []
        if thumbnail:
            if _is_http_url(thumbnail):
                thumbnail = urllib.urlretrieve(thumbnail)[0]
                file_ext = os.path.splitext(thumbnail)[1]
                if not file_ext:
                    file_ext = imghdr.what(thumbnail)
                    if file_ext in ('gif', 'png', 'jpeg'):
                        new_thumbnail = thumbnail + '.' + file_ext
                        os.rename(thumbnail, new_thumbnail)
                        thumbnail = new_thumbnail
            files.append(('thumbnail', thumbnail, os.path.basename(thumbnail)))

        postdata.update(properties)

        # Send the POST request, and return the id from the response
        resp = self.con.post('community/users/' + username + '/update', postdata, files, ssl=True)
            
        if resp:
            return resp.get('success')



    def update_user_role(self, username, role):
        """ Updates a user's role.
        
            Notes
                There are three types of roles in Portal - user, publisher, and administrator.
                A user can share items, create maps, create groups, etc.  A publisher can 
                do everything a user can do and create hosted services.  An administrator can 
                do everything that is possible in Portal.
                
            Arguments
                username        required string, the name of the user whose role will change
                role            required string, one of these values org_user, org_publisher, org_admin
        
            Returns
                a boolean, that indicates success
        
        """
        postdata = self._postdata()
        postdata.update({'user': username, 'role': role})
        resp = self.con.post('portals/self/updateuserrole', postdata, ssl=True)
        if resp:
            return resp.get('success')


    def update_group(self, group_id, title=None, tags=None, description=None,
                     snippet=None, access=None, is_invitation_only=None, 
                     sort_field=None, sort_order=None, is_view_only=None,
                      thumbnail=None):
        """ Updates a group.
        
            Note
                Only provide the values for the arguments you wish to update.
                
            Arguments
                group_id              required string, the group to modify
                title                 optional string, name of the group
                tags                  optional string, comma-delimited list of tags
                description           optional string, describes group in detail
                snippet               optional string, <250 characters summarizes group
                access                optional string, can be private, public, or org
                thumbnail             optional string, URL or file location to group image
                is_invitation_only    optional boolean, defines whether users can join by request.
                sort_field            optional string, specifies how shared items with the group are sorted.
                sort_order            optional string, asc or desc for ascending or descending.
                is_view_only          optional boolean, defines whether the group is searchable
        
            Returns
                a boolean indicating success
        """
        
        
        properties = dict()
        postdata = self._postdata()
        if title:
            properties['title'] = title
        if tags:
            properties['tags'] = tags
        if description:
            properties['description'] = description
        if snippet:
            properties['snippet'] = snippet
        if access:
            properties['access'] = access
        if is_invitation_only:
            properties['isinvitationOnly'] = is_invitation_only
        if sort_field:
            properties['sortField'] = sort_field
        if sort_order:
            properties['sortOrder'] = sort_order
        if is_view_only:
            properties['isViewOnly'] = is_view_only
                    
        postdata.update(properties)

        files = []
        if thumbnail:
            if _is_http_url(thumbnail):
                thumbnail = urllib.urlretrieve(thumbnail)[0]
                file_ext = os.path.splitext(thumbnail)[1]
                if not file_ext:
                    file_ext = imghdr.what(thumbnail)
                    if file_ext in ('gif', 'png', 'jpeg'):
                        new_thumbnail = thumbnail + '.' + file_ext
                        os.rename(thumbnail, new_thumbnail)
                        thumbnail = new_thumbnail
            files.append(('thumbnail', thumbnail, os.path.basename(thumbnail)))

        resp = self.con.post('community/groups/' + group_id + '/update', postdata, files)
        if resp:
            return resp.get('success')



    def get_version(self, force=False):
        """ Returns the portal version (using cache unless force=True). 
        
            Note:
                The version information is retrieved when you create the
                Portal object and then cached for future requests.  If you
                want to make a request to the Portal and not rely on the
                cache then you can set the force argument to True.
                
            Arguments:
                force        boolean, true=make a request, false=use cache
                
            Returns
                a string with the version.  The version is an internal number
                that may not match the version of the product purchased.  So
                2.3 is returned from Portal 10.2.1 for instance.
        
        
        """

        # If we've never retrieved the version before, or the caller is
        # forcing a check of the server, then check the server
        if not self._version or force:
            resp = self.con.post('', self._postdata())
            if not resp:
                old_resturl = _normalize_url(self.url) + 'sharing/'
                resp = self.con.post(old_resturl, self._postdata(), ssl=True)
                if resp:
                    _log.warn('Portal is pre-1.6.2; some things may not work')
                    self._is_pre_162 = True
                    self._is_pre_21 = True
                    self.resturl = old_resturl
                    self.con.baseurl = old_resturl
            else:
                version = resp.get('currentVersion')
                if version == '1.6.2' or version == '2.0':
                    _log.warn('Portal is pre-2.1; some features not supported')
                    self._is_pre_21 = True
            if resp:
                self._version = resp.get('currentVersion')

        return self._version




 

    def _is_searching_public(self, scope):
        if scope == 'public':
            return True
        elif scope == 'org':
            return False
        elif scope == 'default' or scope is None:
            # By default orgs won't search public
            return False if self.is_org() else True
        else:
            raise ValueError('Unknown scope "' + scope + '". Supported ' \
                              + 'values are "public", "org", and "default"')


    def _invitations_page(self, start, num):
        postdata = self._postdata()
        postdata.update({ 'start': start, 'num': num })
        return self.con.post('portals/self/invitations', postdata)


  
    def _postdata(self):
        if self._basepostdata:
            # Return a defensive copy
            return copy.deepcopy(self._basepostdata)
        return None



    def _search_page(self, q=None, bbox=None, start=1, num=10, sortfield='', sortorder='asc'):
        _log.info('Searching items (q=' + str(q) + ', bbox=' + str(bbox) \
                  + ', start=' + str(start) + ', num=' + str(num) + ')')
        postdata = self._postdata()
        postdata.update({ 'q': q or '', 'bbox': bbox or '', 'start': start, 'num': num,
                          'sortField': sortfield, 'sortOrder': sortorder })
        return self.con.post('search', postdata)


    def _groups_page(self, q=None, start=1, num=10, sortfield='',
                     sortorder='asc'):
        _log.info('Searching groups (q=' + str(q) + ', start=' + str(start) \
                  + ', num=' + str(num) + ')')
        postdata = self._postdata()
        postdata.update({ 'q': q, 'start': start, 'num': num,
                          'sortField': sortfield, 'sortOrder': sortorder })
        return self.con.post('community/groups', postdata)


    def _org_users_page(self, start=1, num=10):
        _log.info('Retrieving org users (start=' + str(start) \
                  + ', num=' + str(num) + ')')
        postdata = self._postdata()
        postdata['start'] = start
        postdata['num'] = num
        return self.con.post('portals/self/users', postdata)


    def _users_page(self, q=None, start=1, num=10, sortfield='', sortorder='asc'):
        _log.info('Searching users (q=' + str(q) + ', start=' + str(start) \
                  + ', num=' + str(num) + ')')
        postdata = self._postdata()
        postdata.update({ 'q': q, 'start': start, 'num': num,
                          'sortField': sortfield, 'sortOrder': sortorder })
        return self.con.post('community/users', postdata)

    def _user_item(self, item_id, owner=None, folder_id=None):
        """ Returns a tuple of the item properties, item sharing, and folder id. """

        # First check the cache, and if we have the link, try it
        if id in self._user_item_links_cache:
            user_item_link = self._user_item_links_cache[item_id]
            resp = self.con.post(user_item_link, self._postdata())
            if resp and not resp.get('error'):
                return resp['item'], resp['sharing'], folder_id

        # If we haven't cached the link, or the cached link no longer works,
        # proceed with trying the more manual approach. Start with getting the
        # owner, if not provided as input.
        if not owner:
            item = self.item(item_id)
            if not item:
                raise ValueError('Invalid item id: ' + item_id)
            owner = item['owner']

        # TODO supress warnings when searching

        # If a folder was provided, use it to find the item
        basepath = 'content/users/' + owner + '/'
        if folder_id:
            path = basepath + folder_id + '/items/' + item_id
            resp = self.con.post(path, self._postdata())
            if resp and not resp.get('error'):
                self._user_item_links_cache[item_id] = path
                return resp['item'], resp['sharing'], folder_id

        # Otherwise, first try the root folder
        path = basepath + 'items/' + item_id
        resp = self.con.post(path, self._postdata())
        if resp and not 'error' in resp:
            self._user_item_links_cache[item_id] = path
            return resp['item'], resp['sharing'], folder_id

        # If the item wasnt in root folder, try other folders
        folders = self.folders(owner)
        for folder in folders:
            path = basepath + folder['id'] + '/items/' + item_id
            resp = self.con.post(path, self._postdata())
            if resp and not resp.get('error'):
                self._user_item_links_cache[item_id] = path
                return resp['item'], resp['sharing'], folder['id']

        return None, None, None

    def _user_item_link(self, item_id, owner=None, folder_id=None, path_only=False):
        """ Returns the user link to an item (includes folder if appropriate). """

        # The call to user_item will use the cache, and will validate the link
        item, item_sharing, folder_id = self._user_item(item_id, owner, folder_id)
        if item:
            link = ''
            if not path_only:
                link += self.con.baseurl
                if self.is_all_ssl():
                    link = link.replace('http://', 'https')
            link += 'content/users/' + item['owner'] + '/'
            if not folder_id:
                return link + 'items/' + item_id
            else:
                return link + folder_id + '/items/' + item_id




    def _extract(self, results, props=None):
        if not props or len(props) == 0:
            return results
        newresults = []
        for result in results:
            newresult = dict((p, result[p]) for p in props if p in result)
            newresults.append(newresult)
        return newresults

class _ArcGISConnection(object):
    """ A class users to manage connection to ArcGIS services (Portal and Server). """

    def __init__(self, baseurl, username=None, password=None, key_file=None,
                 cert_file=None, expiration=60, all_ssl=False, referer=None,
                 proxy_host=None, proxy_port=None, ensure_ascii=True):
        """ The _ArcGISConnection constructor. Requires URL and optionally username/password. """

        self.baseurl = _normalize_url(baseurl)
        self.key_file = key_file
        self.cert_file = cert_file
        self.all_ssl = all_ssl
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.ensure_ascii = ensure_ascii
        self.token = None

        # Setup the referer and user agent
        if not referer:
            import socket
            ip = socket.gethostbyname(socket.gethostname())
            referer = socket.gethostbyaddr(ip)[0]
        self._referer = referer
        self._useragent = 'PortalPy/' + __version__

        # Login if credentials were provided
        if username and password:
            self.login(username, password, expiration)
        elif username or password:
            _log.warning('Both username and password required for login')

    def generate_token(self, username, password, expiration=60):
        """ Generates and returns a new token, but doesn't re-login. """
        postdata = { 'username': username, 'password': password,
                     'client': 'referer', 'referer': self._referer,
                     'expiration': expiration, 'f': 'json' }
        resp = self.post('generateToken', postdata, ssl=True)
        if resp:
            return resp.get('token')

    def login(self, username, password, expiration=60):
        """ Logs into the portal using username/password. """
        newtoken = self.generate_token(username, password, expiration)
        if newtoken:
            self.token = newtoken
            self._username = username
            self._password = password
            self._expiration = expiration
        return newtoken

    def relogin(self, expiration=None):
        """ Re-authenticates with the portal using the same username/password. """
        if not expiration:
            expiration = self._expiration
        return self.login(self._username, self._password, expiration)

    def logout(self):
        """ Logs out of the portal. """
        self.token = None

    def is_logged_in(self):
        """ Returns true if logged into the portal. """
        return self.token is not None

    def get(self, path, ssl=False, compress=True, try_json=True, is_retry=False):
        """ Returns result of an HTTP GET. Handles token timeout and all SSL mode."""
        url = path
        if not path.startswith('http://') and not path.startswith('https://'):
            url = self.baseurl + path
        if ssl or self.all_ssl:
            url = url.replace('http://', 'https://')

        # Add the token if logged in
        if self.is_logged_in():
            url = self._url_add_token(url, self.token)

        _log.debug('REQUEST (get): ' + url)

        try:
            # Send the request and read the response
            headers = [('Referer', self._referer),
                       ('User-Agent', self._useragent)]
            if compress:
                headers.append(('Accept-encoding', 'gzip'))
            opener = urllib2.build_opener()
            opener.addheaders = headers
            resp = opener.open(url)
            if resp.info().get('Content-Encoding') == 'gzip':
                buf = StringIO(resp.read())
                f = gzip.GzipFile(fileobj=buf)
                resp_data = f.read()
            else:
                resp_data = resp.read()

            # If we're not trying to parse to JSON, return response as is
            if not try_json:
                return resp_data

            try:
                resp_json = json.loads(resp_data)

                # Convert to ascii if directed to do so
                if self.ensure_ascii:
                    resp_json = _unicode_to_ascii(resp_json)

                # Check for errors, and handle the case where the token timed
                # out during use (and simply needs to be re-generated)
                try:
                    if resp_json.get('error', None):
                        errorcode = resp_json['error']['code']
                        if errorcode == 498 and not is_retry:
                            _log.info('Token expired during get request, ' \
                                      + 'fetching a new token and retrying')
                            newtoken = self.relogin()
                            newpath = self._url_add_token(path, newtoken)
                            return self.get(newpath, ssl, compress, try_json, is_retry=True)
                        elif errorcode == 498:
                            raise RuntimeError('Invalid token')
                        self._handle_json_error(resp_json['error'])
                        return None
                except AttributeError:
                    # Top-level JSON object isnt a dict, so can't have an error
                    pass

                # If the JSON parsed correctly and there are no errors,
                # return the JSON
                return resp_json

            # If we couldnt parse the response to JSON, return it as is
            except ValueError:
                return resp

        # If we got an HTTPError when making the request check to see if it's
        # related to token timeout, in which case, regenerate a token
        except urllib2.HTTPError as e:
            if e.code == 498 and not is_retry:
                _log.info('Token expired during get request, fetching a new ' \
                          + 'token and retrying')
                self.logout()
                newtoken = self.relogin()
                newpath = self._url_add_token(path, newtoken)
                return self.get(newpath, ssl, try_json, is_retry=True)
            elif e.code == 498:
                raise RuntimeError('Invalid token')
            else:
                raise e

    def download(self, path, filepath, ssl=False, is_retry=False):
        """ Downloads result of an HTTP GET. Handles token timeout and all SSL mode."""
        url = path
        if not path.startswith('http://') and not path.startswith('https://'):
            url = self.baseurl + path
        if ssl or self.all_ssl:
            url = url.replace('http://', 'https://')

        # Add the token if logged in
        if self.is_logged_in():
            url = self._url_add_token(url, self.token)

        _log.debug('REQUEST (download): ' + url + ', to ' + filepath)

        # Send the request, and handle the case where the token has
        # timed out (relogin and try again)
        try:
            opener = _StrictURLopener()
            opener.addheaders = [('Referer', self._referer),
                                 ('User-Agent', self._useragent)]
            opener.retrieve(url, filepath)
        except urllib2.HTTPError as e:
            if e.code == 498 and not is_retry:
                _log.info('Token expired during download request, fetching a ' \
                          + 'new token and retrying')
                self.logout()
                newtoken = self.relogin()
                newpath = self._url_add_token(path, newtoken)
                self.download(newpath, filepath, ssl, is_retry=True)
            elif e.code == 498:
                raise RuntimeError('Invalid token')
            else:
                raise e

    def _url_add_token(self, url, token):

        # Parse the URL and query string
        urlparts = urlparse.urlparse(url)
        qs_list = urlparse.parse_qsl(urlparts.query)

        # Update the token query string parameter
        replaced_token = False
        new_qs_list = []
        for qs_param in qs_list:
            if qs_param[0] == 'token':
                qs_param = ('token', token)
                replaced_token = True
            new_qs_list.append(qs_param)
        if not replaced_token:
            new_qs_list.append(('token', token))

        # Rebuild the URL from parts and return it
        return urlparse.urlunparse((urlparts.scheme, urlparts.netloc,
                                    urlparts.path, urlparts.params,
                                    urllib.urlencode(new_qs_list),
                                    urlparts.fragment))

    def post(self, path, postdata=None, files=None, ssl=False, compress=True,
             is_retry=False):
        """ Returns result of an HTTP POST. Supports Multipart requests."""
        url = path
        if not path.startswith('http://') and not path.startswith('https://'):
            url = self.baseurl + path
        if ssl or self.all_ssl:
            url = url.replace('http://', 'https://')

        # Add the token if logged in
        if self.is_logged_in():
            postdata['token'] = self.token

        if _log.isEnabledFor(logging.DEBUG):
            msg = 'REQUEST: ' + url + ', ' + str(postdata)
            if files:
                msg += ', files=' + str(files)
            _log.debug(msg)

        # If there are files present, send a multipart request
        if files:
            parsed_url = urlparse.urlparse(url)
            resp_data = self._postmultipart(parsed_url.netloc,
                                            str(parsed_url.path),
                                            postdata,
                                            files,
                                            parsed_url.scheme == 'https')

        # Otherwise send a normal HTTP POST request
        else:
            encoded_postdata = None
            if postdata:
                encoded_postdata = urllib.urlencode(postdata)
            headers = [('Referer', self._referer),
                       ('User-Agent', self._useragent)]
            if compress:
                headers.append(('Accept-encoding', 'gzip'))
            opener = urllib2.build_opener()
            opener.addheaders = headers
            resp = opener.open(url, data=encoded_postdata)
            if resp.info().get('Content-Encoding') == 'gzip':
                buf = StringIO(resp.read())
                f = gzip.GzipFile(fileobj=buf)
                resp_data = f.read()
            else:
                resp_data = resp.read()

        # Parse the response into JSON
        if _log.isEnabledFor(logging.DEBUG):
            _log.debug('RESPONSE: ' + url + ', ' + _unicode_to_ascii(resp_data))
        resp_json = json.loads(resp_data)

        # Convert to ascii if directed to do so
        if self.ensure_ascii:
            resp_json = _unicode_to_ascii(resp_json)

        # Check for errors, and handle the case where the token timed out
        # during use (and simply needs to be re-generated)
        try:
            if resp_json.get('error', None):
                errorcode = resp_json['error']['code']
                if errorcode == 498 and not is_retry:
                    _log.info('Token expired during post request, fetching a new '
                              + 'token and retrying')
                    self.logout()
                    newtoken = self.relogin()
                    postdata['token'] = newtoken
                    return self.post(path, postdata, files, ssl, compress,
                                     is_retry=True)
                elif errorcode == 498:
                    raise RuntimeError('Invalid token')
                self._handle_json_error(resp_json['error'])
                return None
        except AttributeError:
            # Top-level JSON object isnt a dict, so can't have an error
            pass
        
        return resp_json

    def _postmultipart(self, host, selector, fields, files, ssl):
        boundary, body = self._encode_multipart_formdata(fields, files)
        headers = {
        'User-Agent': self._useragent,
        'Referer': self._referer,
        'Content-Type': 'multipart/form-data; boundary=%s' % boundary
        }
        if self.proxy_host:
            if ssl:
                h = httplib.HTTPSConnection(self.proxy_host, self.proxy_port,
                                            key_file=self.key_file,
                                            cert_file=self.cert_file)
                h.request('POST', 'https://' + host + selector, body, headers)
            else:
                h = httplib.HTTPConnection(self.proxy_host, self.proxy_port)
                h.request('POST', 'http://' + host + selector, body, headers)
        else:
            if ssl:
                h = httplib.HTTPSConnection(host, key_file=self.key_file,
                                            cert_file=self.cert_file)
                h.request('POST', selector, body, headers)
            else:
                h = httplib.HTTPConnection(host)
                h.request('POST', selector, body, headers)
        return h.getresponse().read()

    def _encode_multipart_formdata(self, fields, files):
        boundary = mimetools.choose_boundary()
        buf = StringIO()
        for (key, value) in fields.iteritems():
            buf.write('--%s\r\n' % boundary)
            buf.write('Content-Disposition: form-data; name="%s"' % key)
            buf.write('\r\n\r\n' + _tostr(value) + '\r\n')
        for (key, filepath, filename) in files:
            buf.write('--%s\r\n' % boundary)
            buf.write('Content-Disposition: form-data; name="%s"; filename="%s"\r\n' % (key, filename))
            buf.write('Content-Type: %s\r\n' % (self._get_content_type(filename)))
            f = open(filepath, "rb")
            try:
                buf.write('\r\n' + f.read() + '\r\n')
            finally:
                f.close()
        buf.write('--' + boundary + '--\r\n\r\n')
        buf = buf.getvalue()
        return boundary, buf

    def _get_content_type(self, filename):
        return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

    def _handle_json_error(self, error):
        _log.error(error.get('message', 'Unknown Error'))
        for errordetail in error['details']:
            _log.error(errordetail)


class _StrictURLopener(urllib.FancyURLopener):
    def http_error_default(self, url, fp, errcode, errmsg, headers):
        if errcode != 200:
            raise urllib2.HTTPError(url, errcode, errmsg, headers, fp)

def _normalize_url(url, charset='utf-8'):
    """ Normalizes a URL. Based on http://code.google.com/p/url-normalize."""
    def _clean(string):
        string = unicode(urllib.unquote(string), 'utf-8', 'replace')
        return unicodedata.normalize('NFC', string).encode('utf-8')

    default_port = {
    'ftp': 21,
    'telnet': 23,
    'http': 80,
    'gopher': 70,
    'news': 119,
    'nntp': 119,
    'prospero': 191,
    'https': 443,
    'snews': 563,
    'snntp': 563,
    }
    if isinstance(url, unicode):
        url = url.encode(charset, 'ignore')

    # if there is no scheme use http as default scheme
    if url[0] not in ['/', '-'] and ':' not in url[:7]:
        url = 'http://' + url

    # shebang urls support
    url = url.replace('#!', '?_escaped_fragment_=')

    # splitting url to useful parts
    scheme, auth, path, query, fragment = urlparse.urlsplit(url.strip())
    (userinfo, host, port) = re.search('([^@]*@)?([^:]*):?(.*)', auth).groups()

    # Always provide the URI scheme in lowercase characters.
    scheme = scheme.lower()

    # Always provide the host, if any, in lowercase characters.
    host = host.lower()
    if host and host[-1] == '.':
        host = host[:-1]
    # take care about IDN domains
    host = host.decode(charset).encode('idna')  # IDN -> ACE

    # Only perform percent-encoding where it is essential.
    # Always use uppercase A-through-F characters when percent-encoding.
    # All portions of the URI must be utf-8 encoded NFC from Unicode strings
    path = urllib.quote(_clean(path), "~:/?#[]@!$&'()*+,;=")
    fragment = urllib.quote(_clean(fragment), "~")

    # note care must be taken to only encode & and = characters as values
    query = "&".join(["=".join([urllib.quote(_clean(t), "~:/?#[]@!$'()*+,;=") \
                                for t in q.split("=", 1)]) for q in query.split("&")])

    # Prevent dot-segments appearing in non-relative URI paths.
    if scheme in ["", "http", "https", "ftp", "file"]:
        output = []
        for part in path.split('/'):
            if part == "":
                if not output:
                    output.append(part)
            elif part == ".":
                pass
            elif part == "..":
                if len(output) > 1:
                    output.pop()
            else:
                output.append(part)
        if part in ["", ".", ".."]:
            output.append("")
        path = '/'.join(output)

    # For schemes that define a default authority, use an empty authority if
    # the default is desired.
    if userinfo in ["@", ":@"]:
        userinfo = ""

    # For schemes that define an empty path to be equivalent to a path of "/",
    # use "/".
    if path == "" and scheme in ["http", "https", "ftp", "file"]:
        path = "/"

    # For schemes that define a port, use an empty port if the default is
    # desired
    if port and scheme in default_port.keys():
        if port.isdigit():
            port = str(int(port))
            if int(port) == default_port[scheme]:
                port = ''

    # Put it all back together again
    auth = (userinfo or "") + host
    if port:
        auth += ":" + port
    if url.endswith("#") and query == "" and fragment == "":
        path += "#"
    return urlparse.urlunsplit((scheme, auth, path, query, fragment))

def _parse_hostname(url, include_port=False):
    """ Parses the hostname out of a URL."""
    if url:
        parsed_url = urlparse.urlparse((url))
        return parsed_url.netloc if include_port else parsed_url.hostname

def _is_http_url(url):
    if url:
        return urlparse.urlparse(url).scheme in ['http', 'https']

def _unpack(obj_or_seq, key=None, flatten=False):
    """ Turns a list of single item dicts in a list of the dict's values."""

    # The trivial case (passed in None, return None)
    if not obj_or_seq:
        return None

    # We assume it's a sequence
    new_list = []
    for obj in obj_or_seq:
        value = _unpack_obj(obj, key, flatten)
        new_list.extend(value)

    return new_list

def _unpack_obj(obj, key=None, flatten=False):
    try:
        if key:
            value = [obj.get(key)]
        else:
            value = obj.values()
    except AttributeError:
        value = [obj]

    # Flatten any lists if directed to do so
    if value and flatten:
        value = [item for sublist in value for item in sublist]

    return value

def _unicode_to_ascii(data):
    """ Converts strings and collections of strings from unicode to ascii. """
    if isinstance(data, str):
        return _remove_non_ascii(data)
    if isinstance(data, unicode):
        return _remove_non_ascii(str(data.encode('utf8')))
    elif isinstance(data, collections.Mapping):
        return dict(map(_unicode_to_ascii, data.iteritems()))
    elif isinstance(data, collections.Iterable):
        return type(data)(map(_unicode_to_ascii, data))
    else:
        return data

def _remove_non_ascii(s):
    return ''.join(i for i in s if ord(i) < 128)

def _tostr(obj):
    if not obj:
        return ''
    if isinstance(obj, list):
        return ', '.join(map(_tostr, obj))
    return str(obj)


# This function is a workaround to deal with what's typically described as a
# problem with the web server closing a connection. This is problem
# experienced with www.arcgis.com (first encountered 12/13/2012). The problem
# and workaround is described here:
# http://bobrochel.blogspot.com/2010/11/bad-servers-chunked-encoding-and.html
def _patch_http_response_read(func):
    def inner(*args):
        try:
            return func(*args)
        except httplib.IncompleteRead, e:
            return e.partial

    return inner
httplib.HTTPResponse.read = _patch_http_response_read(httplib.HTTPResponse.read)
