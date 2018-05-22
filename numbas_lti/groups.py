from channels import Group

def group_for_user(user):
    return Group('user-{}'.format(user.id))

def group_for_attempt(attempt):
    return Group('attempt-{}'.format(attempt.id))
