from . import requests_session
from .exceptions import LineItemDoesNotExist
import requests
from requests_oauthlib import OAuth1
import uuid
from django.utils.translation import gettext as _
from django.conf import settings

from hashlib import sha1
from base64 import b64encode

from oauthlib.oauth1 import Client
from oauthlib.common import to_unicode

from pylti1p3.contrib.django.lti1p3_tool_config import DjangoDbToolConf
from pylti1p3.grade import Grade

from lxml import etree

class ReportOutcomeException(Exception):
    def __init__(self,user_data,error):
        self.error = error
        ctx = {
            'user_name': user_data.user.get_full_name(), 
            'error': self.error,
        }
        self.message = _('There was an error reporting data for user {user_name} back to the LTI consumer:\n{error}').format(**ctx)

    def __str__(self):
        return self.message

class ReportAnonymousUserException(Exception):
    def __init__(self):
        self.message = _('Tried to report data for an anonymous user')

class ReportOutcomeTimeoutError(ReportOutcomeException):
    message = _("The request to report data back to the LTI consumer timed out.")
    def __init__(self,timeout_error):
        self.error = timeout_error

class ReportOutcomeConnectionError(ReportOutcomeException):
    message = _("There was an error making a connection to the LTI consumer.")
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

def report_outcome(resource, user):
    user_data = resource.user_data(user) 
    try:
        if resource.lti_11_links.exists():
            report_outcome_lti_11(resource, user_data)
        if resource.lti_13_links.exists():
            report_outcome_lti_13(resource, user_data)
    except requests.exceptions.ConnectionError as e:
        raise ReportOutcomeConnectionError(e) from e
    except requests.exceptions.Timeout as e:
        raise ReportOutcomeTimeoutError(e) from e
    except Exception as e:
        raise ReportOutcomeException(user_data,e) from e

def report_outcome_lti_13(resource, user_data):
    tool_conf = DjangoDbToolConf()

    user = user_data.user

    attempt, completion_status = resource.grade_user(user)

    if attempt.end_time is not None:
        time = attempt.end_time
    else:
        time = attempt.scormelements.first().time

    activity_progress = {
        'not attempted': 'Initialized',
        'incomplete': 'InProgress',
        'completed': 'Completed',
    }[completion_status]

    if completion_status == 'completed':
        grading_progress = 'FullyGraded'
    elif completion_status == 'incomplete':
        grading_progress = 'Pending'
    else:
        grading_progress = 'NotReady'

    user_alias = user.lti_13_aliases.first()

    from django.utils.timezone import now

    # TODO - save the last time the score changed. This could be due to a "cmi.score.raw" element being saved, or a Remark/DiscountPart object being created/updated/deleted.
    grade = Grade()\
        .set_score_given(attempt.raw_score)\
        .set_score_maximum(attempt.max_score)\
        .set_timestamp(now().strftime('%Y-%m-%dT%H:%M:%S+0000'))\
        .set_activity_progress(activity_progress)\
        .set_grading_progress(grading_progress)\
        .set_user_id(user_alias.sub)

    consumer = user_data.consumer

    ags = resource.lti_13_contexts().first().get_ags()

    try:
        lineitem = resource.get_lti_13_lineitem()
    except LineItemDoesNotExist:
        return

    ags.put_grade(grade, lineitem)

def report_outcome_lti_11(resource,user_data):

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

    user = user_data.user

    if user.is_anonymous:
        raise ReportOutcomeException(None,'User is anonymous')
    message_identifier = uuid.uuid4().int & (1<<64)-1
    attempt, completion_status = resource.grade_user(user)
    result = attempt.scaled_score

    if user_data.lti_11.lis_result_sourcedid:
        request_xml = template.format(message_identifier=message_identifier,sourcedId=user_data.lti_11.lis_result_sourcedid,result=result)
        r = requests_session.get_session().post(
                user_data.lti_11.lis_outcome_service_url,
                data = request_xml,
                auth=OAuth1(user_data.consumer.lti_11.key, user_data.consumer.lti_11.secret, signature_type='auth_header', client_class=Client, force_include_body=True),
                headers={'Content-Type': 'application/xml'},
                timeout = getattr(settings,'REQUEST_TIMEOUT',60)
            )

        namespaces = {'ims':'http://www.imsglobal.org/services/ltiv1p1/xsd/imsoms_v1p0'}
        try:
            xml = etree.fromstring(r.content)
        except etree.XMLSyntaxError:
            raise ReportOutcomeFailure(user_data,'Response is not an XML document: {}'.format(r.text))
        except Exception as e:
            raise ReportOutcomeFailure(user_data,'{}\n\n{}'.format(e,r.text))
        status = xml.find('./ims:imsx_POXHeader/ims:imsx_POXResponseHeaderInfo/ims:imsx_statusInfo',namespaces=namespaces)
        code = status.find('ims:imsx_codeMajor',namespaces=namespaces).text
        if code=='success' and r.status_code == 200:
            user_data.last_reported_score = result
            user_data.save()
            return r
        else:
            description = status.find('ims:imsx_description',namespaces=namespaces).text
            raise ReportOutcomeFailure(user_data,description)
