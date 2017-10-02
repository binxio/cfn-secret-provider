from __future__ import generators
import random
import logging
import boto3
import importlib
import requests
import json
import os

log = logging.getLogger()


class ResourceProvider(object):
    """
    Custom CloudFormation Resource Provider.
    """

    def __init__(self):
        """
        constructor
        """
        self.request = None
        self.response = None
        self.context = None
        self.region = boto3.session.Session().region_name
        self.account_id = (boto3.client(
            'sts')).get_caller_identity()['Account']

    @property
    def custom_cfn_resource_name(self):
        return 'Custom::%s' % self.__class__.__name__.replace('Provider', '')

    def set_request(self, request, context):
        """
        sets the lambda request to process.
        """
        self.request = request
        self.context = context
        self.response = {
            'Status': 'SUCCESS',
            'Reason': '',
            'StackId': request['StackId'],
            'RequestId': request['RequestId'],
            'LogicalResourceId': request['LogicalResourceId'],
            'Data': {}
        }
        if 'PhysicalResourceId' in request:
            self.response['PhysicalResourceId'] = request['PhysicalResourceId']

    def get(self, name, default=None):
        """
        returns the custom resource property `name` if it exists, otherwise `default`
        """
        return self.properties[name] if name in self.properties else default

    @property
    def properties(self):
        return self.request['ResourceProperties'] if self.request is not None and 'ResourceProperties' in self.request else {}

    @property
    def physical_resource_id(self):
        """
        returns the PhysicalResourceId from the request.
        """
        return self.request['PhysicalResourceId']

    def set_physical_resource_id(self, physical_resource_id):
        """
        set the PhysicalResourceId in the response to `physical_resource_id`.
        """
        self.response['PhysicalResourceId'] = physical_resource_id

    def is_valid_request(self):
        """
        returns True if `self.request` is a valid request, otherwise False.
        If False, `Reason` and `Status` should be set in `self.response`
        """
        return True

    def set_attribute(self, name, value):
        """
        sets the attribute `name` to `value`. This value can be retrieved using "Fn::GetAtt".
        """
        self.response['Data'][name] = value

    def get_attribute(self, name):
        """
        returns the value of the attribute `name`.
        """
        return self.response['Data'][name] if name in self.response['Data'] else None

    def success(self, reason=None):
        """
        sets response status to SUCCESS
        """
        self.response['Status'] = 'SUCCESS'
        if reason is not None:
            self.response['Reason'] = reason

    def fail(self, reason):
        """
        sets response status to FAILED
        """
        self.response['Status'] = 'FAILED'
        self.response['Reason'] = reason

    def create(self):
        """
        implements the provider resource create. 
        """
        self.fail('create not implemented by %s' % self)

    def update(self):
        """
        implements the provider resource update.
        """
        self.fail('update not implemented by %s' % self)

    def delete(self):
        """
        implements the provider resource delete. 
        """
        self.fail('delete not implemented by %s' % self)

    def execute(self):
        """
        execute the request.
        """
        if self.request['ResourceType'] == self.custom_cfn_resource_name:
            request = self.request['RequestType']
            if self.is_valid_request():
                if request == 'Create':
                    self.create()
                elif request == 'Update':
                    self.update()
                elif request == 'Delete':
                    self.delete()
                else:
                    self.fail('unknown RequestType %s received.' % request)
            elif request == 'Delete':
                # failure to delete an invalid request hangs your cfn...
                self.success()
        else:
            self.fail('ResourceType %s not supported by provider %s' %
                      (self.request['ResourceType'], self.custom_cfn_resource_name))
        return self.response

    def handle(self, request, context):
        """
        handles the CloudFormation request.
        """
        log.debug('received request %s', json.dumps(request))
        self.set_request(request, context)
        self.execute()
        self.send_response()
        return self.response

    def send_response(self):
        """
        sends the response to `ResponseURL`
        """
        url = self.request['ResponseURL']
        log.debug('sending response to %s request %s',
                  url, json.dumps(self.response))
        r = requests.put(url, json=self.response)
        if r.status_code != 200:
            raise Exception('failed to put the response to %s status code %d, %s' %
                            (url, r.status_code, r.text))
