import sys
import uuid
from cfn_secret_provider import handler


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
        if physical_resource_id is not None:
            self['PhysicalResourceId'] = physical_resource_id


def test_create():
    # create a test parameter
    name = '/test/parameter-%s' % uuid.uuid4()
    request = Request('Create', name)
    request['ResourceProperties']['ReturnSecret'] = True
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']

    assert 'Data' in response
    assert 'Secret' in response['Data']
    assert 'Arn' in response['Data']
    assert response['Data']['Arn'] == physical_resource_id

    # delete the parameters
    request = Request('Delete', name, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_request_duplicate_create():
    # prrequest duplicate create
    name = '/test/parameter-%s' % uuid.uuid4()
    request = Request('Create', name)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    request = Request('Create', name)
    response = handler(request, {})
    assert response['Status'] == 'FAILED', response['Reason']


def test_update_name():
    # update parameter name
    name = '/test/parameter-%s' % uuid.uuid4()
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


def test_request_duplicate_through_update():
    # update parameter name
    name = '/test/parameter-%s' % uuid.uuid4()
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
    name = '/test/parameter-%s' % uuid.uuid4()
    request = Request('Create', name)
    request['ResourceProperties']['ReturnSecret'] = False
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']

    assert 'Data' in response
    assert 'Secret' not in response['Data']
    assert 'Arn' in response['Data']
    assert response['Data']['Arn'] == physical_resource_id

    # delete the parameters
    request = Request('Delete', name, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
