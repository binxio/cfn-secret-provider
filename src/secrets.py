import cfn_secret_provider
import cfn_rsakey_provider


def handler(request, context):
    if request['ResourceType'] == 'Custom::RSAKey':
        return cfn_rsakey_provider.handler(request, context)
    else:
        return cfn_secret_provider.handler(request, context)
