import portalpy
import unittest

class TestPortalProperties(unittest.TestCase):

    """    Tests whether PortalPy correctly retrieves the properties from a Portal.
           In order to work it needs to use a Portal with a known state.  A test portal
           has been stood up at portalpy.esri.com for this testing.  If you point it to your
           portal, you may need to modify your portal to get these tests to pass. 
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

    def test_loggedin_authenticated(self):
        """Tests whether the boolean value is_logged_in is correct when the user is logged in."""
        self.assertTrue(self.portalAdmin.is_logged_in, "Logged in user not known.")

    def test_loggedin_anonymous(self):
        """Tests whether the boolean value is_logged_in is correct when the user is NOT logged in."""
        self.assertFalse(self.portalAnon.is_logged_in(), "Anonymous user is logged in.")


    def test_is_all_ssl(self):
        """Tests whether PortalPy has the correct value as to whether Portal is all SSL""" 
        self.assertFalse(self.portalAnon.is_all_ssl(), "PortalPy reports the portal is all ssl when it is not.")

    def test_logged_in_user(self):
        """ Tests whether PortalPy has the correct name of the user"""
        baseEmail       = 'amyuser@nospam'
        baseFullName    = 'Amy User'
        userName        = self.portalUser.logged_in_user()['username']
        email           = self.portalUser.logged_in_user()['email']
        fullName        = self.portalUser.logged_in_user()['fullName']
        

        self.assertEquals(userName, self.portalUserName, "PortalPy reports an incorrect logged in user name.")
        self.assertEquals(fullName, baseFullName, "PortalPy reports an incorrect full name for the user.")
        self.assertEquals(email, baseEmail, "PortalPy reports an incorrect email for the user.")
        

    def test_is_arcgisOnline_when_not(self):
        """Tests whether PortalPy has the correct value as to whether Portal is all SSL""" 
        self.assertFalse(self.portalAnon.is_arcgisonline(), "PortalPy reports the portal is ArcGISOnline when it is not.")


if __name__ == '__main__':
    # unittest.main()
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPortalProperties)
    unittest.TextTestRunner(verbosity=1).run(suite)
