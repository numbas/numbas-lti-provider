from requests_oauthlib import OAuth1
import requests
import uuid
from django.utils.translation import ugettext as _

from hashlib import sha1
from base64 import b64encode

from oauthlib.oauth1 import Client
from oauthlib.common import to_unicode

from lxml import etree

class ReportOutcomeException(Exception):
    pass

class ReportOutcomeConnectionError(ReportOutcomeException):
    message = _("Error making connection to LTI consumer")
    def __init__(self,connection_error):
        self.error = connection_error

class ReportOutcomeFailure(ReportOutcomeException):
    def __init__(self,user_data,consumer_message):
        self.consumer_message = consumer_message
        ctx = {
            'user_name': user_data.user.get_full_name(), 
            'consumer_message': self.consumer_message,
        }
        self.message = _('Outcome report for user {user_name} failed; the LTI consumer said: {consumer_message}').format(**ctx)

def report_outcome_for_attempt(attempt):
    return report_outcome(attempt.resource,attempt.user)

def report_outcome(resource,user):

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
    user_data = resource.user_data(user) 
    result = resource.grade_user(user)

    if user_data.lis_result_sourcedid:
        try:
            r = requests.post(
                    user_data.lis_outcome_service_url,
                    data = template.format(message_identifier=message_identifier,sourcedId=user_data.lis_result_sourcedid,result=result),
                    auth=OAuth1(user_data.consumer.key,user_data.consumer.secret,signature_type='auth_header',client_class=Client, force_include_body=True),
                    headers={'Content-Type': 'application/xml'}
                )

            if r.status_code!=200:
                raise ReportOutcomeFailure(user_data,r.text)

            namespaces = {'ims':'http://www.imsglobal.org/services/ltiv1p1/xsd/imsoms_v1p0'}
            try:
                xml = etree.fromstring(r.content)
            except etree.XMLSyntaxError:
                raise ReportOutcomeFailure(user_data,'Response is not an XML document: {}'.format(r.text))
            except Exception as e:
                raise ReportOutcomeFailure(user_data,'{}\n\n{}'.format(e,r.text))
            status = xml.find('./ims:imsx_POXHeader/ims:imsx_POXResponseHeaderInfo/ims:imsx_statusInfo',namespaces=namespaces)
            code = status.find('ims:imsx_codeMajor',namespaces=namespaces).text
            if code=='success':
                user_data.last_reported_score = result
                user_data.save()
                return r
            else:
                description = status.find('ims:imsx_description',namespaces=namespaces).text
                raise ReportOutcomeFailure(user_data,description)
        except requests.exceptions.ConnectionError as e:
            raise ReportOutcomeConnectionError(e)
