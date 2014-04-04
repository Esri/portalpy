import portalpy
import unittest
import random


portalUrl           = "https://portalpy.esri.com/arcgis"
agolUrl             = "https://arcgis.com"
group_id            = "67e1761068b7453693a0c68c92a62e2e"    # group id of existing group "GIS Department"
portalAdminName     = "portaladmin"
portalAdminPassword = "portaladmin"
portalUserName      = 'amy.user'
portalUserPassword  = "amy.user"
test_user           = dict()
test_user_conn      = dict()
users               = ['test_update_user', 'test_update_user_role', 'test_reset_user', 'test_delete_user_with_items1',
                       'test_delete_user_with_items2', 'test_delete_user_no_items']
group_owners        = ['test_delete_user_with_items1']
test_group          = dict()

def setUpModule():
    """
       Try to put as little as possible in the setUpModule or you potentially break
       test isolation.  
       
       CAUTION:
       A few test methods need to modify a test user and so a pre-created
       user in the portal can't be used.  That means the user must be created when the tests
       are run. Creating users is an action that is appropriate for a setup method.  However
       we don't want to create a test user on every setup method because that slows down the
       running of the tests considerably since most test methods don't need a custom user.
       To maintain test isolation while getting high performance, we create test users for
       the particular methods that need them when the test module starts and clean up those
       users when the module stops.
       
       TIP:
       To create a user for your test method, all you need to do is add a a name to the 
       users global list above and it will create a user for your method named test_user[your_user]
       and create a connection for that user called test_user_conn[your_user] and clean them up 
       for you at the end.
         
        
    """

    portal = portalpy.Portal(portalUrl)

    for user in users:
        test_user[user]         = utility_create_random_user(portal)
        test_user_conn[user]    = portalpy.Portal(portalUrl, test_user[user], test_user[user])

    for owner in group_owners:
        test_group[owner]       = utility_create_random_group(test_user_conn[owner])

    # This creates a random group for the test_delete_user user
        

def tearDownModule():
    portal = portalpy.Portal(portalUrl, portalAdminName, portalAdminPassword)

    for owner in group_owners:
        portal.delete_group(test_group[owner])

    for user in users:
        portal.delete_user(test_user[user])
        
def utility_create_random_user(portal):
    while True: 
        usernum = random.randint(1,5000)
        test_user_name = "test" + str(usernum) + "." + "user"  
        test_user_password = test_user_name
        resp = portal.search_users(test_user_name) 
        if len(resp) == 0: 
            resp = portal.signup(username=test_user_name, password=test_user_password, fullname=test_user_name, email=test_user_name + "@esri.com" )
            break
        else: 
            continue
    return test_user_name

def utility_create_random_group(portal):
    while True: 
        groupnum = random.randint(1,5000)
        group_name = "test" + str(groupnum) + "." + "group"  
        resp = portal.search_groups(group_name) 
        if len(resp) == 0: 
            group_id = portal.create_group(group_name, 'test', 'a random group')
            break
        else: 
            continue
    return group_id


class TestUserGroups(unittest.TestCase):

    """    Tests whether PortalPy correctly handles user and group management functions
     """
  
    def setUp(self):
        self.portalAdmin    = portalpy.Portal(portalUrl, portalAdminName, portalAdminPassword)
        self.portalUser     = portalpy.Portal(portalUrl, portalUserName, portalUserPassword)
        self.portalAnon     = portalpy.Portal(portalUrl)

        self.test_group_id  = utility_create_random_group(self.portalAdmin)
        
    def tearDown(self):
        self.portalAdmin.delete_group(self.test_group_id)
        


    # admin access is required 
    def test_add_group_users(self):
        resp = self.portalAdmin.add_group_users(["amy.user", "bob.user"], self.test_group_id)
        self.assertEqual(len(resp['notAdded']), 0, "Users are not added  to the group successfully")         
    
    # admin access is required to retrieve the membership information.  
    def test_get_group(self):        
        group_info = self.portalAdmin.get_group(group_id)
        self.assertEqual(group_info['owner'], 'testuser', 'GIS Department group not owned by testuser')
        self.assertEqual(group_info['tags'][0], 'test', 'GIS Department test tag not listed.')
        self.assertEqual(group_info['thumbnail'], 'gis.jpeg', 'GIS Department thumbnail incorrect.')
        self.assertEqual(group_info['access'], 'public', 'GIS Department does not list public access.')
        self.assertEqual(group_info['userMembership']['memberType'], 'none', 'userMembership incorrect')        
        
    def test_get_group_members(self):        
        resp = self.portalAnon.get_group_members(group_id)
        self.assertEqual(resp['owner'], 'testuser', 'incorrect owner info of GIS Department group.')
        self.assertEqual(resp['admins'][0], 'testuser', 'incorrect admin info of GIS Department group.')
        self.assertEqual(resp['users'], ["amy.user", "bob.user"], 'incorrect member info of GIS Department group.')         

    # admin access is required
    def test_invite_group_users(self): 
        resp = self.portalAdmin.invite_group_users(["amy.user", "bob.user"], self.test_group_id, "group_admin")
        self.assertTrue(resp, "Users are not invited to group successfully")     
         
    # admin access is required     
    def test_remove_group_users(self):    
        self.portalAdmin.add_group_users(["amy.user", "bob.user"], self.test_group_id)
        resp = self.portalAdmin.remove_group_users(["amy.user", "bob.user"], self.test_group_id)
        self.assertEqual(len(resp['notRemoved']), 0, "Users are not removed successfully")  
        
    # admin access is required 
    def test_reassign_group(self): 
        resp = self.portalAdmin.reassign_group(self.test_group_id, "amy.user")
        self.assertTrue(resp, "Group is not assigned to another owner successfully")          
   
     
   
    def test_search_groups(self): 
        resp = self.portalAnon.search_groups('owner: portaladmin','created')
        self.assertGreater(len(resp), 0, 'no search result owner is returned. ')  
        self.assertEqual(resp[0]['title'], 'Featured Maps and Apps', 'searched result owner incorrect.')
        
        resp = self.portalAnon.search_groups("id:67e1761068b7453693a0c68c92a62e2e")
        self.assertGreater(len(resp), 0, 'no search result id is returned. ')  
        self.assertEqual(resp[0]['title'], 'GIS Department', 'searched result id incorrect.')          
           
        resp = self.portalAdmin.search_groups("access:public",'owner', 'desc', 100, False)
        self.assertGreater(len(resp), 0, 'no search result access is returned. ')  
        self.assertEqual(resp[0]['title'], 'GIS Department', 'searched result access incorrect.')
       
        resp = self.portalAdmin.search_groups('tags: test', 'title')
        self.assertGreater(len(resp), 0, 'no search result tags is returned. ')  
        groupFound = False
        for group in resp :
            if (group['title'] == "Charlie's group" ) :
                groupFound = True
        self.assertTrue(groupFound, 'group not found when searching tags')
        #self.assertEqual(resp[0]['title'], "Charlie's group", 'searched result tags incorrect.')       
 
    # admin access is required
    ## Update is needed with properties ###
    def test_update_groups(self): 
        resp = self.portalAdmin.update_group(self.test_group_id, '', 'http://bit.ly/WEaIh5' )
        self.assertTrue(resp, "Group is not updated successfully")       
        
    def test_leave_groups(self):         
        resp = self.portalAdmin.add_group_users(["amy.user"], self.test_group_id)     
        self.assertEqual(len(resp['notAdded']), 0, "User amy is not added  to the group successfully. ")
        
        #self.assertTrue(self.portalUser.is_logged_in, "User is not logged in.")
        
        resp = self.portalUser.leave_group(self.test_group_id)
        self.assertTrue(resp, "User amy does not leave the group successfully.")
        
    def test_get_group_thumbnail(self):   
        resp = self.portalAnon.get_group_thumbnail(group_id)
        thumbnaillength = "8353"
        self.assertEqual(len(resp), int(thumbnaillength), "The group thumbnail is not returned successfully. ")
        
    def test_get_generate_token(self): 
        # expiration time ranges from 1 minute to 1 year
        expiration = random.randint(1,525600)                 
        resp = self.portalAnon.generate_token(portalUserName, portalUserPassword, expiration)
        self.assertGreaterEqual (len(resp), 128, "Token is not generated successfully. ")
        self.assertLessEqual (len(resp), 152, "Token is not generated successfully." )        
        
    def test_login(self): 
        expiration = random.randint(1,525600)                 
        resp = self.portalAnon.login(portalUserName, portalUserName, expiration)
        self.assertGreaterEqual (len(resp), 128, "User is not logged in successfully. ")
        self.assertLessEqual (len(resp), 152, "User is not logged in successfully. " )       

    #admin access is required 
    def test_get_org_users(self):    
        resp = self.portalAdmin.get_org_users (50);  
        foundUser = False
        foundPortalAdmin = False
        for user in resp :
            if (user['username'] == portalUserName and user['role'] == 'org_user') :
                foundUser = True
            if user['username'] == portalAdminName and user['role'] == 'org_admin' :
                foundPortalAdmin = True
        self.assertTrue(foundUser, "User not found in org_users response.")
        self.assertTrue(foundPortalAdmin, "Admin not found in org_admin response.")
            

    
    def test_update_user(self): 
        resp = test_user_conn['test_update_user'].update_user(test_user['test_update_user'], description="it is a test account", access="private")
        self.assertTrue(resp, "User's properties are not updated successfully.")

    #admin access is required     
    def test_update_user_role(self): 
        resp = self.portalAdmin.update_user_role(test_user['test_update_user_role'], "org_admin")
        self.assertTrue(resp, "User's role is not updated successfully. ")   
    
    def test_reset_user(self): 
        resp = test_user_conn['test_reset_user'].reset_user(test_user['test_reset_user'], test_user['test_reset_user'], 
                                             new_password="new" + test_user['test_reset_user'], 
                                             new_security_question=0, 
                                             new_security_answer="Redlands, CA")
        self.assertTrue(resp, "User is not reset successfully. ")
    
    def test_search_users(self): 
        resp = self.portalAnon.search_users('username:amy.user',)
        self.assertGreater(len(resp), 0, 'No user search result owner is returned. ')          
        
        resp = self.portalAnon.search_users("tags:undefined",'created', sort_order='desc', add_org=True)
        self.assertGreater(len(resp), 0, 'No user search result access is returned. ')      
       
    def test_delete_user_with_items(self):
        resp = self.portalAdmin.delete_user(test_user['test_delete_user_with_items1'], test_user['test_delete_user_with_items2'])
        self.assertTrue(resp, "Unable to delete user, but expected to be able to.")
    
    def test_delete_user_no_items(self):
        resp = self.portalAdmin.delete_user(test_user['test_delete_user_no_items'])
        self.assertTrue(resp, "Unable to delete a user with no items")
    
    
if __name__ == '__main__':
    # unittest.main()
    suite = unittest.TestLoader().loadTestsFromTestCase(TestUserGroups)
    unittest.TextTestRunner(verbosity=3).run(suite)
