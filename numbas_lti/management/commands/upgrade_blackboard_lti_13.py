"""
Copy user information for a Blackboard LTI 1.1 connection to work with LTI 1.3.

Blackboard automatically removes the LTI 1.1 connection when you add an LTI 1.3 connection.

We're left with user data for LTI 1.1, which isn't necessarily the same as would be provided under LTI 1.3.

However, Blackboard seems to give the same user IDs under both protocols, so we can create LTI_13_UserAlias objects based on the LTI_11_UserAlias objects.
"""

from numbas_lti.models import LTI_11_UserAlias, LTI_13_UserAlias


from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Migrate LTI user aliases from LTI 1.1 to LTI 1.3. This should only be necessary for Blackboard connections.'

    def add_arguments(self, parser):
        parser.add_argument('--consumer', help='Key of the consumer to upgrade. If not given, data for all LTI 1.1 consumers is upgraded.')

    def handle(self, *args, **options):
        lti_11_aliases = LTI_11_UserAlias.objects.all()

        consumer_key = options['consumer']
        if consumer_key:
            lti_11_aliases = lti_11_aliases.filter(consumer__lti_11__key=consumer_key)

        num_upgraded = 0
        for ua in lti_11_aliases:
            u = ua.user
            try:
                LTI_13_UserAlias.objects.get_or_create(
                    consumer=ua.consumer,
                    user=u,
                    defaults={
                        'sub':ua.consumer_user_id,
                        'full_name': u.get_full_name(),
                        'given_name': u.first_name,
                        'family_name': u.last_name,
                        'email': u.email
                    }
                )
                num_upgraded += 1
            except LTI_13_UserAlias.MultipleObjectsReturned:
                pass

        print(f"Migrated {num_upgraded} user aliases.")
