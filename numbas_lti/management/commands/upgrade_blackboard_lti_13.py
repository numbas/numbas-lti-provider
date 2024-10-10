"""
Copy user information for a Blackboard LTI 1.1 connection to work with LTI 1.3.

Blackboard automatically removes the LTI 1.1 connection when you add an LTI 1.3 connection.

We're left with user data for LTI 1.1, which isn't necessarily the same as would be provided under LTI 1.3.

However, Blackboard seems to give the same user IDs under both protocols, so we can create LTI_13_UserAlias objects based on the LTI_11_UserAlias objects.
"""

from numbas_lti.models import LTI_11_UserAlias, LTI_13_UserAlias, LTIConsumer, User, Attempt


from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Migrate LTI user aliases from LTI 1.1 to LTI 1.3. This should only be necessary for Blackboard connections.'

    def add_arguments(self, parser):
        parser.add_argument('to_consumer', help='ID of the LTI 1.3 consumer to upgrade to.')
        parser.add_argument('--merge-accounts', action='store_true', help='Merge any user accounts created through LTI 1.3 with accounts created through LTI 1.1.')
        parser.add_argument('--consumer', type=int, help='Key of the consumer to upgrade. If not given, data for all LTI 1.1 consumers is upgraded.')

    def handle(self, *args, **options):
        lti_11_aliases = LTI_11_UserAlias.objects.all()

        consumer_key = options['consumer']
        if consumer_key:
            lti_11_aliases = lti_11_aliases.filter(consumer__lti_11__key=consumer_key)

        lti_13_consumer = LTIConsumer.objects.get(pk=options['to_consumer'])
        print(f"Upgrading to consumer {lti_13_consumer}")
        if options['merge_accounts']:
            users_to_merge = User.objects.filter(lti_13_aliases__consumer=lti_13_consumer, lti_11_aliases=None).filter(lti_13_aliases__sub__in=lti_11_aliases.values('consumer_user_id'))
            for u in users_to_merge:
                ou = User.objects.filter(lti_11_aliases__consumer_user_id__in=u.lti_13_aliases.values('sub')).first()
                self.merge_user(new_user=u, old_user=ou)

        num_upgraded = 0
        for ua in lti_11_aliases:
            u = ua.user
            try:
                obj, created = LTI_13_UserAlias.objects.get_or_create(
                    consumer=lti_13_consumer,
                    user=u,
                    defaults={
                        'sub': ua.consumer_user_id,
                        'full_name': u.get_full_name(),
                        'given_name': u.first_name,
                        'family_name': u.last_name,
                        'email': u.email
                    }
                )
                num_upgraded += 1 if created else 0
            except LTI_13_UserAlias.MultipleObjectsReturned:
                pass

        print(f"Migrated {num_upgraded} user aliases.")

    def merge_user(self, new_user, old_user):
        print(f"Merging {new_user.get_full_name()} ({new_user.pk}) with {old_user.get_full_name()} ({old_user.pk})")
        fields = [f for f in User._meta.get_fields() if f.auto_created and not f.concrete and not hasattr(f, 'through')]
        for f in fields:
            objects = f.related_model.objects.filter(**{f.field.name: new_user.pk})
            for o in objects:
                setattr(o, f.field.name, old_user)
            f.related_model.objects.bulk_update(objects, [f.field.name])

        deleted_attempts = Attempt.objects.deleted().filter(user=new_user)
        for a in deleted_attempts:
            a.user = old_user
        Attempt.objects.deleted().bulk_update(deleted_attempts, ['user'])

        new_user.delete()
