import os
import logging

import cfn_secret_provider
import cfn_rsakey_provider
import cfn_keypair_provider
import cfn_accesskey_provider
import cfn_dsakey_provider
import cfn_read_only_secret_provider
import cfn_secrets_manager_secret_provider
import cfn_random_bytes_provider

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


def handler(request, context):
    if request["ResourceType"] == "Custom::RSAKey":
        return cfn_rsakey_provider.handler(request, context)
    if request["ResourceType"] == "Custom::DSAKey":
        return cfn_dsakey_provider.handler(request, context)
    elif request["ResourceType"] == "Custom::KeyPair":
        return cfn_keypair_provider.handler(request, context)
    elif request["ResourceType"] == "Custom::AccessKey":
        return cfn_accesskey_provider.handler(request, context)
    elif request["ResourceType"] == "Custom::SecretsManagerSecret":
        return cfn_secrets_manager_secret_provider.handler(request, context)
    elif request["ResourceType"] == "Custom::ReadOnlySecret":
        return cfn_read_only_secret_provider.handler(request, context)
    elif request["ResourceType"] == "Custom::RandomBytes":
        return cfn_random_bytes_provider.handler(request, context)
    else:
        return cfn_secret_provider.handler(request, context)
