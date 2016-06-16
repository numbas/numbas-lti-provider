from requests_oauthlib import OAuth1
import requests
import uuid

from hashlib import sha1
from base64 import b64encode

from oauthlib.oauth1 import Client
from oauthlib.common import to_unicode

class BodyHashClient(Client):
    # from https://github.com/requests/requests-oauthlib/issues/125

    def get_oauth_params(self, request):
        params = super(BodyHashClient, self).get_oauth_params(request)
        digest = b64encode(sha1(request.body.encode('UTF-8')).digest())
        params.append(('oauth_body_hash', to_unicode(digest)))
        return params

def report_outcome(attempt):

    template = """<?xml version = "1.0" encoding = "UTF-8"?>
    <imsx_POXEnvelopeRequest xmlns = "http://www.imsglobal.org/services/ltiv1p1/xsd/imsoms_v1p0">
      <imsx_POXHeader>
        <imsx_POXRequestHeaderInfo>
          <imsx_version>V1.0</imsx_version>
          <imsx_messageIdentifier>{message_identifier}</imsx_messageIdentifier>
        </imsx_POXRequestHeaderInfo>
      </imsx_POXHeader>
      <imsx_POXBody>
        <replaceResultRequest>
          <resultRecord>
            <sourcedGUID>
              <sourcedId>{sourcedId}</sourcedId>
            </sourcedGUID>
            <result>
              <resultScore>
                <language>en</language>
                <textString>{result}</textString>
              </resultScore>
            </result>
          </resultRecord>
        </replaceResultRequest>
      </imsx_POXBody>
    </imsx_POXEnvelopeRequest>
    """

    message_identifier = uuid.uuid4().int & (1<<64)-1
    user_data = attempt.user.lti_data.get(resource=attempt.resource)
    result = attempt.resource.grade_user(attempt.user)

    if user_data.lis_result_sourcedid:
        print("Posting {}".format(attempt.scaled_score))
        r = requests.post(
                user_data.lis_outcome_service_url,
                data = template.format(message_identifier=message_identifier,sourcedId=user_data.lis_result_sourcedid,result=result),
                auth=OAuth1('clp','dude',signature_type='auth_header',client_class=BodyHashClient, force_include_body=True),
                headers={'Content-Type': 'application/xml'}
            )
        print(r.status_code)
