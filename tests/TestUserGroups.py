import portalpy
import unittest
import random


class TestUserGroups(unittest.TestCase):

    """    Tests whether PortalPy correctly handles user and group management functions
     """

    portalUrl           = "https://portalpy.esri.com/arcgis"
    agolUrl             = "https://arcgis.com"
    portalAdminName     = "portaladmin"
    portalAdminPassword = "portaladmin"
    portalUserName      = 'amy.user'
    portalUserPassword  = "amy.user"
    
    def setUp(self):
        self.portalAdmin = portalpy.Portal(self.portalUrl, self.portalAdminName, self.portalAdminPassword)
        self.portalUser = portalpy.Portal(self.portalUrl, self.portalUserName, self.portalUserPassword)
        self.portalAnon = portalpy.Portal(self.portalUrl)
        
        # group id of existing group "GIS Department"
        self.group_id = "67e1761068b7453693a0c68c92a62e2e"  
        
        # create a new group 
        groupnum = random.randint(1,5000)
        self.test_group_name = "group" + str(groupnum)
        self.test_group_id = self.portalAdmin.create_group(self.test_group_name, 'test', description="it is a test group")   
        
        # create a new user        
        while True: 
            usernum = random.randint(1,5000)
            self.test_user_name = "test" + str(usernum) + "." + "user"  
            self.test_user_password = self.test_user_name
            resp = self.portalAnon.search_users(self.test_user_name) 
            if len(resp) == 0: 
                resp = self.portalAnon.signup(self.test_user_name, self.test_user_name, self.test_user_password, self.test_user_name + "@esri.com" )        
                self.assertTrue(resp, "New user " + self.test_user_name + " is not signed up successfully. ") 
                break
            else: 
                continue
            
        self.portalNewUser = portalpy.Portal(self.portalUrl, self.test_user_name, self.test_user_password)
        
    def tearDown(self):
        self.portalAdmin.delete_group(self.test_group_id)
        
        ## Delete_User needs to be updated when cascade = true ##
        #resp = self.portalAdmin.delete_user(self.test_user_name, True, self.portalUserName)
        
        resp = self.portalAdmin.delete_user(self.test_user_name, False)
        self.assertTrue(resp, "New user " + self.test_user_name + " is not deleted successfully. ") 

    # admin access is required 
    def test_add_group_users(self):
        resp = self.portalAdmin.add_group_users(["amy.user", "bob.user"], self.test_group_id)
        self.assertEqual(len(resp['notAdded']), 0, "Users are not added  to the group successfully")         
    
    # admin access is required to retrieve the membership information.  
    def test_get_group(self):        
        group_info = self.portalAdmin.get_group(self.group_id)
        self.assertEqual(group_info['owner'], 'testuser', 'GIS Department group not owned by testuser')
        self.assertEqual(group_info['tags'][0], 'test', 'GIS Department test tag not listed.')
        self.assertEqual(group_info['thumbnail'], 'gis.jpeg', 'GIS Department thumbnail incorrect.')
        self.assertEqual(group_info['access'], 'public', 'GIS Department does not list public access.')
        self.assertEqual(group_info['userMembership']['memberType'], 'none', 'userMembership incorrect')        
        
    def test_get_group_memebers(self):        
        resp = self.portalAnon.get_group_members(self.group_id)
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
        self.assertEqual(resp[0]['title'], "Charlie's group", 'searched result tags incorrect.')       
 
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
        resp = self.portalAnon.get_group_thumbnail(self.group_id)
        thumbnaillength = "8353"
        self.assertEqual(len(resp), int(thumbnaillength), "The group thumbnail is not returned successfully. ")
        
    def test_get_generate_token(self): 
        # expiration time ranges from 1 minute to 1 year
        expiration = random.randint(1,525600)                 
        resp = self.portalAnon.generate_token(self.test_user_name, self.test_user_password, expiration)
        self.assertGreaterEqual (len(resp), 128, "Token is not generated successfully. ")
        self.assertLessEqual (len(resp), 152, "Token is not generated successfully." )        
        
    def test_login(self): 
        expiration = random.randint(1,525600)                 
        resp = self.portalAnon.login(self.test_user_name, self.test_user_password, expiration)
        self.assertGreaterEqual (len(resp), 128, "User is not logged in successfully. ")
        self.assertLessEqual (len(resp), 152, "User is not logged in successfully. " )       

    #admin access is required 
    def test_get_org_users(self):    
        resp = self.portalAdmin.get_org_users (50);  
        self.assertEqual(resp[0]['username'], "amy.user", "Username within organization is not returned successfully. " )
        self.assertEqual(resp[0]['role'], "org_user", "User role within organization is not returned successfully. " )
        self.assertEqual(resp[3]['username'], "portaladmin", "Username within organization is not returned successfully. " )
        self.assertEqual(resp[3]['role'], "org_admin", "User role within organization is not returned successfully. " )
    
    
    def test_update_user(self): 
        resp = self.portalNewUser.update_user(self.test_user_name, description="it is a test account", access="private")
        self.assertTrue(resp, "User's properties are not updated successfully. ")

    #admin access is required     
    def test_update_user_role(self): 
        resp = self.portalAdmin.update_user_role(self.test_user_name, "org_admin")
        self.assertTrue(resp, "User's role is not updated successfully. ")   
    
    def test_reset_user(self): 
        resp = self.portalNewUser.reset_user(self.test_user_name, self.test_user_password, 
                                             new_password="new" + self.test_user_password, 
                                             new_security_question=0, 
                                             new_security_answer="Redlands, CA")
        self.assertTrue(resp, "User is not resetted successfully. ")
    
    def test_search_users(self): 
        resp = self.portalAnon.search_users('username:amy.user',)
        self.assertGreater(len(resp), 0, 'No user search result owner is returned. ')          
        
        resp = self.portalAnon.search_users("tags:undefined",'created', sort_order='desc', add_org=True)
        self.assertGreater(len(resp), 0, 'No user search result access is returned. ')      
       
    
    
if __name__ == '__main__':
    # unittest.main()
    suite = unittest.TestLoader().loadTestsFromTestCase(TestUserGroups)
    unittest.TextTestRunner(verbosity=1).run(suite)
