def group_for_user(user):
    return 'user-{}'.format(user.id)

def group_for_attempt(attempt):
    return 'attempt-{}'.format(attempt.id)

def group_for_resource(resource):
    return 'resource-{}'.format(resource.id)

def group_for_resource_stats(resource):
    return 'resource-{}-stats'.format(resource.id)
