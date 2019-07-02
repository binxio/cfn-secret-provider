import sys
import boto3
import hashlib
import uuid
from base64 import b64encode, b64decode
from cfn_secret_provider import SecretProvider
from secrets import handler

kms = boto3.client('kms')


def test_defaults():
    request = Request('Create', 'abc')
    r = SecretProvider()
    r.set_request(request, {})
    assert r.is_valid_request()
    assert r.get('Length') == 30
    assert r.get('Alphabet') == r.request_schema['properties']['Alphabet']['default']
    assert not r.get('ReturnSecret')
    assert r.get('KeyAlias') == 'alias/aws/ssm'
    assert r.get('Description') == ''
    assert isinstance(r.get('NoEcho'), bool) and r.get('NoEcho')


def test_type_convert():
    request = Request('Create', 'abc')
    request['ResourceProperties']['Length'] = '62'
    request['ResourceProperties']['ReturnSecret'] = 'true'
    request['ResourceProperties']['RefreshOnUpdate'] = 'true'
    r = SecretProvider()
    r.set_request(request, {})
    assert r.is_valid_request()
    assert r.get('Length') == 62
    assert r.get('ReturnSecret')

    request['ResourceProperties']['Length'] = 'fouteboole62'
    r = SecretProvider()
    r.set_request(request, {})
    assert not r.is_valid_request()

    request['ResourceProperties']['Length'] = u'62'
    request['ResourceProperties']['ReturnSecret'] = u'true'
    r.set_request(request, {})
    assert r.is_valid_request()
    assert r.get('Length') == 62
    assert r.get('ReturnSecret')


def test_create():
    # create a test parameter
    name = '/test/1-parameter-%s' % uuid.uuid4()
    request = Request('Create', name)
    request['ResourceProperties']['ReturnSecret'] = True
    request['ResourceProperties']['Description'] = 'A beautiful secret'
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']
    assert isinstance(physical_resource_id, str)

    assert 'Data' in response
    assert 'Secret' in response['Data']
    assert 'Arn' in response['Data']
    assert 'Hash' in response['Data']
    assert 'Version' in response['Data']
    assert 'NoEcho' in response
    assert response['Data']['Arn'] == physical_resource_id
    assert response['Data']['Hash'] == hashlib.md5(response['Data']['Secret'].encode('utf8')).hexdigest()
    assert response['Data']['Version'] == 1
    assert response['NoEcho'] == True

    # update the key
    hash = response['Data']['Hash']
    request['RequestType'] = 'Update'
    request['ResourceProperties']['RefreshOnUpdate'] = True
    request['PhysicalResourceId'] = physical_resource_id
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert response['Data']['Arn'] == physical_resource_id
    assert response['Data']['Version'] == 2
    assert response['Data']['Hash'] != hash

    response = handler(request, {})
    # delete the parameters
    request = Request('Delete', name, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_request_duplicate_create():
    # prrequest duplicate create
    name = '/test/2-parameter-%s' % uuid.uuid4()
    request = Request('Create', name)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    physical_resource_id = response['PhysicalResourceId']

    request = Request('Create', name)
    response = handler(request, {})
    assert response['Status'] == 'FAILED', response['Reason']

    request = Request('Delete', name, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_update_name():
    # update parameter name
    name = '/test/3-parameter-%s' % uuid.uuid4()
    request = Request('Create', name)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']

    name_2 = '%s-2' % name
    request = Request('Update', name_2, physical_resource_id)
    request['ResourceProperties']['ReturnSecret'] = True
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    assert 'Data' in response and 'Secret' in response['Data']

    physical_resource_id_2 = response['PhysicalResourceId']
    assert physical_resource_id != physical_resource_id_2

    # delete the parameters
    request = Request('Delete', name, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    request = Request('Delete', name, physical_resource_id_2)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_update_secret():
    name = 'k%s' % uuid.uuid4()
    request = Request('Create', name)
    request['ResourceProperties']['ReturnSecret'] = True
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']
    secret_1 = response['Data']['Secret']
    secure_hash = response['Data']['Hash']
    assert secure_hash == hashlib.md5(secret_1.encode('utf8')).hexdigest()

    name_2 = 'k2%s' % name
    request = Request('Update', name_2, physical_resource_id)
    request['ResourceProperties']['RefreshOnUpdate'] = True
    request['ResourceProperties']['ReturnSecret'] = True
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    secure_hash_2 = response['Data']['Hash']

    physical_resource_id_2 = response['PhysicalResourceId']
    assert physical_resource_id != physical_resource_id_2

    secret_2 = response['Data']['Secret']
    assert secret_1 != secret_2

    assert secure_hash != secure_hash_2

    # delete secrets
    request = Request('Delete', name, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    request = Request('Delete', name, physical_resource_id_2)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_request_duplicate_through_update():
    # update parameter name
    name = '/test/4-parameter-%s' % uuid.uuid4()
    request = Request('Create', name)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    physical_resource_id = response['PhysicalResourceId']

    name_2 = '%s-2' % name
    request = Request('Create', name_2)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id_2 = response['PhysicalResourceId']

    request = Request('Update', name, physical_resource_id_2)
    response = handler(request, {})
    assert response['Status'] == 'FAILED', response['Reason']

    # delete the parameters
    request = Request('Delete', name, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    request = Request('Delete', name, physical_resource_id_2)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_create_no_return_secret():
    # create a test parameter
    name = '/test/5-parameter-%s' % uuid.uuid4()
    request = Request('Create', name)
    request['ResourceProperties']['ReturnSecret'] = False
    request['ResourceProperties']['NoEcho'] = False
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']

    assert 'Data' in response
    assert 'Secret' not in response['Data']
    assert 'Arn' in response['Data']
    assert 'NoEcho' in response and response['NoEcho'] == False
    assert response['Data']['Arn'] == physical_resource_id

    # delete the parameters
    request = Request('Delete', name, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_no_echo():
    # create a test parameter
    name = '/test/parameter-%s' % uuid.uuid4()
    request = Request('Create', name)
    request['ResourceProperties']['ReturnSecret'] = True
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'NoEcho' in response
    assert response['NoEcho'] == True
    physical_resource_id = response['PhysicalResourceId']

    # update NoEcho
    request['PhysicalResourceId'] = physical_resource_id
    request['ResourceProperties']['NoEcho'] = False
    request['RequestType'] = 'Update'
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'NoEcho' in response
    assert response['NoEcho'] == False

    # delete NoEcho parameter
    request['RequestType'] = 'Delete'
    request = Request('Delete', name, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_create_with_content():
    # create a test parameter with content value set
    name = '/test/6-parameter-%s' % uuid.uuid4()
    secretContent = 'Don\'t read my secret'
    request = Request('Create', name)
    request['ResourceProperties']['ReturnSecret'] = True
    request['ResourceProperties']['Description'] = 'A custom secret'
    request['ResourceProperties']['Content'] = secretContent
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']
    assert isinstance(physical_resource_id, str)

    assert 'Data' in response
    assert 'Secret' in response['Data']
    assert 'Arn' in response['Data']
    assert 'Hash' in response['Data']
    assert 'Version' in response['Data']
    assert response['Data']['Arn'] == physical_resource_id
    assert response['Data']['Hash'] == hashlib.md5(response['Data']['Secret'].encode('utf8')).hexdigest()
    assert response['Data']['Secret'] == secretContent
    assert response['Data']['Version'] == 1

    # delete the parameters
    request = Request('Delete', name, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def get_kms_key():
    for response in kms.get_paginator('list_aliases').paginate():
        key_id = next(map(lambda a: a['TargetKeyId'], filter(lambda a: a['AliasName']
                                                             == 'alias/cmk/parameters', response['Aliases'])), None)
        if key_id:
            return key_id

    response = kms.create_key(Description='key for cfn-secret-provider')
    key_id = response['KeyMetadata']['KeyId']
    response = kms.create_alias(AliasName='alias/cmk/parameters', TargetKeyId=key_id)
    return key_id


def encrypt_to_base64(secret):
    key_id = get_kms_key()
    response = kms.encrypt(KeyId='alias/cmk/parameters', Plaintext=secret.encode('utf8'))
    return b64encode(response['CiphertextBlob']).decode('ascii')


def test_create_with_encypted_content():
    # create a test parameter with content value set
    name = '/test/7-parameter-%s' % uuid.uuid4()
    secret_content = 'Don\'t read my encrypted secret'
    request = Request('Create', name)

    encrypted_secret_content = encrypt_to_base64(secret_content)

    request['ResourceProperties']['ReturnSecret'] = True
    request['ResourceProperties']['Description'] = 'A encrypted custom secret'
    request['ResourceProperties']['EncryptedContent'] = encrypted_secret_content
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']
    assert isinstance(physical_resource_id, str)

    assert 'Data' in response
    assert 'Secret' in response['Data']
    assert 'Arn' in response['Data']
    assert 'Hash' in response['Data']
    assert 'Version' in response['Data']
    assert response['Data']['Arn'] == physical_resource_id
    assert response['Data']['Hash'] == hashlib.md5(response['Data']['Secret'].encode('utf8')).hexdigest()
    assert response['Data']['Secret'] == secret_content
    assert response['Data']['Version'] == 1

    secret_content = secret_content + " v2"
    request['RequestType'] = 'Update'
    request['PhysicalResourceId'] = physical_resource_id
    request['ResourceProperties']['EncryptedContent'] = encrypt_to_base64(secret_content)
    request['ResourceProperties']['RefreshOnUpdate'] = True
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    assert physical_resource_id == response['PhysicalResourceId']
    assert response['Data']['Secret'] == secret_content
    assert response['Data']['Version'] == 2

    # delete the parameters
    request = Request('Delete', name, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_create_with_bad_encrypted_values():
    # create a test parameter with content value set
    name = '/test/parameter-%s' % uuid.uuid4()
    request = Request('Create', name)
    request['ResourceProperties']['ReturnSecret'] = True
    request['ResourceProperties']['Description'] = 'A encrypted custom secret'
    request['ResourceProperties']['EncryptedContent'] = "Unencrypted secret here"
    response = handler(request, {})
    assert response['Status'] == 'FAILED', response['Reason']
    assert response['Reason'].startswith('EncryptedContent is not base64 encoded')

    request['ResourceProperties']['ReturnSecret'] = True
    request['ResourceProperties']['Description'] = 'A encrypted custom secret'
    request['ResourceProperties']['EncryptedContent'] = b64encode(b"not a KMS encrypted value here").decode('ascii')
    response = handler(request, {})
    assert response['Status'] == 'FAILED', response['Reason']
    assert response['Reason'].startswith('An error occurred (InvalidCiphertextException)')

    request['ResourceProperties']['ReturnSecret'] = True
    request['ResourceProperties']['Content'] = 'A encrypted custom secret'
    request['ResourceProperties']['EncryptedContent'] = b64encode(b"not a KMS encrypted value here").decode('ascii')
    response = handler(request, {})
    assert response['Status'] == 'FAILED', response['Reason']
    assert response['Reason'].startswith('Specify either "Content" or "EncryptedContent"')

def test_unchanged_physical_resource_id():
    name = 'k%s' % uuid.uuid4()
    request = Request('Create', name)
    request['ResourceProperties']['ReturnSecret'] = True
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']

    old_style_physical_resource_id = physical_resource_id.split('/', 2)[0] + '//' + name
    request = Request('Update', name, old_style_physical_resource_id)
    request['ResourceProperties']['RefreshOnUpdate'] = True
    request['ResourceProperties']['ReturnSecret'] = True
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    assert old_style_physical_resource_id == response['PhysicalResourceId']

    # delete secrets
    request = Request('Delete', name, old_style_physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


class Request(dict):

    def __init__(self, request_type, name, physical_resource_id=None):
        self.update({
            'RequestType': request_type,
            'ResponseURL': 'https://httpbin.org/put',
            'StackId': 'arn:aws:cloudformation:us-west-2:EXAMPLE/stack-name/guid',
            'RequestId': 'request-%s' % uuid.uuid4(),
            'ResourceType': 'Custom::Secret',
            'LogicalResourceId': 'MySecret',
            'ResourceProperties': {
                'Name': name
            }})
        self['PhysicalResourceId'] = physical_resource_id if physical_resource_id is not None else str(uuid.uuid4())
