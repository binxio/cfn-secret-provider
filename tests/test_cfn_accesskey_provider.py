import re
import json
import uuid
import pytest
import boto3
from botocore.exceptions import ClientError
from cfn_accesskey_provider import handler

iam = boto3.client('iam')
ssm = boto3.client('ssm')

created_users = []
def create_user(name):
    iam.create_user(UserName=name)
    created_users.append(name)

def delete_users():
    for name in created_users:
        keys = iam.list_access_keys(UserName=name)
        for key in keys['AccessKeyMetadata']:
            iam.delete_access_key(UserName=name, AccessKeyId=key['AccessKeyId'])
        iam.delete_user(UserName=name)

        parameters = ssm.get_parameters_by_path(Path='/' + name)
        for parameter in parameters['Parameters']:
            try:
                ssm.delete_parameter(Name=parameter['Name'])
            except ssm.exceptions.ParameterNotFound:
                pass

        try:
            ssm.delete_parameter(Name='/' + name)
        except ssm.exceptions.ParameterNotFound:
            pass

@pytest.yield_fixture(scope="session", autouse=True)
def setup():
    yield
    delete_users()

def extract_name(physical_resource_id):
    m = re.match(r'arn:aws:ssm:(?P<region>[^:]*):(?P<account>[^:]*):parameter/(?P<name>.*)', physical_resource_id)
    return m.group('name') if m else None


def valid_deleted_state(request, response):
    data = response['Data']
    properties = request['ResourceProperties']
    name = properties['ParameterPath']

    for n in [ '/aws_access_key_id', '/aws_secret_access_key', '/smtp_password']:
        try:
            parameter = ssm.get_parameter(Name=name + n)
            assert False, 'parameter {}{} still exists'.format(name, n)
        except ssm.exceptions.ParameterNotFound as e:
            pass

    keys = iam.list_access_keys(UserName=properties['UserName'])['AccessKeyMetadata']
    assert len(keys) == 0, keys


def valid_state(request, response):
    data = response['Data']
    properties = request['ResourceProperties']
    name = properties['ParameterPath']

    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']
    assert name == extract_name(physical_resource_id)

    parameter = ssm.get_parameter(Name=name + '/aws_access_key_id', WithDecryption=True)['Parameter']
    access_key_id = parameter['Value']
    if 'AccessKeyId' in data:
        assert data['AccessKeyId'] == access_key_id

    if 'ReturnSecret' not in properties or not properties['ReturnSecret']:
        assert 'SecretAccessKey' not in data
    else:
        assert 'SecretAccessKey' in data
        assert 'AccessKeyId' in data

    parameter = ssm.get_parameter(Name=name + '/aws_secret_access_key', WithDecryption=True)['Parameter']
    if 'SecretAccessKey' in data:
        assert data['SecretAccessKey'] == parameter['Value']

    parameter = ssm.get_parameter(Name=name + '/smtp_password', WithDecryption=True)['Parameter']
    if 'SMTPPassword' in data:
        assert data['SMTPPassword'] == parameter['Value']

    if 'ReturnPassword' not in properties or not properties['ReturnPassword']:
        assert 'SMTPPassword' not in data
    else:
        assert 'SMTPPassword' in data
        assert 'AccessKeyId' in data

    try:
        keys = iam.list_access_keys(UserName=properties['UserName'])['AccessKeyMetadata']
        found = next(iter(filter(lambda x: x['AccessKeyId'] == access_key_id, keys)), None)
        assert found
    except ClientError as e:
        assert False, e.response


def test_create():
    name = 'test-{}'.format(uuid.uuid4())
    parameter_path = '/{0}/{0}'.format(name)
    create_user(name)
    request = Request('Create', name, parameter_path)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    valid_state(request, response)

    #update to obtain secret
    request = Request('Update', name, parameter_path, response['PhysicalResourceId'])
    request['ResourceProperties']['ReturnSecret'] = True
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    valid_state(request, response)
    secret_access_key = response['Data']['SecretAccessKey']

    #update to obtain password
    request = Request('Update', name, parameter_path, response['PhysicalResourceId'])
    request['ResourceProperties']['ReturnPassword'] = True
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    valid_state(request, response)
    smtp_password = response['Data']['SMTPPassword']

    # refresh the keys
    request = Request('Update', name, parameter_path, response['PhysicalResourceId'])
    request['ResourceProperties']['ReturnSecret'] = True
    request['ResourceProperties']['ReturnPassword'] = True
    request['ResourceProperties']['Serial'] = 2
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    valid_state(request, response)
    assert response['Data']['SecretAccessKey'] != secret_access_key
    secret_access_key = response['Data']['SecretAccessKey']
    physical_resource_id = response['PhysicalResourceId']

    # change the user
    name2 = 'test-{}'.format(uuid.uuid4())
    create_user(name2)

    request['OldResourceProperties'] = json.loads(json.dumps(request['ResourceProperties']))
    request['ResourceProperties']['UserName'] = name2
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    valid_state(request, response)
    assert response['PhysicalResourceId'] == physical_resource_id
    assert response['Data']['SecretAccessKey'] != secret_access_key
    secret_access_key = response['Data']['SecretAccessKey']

    # change the user and parameter
    parameter_path_2 = '/{0}/new-{0}'.format(name)

    request['OldResourceProperties'] = json.loads(json.dumps(request['ResourceProperties']))
    request['ResourceProperties']['UserName'] = name
    request['ResourceProperties']['ParameterPath'] = parameter_path_2
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    physical_resource_id_2 = response['PhysicalResourceId']
    assert parameter_path_2 == extract_name(physical_resource_id_2)
    assert 'SMTPPassword' in response['Data']
    assert 'SecretAccessKey' in response['Data']
    assert response['Data']['SecretAccessKey'] != secret_access_key
    secret_access_key = response['Data']['SecretAccessKey']

    # inactivate the key
    request['OldResourceProperties'] = json.loads(json.dumps(request['ResourceProperties']))
    request['ResourceProperties']['Status'] = 'Inactive'
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    valid_state(request, response)
    physical_resource_id_2 = response['PhysicalResourceId']
    assert parameter_path_2 == extract_name(physical_resource_id_2)
    assert response['Data']['SecretAccessKey'] == secret_access_key


    # delete access key
    request = Request('Delete', name2, parameter_path, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    valid_deleted_state(request, response)

    # delete access key 2
    request = Request('Delete', name, parameter_path_2, physical_resource_id_2)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    valid_deleted_state(request, response)



class Request(dict):

    def __init__(self, request_type, user_name, parameter_path,  physical_resource_id=None):
        self.update({
            'RequestType': request_type,
            'ResponseURL': 'https://httpbin.org/put',
            'StackId': 'arn:aws:cloudformation:us-west-2:EXAMPLE/stack-name/guid',
            'RequestId': 'request-%s' % uuid.uuid4(),
            'ResourceType': 'Custom::AccessKey',
            'LogicalResourceId': 'MyAccessKey',
            'ResourceProperties': {
                'UserName': user_name,
                'ParameterPath': parameter_path
            }})
        self['PhysicalResourceId'] = physical_resource_id if physical_resource_id is not None else str(uuid.uuid4())
