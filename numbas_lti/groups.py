from channels import Group

def group_for_user(user):
    return Group('user-{}'.format(user.id))

def group_for_attempt(attempt):
    return Group('attempt-{}'.format(attempt.id))

def group_for_resource_stats(resource):
    return Group('resource-{}-stats'.format(resource.pk))
