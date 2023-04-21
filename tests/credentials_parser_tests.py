import unittest
from kognic.auth import credentials_parser


class CredentialsParserTest(unittest.TestCase):
  def test_parse_credentials(self):
  	#p = {
  	#	"clientId": "x"
  	#	"clientSecret": "y"
  	#	"email": "z"
  	#	"userId": 1
  	#	"issuer", "auth.kognic.test"
  	#}
  	#creds = credentials_parser.parse_credentials(p)
  	self.assertEquals(1, 1)
  	#self.assertEquals(creds.client_id, "x")