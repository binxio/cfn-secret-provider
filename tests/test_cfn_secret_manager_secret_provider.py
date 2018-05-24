import json
import uuid
from base64 import b64encode

from cfn_secrets_manager_secret_provider import SecretsManagerSecretProvider as SecretProvider
from secrets import handler


def test_defaults():
    request = Request('Create', 'abc', 'v1')
    del request['ResourceProperties']['RecoveryWindowInDays']

    r = SecretProvider()
    r.set_request(request, {})
    assert r.is_valid_request()
    assert r.get('KmsKeyId') == 'alias/aws/secretsmanager'
    assert r.get('Description') == ''
    assert r.get('RecoveryWindowInDays') == 30
    assert isinstance(r.get('NoEcho'), bool) and r.get('NoEcho')


def test_type_convert():
    request = Request('Create', 'abc', 'v1')
    request['ResourceProperties']['RecoveryWindowInDays'] = '15'
    request['ResourceProperties']['NoEcho'] = 'false'
    r = SecretProvider()
    r.set_request(request, {})
    assert r.is_valid_request()
    assert r.get('RecoveryWindowInDays') == 15
    assert isinstance(r.get('NoEcho'), bool) and not r.get('NoEcho')

    request = Request('Create', 'abc', 'v1')
    request['ResourceProperties']['RecoveryWindowInDays'] = 'fouteboole15'
    r = SecretProvider()
    r.set_request(request, {})
    assert not r.is_valid_request()

    request = Request('Create', 'abc', 'v1')
    request['ResourceProperties']['NoEcho'] = 'False'
    r = SecretProvider()
    r.set_request(request, {})
    assert not r.is_valid_request()


def create_secret(binary=False):
    # create a secret
    name = '/test/secret-{}'.format(uuid.uuid4())
    request = Request('Create', name, secret={"msg": "het is hier geweldig!"}, binary_secret=binary)
    request['ResourceProperties']['ClientRequestToken'] = request['RequestId']
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']

    assert 'VersionId' in response['Data']
    assert response['Data']['VersionId'] == request['RequestId']
    assert response['NoEcho'] == True
    version_id = response['Data']['VersionId']

    # update the secret
    request = Request('Update', name, secret={"msg": "het was hier geweldig!"}, binary_secret=binary,
                      physical_resource_id=physical_resource_id)
    request['OldResourceProperties'] = {}
    request['OldResourceProperties']['Tags'] = request['ResourceProperties']['Tags']
    request['ResourceProperties']['Tags'] = [{'Key': 'Group', 'Value': 'Admin'}]
    update_response = handler(request, {})
    assert update_response['Status'] == 'SUCCESS', response['Reason']
    assert update_response['PhysicalResourceId'] == physical_resource_id
    assert update_response['Data']['VersionId'] == request['RequestId']

    response = handler(request, {})
    # delete the secret
    # request = Request('Delete', name, physical_resource_id=physical_resource_id)
    # response = handler(request, {})
    # assert response['Status'] == 'SUCCESS', response['Reason']


def test_create_secret():
    create_secret(binary=False)


def test_create_binary_secret():
    create_secret(binary=True)


class Request(dict):

    def __init__(self, request_type, name, secret=None, binary_secret=None, physical_resource_id=None):
        self.update({
            'RequestType': request_type,
            'ResponseURL': 'https://httpbin.org/put',
            'StackId': 'arn:aws:cloudformation:us-west-2:EXAMPLE/stack-name/guid',
            'RequestId': 'request-%s' % uuid.uuid4(),
            'ResourceType': 'Custom::SecretsManagerSecret',
            'LogicalResourceId': 'MySecret',
            'ResourceProperties': {
                'Name': name,
                'RecoveryWindowInDays': 7,
                'Tags': [{'Key': 'IsBinary', 'Value': str(binary_secret)}]
            }})
        self['PhysicalResourceId'] = physical_resource_id if physical_resource_id is not None else str(uuid.uuid4())
        if not binary_secret and secret:
            self['ResourceProperties']['SecretString'] = secret
        if binary_secret and secret:
            self['ResourceProperties']['SecretBinary'] = b64encode(json.dumps(secret).encode()).decode('ascii')

    def get_property(self, name):
        return self['ResourceProperties'][name] if name in self['ResourceProperties'] else None

    def set_property(self, name, value):
        self['ResourceProperties'][name] = value
