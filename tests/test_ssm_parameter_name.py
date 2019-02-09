import ssm_parameter_name


def test_arn_to_name():
    region = 'eu-central-1'
    account = '111111111114'
    test_set = {
        'issue-25': 'issue-25',
        'demo/issue-25': '/demo/issue-25',
        '/demo/issue-25': '/demo/issue-25'
    }
    for name, expect in test_set.items():
        arn = ssm_parameter_name.to_arn(region, account, name)
        assert expect == ssm_parameter_name.from_arn(arn)


def test_name_from_arn():
    test_set = {
        'arn:aws:ssm:eu-central-1:111111111114:parameter/issue-25': 'issue-25',
        'arn:aws:ssm:eu-central-1:111111111114:parameter/demo/issue-25': '/demo/issue-25',
        'arn:aws:ssm:eu-central-1:111111111114:parameter//demo/issue-25': '/demo/issue-25',
        'arn:aws:ssm:eu-central-1:111111111114:document/SSM:RunShell': None
    }
    for arn, expect in test_set.items():
        name = ssm_parameter_name.from_arn(arn)
        assert expect == name
