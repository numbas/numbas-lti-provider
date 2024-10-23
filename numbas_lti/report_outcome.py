from . import requests_session
from .exceptions import LineItemDoesNotExist
from datetime import timedelta
import requests
from requests_oauthlib import OAuth1
import uuid
from django.utils.timezone import now
from django.utils.translation import gettext as _
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from hashlib import sha1
from base64 import b64encode

from oauthlib.oauth1 import Client
from oauthlib.common import to_unicode

from pylti1p3.contrib.django.lti1p3_tool_config import DjangoDbToolConf
from pylti1p3.grade import Grade

from lxml import etree

from .models import ReportProcess, UserScoreReported, User

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

def report_all_resource_scores(resource):
    if ReportProcess.objects.filter(resource=resource,status='reporting').exists():
        return

    process = ReportProcess.objects.create(resource=resource)

    errors = []

    try:
        if resource.lti_13_links.exists():
            resource.get_lti_13_lineitem(create=True)

        for user in User.objects.filter(attempts__resource=resource, attempts__deleted=False).distinct():
            try:
                request = report_outcome(resource, user, report_process=process)
            except ReportOutcomeException as e:
                errors.append(e)

    except Exception as e:
        errors.append(e)

    if len(errors):
        process.status = 'error'
        process.response = '\n'.join(str(e) for e in errors)
    else:
        process.status = 'complete'
    process.dismissed = False
    process.save(update_fields=['status','response','dismissed'])

    return process

def report_outcome_for_attempt(attempt):
    return report_outcome(attempt.resource,attempt.user)

def report_outcome(resource, user, report_process=None) -> UserScoreReported:
    """
        Report the outcome of a student on a particular resource.
        Returns a UserScoreReported object containing details about the report.
        Calls either ``report_outcome_lti_13`` or ``report_outcome_lti_11`` depending on how the resource is linked to.
        Those methods should fill in the UserScoreReported object.
    """
    user_data = resource.user_data(user) 

    score_report = UserScoreReported(
        user=user,
        resource=resource,
        report_process=report_process
    )

    try:
        if resource.lti_13_links.exists():
            report_outcome_lti_13(resource, user_data, score_report=score_report)
        elif resource.lti_11_links.exists():
            report_outcome_lti_11(resource, user_data, score_report=score_report)
    except requests.exceptions.ConnectionError as e:
        conn_err = ReportOutcomeConnectionError(e)
        score_report.error = str(conn_err)
        raise conn_err from e
    except requests.exceptions.Timeout as e:
        timeout_err = ReportOutcomeTimeoutError(e)
        score_report.error = str(timeout_err)
        raise timeout_err from e
    except Exception as e:
        outcome_err = ReportOutcomeException(user_data,e)
        score_report.error = str(e)
        raise outcome_err from e
    finally:
        score_report.save()

    return score_report

def report_outcome_lti_13(resource, user_data, score_report):
    tool_conf = DjangoDbToolConf()

    user = user_data.user

    attempt, completion_status = resource.grade_user(user)

    time = now()
    time_offset = getattr(settings,'REPORT_SCORE_SUBTRACT_MINUTES',1) * timedelta(minutes=1)
    time -= time_offset

    activity_progress = {
        'not attempted': 'Initialized',
        'incomplete': 'Initialized',
        'completed': 'Completed',
    }[completion_status]

    if completion_status == 'completed':
        grading_progress = 'FullyGraded'
    elif completion_status == 'incomplete':
        grading_progress = 'PendingManual'
    else:
        grading_progress = 'NotReady'

    user_alias = user.lti_13_aliases.first()

    raw_score = attempt.raw_score
    max_score = attempt.max_score
    start_time = attempt.start_time
    submitted_time = None

    # TODO - save the last time the score changed. This could be due to a "cmi.score.raw" element being saved, or a Remark/DiscountPart object being created/updated/deleted.
    grade = Grade()\
        .set_score_given(raw_score)\
        .set_score_maximum(max_score)\
        .set_timestamp(time)\
        .set_started_at(start_time)\
        .set_activity_progress(activity_progress)\
        .set_grading_progress(grading_progress)\
        .set_user_id(user_alias.sub)

    if attempt.end_time:
        submitted_time = attempt.end_time - time_offset
        grade = grade.set_submitted_at(submitted_time)

    score_report.attempt = attempt
    score_report.time = time
    score_report.raw_score = raw_score
    score_report.max_score = max_score
    score_report.completion_status = completion_status
    score_report.start_time = start_time
    score_report.submitted_time = submitted_time

    consumer = user_data.consumer

    ags = resource.lti_13_contexts().first().get_ags()

    try:
        lineitem = resource.get_lti_13_lineitem()
    except LineItemDoesNotExist:
        return

    ags.put_grade(grade, lineitem)

def report_outcome_lti_11(resource,user_data, score_report):

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

    score_report.attempt = attempt
    score_report.time = now()
    score_report.raw_score = attempt.raw_score
    score_report.max_score = attempt.max_score
    score_report.completion_status = completion_status
    score_report.start_time = attempt.start_time

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
