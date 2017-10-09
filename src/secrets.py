import os
import logging
import cfn_secret_provider
import cfn_rsakey_provider
import cfn_keypair_provider

logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))

def handler(request, context):
    if request['ResourceType'] == 'Custom::RSAKey':
        return cfn_rsakey_provider.handler(request, context)
    elif request['ResourceType'] == 'Custom::KeyPair':
        return cfn_keypair_provider.handler(request, context)
    else:
        return cfn_secret_provider.handler(request, context)
